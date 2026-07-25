"""
emwsmd_GUI.0.1.5.py
Ey Mann, wo sind meine Drohnen! - GUI-Version (auf Basis von emwsmd.py v3.1.8)

Eigenstaendige, komplette Anwendung: Auth, ESI-Abfrage, Datenaufbereitung UND GUI
liegen in dieser einen Datei. Die Konsolen-Version wird nicht mehr separat benoetigt.

Versionsschema fuer diese GUI-Reihe: emwsmd_GUI.<major>.<minor>.<patch>.py
Diese Datei: emwsmd_GUI.0.1.5.py

Installation (im aktivierten venv):
    pip install "flet[all]" requests

Start:
    python "emwsmd_GUI.0.1.5.py"
"""

import base64
import configparser
import csv
import hashlib
import http.server
import io
import json
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser

import requests
import flet as ft

# ---------------------------------------------------------------------------
# Konstanten (unveraendert aus emwsmd.py)
# ---------------------------------------------------------------------------

APP_NAME = "emwsmd_gui"
APP_TAGLINE = "Ey Mann, wo sind meine Drohnen!"
GUI_VERSION = "0.1.5"

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


# ---------------------------------------------------------------------------
# Auth (unveraendert aus emwsmd.py)
# ---------------------------------------------------------------------------

class EveAuthPKCE:
    def __init__(self, config_path=CONFIG_PATH_DEFAULT, client_id=APP_CLIENT_ID):
        self.config_path = config_path
        self.client_id = client_id.strip()

        if not os.path.exists(self.config_path):
            legacy_config_path = "config.ini"
            if os.path.exists(legacy_config_path):
                os.replace(legacy_config_path, self.config_path)

        self.config = configparser.ConfigParser(interpolation=None)
        self.config.read(self.config_path)

        if not self.config.has_section("eve_esi"):
            self.config.add_section("eve_esi")
        if not self.config.has_section("eve_token_cache"):
            self.config.add_section("eve_token_cache")
        if not self.config.has_section("last_char"):
            self.config.add_section("last_char")

        self.refresh_token = self.config["eve_esi"].get("refresh_token", "").strip()
        self._access_token = self.config["eve_token_cache"].get("access_token", "").strip() or None
        try:
            self._expires_at = float(self.config["eve_token_cache"].get("expires_at", "0"))
        except ValueError:
            self._expires_at = 0
        self._code_verifier = None

    def has_client_id(self):
        return bool(self.client_id and self.client_id != "DEINE_CLIENT_ID_HIER")

    def has_refresh_token(self):
        return bool(self.refresh_token)

    def get_last_char(self):
        """Liest (character_id, character_name) aus [last_char], oder (None, None)."""
        cid = self.config["last_char"].get("character_id", "").strip()
        cname = self.config["last_char"].get("character_name", "").strip()
        if cid and cname:
            try:
                return int(cid), cname
            except ValueError:
                return None, None
        return None, None

    def set_last_char(self, character_id, character_name):
        self.config["last_char"]["character_id"] = str(character_id)
        self.config["last_char"]["character_name"] = character_name
        with open(self.config_path, "w", encoding="utf-8") as f:
            self.config.write(f)

    def clear_last_char(self):
        self.config["last_char"]["character_id"] = ""
        self.config["last_char"]["character_name"] = ""
        with open(self.config_path, "w", encoding="utf-8") as f:
            self.config.write(f)

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
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("utf-8")).digest()
        ).decode("utf-8").rstrip("=")
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
        verifier = self.config["eve_token_cache"].get("pkce_code_verifier", "").strip() or self._code_verifier
        if not verifier:
            raise RuntimeError("PKCE code_verifier fehlt. Bitte Login erneut starten.")
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Host": "login.eveonline.com"}
        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "client_id": self.client_id,
            "code_verifier": verifier,
        }
        resp = requests.post(TOKEN_URL, headers=headers, data=data, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        self._save_tokens(payload["access_token"], payload["expires_in"], payload["refresh_token"])
        return payload

    def _refresh_access_token(self):
        if not self.refresh_token:
            raise RuntimeError("Kein refresh_token vorhanden. Login erforderlich.")
            page.update()
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Host": "login.eveonline.com"}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
        }
        resp = requests.post(TOKEN_URL, headers=headers, data=data, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        self._save_tokens(
            payload["access_token"], payload["expires_in"], payload.get("refresh_token", self.refresh_token)
        )
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
    protocol_version = "HTTP/1.1"  # noetig, damit Content-Length + Connection: close sauber greifen

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        _auth_code_holder["code"] = params.get("code", [None])[0]

        body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;display:grid;place-items:center;height:100vh;
background:#1b1b1b;color:#e5e5e5;font:16px system-ui,sans-serif;">
<div style="padding:2rem 2.5rem;background:#252525;border:1px solid #3a3a3a;
border-radius:12px;text-align:center;box-shadow:0 8px 24px rgba(0,0,0,.35);">
<h2 style="margin:0 0 .75rem">{APP_TAGLINE}</h2>
<div>Autorisierung erfolgreich.</div>
<div style="margin-top:.5rem;color:#b0b0b0">Dieses Fenster kann geschlossen werden.</div>
</div></body></html>""".encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")  # verhindert Keep-Alive-Wartezeit beim Client
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True  # Server soll die Verbindung sofort beenden, nicht auf weitere Requests warten
        return
    def log_message(self, format, *args):
        pass


def run_login_flow(auth, log=print, open_browser=True):
    if not auth.has_client_id():
        raise RuntimeError("APP_CLIENT_ID ist noch nicht gesetzt.")

    _auth_code_holder.pop("code", None)  # alten Code aus einem frueheren Versuch verwerfen

    authorize_url = auth.get_authorize_url(REDIRECT_URI, SCOPES)
    log("Oeffne Login-Seite im Browser ...")
    if open_browser:
        try:
            webbrowser.open(authorize_url)
        except Exception:
            pass

    http.server.HTTPServer.allow_reuse_address = True
    server = http.server.HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    server.timeout = 1  # kurze Zyklen statt einem langen Block, damit wir sofort reagieren koennen
    log(f"Warte bis zu {CALLBACK_SERVER_TIMEOUT} Sekunden auf Autorisierung im Browser ...")

    deadline = time.time() + CALLBACK_SERVER_TIMEOUT
    code = None
    while time.time() < deadline:
        server.handle_request()  # kehrt nach 1s zurueck, falls keine Anfrage ankam
        code = _auth_code_holder.get("code")
        if code:
            break
        # Falls eine irrelevante Anfrage (z.B. favicon.ico) den einzigen Request "verbraucht" hat,
        # machen wir einfach im naechsten Zyklus weiter und warten auf die echte /callback-Anfrage.

    server.server_close()

    if not code:
        raise RuntimeError("Login fehlgeschlagen: kein Code erhalten (Timeout).")

    payload = auth.exchange_code_for_token(code)
    log("Login erfolgreich, Tokens gespeichert.")
    return payload


def ensure_authenticated(auth, log=print):
    if not auth.has_refresh_token():
        run_login_flow(auth, log=log)
        return
    try:
        auth.get_access_token()
    except Exception:
        log("Gespeicherter Token ist ungueltig/abgelaufen, starte Login neu ...")
        run_login_flow(auth, log=log)


# ---------------------------------------------------------------------------
# ESI-Datenlogik (unveraendert aus emwsmd.py, mit optionalem progress-callback)
# ---------------------------------------------------------------------------

def get_all_drone_type_ids():
    r = requests.get(f"{ESI_BASE}/universe/categories/{DRONE_CATEGORY_ID}/", timeout=15)
    r.raise_for_status()
    type_ids = []
    for gid in r.json()["groups"]:
        gr = requests.get(f"{ESI_BASE}/universe/groups/{gid}/", timeout=15)
        gr.raise_for_status()
        type_ids.extend(gr.json().get("types", []))
    return type_ids


def get_type_info(type_id, cache):
    if type_id in cache:
        return cache[type_id]
    r = requests.get(f"{ESI_BASE}/universe/types/{type_id}/", timeout=15)
    r.raise_for_status()
    data = r.json()
    info = (data["name"], data.get("packaged_volume", data.get("volume", 0.0)))
    cache[type_id] = info
    return info


def get_character_assets(character_id, auth, progress=None):
    assets = []
    page = 1
    while True:
        r = requests.get(
            f"{ESI_BASE}/characters/{character_id}/assets/",
            headers=auth.get_auth_header(),
            params={"page": page},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        assets.extend(data)
        pages = int(r.headers.get("x-pages", 1))
        if progress:
            progress("inventory", f"Seite {page}/{pages} ({len(assets)} Items bisher)", page, pages)
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


def get_character_name(character_id):
    r = requests.get(f"{ESI_BASE}/characters/{character_id}/", timeout=15)
    r.raise_for_status()
    return r.json()["name"]


def get_character_system_id(character_id, auth):
    r = requests.get(f"{ESI_BASE}/characters/{character_id}/location/", headers=auth.get_auth_header(), timeout=15)
    r.raise_for_status()
    return r.json()["solar_system_id"]


def get_location_system_id(location_id, location_type, auth, cache):
    cache_key = (location_id, location_type)
    if cache_key in cache:
        return cache[cache_key]
    if location_type == "solar_system":
        cache[cache_key] = location_id
        return location_id
    r = requests.get(f"{ESI_BASE}/universe/stations/{location_id}/", timeout=15)
    if r.status_code == 200:
        system_id = r.json()["system_id"]
        cache[cache_key] = system_id
        return system_id
    r = requests.get(f"{ESI_BASE}/universe/structures/{location_id}/", headers=auth.get_auth_header(), timeout=15)
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
    r = requests.get(f"{ESI_BASE}/route/{origin_system_id}/{destination_system_id}/", timeout=15)
    r.raise_for_status()
    jumps = max(0, len(r.json()) - 1)
    cache[cache_key] = jumps
    return jumps


def get_location_name(location_id, location_type, auth, cache, _error_count=None):
    if location_id in cache:
        return cache[location_id]
    name = f"Unbekannte Struktur {location_id}"
    try:
        if location_type == "solar_system":
            r = requests.get(f"{ESI_BASE}/universe/systems/{location_id}/", timeout=15)
            r.raise_for_status()
            name = r.json()["name"]
        else:
            r = requests.get(f"{ESI_BASE}/universe/stations/{location_id}/", timeout=15)
            if r.status_code == 200:
                name = r.json()["name"]
            else:
                r = requests.get(f"{ESI_BASE}/universe/structures/{location_id}/", headers=auth.get_auth_header(), timeout=15)
                if r.status_code == 200:
                    name = r.json()["name"]
    except requests.RequestException:
        pass
    cache[location_id] = name
    return name


def count_drones(character_id, auth, progress=None):
    """
    progress(phase: str, msg: str, current: int|None, total: int|None) wird waehrend der
    Verarbeitung aufgerufen. phase ist einer von: "types", "inventory", "routes".
    current/total = None bedeutet: unbestimmter Fortschritt (Phase hat keine bekannte Groesse).
    Die GUI zeigt pro Phase eine eigene Anzeige (siehe build_gui).
    """
    def report(phase, msg, current=None, total=None):
        if progress:
            progress(phase, msg, current, total)

    report("types", "Ermittle Drohnen-Typen aus der EVE-Datenbank ...")
    drone_type_ids = set(get_all_drone_type_ids())
    report("types", "Drohnen-Typen ermittelt.", 1, 1)

    report("inventory", "Lade Charakter-Inventar ...")
    assets = get_character_assets(
        character_id, auth,
        progress=lambda phase, msg, cur, tot: report(phase, msg, cur, tot),
    )
    report("inventory", f"Inventar geladen ({len(assets)} Items).", 1, 1)

    item_by_id = {a["item_id"]: a for a in assets}

    type_cache = {}
    location_name_cache = {}
    location_system_cache = {}
    route_cache = {}

    by_name = {}
    by_station = {}

    current_system_id = None
    try:
        current_system_id = get_character_system_id(character_id, auth)
    except requests.RequestException:
        pass

    drone_items = [item for item in assets if item["type_id"] in drone_type_ids]
    total_drone_items = len(drone_items)

    report("routes", f"{total_drone_items} Drohnen-Eintraege gefunden. Beginne Stations-Aufloesung ...",
           0, total_drone_items)

    for idx, item in enumerate(drone_items, start=1):
        tid = item["type_id"]
        qty = item.get("quantity", 1)
        name, vol_each = get_type_info(tid, type_cache)

        entry = by_name.setdefault(name, {"qty": 0, "volume_each": vol_each})
        entry["qty"] += qty

        root_id, root_type = resolve_root_location(item, item_by_id)
        station_name = get_location_name(root_id, root_type, auth, location_name_cache)

        jumps = None
        if current_system_id is not None:
            try:
                target_system_id = get_location_system_id(root_id, root_type, auth, location_system_cache)
                jumps = get_jump_count(current_system_id, target_system_id, route_cache)
            except requests.RequestException:
                pass

        sentry = by_station.setdefault(station_name, {"qty": 0, "volume": 0.0, "jumps": jumps})
        if sentry.get("jumps") is None and jumps is not None:
            sentry["jumps"] = jumps
        sentry["qty"] += qty
        sentry["volume"] += qty * vol_each

        report("routes", f"Route: {station_name} | {len(by_station)} Stationen bisher ...",
               idx, total_drone_items)

    total = sum(v["qty"] for v in by_name.values())
    return total, by_name, by_station


def build_html(total, by_name, by_station, output_path=REPORT_FILENAME_DEFAULT):
    name_rows = "".join(
        f"<tr><td>{name}</td><td>{data['qty']}</td>"
        f"<td>{data['volume_each']:.2f} m3</td>"
        f"<td>{data['qty'] * data['volume_each']:.2f} m3</td></tr>"
        for name, data in sorted(by_name.items())
    )
    station_rows = "".join(
        f"<tr><td>{station}</td>"
        f"<td>{data.get('jumps') if data.get('jumps') is not None else 'unbekannt'}</td>"
        f"<td>{data['qty']}</td><td>{data['volume']:.2f} m3</td></tr>"
        for station, data in sorted(
            by_station.items(),
            key=lambda item: (
                item[1].get("jumps") is None,
                item[1].get("jumps") if item[1].get("jumps") is not None else 999999,
                item[0].lower(),
            ),
        )
    )
    html = f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>{REPORT_TITLE}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 2em; background:#1a1a1a; color:#d5d5d5; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
th, td {{ border: 1px solid #444; padding: 6px 10px; text-align: left; }}
th {{ background:#2b2b2b; color:#eaeaea; }}
</style></head>
<body>
<h1>{REPORT_TITLE}</h1>
<p>Gesamtanzahl aller Drohnen: <strong>{total}</strong></p>
<h2>Nach Drohnenname</h2>
<table><tr><th>Drohnenname</th><th>Anzahl</th><th>Volumen/Stk</th><th>Gesamtvolumen</th></tr>
{name_rows}</table>
<h2>Transport-Uebersicht pro Station</h2>
<table><tr><th>Station</th><th>Jumps</th><th>Anzahl Drohnen</th><th>Volumen gesamt</th></tr>
{station_rows}</table>
</body></html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


# ---------------------------------------------------------------------------
# GUI (Flet)
# ---------------------------------------------------------------------------

def main(page: ft.Page):
    page.title = f"{APP_TAGLINE} (GUI v{GUI_VERSION})"
    page.window_width = 980
    page.window_height = 720
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20

    auth_holder = {"auth": None}
    result_holder = {"total": 0, "by_name": {}, "by_station": {}}
    busy = {"value": False}
    progress_state = {"phase": None, "msg": "", "current": None, "total": None}

    status_text = ft.Text("Bereit.", size=14, color=ft.Colors.GREY_400)
    character_text = ft.Text("Nicht angemeldet.", size=14, weight=ft.FontWeight.BOLD)
    total_text = ft.Text("", size=18, weight=ft.FontWeight.BOLD)

    phase_loading_label = ft.Text("1. Drohnen-Daten laden", size=13, color=ft.Colors.GREY_400)
    phase_loading_bar = ft.ProgressBar(value=None, visible=False, width=400)
    phase_loading_status = ft.Text("", size=12, color=ft.Colors.GREY_500)

    phase_routes_label = ft.Text("2. Stationen/Routen aufloesen", size=13, color=ft.Colors.GREY_400)
    phase_routes_bar = ft.ProgressBar(value=0, visible=False, width=400)
    phase_routes_status = ft.Text("", size=12, color=ft.Colors.GREY_500)

    progress_column = ft.Column(
        [
            phase_loading_label, phase_loading_bar, phase_loading_status,
            phase_routes_label, phase_routes_bar, phase_routes_status,
        ],
        spacing=2,
        visible=False,
    )

    login_btn = ft.Button("Login (EVE SSO)", icon=ft.Icons.LOGIN)
    scan_btn = ft.Button("Drohnen scannen", icon=ft.Icons.RADAR, disabled=True)
    export_csv_btn = ft.OutlinedButton("Export CSV", icon=ft.Icons.TABLE_VIEW, disabled=True)
    export_html_btn = ft.OutlinedButton("Export HTML", icon=ft.Icons.HTML, disabled=True)

    name_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Drohnenname")),
            ft.DataColumn(ft.Text("Anzahl"), numeric=True),
            ft.DataColumn(ft.Text("Volumen/Stk (m3)"), numeric=True),
            ft.DataColumn(ft.Text("Gesamtvolumen (m3)"), numeric=True),
        ],
        rows=[],
    )

    station_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Station")),
            ft.DataColumn(ft.Text("Jumps"), numeric=True),
            ft.DataColumn(ft.Text("Anzahl Drohnen"), numeric=True),
            ft.DataColumn(ft.Text("Volumen (m3)"), numeric=True),
        ],
        rows=[],
    )

    tabs = ft.Tabs(
        length=2,
        selected_index=0,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Nach Drohnenname"),
                        ft.Tab(label="Nach Station"),
                    ],
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        ft.Container(ft.Column([name_table], scroll=ft.ScrollMode.AUTO), padding=10),
                        ft.Container(ft.Column([station_table], scroll=ft.ScrollMode.AUTO), padding=10),
                    ],
                ),
            ],
        ),
    )

    def apply_progress():
        phase = progress_state["phase"]
        msg = progress_state["msg"]
        current = progress_state["current"]
        total = progress_state["total"]

        progress_column.visible = phase is not None
        phase_loading_bar.visible = phase in ("types", "inventory")
        phase_routes_bar.visible = phase == "routes"

        phase_loading_status.value = ""
        phase_routes_status.value = ""

        if phase in ("types", "inventory"):
            phase_loading_status.value = msg
            phase_loading_bar.value = None
        elif phase == "routes":
            phase_routes_status.value = msg
            if current is not None and total:
                phase_routes_bar.value = current / total
            else:
                phase_routes_bar.value = None

    def on_progress_message(message):
        if message.get("topic") != "progress":
            return

        progress_state["phase"] = message.get("phase")
        progress_state["msg"] = message.get("msg", "")
        progress_state["current"] = message.get("current")
        progress_state["total"] = message.get("total")

        apply_progress()
        page.update()

    page.pubsub.subscribe(on_progress_message)

    def set_busy(is_busy: bool):
        busy["value"] = is_busy

        login_btn.disabled = is_busy
        scan_btn.disabled = is_busy or auth_holder["auth"] is None
        export_csv_btn.disabled = is_busy or not result_holder["by_name"]
        export_html_btn.disabled = is_busy or not result_holder["by_name"]

        if not is_busy:
            progress_state["phase"] = None
            progress_state["msg"] = ""
            progress_state["current"] = None
            progress_state["total"] = None
            progress_column.visible = False
            phase_loading_bar.visible = False
            phase_routes_bar.visible = False
            phase_loading_status.value = ""
            phase_routes_status.value = ""

        page.update()

    def set_status(msg: str, error: bool = False):
        status_text.value = msg
        status_text.color = ft.Colors.RED_300 if error else ft.Colors.GREY_400
        page.update()

    def gui_progress_callback(phase, msg, current, total):
        """
        PubSub-Callback: der Worker-Thread publiziert nur Daten, die GUI aktualisiert
        im Haupt-Event-Loop.
        """
        page.pubsub.send_all({"topic": "progress", "phase": phase, "msg": msg, "current": current, "total": total,})

    def on_login_message(message):
        if message.get("topic") != "login":
            return

        kind = message.get("kind")

        if kind == "busy_start":
            set_busy(True)
            return

        if kind == "busy_done":
            set_busy(False)
            return

        if kind == "status":
            set_status(message.get("msg", ""), error=message.get("error", False))
            return

        if kind == "login_success":
            char_id = message.get("char_id")
            char_name = message.get("char_name")

            if char_name:
                character_text.value = f"Angemeldet als {char_name} (Character-ID: {char_id})"
            else:
                character_text.value = f"Angemeldet (Character-ID: {char_id})"

            status_text.value = "Login erfolgreich."
            status_text.color = ft.Colors.GREY_400
            scan_btn.disabled = False
            export_csv_btn.disabled = not result_holder["by_name"]
            export_html_btn.disabled = not result_holder["by_name"]
            page.update()
            return

        if kind == "login_error":
            character_text.value = "Nicht angemeldet."
            status_text.value = message.get("msg", "Login fehlgeschlagen.")
            status_text.color = ft.Colors.RED_300
            scan_btn.disabled = True
            export_csv_btn.disabled = True
            export_html_btn.disabled = True
            page.update()
            return

    page.pubsub.subscribe(on_login_message)

    def on_scan_message(message):
        if message.get("topic") != "scan":
            return

        kind = message.get("kind")

        if kind == "busy_start":
            set_busy(True)
            return

        if kind == "busy_done":
            set_busy(False)
            return

        if kind == "status":
            set_status(message.get("msg", ""), error=message.get("error", False))
            return

        if kind == "character_resolved":
            character_text.value = message.get("text", character_text.value)
            page.update()
            return

        if kind == "scan_result":
            total = message["total"]
            by_name = message["by_name"]
            by_station = message["by_station"]

            result_holder["total"] = total
            result_holder["by_name"] = by_name
            result_holder["by_station"] = by_station

            name_table.rows = [
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(name)),
                    ft.DataCell(ft.Text(str(data["qty"]))),
                    ft.DataCell(ft.Text(f"{data['volume_each']:.2f}")),
                    ft.DataCell(ft.Text(f"{data['qty'] * data['volume_each']:.2f}")),
                ])
                for name, data in sorted(by_name.items())
            ]

            station_table.rows = [
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(station)),
                    ft.DataCell(ft.Text(
                        str(data.get("jumps")) if data.get("jumps") is not None else "unbekannt"
                    )),
                    ft.DataCell(ft.Text(str(data["qty"]))),
                    ft.DataCell(ft.Text(f"{data['volume']:.2f}")),
                ])
                for station, data in sorted(
                    by_station.items(),
                    key=lambda item: (
                        item[1].get("jumps") is None,
                        item[1].get("jumps") if item[1].get("jumps") is not None else 999999,
                        item[0].lower(),
                    ),
                )
            ]

            total_text.value = f"Gesamtanzahl aller Drohnen: {total}  |  Stationen: {len(by_station)}"

            export_csv_btn.disabled = False
            export_html_btn.disabled = False

            page.update()
            return

    page.pubsub.subscribe(on_scan_message)    

    def do_login(e):
        set_busy(True)

        def worker():
            try:
                auth = auth_holder["auth"] or EveAuthPKCE()
                auth_holder["auth"] = auth

                if auth.has_refresh_token():
                    page.pubsub.send_all({
                        "topic": "login",
                        "kind": "status",
                        "msg": "Vorhandener Tokencache gefunden, pruefe/erneuere Zugang ...",
                        "error": False,
                    })
                else:
                    page.pubsub.send_all({
                        "topic": "login",
                        "kind": "status",
                        "msg": "Kein Tokencache vorhanden, oeffne Login-Seite im Browser ...",
                        "error": False,
                    })

                ensure_authenticated(
                    auth,
                    log=lambda m: page.pubsub.send_all({
                        "topic": "login",
                        "kind": "status",
                        "msg": m,
                        "error": False,
                    }),
                )

                char_id = auth.get_character_id()
                char_name = None
                try:
                    char_name = get_character_name(char_id)
                    auth.set_last_char(char_id, char_name)
                except Exception:
                    pass

                page.pubsub.send_all({
                    "topic": "login",
                    "kind": "login_success",
                    "char_id": char_id,
                    "char_name": char_name,
                })

            except Exception as ex:
                auth_holder["auth"] = None
                page.pubsub.send_all({
                    "topic": "login",
                    "kind": "login_error",
                    "msg": f"Login fehlgeschlagen: {ex}",
                })
            finally:
                page.pubsub.send_all({
                    "topic": "login",
                    "kind": "busy_done",
                })

        threading.Thread(target=worker, daemon=True).start()

    def do_scan(e):
        auth = auth_holder["auth"]
        if auth is None:
            set_status("Bitte zuerst einloggen.", error=True)
            return

        set_busy(True)

        def worker():
            try:
                page.pubsub.send_all({
                    "topic": "scan",
                    "kind": "status",
                    "msg": "Scan gestartet ...",
                    "error": False,
                })

                character_id = auth.get_character_id()
                last_id, last_name = auth.get_last_char()

                if last_id != character_id or not last_name:
                    try:
                        resolved_name = get_character_name(character_id)
                        auth.set_last_char(character_id, resolved_name)
                        page.pubsub.send_all({
                            "topic": "scan",
                            "kind": "character_resolved",
                            "text": f"Angemeldet als {resolved_name} (Character-ID: {character_id})",
                        })
                    except Exception:
                        pass

                total, by_name, by_station = count_drones(
                    character_id, auth, progress=gui_progress_callback
                )

                page.pubsub.send_all({
                    "topic": "scan",
                    "kind": "scan_result",
                    "total": total,
                    "by_name": by_name,
                    "by_station": by_station,
                })

                page.pubsub.send_all({
                    "topic": "scan",
                    "kind": "status",
                    "msg": f"Fertig: {len(by_name)} Drohnentypen, {len(by_station)} Stationen geladen.",
                    "error": False,
                })

            except requests.exceptions.Timeout:
                page.pubsub.send_all({
                    "topic": "scan",
                    "kind": "status",
                    "msg": "EVE-Server antwortet nicht (Zeitueberschreitung). Bitte spaeter erneut versuchen.",
                    "error": True,
                })
            except requests.exceptions.ConnectionError:
                page.pubsub.send_all({
                    "topic": "scan",
                    "kind": "status",
                    "msg": "Keine Verbindung zu EVE Online moeglich. Internet pruefen und erneut versuchen.",
                    "error": True,
                })
            except requests.exceptions.HTTPError as ex:
                status_code = ex.response.status_code if ex.response is not None else "?"
                if status_code == 504:
                    msg = "EVE-Server ueberlastet oder im Neustart (504). Bitte in ein paar Minuten erneut versuchen."
                elif status_code == 503:
                    msg = "EVE-Server aktuell nicht erreichbar (503, evtl. Wartungsarbeiten). Spaeter erneut versuchen."
                elif status_code in (401, 403):
                    msg = "Anmeldung abgelaufen oder ungueltig. Bitte erneut einloggen."
                else:
                    msg = f"EVE-Server-Fehler ({status_code}). Bitte erneut versuchen."

                page.pubsub.send_all({
                    "topic": "scan",
                    "kind": "status",
                    "msg": msg,
                    "error": True,
                })
            except Exception as ex:
                page.pubsub.send_all({
                    "topic": "scan",
                    "kind": "status",
                    "msg": f"Unerwarteter Fehler: {ex}",
                    "error": True,
                })
            finally:
                page.pubsub.send_all({
                    "topic": "scan",
                    "kind": "busy_done",
                })

        threading.Thread(target=worker, daemon=True).start()

    def export_csv(e):
        by_name = result_holder["by_name"]
        if not by_name:
            set_status("Keine Daten zum Exportieren. Bitte zuerst scannen.", error=True)
            page.update()
            return
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Drohnenname", "Anzahl", "Volumen/Stk (m3)", "Gesamtvolumen (m3)"])
        for name, data in sorted(by_name.items()):
            writer.writerow([name, data["qty"], data["volume_each"],
                              round(data["qty"] * data["volume_each"], 2)])
        filename = f"{APP_NAME}_export.csv"
        with open(filename, "w", encoding="utf-8", newline="") as f:
            f.write(buf.getvalue())
        set_status(f"CSV exportiert: {filename}")
        page.update()

    def export_html(e):
        total = result_holder["total"]
        by_name = result_holder["by_name"]
        by_station = result_holder["by_station"]
        if not by_name:
            set_status("Keine Daten zum Exportieren. Bitte zuerst scannen.", error=True)
            page.update()
            return
        path = build_html(total, by_name, by_station, REPORT_FILENAME_DEFAULT)
        set_status(f"HTML-Bericht exportiert: {path}")
        page.update()

    login_btn.on_click = do_login
    scan_btn.on_click = do_scan
    export_csv_btn.on_click = export_csv
    export_html_btn.on_click = export_html

    def check_existing_session():
        # Rein lokale Pruefung ohne Netzwerkzugriff: Tokencache + [last_char]-Rubrik werden gelesen.
        # Kein Refresh, keine Namensaufloesung per API beim Start - das passiert erst bei Bedarf
        # (Login-Klick bzw. Scan), damit der Start sofort reagiert.
        try:
            auth = EveAuthPKCE()
            if not auth.has_refresh_token():
                character_text.value = "Nicht angemeldet."
                page.update()
                return

            auth_holder["auth"] = auth
            last_id, last_name = auth.get_last_char()

            # Falls ein noch gueltiger Access-Token im Cache liegt, koennen wir die ID lokal aus dem
            # JWT lesen (kein Netzwerk) und mit [last_char] abgleichen.
            jwt_char_id = None
            if auth._access_token:
                try:
                    jwt_char_id = auth.get_character_id()
                except Exception:
                    jwt_char_id = None

            if jwt_char_id is not None and last_id is not None and jwt_char_id != last_id:
                # ID im Token passt nicht mehr zu [last_char] -> veralteten Eintrag verwerfen
                auth.clear_last_char()
                last_id, last_name = None, None

            if last_id is not None and last_name:
                character_text.value = f"Angemeldet als {last_name} (Character-ID: {last_id})"
            elif jwt_char_id is not None:
                character_text.value = f"Angemeldet (Character-ID: {jwt_char_id})"
            else:
                character_text.value = "Tokencache vorhanden. Bitte einloggen zum Bestaetigen."

            scan_btn.disabled = False
        except Exception:
            character_text.value = "Nicht angemeldet."
        page.update()

    check_existing_session()  # synchron und lokal, kein Thread noetig - dauert nur Millisekunden

    page.add(
        ft.Row(
            [
                ft.Text(APP_TAGLINE, size=22, weight=ft.FontWeight.BOLD),
                ft.Text(f"GUI v{GUI_VERSION}", size=12, color=ft.Colors.GREY_500),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        ft.Divider(),
        ft.Row([login_btn, scan_btn, export_csv_btn, export_html_btn], wrap=True),
        character_text,
        ft.Column([ft.Row([status_text], alignment=ft.MainAxisAlignment.START), progress_column]),
        ft.Divider(),
        total_text,
        ft.SafeArea(expand=True, content=ft.Container(content=tabs, expand=True)),
    )


if __name__ == "__main__":
    ft.run(main)
