# Teltonika RutOS für Home Assistant

<img src="custom_components/teltonika_rutos/brand/icon.png" alt="" width="96" align="right">

Home-Assistant-Integration für Teltonika-Router über die **native RutOS-REST-API**.

Entwickelt und getestet am **RUTC50** mit RutOS `7.24.1` (API 1.16.1). Andere RutOS-Geräte
sollten funktionieren — mit einer Einschränkung, siehe [Andere Modelle](#andere-modelle).

[![Repository zu HACS hinzufügen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=omc69&repository=ha-teltonika-rutos-api&category=integration)

[![Integration einrichten](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=teltonika_rutos)

![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)
![Version](https://img.shields.io/github/v/release/omc69/ha-teltonika-rutos-api)
![Lizenz](https://img.shields.io/github/license/omc69/ha-teltonika-rutos-api)

---

## Warum diese Integration

**Keine externen Abhängigkeiten.** Der API-Client liegt im Paket (`api.py`), `requirements` ist
leer. Nichts wird zur Laufzeit von GitHub oder PyPI nachgeladen — die Integration lädt auch dann
noch, wenn ein fremdes Repository verschwindet.

**Ein Abruf statt vieler Register.** `gps/position/status` liefert Position, Höhe, Geschwindigkeit,
Genauigkeit, Satellitenzahl, Kurs und Fix-Status in einem einzigen Aufruf — alle Werte aus
demselben Moment. Über Modbus braucht es dafür ein Dutzend Einzelregister.

**Werte, die Modbus nicht hat.** RSRP, RSRQ, SINR, Signalqualität, Funkzelle, Frequenzband und
Modem-Temperatur.

---

## Entitäten

### Sensoren

| Gruppe | Entitäten |
|---|---|
| GPS | Breitengrad `DIAG`, Längengrad `DIAG`, Höhe, Geschwindigkeit, Genauigkeit `DIAG`, Satelliten, Kurs `DIAG` |
| Signal | Mobilfunk-Signal, Signalqualität, RSRP `DIAG`, RSRQ `DIAG`, SINR `DIAG` |
| Netz | Netzbetreiber, Verbindungstyp, Verbindungsstatus, Netzregistrierung `DIAG`, Frequenzband `DIAG`, Funkzelle `DIAG` |
| SIM | Aktive SIM, SIM-Status `DIAG` |
| Modem | Temperatur, empfangen `DIAG`, gesendet `DIAG` |
| Interfaces | je Interface ein Zähler für empfangen und gesendet `DIAG` |
| Kennungen | IMEI, IMSI, ICCID — `DIAG`, **standardmäßig deaktiviert** |

`DIAG` = als Diagnose eingestuft, in der Geräteansicht eingeklappt.

Die Kennungen sind bewusst abgeschaltet: IMEI, IMSI und ICCID identifizieren Karte und Gerät
eindeutig. Wer sie braucht, schaltet sie einzeln frei.

### Binäre Sensoren

GPS-Fix · Mobilfunkverbindung · SIM eingelegt

### Schalter

Ein Schalter je konfigurierter WireGuard-Instanz. Der Zustand kommt bei jedem Abruf direkt vom
Router, folgt also auch Änderungen aus der Router-Oberfläche.

Das Attribut `full_tunnel` weist aus, ob die Peers `0.0.0.0/0` oder `::/0` routen — dann läuft
eingeschaltet **der gesamte** Verkehr des Routers durch den Tunnel, nicht nur der ins entfernte
Netz. Die Integration verhindert das nicht; sie macht es sichtbar, damit eine Oberfläche davor
warnen kann.

---

## Installation

### Über HACS

Am schnellsten über den Knopf oben — er öffnet das Repository direkt in deiner HACS-Instanz.
Danach herunterladen und Home Assistant neu starten.

Von Hand:

1. HACS → **Benutzerdefinierte Repositories** → `https://github.com/omc69/ha-teltonika-rutos-api`,
   Kategorie **Integration**
2. **Teltonika RutOS** herunterladen, Home Assistant neu starten
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Teltonika RutOS**

> **Eine Aktualisierung wird nicht angeboten?** HACS fragt eigene Repositories nur etwa alle
> 48 Stunden bei GitHub nach. Repository in HACS öffnen → **⋮ → Update information** erzwingt
> den Abgleich.

### Manuell

`custom_components/teltonika_rutos/` nach `/config/custom_components/` kopieren, neu starten.

### Voraussetzung am Router

Die REST-API muss aktiviert sein: **Dienste → API**. Ohne sie antwortet der Router nicht.

---

## Einrichtung

| Feld | Hinweis |
|---|---|
| IP-Adresse | `192.168.1.1`, `https://192.168.1.1` oder `https://192.168.1.1/api` — alle drei Formen werden akzeptiert |
| Benutzername | ein Web-UI-Benutzer, nicht zwingend `root` |
| Passwort | |
| TLS-Zertifikat prüfen | **aus lassen.** RutOS liefert ein selbstsigniertes Zertifikat |

Vor dem Login prüft die Integration über `unauthorized/status`, ob unter der Adresse überhaupt ein
RutOS-Gerät antwortet. Eine falsche Adresse wird dadurch als solche gemeldet und nicht als
„falsches Passwort" — der irreführendere der beiden Fälle.

Das Abfrageintervall lässt sich in den Optionen zwischen 10 und 600 Sekunden einstellen
(Vorgabe: 30).

---

## Andere Modelle

**Übernimm keine Endpunktlisten aus anderen Projekten.** Die RutOS-API unterscheidet sich zwischen
Modellen deutlich. Am RUTC50 antworten mehrere Endpunkte, die auf dem RUTX50 funktionieren, mit
`403`, `404` oder `501`:

| Endpunkt | RUTC50 | Folge |
|---|---|---|
| `backup/config` | `403` | keine Backup-Funktion |
| `system/fw/status` | `403` | keine Firmware-Entität |
| `system/logs/status` | `403` | |
| `simcard/status` | `404` | SIM-Daten kommen aus `modems/status` |
| `wireguard/status` | `501` | Zustand kommt aus `wireguard/config` |

Bemerkenswert: Die `403` treten auf, obwohl sich das Konto mit `group: admin` anmeldet.

Die Integration behandelt das gutmütig — ein Endpunkt, der `403`, `404` oder `501` liefert, wird
einmal protokolliert und danach übersprungen. Die übrigen Entitäten bleiben nutzbar.

---

## Gestaltungsentscheidungen

**Alle Werte kommen als Zeichenkette.** `gps/position/status` liefert `"0"` und `"49.155721"`,
`modems/status` dagegen echte Zahlen. Beides wird in `api.py` konvertiert; kein Plattformmodul
sieht je einen Zahlen-String. Das ist kein Schönheitsproblem: Ein Vergleich `wert == "0"` schlägt
lautlos fehl, sobald irgendwo eine Typumwandlung dazwischenkommt.

**Ein Nullwert ist ein Wert.** Entitäten melden nur dann „nicht verfügbar", wenn das Feld ganz
fehlt — nie bei `0`. Geschwindigkeit `0` und SINR `0` sind gültige Messwerte.

**`wireless/interfaces/status` wird nicht abgefragt.** Die Antwort ist rund 12 kB, weil sie jeden
WLAN-Client mit Datenraten auflistet. Alle 30 Sekunden ist das zu viel für ein kleines Gerät.

**Kein Reboot-Knopf.** Technisch möglich, aber ein Knopf, der das Gerät vom Netz nimmt, gehört
nicht ohne Weiteres in ein Dashboard. Kommt frühestens, wenn alles andere stabil läuft.

---

## Datenschutz

Die Rohantworten des Routers enthalten IMSI, ICCID, IMEI, MAC-Adressen, SSIDs, WLAN-Schlüssel und
VPN-Endpunkte. Der Diagnose-Download (`diagnostics.py`) redigiert diese Felder rekursiv, weil
Diagnosedateien ungelesen an Fehlerberichte gehängt werden.

Wer Beispieldaten für Tests beisteuert: Struktur behalten, Werte ersetzen.

---

## Entwicklung

`scripts/smoke_test.py` prüft den Client gegen einen echten Router — Typkonvertierung, URL-Aufbau,
alle Endpunkte, Token-Wiederverwendung und die Fehlerpfade für `403`, `501` und falsche
Zugangsdaten. Home Assistant wird dafür nicht gebraucht, nur `aiohttp`.

```bash
python -m venv .venv && .venv/bin/pip install aiohttp
RUTOS_HOST=192.168.1.1 RUTOS_USER=... RUTOS_PASS=... .venv/bin/python scripts/smoke_test.py
```

---

## Markenbild und Home Assistant

Seit HA das Markenbild über den eigenen Endpunkt `/api/brands/integration/{domain}/…` ausliefert,
prüft das Backend **zuerst das lokale `brand`-Verzeichnis der Integration** und greift erst danach
auf das CDN zurück (`homeassistant/components/brands/__init__.py`):

```python
brand_dir = Path(integration.file_path) / "brand"
# 1. Try custom integration local files
# 2. Try cache / CDN
```

Ein Pull Request gegen `home-assistant/brands` ist damit nicht nötig.

## Stand

Version 0.2.0 — Sensoren, binäre Sensoren, WireGuard-Schalter, lokale Marken-Assets.

Nicht enthalten und vorerst nicht geplant: Backup und Firmware-Aktualisierung. Beide Endpunkte
antworten am RUTC50 mit `403`, obwohl sich das Konto als `group: admin` anmeldet — ohne geklärte
Rechtelage ist dort nichts zu bauen.
