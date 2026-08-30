"""Testet api.py gegen den echten Router - ohne Home Assistant."""
import asyncio, os, sys, pathlib, importlib.util, types
import aiohttp

# Ein synthetisches Paket bauen: der echte Paket-__init__ wuerde Home Assistant
# importieren, das hier nicht installiert ist. api.py und const.py haengen nur
# an aiohttp/yarl und lassen sich so isoliert testen.
_dir = pathlib.Path(os.environ.get("RUTOS_INT", str(pathlib.Path(__file__).resolve().parent.parent))) / "custom_components/teltonika_rutos"
_pkg = types.ModuleType("trut")
_pkg.__path__ = [str(_dir)]
sys.modules["trut"] = _pkg

def _load(name):
    spec = importlib.util.spec_from_file_location(f"trut.{name}", _dir / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"trut.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod

_load("const")
_api = _load("api")
RutosClient = _api.RutosClient
RutosAuthError = _api.RutosAuthError
RutosNotSupportedError = _api.RutosNotSupportedError
RutosPermissionError = _api.RutosPermissionError
to_bool, to_float, to_int = _api.to_bool, _api.to_float, _api.to_int

def check(label, got, want):
    ok = got == want
    print(f"  {'OK ' if ok else 'FEHLER'} {label:34} got={got!r} want={want!r}")
    return ok

async def main():
    print("=== Typkonvertierung ===")
    fails = 0
    for lbl, got, want in [
        ("to_int('0')",       to_int("0"), 0),
        ("to_int('10')",      to_int("10"), 10),
        ("to_int('10.0')",    to_int("10.0"), 10),
        ("to_int(-74)",       to_int(-74), -74),
        ("to_int('')",        to_int(""), None),
        ("to_int('N/A')",     to_int("N/A"), None),
        ("to_float('49.15')", to_float("49.155721"), 49.155721),
        ("to_bool('0')",      to_bool("0"), False),
        ("to_bool('1')",      to_bool("1"), True),
        ("to_bool(True)",     to_bool(True), True),
        ("to_bool('x')",      to_bool("x"), None),
    ]:
        fails += not check(lbl, got, want)

    print("\n=== URL-Aufbau ===")
    for host, want in [
        ("192.168.1.1", "https://192.168.1.1"),
        ("https://192.168.1.1", "https://192.168.1.1"),
        ("https://192.168.1.1/api", "https://192.168.1.1"),
        ("192.168.1.1/", "https://192.168.1.1"),
    ]:
        c = RutosClient(None, host, "u", "p")
        fails += not check(f"host={host}", c.base_url, want)

    print("\n=== Gegen den echten Router ===")
    async with aiohttp.ClientSession() as session:
        c = RutosClient(session, os.environ["RUTOS_HOST"], os.environ["RUTOS_USER"], os.environ["RUTOS_PASS"])

        info = await c.async_probe()
        print(f"  OK  probe (ohne Auth)               model={info.get('device_model')} api={info.get('api_version')}")

        gps = await c.async_get_gps()
        print(f"  OK  gps                             {len(gps)} Felder, fix={gps.get('fix_status')} sats={gps.get('satellites')}")
        assert to_float(gps["latitude"]) is not None, "latitude nicht konvertierbar"
        assert to_int(gps["satellites"]) is not None, "satellites nicht konvertierbar"

        modems = await c.async_get_modems()
        m = modems[0]
        print(f"  OK  modems                          {len(modems)} Modem(s), signal={m.get('signal')} temp={m.get('temperature')}")

        ifaces = await c.async_get_interfaces()
        named = [i for i in ifaces if i.get('id')]
        print(f"  OK  interfaces                      {len(ifaces)} gesamt, {len(named)} mit id")

        wg = await c.async_get_wireguard()
        print(f"  OK  wireguard                       {len(wg)} Instanz(en): {[w.get('id') for w in wg]}")

        # Token-Wiederverwendung: zweiter Aufruf darf nicht neu einloggen
        tok1 = c._token
        await c.async_get_gps()
        print(f"  {'OK ' if c._token == tok1 else 'FEHLER'} Token wiederverwendet             {c._token == tok1}")
        fails += (c._token != tok1)

        # 403 muss als RutosPermissionError ankommen
        try:
            await c._get("backup/config")
            print("  FEHLER 403 wurde nicht als Fehler erkannt")
            fails += 1
        except RutosPermissionError:
            print("  OK  403 -> RutosPermissionError")
        # 501 muss als RutosNotSupportedError ankommen
        try:
            await c._get("wireguard/status")
            print("  FEHLER 501 wurde nicht als Fehler erkannt")
            fails += 1
        except RutosNotSupportedError:
            print("  OK  501 -> RutosNotSupportedError")

        # Falsches Passwort muss RutosAuthError geben
        bad = RutosClient(session, os.environ["RUTOS_HOST"], os.environ["RUTOS_USER"], "definitiv-falsch")
        try:
            await bad.async_verify_credentials()
            print("  FEHLER falsches Passwort akzeptiert")
            fails += 1
        except RutosAuthError:
            print("  OK  falsches Passwort -> RutosAuthError")

    print(f"\n{'ALLE TESTS BESTANDEN' if not fails else str(fails) + ' FEHLER'}")
    return 1 if fails else 0

sys.exit(asyncio.run(main()))
