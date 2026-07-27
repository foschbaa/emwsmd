
# 🛰️ emwsmd
### *Ey Mann, wo sind meine Drohnen!*

Ein EVE Online GUI-Tool, das deine Drohnen in **Stationen und Containern** zaehlt, dir zeigt wo sie liegen - und dich per Klick direkt dorthin routet.

[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)](#-download--start)
[![Made for](https://img.shields.io/badge/EVE%20Online-ESI%20API-2C2C54?logo=eve-online&logoColor=white)](#)
[![Build](https://img.shields.io/badge/Build-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](#-windows-release-build)
[![License](https://img.shields.io/badge/Status-Aktiv-brightgreen)](#)

</div>

---

## ✨ Was macht emwsmd?

emwsmd durchsucht dein Charakter-Inventar ueber die EVE ESI-API und zaehlt **alle Drohnen, die in Stationen oder Containern liegen** – Drohnen im All werden nicht erfasst.

<table>
<tr>
<td width="50%" valign="top">

**Die GUI zeigt dir:**
- 🧮 Drohnen gesamt, nach Namen gruppiert
- 🏠 Lagerort nach Station oder Struktur
- 📦 benoetigtes Transportvolumen
- 🚀 Jumps von deinem Standort zur Zielstation
- 🧭 Route setzen / Waypoint hinzufuegen per Klick

</td>
<td width="50%" valign="top">

**Auf einen Blick:**
- Login per EVE SSO (Browser)
- Zwei Ansichten: nach Name / nach Station
- CSV- & HTML-Export
- Direktes Routing an den Charakter im Spiel
- Login-Button wird nach Login automatisch zu Logout

</td>
</tr>
</table>

---

## 🖥️ Plattform-Status

| Plattform | Status | Weg |
|---|---|---|
| 🪟 **Windows** | ✅ Fertige Version | Release-ZIP herunterladen, `emwsmd-gui.exe` starten |
| 🐧 Linux | 🔧 Vorerst kein Fertig-Build | `.py` direkt starten oder eigenen PyInstaller-Build erstellen |
| 🍎 macOS | 🔧 Vorerst kein Fertig-Build | `.py` direkt starten oder eigenen PyInstaller-Build erstellen |

Die Windows-.exe ist der **empfohlene Weg** fuer die meisten Nutzer.

---

## ⚠️ Sicherheitshinweis

> ### 🔒 Gib **niemals** die Datei `tokencache` weiter.
> Sie enthaelt deine lokal gespeicherten EVE-Login-Daten. Nicht in ZIPs, Discord, Support-Tickets oder Git-Repos hochladen.

---

## 🚀 Download & Start

### 🪟 Windows (empfohlen)

1. Neueste Release-ZIP von der [Releases-Seite](../../releases) herunterladen
2. ZIP entpacken
3. `emwsmd-gui.exe` doppelklicken
4. Auf **Login (EVE SSO)** klicken → Browser oeffnet sich automatisch
5. Charakter auswaehlen und autorisieren
6. Zurueck in der App: **Drohnen scannen** klicken

### 🐧🍎 Linux / macOS

Noch kein fertiger Build – aber einfach selbst starten:

```bash
pip install "flet[all]"==0.28.3 requests==2.32.5
python emwsmd_GUI.py
```

Oder eigenen Build erstellen:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name emwsmd-gui emwsmd_GUI.py
```

---

## 🧭 Erster Ablauf

```
GUI starten
   │
   ▼
Login (EVE SSO) klicken ──▶ Browser: Charakter waehlen + autorisieren
   │
   ▼
Button wird zu "Logout" · "Drohnen scannen" wird aktiv
   │
   ▼
Scan starten ──▶ Ansicht "Nach Drohnenname" oder "Nach Station"
   │
   ▼
Optional: CSV/HTML exportieren oder Route/Waypoint direkt setzen
```

---

## 📍 Routing direkt aus der GUI

Im Tab **Nach Station** hat jede Zeile zwei Aktions-Buttons:

| Button | Wirkung |
|---|---|
| 🧭 **Route setzen** | Setzt die Station als neues Ziel, loescht andere Wegpunkte |
| ➕ **Waypoint hinzufuegen** | Haengt die Station an die bestehende Route an |

Dafuer wird der Scope `esi-ui.write_waypoint.v1` benoetigt. Passt ein alter Token nicht mehr zu den benoetigten Scopes, wird er automatisch zurueckgesetzt und ein neuer Browser-Login angefordert – ganz ohne manuelles Aufraeumen.

---

## 📁 Inhalt des Windows-Pakets

| Datei | Bedeutung |
|---|---|
| `emwsmd-gui.exe` | die fertige Windows-Anwendung |
| `README.txt` | Kurzanleitung im Release-ZIP |
| `tokencache` *(entsteht nach 1. Login)* | 🔒 lokaler Login-Cache – niemals weitergeben |
| `emwsmd_gui_Bericht.html` | HTML-Export aus der Anwendung |
| `emwsmd_gui_export.csv` | CSV-Export aus der Anwendung |

---

## 🛠️ Windows Release Build

Die `.exe` wird automatisch per GitHub Actions gebaut, sobald ein Release veroeffentlicht wird: PyInstaller erstellt `emwsmd-gui.exe`, die App wird zusammen mit der README als `emwsmd-gui_windows.zip` an das Release angehaengt.

---

<div align="center">

**Die GUI ist der Hauptpfad dieses Projekts.**
Neue Features fliessen in die GUI – eine separate CLI wird nicht mehr aktiv weitergefuehrt.