"""
emwsmd - Ey Mann, wo sind meine Drohnen!
Version 3.1.9

Neue PKCE-basierte Desktop-Version:
- feste Client ID im Programm
- kein Client Secret mehr im Tool gespeichert
- nur noch Login mit Character-Auswahl im Browser
- geeignet fuer Windows 10 / Windows 11

WICHTIG:
Vor dem Bauen bitte APP_CLIENT_ID unten auf deine EVE Application Client ID setzen.
Die App sollte fuer Desktop/Native PKCE genutzt werden.
"""

import argparse
import base64
import configparser
import hashlib
import http.server
import json
import os
import secrets
import shutil
import time
import urllib.parse
import webbrowser

import requests

APP_NAME = "emwsmd"
APP_TAGLINE = "Ey Mann, wo sind meine Drohnen!"
VERSION = "3.1.9"
REPORT_TITLE = f"{APP_TAGLINE}"
REPORT_FILENAME_DEFAULT = f"{APP_NAME}_Bericht.html"

AUTH_URL = "https://login.eveonline.com/v2/oauth/authorize"
TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
ESI_BASE = "https://esi.evetech.net/latest"
DRONE_CATEGORY_ID = 18

CALLBACK_PORT = 8765
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"
SCOPES = [
    "esi-assets.read_assets.v1",
    "esi-location.read_location.v1",
    "esi-universe.read_structures.v1",
]
CONFIG_PATH_DEFAULT = "tokencache"
CALLBACK_SERVER_TIMEOUT = 60

# HIER DEINE FESTE APP-ID EINTRAGEN
APP_CLIENT_ID = "29700e84fef64d7aa0a5f9bbc49f81cc"


class EveAuthPKCE:
    def __init__(self, config_path=CONFIG_PATH_DEFAULT, client_id=APP_CLIENT_ID):
        self.config_path = config_path
        self.client_id = client_id.strip()

        if not os.path.exists(self.config_path):
            legacy_config_path = "config.ini"
            if os.path.exists(legacy_config_path):
                print(f"Alte config.ini gefunden, verschiebe zu {self.config_path} ...")
                os.replace(legacy_config_path, self.config_path)

        self.config = configparser.ConfigParser(interpolation=None)
        self.config.read(self.config_path)
        if not self.config.has_section("eve_esi"):
            self.config.add_section("eve_esi")
        if not self.config.has_section("eve_token_cache"):
            self.config.add_section("eve_token_cache")
        self.refresh_token = self.config["eve_esi"].get(
            "refresh_token", "").strip()
        self._access_token = self.config["eve_token_cache"].get(
            "access_token", "").strip() or None
        try:
            self._expires_at = float(
                self.config["eve_token_cache"].get("expires_at", "0"))
        except ValueError:
            self._expires_at = 0
        self._code_verifier = None

    def has_client_id(self):
        return bool(self.client_id and self.client_id != "DEINE_CLIENT_ID_HIER")

    def has_refresh_token(self):
        return bool(self.refresh_token)

    def _save_tokens(self, access_token, expires_in, refresh_token):
        self._access_token = access_token
        self._expires_at = time.time() + expires_in - 30
        self.refresh_token = refresh_token
        self.config["eve_esi"]["refresh_token"] = refresh_token
        self.config["eve_token_cache"]["access_token"] = access_token
        self.config["eve_token_cache"]["expires_at"] = str(self._expires_at)
        self.config["eve_token_cache"]["refresh_token"] = refresh_token
        with open(self.config_path, "w", encoding="utf-8") as f:
            self.config.write(f)

    def generate_pkce(self):
        verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)).decode("utf-8").rstrip("=")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(
            verifier.encode("utf-8")).digest()).decode("utf-8").rstrip("=")
        self._code_verifier = verifier
        self.config["eve_token_cache"]["pkce_code_verifier"] = verifier
        with open(self.config_path, "w", encoding="utf-8") as f:
            self.config.write(f)
        return verifier, challenge

    def get_authorize_url(self, redirect_uri, scopes, state="emwsmd-pkce"):
        verifier, challenge = self.generate_pkce()
        params = {
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_token(self, auth_code):
        verifier = self.config["eve_token_cache"].get(
            "pkce_code_verifier", "").strip() or self._code_verifier
        if not verifier:
            raise RuntimeError(
                "PKCE code_verifier fehlt. Bitte Login erneut starten.")
        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "Host": "login.eveonline.com"}
        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "client_id": self.client_id,
            "code_verifier": verifier,
        }
        resp = requests.post(TOKEN_URL, headers=headers, data=data)
        resp.raise_for_status()
        payload = resp.json()
        self._save_tokens(payload["access_token"],
                          payload["expires_in"], payload["refresh_token"])
        return payload

    def _refresh_access_token(self):
        if not self.refresh_token:
            raise RuntimeError(
                "Kein refresh_token vorhanden. Login erforderlich.")
        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "Host": "login.eveonline.com"}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
        }
        resp = requests.post(TOKEN_URL, headers=headers, data=data)
        resp.raise_for_status()
        payload = resp.json()
        self._save_tokens(payload["access_token"], payload["expires_in"], payload.get(
            "refresh_token", self.refresh_token))
        return payload["access_token"]

    def get_access_token(self):
        if self._access_token and time.time() < self._expires_at:
            return self._access_token
        return self._refresh_access_token()

    def get_auth_header(self):
        return {"Authorization": f"Bearer {self.get_access_token()}"}

    def get_character_id(self):
        token = self.get_access_token()
        payload_b64 = token.split(".")[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return int(payload["sub"].split(":")[-1])


_auth_code_holder = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        _auth_code_holder["code"] = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            f"""<!DOCTYPE html>
            <html>
                <body style="margin:0;display:grid;place-items:center;height:100vh;
                background:#1b1b1b;color:#e5e5e5;font:16px system-ui,sans-serif">
                <div style="padding:2rem 2.5rem;background:#252525;border:1px solid #3a3a3a;
                border-radius:12px;text-align:center;box-shadow:0 8px 24px rgba(0,0,0,.35)">
                <h2 style="margin:0 0 .75rem">{APP_TAGLINE}</h2>
                <div>✓ Autorisierung erfolgreich.</div>
                <div style="margin-top:.5rem;color:#b0b0b0">
                Dieses Fenster kann geschlossen werden.
                </div>
                </div>
                </body>
                </html>""".encode("utf-8")
        )

    def log_message(self, format, *args):
        pass


def run_login_flow(auth):
    print()
    print("=" * 60)
    print(f"{APP_NAME} - EVE Online ESI Setup - Login erforderlich")
    print("=" * 60)
    if not auth.has_client_id():
        raise RuntimeError(
            "APP_CLIENT_ID ist noch nicht gesetzt. Bitte im Skript die feste Client ID eintragen und neu bauen."
        )
    print("Im naechsten Schritt wirst du im Browser aufgefordert,")
    print("dich bei EVE SSO einzuloggen und den Zugriff zu autorisieren.")
    print("Im Browser waehlst du nur noch deinen Character fuer den Login aus.")
    print()
    print("Die App wird folgende Berechtigungen anfordern:")
    for scope in SCOPES:
        print(f"  - {scope}")

    authorize_url = auth.get_authorize_url(REDIRECT_URI, SCOPES)
    print()
    print("Folgender link oeffnet sich automatisch im Browser:")
    print(authorize_url)
    try:
        webbrowser.open(authorize_url)
    except Exception:
        pass

    server = http.server.HTTPServer(
        ("localhost", CALLBACK_PORT), _CallbackHandler)
    server.timeout = CALLBACK_SERVER_TIMEOUT
    print()
    print(f"Warte {CALLBACK_SERVER_TIMEOUT} Sekunden auf die Autorisierung im Browser...")
    server.handle_request()
    server.server_close()

    code = _auth_code_holder.get("code")
    if not code:
        raise RuntimeError("Login fehlgeschlagen: kein Code erhalten.")

    payload = auth.exchange_code_for_token(code)
    print()
    print("Erfolgreich! Access- und Refresh-Token wurden in config.ini gespeichert.")
    print(f"Access Token laeuft ab in {payload['expires_in']} Sekunden, wird danach automatisch erneuert.")
    print("=" * 60)


def ensure_authenticated(auth):
    if not auth.has_refresh_token():
        run_login_flow(auth)
        return
    try:
        auth.get_access_token()
    except Exception:
        print("Gespeicherter Token ist ungueltig oder abgelaufen und konnte nicht erneuert werden.")
        run_login_flow(auth)


def get_all_drone_type_ids():
    r = requests.get(f"{ESI_BASE}/universe/categories/{DRONE_CATEGORY_ID}/")
    r.raise_for_status()
    type_ids = []
    for gid in r.json()["groups"]:
        gr = requests.get(f"{ESI_BASE}/universe/groups/{gid}/")
        gr.raise_for_status()
        type_ids.extend(gr.json().get("types", []))
    return type_ids


def get_type_info(type_id, cache):
    if type_id in cache:
        return cache[type_id]
    r = requests.get(f"{ESI_BASE}/universe/types/{type_id}/")
    r.raise_for_status()
    data = r.json()
    info = (data["name"], data.get("packaged_volume", data.get("volume", 0.0)))
    cache[type_id] = info
    return info


def get_character_assets(character_id, auth):
    assets = []
    page = 1
    while True:
        r = requests.get(
            f"{ESI_BASE}/characters/{character_id}/assets/",
            headers=auth.get_auth_header(),
            params={"page": page},
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        assets.extend(data)
        pages = int(r.headers.get("x-pages", 1))
        print(
            f"  Lade Assets: Seite {page}/{pages} ({len(assets)} Items bisher) ...", flush=True)
        if page >= pages:
            break
        page += 1
    return assets


def resolve_root_location(item, item_by_id, visited=None):
    if visited is None:
        visited = set()
    current = item
    while current["location_type"] == "item":
        loc_id = current["location_id"]
        if loc_id in visited:
            break
        visited.add(loc_id)
        parent = item_by_id.get(loc_id)
        if parent is None:
            break
        current = parent
    return current["location_id"], current["location_type"]


def get_character_system_id(character_id, auth):
    r = requests.get(
        f"{ESI_BASE}/characters/{character_id}/location/",
        headers=auth.get_auth_header(),
    )
    r.raise_for_status()
    return r.json()["solar_system_id"]


def get_location_system_id(location_id, location_type, auth, cache):
    cache_key = (location_id, location_type)
    if cache_key in cache:
        return cache[cache_key]

    if location_type == "solar_system":
        cache[cache_key] = location_id
        return location_id

    r = requests.get(f"{ESI_BASE}/universe/stations/{location_id}/")
    if r.status_code == 200:
        system_id = r.json()["system_id"]
        cache[cache_key] = system_id
        return system_id

    r = requests.get(
        f"{ESI_BASE}/universe/structures/{location_id}/",
        headers=auth.get_auth_header(),
    )
    r.raise_for_status()
    system_id = r.json()["solar_system_id"]
    cache[cache_key] = system_id
    return system_id


def get_jump_count(origin_system_id, destination_system_id, cache):
    cache_key = (origin_system_id, destination_system_id)
    if cache_key in cache:
        return cache[cache_key]

    if origin_system_id == destination_system_id:
        cache[cache_key] = 0
        return 0

    r = requests.get(
        f"{ESI_BASE}/route/{origin_system_id}/{destination_system_id}/")
    r.raise_for_status()
    jumps = max(0, len(r.json()) - 1)
    cache[cache_key] = jumps
    return jumps


def get_location_name(location_id, location_type, auth, cache, error_count=[0]):
    if location_id in cache:
        return cache[location_id]
    name = f"Unbekannte Struktur ({location_id})"
    try:
        if location_type == "solar_system":
            r = requests.get(f"{ESI_BASE}/universe/systems/{location_id}/")
            r.raise_for_status()
            name = r.json()["name"]
        else:
            r = requests.get(f"{ESI_BASE}/universe/stations/{location_id}/")
            if r.status_code == 200:
                name = r.json()["name"]
            else:
                r = requests.get(
                    f"{ESI_BASE}/universe/structures/{location_id}/",
                    headers=auth.get_auth_header(),
                )
                if r.status_code == 200:
                    name = r.json()["name"]
                else:
                    error_count[0] += 1
                    if error_count[0] % 20 == 0:
                        time.sleep(2)
    except requests.RequestException:
        error_count[0] += 1
    cache[location_id] = name
    return name


def count_drones(character_id, auth):
    print("Ermittle Drohnen-Typen aus der EVE-Datenbank ...", flush=True)
    drone_type_ids = set(get_all_drone_type_ids())
    print("Lade Charakter-Inventar (kann bei vielen Items dauern) ...", flush=True)
    assets = get_character_assets(character_id, auth)
    item_by_id = {a["item_id"]: a for a in assets}
    print(f"Insgesamt {len(assets)} Items geladen."
          f" Filtere Drohnen und loese Stationen auf ...", flush=True)

    type_cache = {}
    location_name_cache = {}
    location_system_cache = {}
    route_cache = {}
    by_name = {}
    by_station = {}

    current_system_id = None
    try:
        current_system_id = get_character_system_id(character_id, auth)
        print(f"Aktueller Standort-System-ID: {current_system_id}", flush=True)
    except requests.RequestException as exc:
        print(f"Konnte aktuellen Standort nicht ermitteln: {exc}", flush=True)

    drone_items = [
        item for item in assets if item["type_id"] in drone_type_ids]
    total_drone_items = len(drone_items)
    print(f"{total_drone_items} Drohnen-Eintraege gefunden. Beginne Stations-Aufloesung ...", flush=True)

    for idx, item in enumerate(drone_items, start=1):
        tid = item["type_id"]
        qty = item.get("quantity", 1)
        name, vol_each = get_type_info(tid, type_cache)
        entry = by_name.setdefault(name, {"qty": 0, "volume_each": vol_each})
        entry["qty"] += qty
        root_id, root_type = resolve_root_location(item, item_by_id)
        station_name = get_location_name(
            root_id, root_type, auth, location_name_cache)

        jumps = None
        if current_system_id is not None:
            try:
                target_system_id = get_location_system_id(
                    root_id, root_type, auth, location_system_cache)
                jumps = get_jump_count(
                    current_system_id, target_system_id, route_cache)
                print(
                    f"  Route: {station_name} | Zielsystem {target_system_id} | {jumps} Jumps", flush=True)
            except requests.RequestException as exc:
                print(
                    f"  Route konnte nicht berechnet werden fuer {station_name}: {exc}", flush=True)

        s_entry = by_station.setdefault(
            station_name, {"qty": 0, "volume": 0.0, "jumps": jumps})
        if s_entry.get("jumps") is None and jumps is not None:
            s_entry["jumps"] = jumps
        s_entry["qty"] += qty
        s_entry["volume"] += qty * vol_each
        if idx % 100 == 0 or idx == total_drone_items:
            print(
                f"  Fortschritt: {idx}/{total_drone_items} Eintraege verarbeitet, {len(by_station)} Stationen bisher ...", flush=True)

    total = sum(v["qty"] for v in by_name.values())
    return total, by_name, by_station


def build_html(total, by_name, by_station, output_path=REPORT_FILENAME_DEFAULT):
    name_rows = "".join(
        f"<tr><td>{name}</td><td>{data['qty']}</td><td>{data['volume_each']:.2f} m3</td><td>{data['qty'] * data['volume_each']:.2f} m3</td></tr>"
        for name, data in sorted(by_name.items())
    )
    station_rows = "".join(
        f"<tr><td>{station}</td><td>{data.get('jumps') if data.get('jumps') is not None else 'unbekannt'}</td><td>{data['qty']}</td><td>{data['volume']:.2f} m3</td></tr>"
        for station, data in sorted(
            by_station.items(),
            key=lambda item: (
                item[1].get('jumps') is None,
                item[1].get('jumps') if item[1].get(
                    'jumps') is not None else 999999,
                item[0].lower(),
            ),
        )
    )
    html = f"""<!DOCTYPE html>
<html lang=\"de\">
<head>
<meta charset=\"utf-8\">
<title>{REPORT_TITLE}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 2em; background: #1a1a1a; color: #d5d5d5; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
  th, td {{ border: 1px solid #444; padding: 6px 10px; text-align: left; }}
  th {{ background: #2b2b2b; color: #eaeaea; }}
  details {{ margin-bottom: 1.5em; }}
  summary {{ font-size: 1.1em; cursor: pointer; font-weight: bold; color: #d5d5d5; }}
  button {{ padding: 8px 14px; font-size: 1em; cursor: pointer; margin-bottom: 1em; background: #333; color: #eee; border: 1px solid #444; border-radius: 6px; }}
  .watermark {{ margin-top: 3em; text-align: right; font-size: 1.5em; color: #1e1e1f; user-select: none; }}
</style>
</head>
<body>
<h1>{REPORT_TITLE}</h1>
<p>Gesamtanzahl aller Drohnen: <strong>{total}</strong></p>
<details open>
  <summary>Drohnen nach Name (aufklappen)</summary>
  <table>
    <tr><th>Drohnenname</th><th>Anzahl</th><th>Volumen/Stk</th><th>Gesamtvolumen</th></tr>
    {name_rows}
  </table>
</details>
<button onclick=\"document.getElementById('stationTable').style.display = document.getElementById('stationTable').style.display === 'none' ? 'block' : 'none';\">
  Transport-Uebersicht pro Station anzeigen/verstecken
</button>
<div id=\"stationTable\" style=\"display:none;\">
  <h2>Transport-Uebersicht pro Station</h2>
  <table>
    <tr><th>Station</th><th>Jumps</th><th>Anzahl Drohnen</th><th>Volumen (gesamt)</th></tr>
    {station_rows}
  </table>
</div>
<div class=\"watermark\">by Foschbaa</div>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - {APP_TAGLINE} (v{VERSION})")
    parser.add_argument("action", nargs="?", default="count", choices=[
                        "count", "install"], help="'count' (Standard): Drohnen zaehlen. 'install': nur Login/Setup erzwingen.")
    parser.add_argument("character_id", type=int, nargs="?", default=None)
    parser.add_argument("--config", default=CONFIG_PATH_DEFAULT)
    parser.add_argument("--output", default=REPORT_FILENAME_DEFAULT)
    args = parser.parse_args()

    print()
    print(f"{APP_NAME} v{VERSION} -- {APP_TAGLINE}")
    print()
    print("Das Tool startet jetzt und ruft die Daten von EVE Online ab.")
    print("Bei sehr vielen Drohnen/Stationen kann das mehrere Minuten dauern")
    print()

    auth = EveAuthPKCE(config_path=args.config)

    if args.action == "install":
        if auth.has_refresh_token():
            print("Es ist bereits ein refresh_token in config.ini vorhanden.")
            answer = input(
                "Trotzdem neu einloggen und Token ersetzen? (j/N): ").strip().lower()
            if answer != "j":
                print("Setup abgeschlossen, bestehender Token wird weiter genutzt.")
                return
        run_login_flow(auth)
        print("Setup abgeschlossen. Naechster Aufruf ohne Argument zaehlt automatisch die Drohnen.")
        return

    try:
        ensure_authenticated(auth)
        character_id = args.character_id or auth.get_character_id()
        character_system_id = get_character_system_id(character_id, auth)
        location_name_cache = {}
        character_system_name = get_location_name(
            character_system_id,
            "solar_system",
            auth,
            location_name_cache,
        )
    except RuntimeError as exc:
        print(f"FEHLER: {exc}")
        return

    total, by_name, by_station = count_drones(character_id, auth)
    path = build_html(total, by_name, by_station, args.output)

    print()
    print(f"Character-ID: ({character_id})")
    print(f"Character-Position: {character_system_name} ({character_system_id})")
    print()
    print(f"Gesamtanzahl Drohnen: {total}")
    print(f"Anzahl der Stationen mit Drohnen: {len(by_station)}")
    print()
    print(f"Bericht geschrieben nach: {path}")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nEin Fehler ist aufgetreten: {e}\n")
    finally:
        input(f"\nDruecke Enter zum Beenden ...")
