"""Pipeline de datos de PITLANE — todo automatizado en cada build.

Fuentes:
  - Jolpica F1 (sucesora de la API Ergast): calendario, clasificaciones, resultados.
  - Wikipedia REST: retrato y bio corta de cada piloto.
  - RSS de medios especializados: titulares de actualidad.

Salida: src/data/site.json (+ imágenes descargadas en assets/).
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

import time
import urllib.error
import urllib.request

IMAGE_TTL_DAYS = int(os.environ.get("PITLANE_IMAGE_TTL", "10"))
SKIP_IMAGES = os.environ.get("PITLANE_SKIP_IMAGES") == "1"  # modo rápido: solo datos

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "src" / "data"
ASSETS = ROOT / "assets"
def detect_season() -> int:
    """Temporada activa sin intervención: el año en curso si ya hay calendario,
    el anterior en pretemporada o si la API aún no lo publica."""
    forced = os.environ.get("PITLANE_SEASON")
    if forced:
        return int(forced)
    year = date.today().year
    for candidate in (year, year - 1):
        try:
            body = get_json(f"{API}/{candidate}.json?limit=100")
            if body["MRData"]["RaceTable"]["Races"]:
                return candidate
        except Exception:
            continue
    return year


SEASON = 0  # se resuelve al arrancar, con detección automática
API = "https://api.jolpi.ca/ergast/f1"

UA = {"User-Agent": "PitlaneBot/1.0 (sitio informativo no oficial de F1)"}

GP_ES = {
    "Australian": "Australia", "Chinese": "China", "Japanese": "Japón", "Bahrain": "Baréin",
    "Saudi Arabian": "Arabia Saudí", "Miami": "Miami", "Canadian": "Canadá", "Monaco": "Mónaco",
    "Barcelona": "Barcelona", "Spanish": "España", "Austrian": "Austria", "British": "Gran Bretaña",
    "Belgian": "Bélgica", "Hungarian": "Hungría", "Dutch": "Países Bajos", "Italian": "Italia",
    "Azerbaijan": "Azerbaiyán", "Singapore": "Singapur", "United States": "Estados Unidos",
    "Mexico City": "Ciudad de México", "Mexican": "México", "Brazilian": "Brasil",
    "São Paulo": "Sao Paulo", "Las Vegas": "Las Vegas", "Qatar": "Catar", "Abu Dhabi": "Abu Dabi",
    "Emilia-Romagna": "Emilia-Romaña", "Portuguese": "Portugal", "Turkish": "Turquía",
    "Russian": "Rusia", "Eifel": "Eifel", "Styrian": "Estiria", "Tuscan": "Toscana",
}

NATIONALITY_ES = {
    "Italian": "italiano", "British": "británico", "German": "alemán", "French": "francés",
    "Spanish": "español", "Dutch": "neerlandés", "Mexican": "mexicano", "Brazilian": "brasileño",
    "Australian": "australiano", "Canadian": "canadiense", "Japanese": "japonés", "Chinese": "chino",
    "Monegasque": "monegasco", "Austrian": "austriaco", "Belgian": "belga", "Hungarian": "húngaro",
    "Azerbaijani": "azerbaiyano", "Singaporean": "singapurense", "Thai": "tailandés",
    "Finnish": "finlandés", "Danish": "danés", "Swiss": "suizo", "Swedish": "sueco",
    "New Zealander": "neozelandés", "Argentine": "argentino", "American": "estadounidense",
    "Portuguese": "portugués", "Polish": "polaco", "Russian": "ruso", "South African": "sudafricano",
    "Turkish": "turco", "Saudi": "saudí", "Bahraini": "bareiní",
}

COUNTRY_ES = {
    "Australia": "Australia", "China": "China", "Japan": "Japón", "USA": "Estados Unidos",
    "Canada": "Canadá", "Monaco": "Mónaco", "Spain": "España", "Austria": "Austria",
    "UK": "Reino Unido", "Belgium": "Bélgica", "Hungary": "Hungría", "Netherlands": "Países Bajos",
    "Italy": "Italia", "Azerbaijan": "Azerbaiyán", "Malaysia": "Malasia", "Singapore": "Singapur",
    "Mexico": "México", "Brazil": "Brasil", "Qatar": "Catar", "UAE": "Emiratos Árabes Unidos",
}

FLAG = {
    "Australia": "🇦🇺", "China": "🇨🇳", "Japan": "🇯🇵", "USA": "🇺🇸", "Canada": "🇨🇦",
    "Monaco": "🇲🇨", "Spain": "🇪🇸", "Austria": "🇦🇹", "UK": "🇬🇧", "Belgium": "🇧🇪",
    "Hungary": "🇭🇺", "Netherlands": "🇳🇱", "Italy": "🇮🇹", "Azerbaijan": "🇦🇿",
    "Malaysia": "🇲🇾", "Singapore": "🇸🇬", "Mexico": "🇲🇽", "Brazil": "🇧🇷",
    "Qatar": "🇶🇦", "UAE": "🇦🇪", "Germany": "🇩🇪", "France": "🇫🇷", "Saudi Arabia": "🇸🇦",
    "Bahrain": "🇧🇭", "Portugal": "🇵🇹", "Turkey": "🇹🇷", "South Africa": "🇿🇦",
    "Argentina": "🇦🇷", "Finland": "🇫🇮", "New Zealand": "🇳🇿", "Denmark": "🇩🇰",
    "Switzerland": "🇨🇭", "Sweden": "🇸🇪", "Poland": "🇵🇱", "Russia": "🇷🇺",
}

MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MONTHS_LONG = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"]


def nrm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def get(url: str, timeout: int = 45, retries: int = 4) -> bytes:
    """GET con reintento y espera cuando Wikimedia responde 429."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                wait = int(e.headers.get("Retry-After") or 0) or 8 * (attempt + 1)
                time.sleep(min(wait, 30))
                continue
            raise
    raise last  # type: ignore[misc]


def get_json(url: str) -> dict:
    if "wikipedia.org" in url:
        time.sleep(0.9)
    return json.loads(get(url).decode("utf-8"))


def slug(s: str) -> str:
    s = nrm(s).replace("ø", "o")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


# --------------------------------------------------------------------------- API
def fetch_api() -> dict:
    cal = get_json(f"{API}/{SEASON}.json?limit=100")["MRData"]["RaceTable"]["Races"]
    drivers = get_json(f"{API}/{SEASON}/driverstandings.json?limit=100")["MRData"][
        "StandingsTable"]["StandingsLists"][0]
    teams = get_json(f"{API}/{SEASON}/constructorstandings.json?limit=100")["MRData"][
        "StandingsTable"]["StandingsLists"][0]
    # la consulta global recorta a 100 registros (~5 carreras), así que se pide ronda a ronda
    qualifying, sprint = [], []
    for r in cal:
        for kind, bucket in (("qualifying", qualifying), ("sprint", sprint)):
            try:
                body = get_json(f"{API}/{SEASON}/{r['round']}/{kind}.json")
                races = body["MRData"]["RaceTable"]["Races"]
                if races and races[0].get("QualifyingResults" if kind == "qualifying" else "SprintResults"):
                    bucket.append(races[0])
            except Exception:
                continue

    results = []
    for r in cal:
        try:
            body = get_json(f"{API}/{SEASON}/{r['round']}/results.json")
            races = body["MRData"]["RaceTable"]["Races"]
            if races and races[0].get("Results"):
                results.append(races[0])
        except Exception:
            continue
    return {"calendar": cal, "drivers": drivers, "teams": teams, "results": results,
            "qualifying": qualifying, "sprint": sprint}


SESSION_FIELDS = [
    ("FirstPractice", "Libres 1", "FP1"),
    ("SecondPractice", "Libres 2", "FP2"),
    ("ThirdPractice", "Libres 3", "FP3"),
    ("SprintQualifying", "Clasificación sprint", "SQ"),
    ("SprintShootout", "Clasificación sprint", "SQ"),
    ("Sprint", "Sprint", "SPR"),
    ("Qualifying", "Clasificación", "Q"),
]

try:  # zona horaria real si hay base de datos IANA
    from zoneinfo import ZoneInfo
    _MADRID = ZoneInfo("Europe/Madrid")
except Exception:  # respaldo: España es UTC+1 en invierno y UTC+2 en verano
    _MADRID = None


def to_madrid(dt):
    """Hora peninsular a partir de un datetime UTC."""
    from datetime import timedelta, timezone
    if _MADRID is not None:
        return dt.astimezone(_MADRID)
    # regla de horario de verano de la UE: último domingo de marzo a último domingo de octubre
    def last_sunday(y, m):
        d = datetime(y, m + 1, 1) - timedelta(days=1)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    local = dt.replace(tzinfo=timezone.utc) + timedelta(hours=1)
    start, end = last_sunday(local.year, 3), last_sunday(local.year, 10)
    if start <= local.replace(tzinfo=None) < end:
        local += timedelta(hours=1)
    return local


def parse_session(node: dict) -> dict | None:
    if not node or "date" not in node:
        return None
    raw = f"{node['date']}T{node.get('time', '00:00:00Z').rstrip('Z')}"
    try:
        utc = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    except Exception:
        return None
    mad = to_madrid(utc)
    return {
        "utc": utc.isoformat(),
        "iso": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": utc.date().isoformat(),
        "day": f"{["lun", "mar", "mié", "jue", "vie", "sáb", "dom"][mad.weekday()]} {mad.day}",
        "time_es": mad.strftime("%H:%M"),
        "time_utc": utc.strftime("%H:%M"),
    }


def gp_name(race: dict) -> str:
    base = race["raceName"].replace(" Grand Prix", "").strip()
    es = GP_ES.get(base, base)
    if "in Malaysia" in race["raceName"]:
        es = "Malasia"
    return f"GP de {es}"


def build_calendar(races: list, today: date) -> list:
    out = []
    for r in races:
        d = date.fromisoformat(r["date"])
        loc = r["Circuit"]["Location"]
        out.append({
            "round": int(r["round"]),
            "name": gp_name(r),
            "official": r["raceName"],
            "circuit": r["Circuit"]["circuitName"],
            "circuit_id": r["Circuit"]["circuitId"],
            "locality": loc["locality"],
            "country": loc["country"],
            "country_es": COUNTRY_ES.get(loc["country"], loc["country"]),
            "flag": FLAG.get(loc["country"], "🏁"),
            "date": r["date"],
            "date_human": f"{d.day} {MONTHS[d.month - 1]} {d.year}",
            "date_long": f"{d.day} de {MONTHS_LONG[d.month - 1]} de {d.year}",
            "weekday": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][d.weekday()],
            "done": d < today,
            "is_next": False,
            "winner": None,
            "sessions": [],
        })
    return out


def attach_results(calendar: list, results: list) -> None:
    """Clasificación completa de cada carrera disputada."""
    by_round = {int(r["round"]): r for r in results}
    for race in calendar:
        raw = by_round.get(race["round"])
        if not raw:
            continue
        rows = []
        for res in raw.get("Results", []):
            drv = res["Driver"]
            tm = res["Constructor"]
            fl = res.get("FastestLap") or {}
            rows.append({
                "pos": res["positionText"],
                "pos_num": int(res["position"]) if res["position"].isdigit() else 99,
                "driver": f"{drv['givenName']} {drv['familyName']}",
                "driver_id": drv["driverId"],
                "code": drv.get("code", ""),
                "team": tm["name"],
                "team_id": tm["constructorId"],
                "grid": int(res["grid"]) if str(res["grid"]).isdigit() else 0,
                "laps": res.get("laps", ""),
                "time": (res.get("Time") or {}).get("time", "") or res.get("status", ""),
                "status": res.get("status", ""),
                "points": int(float(res.get("points", 0))),
                "fastest": (fl.get("Time") or {}).get("time", ""),
                "fastest_rank": fl.get("rank", ""),
            })
        race["results"] = rows
        race["finished"] = len(rows)


def attach_qualifying(calendar: list, raw: list) -> None:
    """Tiempos de la clasificación (Q1/Q2/Q3) y del sprint si lo hay."""
    by_round = {int(r["round"]): r for r in raw}
    for race in calendar:
        item = by_round.get(race["round"])
        if not item:
            continue
        if item.get("QualifyingResults"):
            race["qualifying"] = [{
                "pos": q["position"],
                "driver": f"{q['Driver']['givenName']} {q['Driver']['familyName']}",
                "driver_id": q["Driver"]["driverId"],
                "code": q["Driver"].get("code", ""),
                "team": q["Constructor"]["name"],
                "team_id": q["Constructor"]["constructorId"],
                "q1": (q.get("Q1") or ""), "q2": (q.get("Q2") or ""), "q3": (q.get("Q3") or ""),
            } for q in item["QualifyingResults"]]
        if item.get("SprintResults"):
            race["sprint"] = [{
                "pos": x["positionText"],
                "driver": f"{x['Driver']['givenName']} {x['Driver']['familyName']}",
                "driver_id": x["Driver"]["driverId"],
                "code": x["Driver"].get("code", ""),
                "team": x["Constructor"]["name"],
                "team_id": x["Constructor"]["constructorId"],
                "points": int(float(x.get("points", 0))),
                "time": (x.get("Time") or {}).get("time", "") or x.get("status", ""),
            } for x in item["SprintResults"]]


def attach_sessions(calendar: list, raw_races: list) -> None:
    """Horarios de todas las sesiones del fin de semana."""
    for race, raw in zip(calendar, raw_races):
        items = []
        for field, label, code in SESSION_FIELDS:
            s_ = parse_session(raw.get(field))
            if s_:
                items.append({"name": label, "code": code, **s_})
        race_s = parse_session({"date": raw["date"], "time": raw.get("time", "00:00:00Z")})
        if race_s:
            items.append({"name": "Carrera", "code": "RACE", **race_s})
        items.sort(key=lambda x: x["utc"])
        race["sessions"] = items


def attach_winners(calendar: list, results: list) -> None:
    by_round = {int(r["round"]): r for r in results}
    for c in calendar:
        r = by_round.get(c["round"])
        if not r or not r.get("Results"):
            continue
        res = r["Results"]
        c["winner"] = res[0]["Driver"]["familyName"]
        c["winner_team"] = res[0]["Constructor"]["constructorId"]
        c["podium"] = [
            {"pos": x["position"], "name": x["Driver"]["familyName"],
             "team": x["Constructor"]["constructorId"], "code": x["Driver"].get("code", "")}
            for x in res[:3]
        ]
        fl = res[0].get("FastestLap")
        c["fastest_lap"] = fl["Time"]["time"] if fl else None


def circuit_history(circuit_id: str) -> dict:
    """Palmarés del circuito: victorias por piloto y equipo, ediciones y últimos ganadores."""
    try:
        body = get_json(f"{API}/circuits/{circuit_id}/results/1.json?limit=100")
        races = body["MRData"]["RaceTable"]["Races"]
    except Exception:
        return {}
    if not races:
        return {}

    by_team, by_driver, winners = {}, {}, []
    for r in races:
        res = r["Results"][0]
        team = res["Constructor"]["name"]
        team_id = res["Constructor"]["constructorId"]
        drv = f"{res['Driver']['givenName']} {res['Driver']['familyName']}"
        row = by_team.setdefault(team, {"wins": 0, "id": team_id})
        row["wins"] += 1
        by_driver[drv] = by_driver.get(drv, 0) + 1
        winners.append({"year": r["season"], "gp": r["raceName"], "driver": drv,
                        "team": team, "team_id": team_id})

    winners.sort(key=lambda w: w["year"], reverse=True)
    teams = sorted(({"name": n, "wins": v["wins"], "id": v["id"]} for n, v in by_team.items()),
                   key=lambda t: -t["wins"])[:5]
    top_driver = max(by_driver.items(), key=lambda kv: kv[1])
    drivers_top = [{"name": n, "wins": w}
                   for n, w in sorted(by_driver.items(), key=lambda kv: -kv[1])[:5]]
    spec = CIRCUIT_SPECS.get(circuit_id)
    return {
        "editions": len(races),
        "first_year": races[0]["season"],
        "last_year": races[-1]["season"],
        "winners": winners[:8],
        "teams": teams,
        "drivers": drivers_top,
        "distinct_winners": len(by_driver),
        "max_wins": teams[0]["wins"] if teams else 1,
        "max_driver_wins": drivers_top[0]["wins"] if drivers_top else 1,
        "top_team": {"name": teams[0]["name"], "wins": teams[0]["wins"]} if teams else None,
        "top_driver": {"name": top_driver[0], "wins": top_driver[1]},
        "length_km": spec[0] if spec else None,
        "laps": spec[1] if spec else None,
    }


def circuit_blurb(name: str, locality: str, country: str, history: dict, gp: str) -> str:
    """Texto propio, corto y factual: nada de párrafos de enciclopedia."""
    if not history:
        return f"{name}, en {locality} ({country}). Sede del {gp}."
    n = history["editions"]
    w = history["distinct_winners"]
    plural = lambda k, one, many: one if k == 1 else f"{k} {many}"
    parts = [
        f"{name}, en {locality} ({country}). Ha acogido {plural(n, 'una edición', str(n) + ' ediciones')} "
        f"del mundial desde {history['first_year']}, con "
        f"{plural(w, 'un solo ganador', 'ganadores distintos')}."
        if n == 1 else
        f"{name}, en {locality} ({country}). Ha acogido {n} ediciones del mundial "
        f"desde {history['first_year']}, con {w} ganadores distintos.",
    ]
    if history.get("top_team"):
        tw = history["top_team"]["wins"]
        parts.append(f"El equipo más laureado es {history['top_team']['name']}, "
                     f"con {plural(tw, 'una victoria', 'victorias')}.")
    if history.get("top_driver") and history["top_driver"]["wins"] > 1:
        parts.append(f"El piloto con más triunfos es {history['top_driver']['name']} "
                     f"({history['top_driver']['wins']}).")
    if history.get("length_km"):
        parts.append(f"El trazado mide {history['length_km']:.3f} km y la carrera se disputa "
                     f"a {history['laps']} vueltas.")
    return " ".join(parts)


def enrich_circuits(raw_races: list, calendar: list) -> list:
    """Ficha de cada circuito con foto y descripción de Wikipedia."""
    out = []
    for raw, race in zip(raw_races, calendar):
        c = raw["Circuit"]
        cid = c["circuitId"]
        title = c["url"].rsplit("/", 1)[-1]
        raw_name = raw["raceName"].replace(" Grand Prix", "").strip()
        hist = circuit_history(cid)
        out.append({
            "id": cid,
            "name": c["circuitName"],
            "locality": c["Location"]["locality"],
            "country": c["Location"]["country"],
            "country_es": COUNTRY_ES.get(c["Location"]["country"], c["Location"]["country"]),
            "flag": race["flag"],
            "wiki": title,
            "photo": circuit_photo({"id": cid, "name": c["circuitName"],
                                    "locality": c["Location"]["locality"],
                                    "gp": GP_ES.get(raw_name, raw_name),
                                    "wiki": title}),
            "about": circuit_blurb(c["circuitName"], c["Location"]["locality"],
                                   COUNTRY_ES.get(c["Location"]["country"], c["Location"]["country"]),
                                   hist, race["name"]),
            "round": race["round"],
            "gp": race["name"],
            "date": race["date"],
            "date_human": race["date_human"],
            "weekday": race["weekday"],
            "date_long": race["date_long"],
            "done": race["done"],
            "is_next": race["is_next"],
            "winner": race.get("winner"),
            "history": hist,
        })
    return out


def team_head_to_head(drivers: list, team_id: str) -> list:
    rows = [d for d in drivers if d["team"] and d["team"]["id"] == team_id]
    rows.sort(key=lambda d: -d["points"])
    return rows


def build_teams(api: dict, calendar: list) -> list:
    cons = api["teams"]["ConstructorStandings"]
    drivers = api["drivers"]["DriverStandings"]
    out = []
    for c in cons:
        cid = c["Constructor"]["constructorId"]
        roster = []
        for d in drivers:
            ids = [x["constructorId"] for x in d["Constructors"]]
            if cid in ids:
                roster.append({
                    "id": d["Driver"]["driverId"],
                    "name": f"{d['Driver']['givenName']} {d['Driver']['familyName']}",
                    "last": d["Driver"]["familyName"],
                    "code": d["Driver"].get("code") or d["Driver"]["familyName"][:3].upper(),
                    "num": d["Driver"].get("permanentNumber") or "",
                    "pos": int(d["position"]),
                    "points": int(float(d["points"])),
                    "wins": int(d["wins"]),
                })
        roster.sort(key=lambda x: x["pos"])
        out.append({
            "id": cid,
            "name": c["Constructor"]["name"],
            "nationality": c["Constructor"].get("nationality", ""),
            "pos": int(c["position"]),
            "points": int(float(c["points"])),
            "wins": int(c["wins"]),
            "drivers": roster,
        })
    return out


def prev_seasons(team_ids: list, years=(2024, 2025)) -> dict:
    """Posición y puntos de cada escudería en las dos temporadas anteriores."""
    out = {tid: [] for tid in team_ids}
    for y in years:
        try:
            d = get_json(f"{API}/{y}/constructorstandings.json?limit=100")
            rows = d["MRData"]["StandingsTable"]["StandingsLists"][0]["ConstructorStandings"]
        except Exception:
            continue
        for r in rows:
            cid = r["Constructor"]["constructorId"]
            if cid in out:
                out[cid].append({"season": y, "pos": int(r["position"]),
                                 "points": int(float(r["points"]))})
    return out


PTS_DRIVER = 25      # puntos máximos de un piloto por carrera
PTS_TEAM = 43        # 1º y 2º de un equipo en la misma carrera


def championship_state(teams: list, drivers: list, rounds_done: int, total_races: int) -> dict:
    """¿Está decidido el título? Si no, cuánto falta.

    Regla simple y honesta: si la ventaja del líder supera todo lo que puede sumar
    el segundo en las carreras que quedan, el título está matemáticamente cerrado.
    """
    remaining = max(0, total_races - rounds_done)
    out = {}
    for kind, rows, per_race in (("drivers", drivers, PTS_DRIVER), ("constructors", teams, PTS_TEAM)):
        if not rows:
            continue
        first, second = rows[0], (rows[1] if len(rows) > 1 else None)
        gap = first["points"] - (second["points"] if second else 0)
        max_left = remaining * per_race
        decided = remaining == 0 or gap > max_left
        out[kind] = {
            "id": first["id"],
            "name": first.get("full") or first.get("name"),
            "points": first["points"],
            "team": (first.get("team") or {}).get("id") if kind == "drivers" else first["id"],
            "gap": gap,
            "remaining": remaining,
            "max_left": max_left,
            "decided": decided,
            "rival": (second.get("full") or second.get("name")) if second else None,
            "rival_points": second["points"] if second else 0,
        }
    return out


def build_drivers(api: dict, teams: list) -> list:
    team_of = {}
    for t in teams:
        for d in t["drivers"]:
            team_of[d["id"]] = t
    out = []
    for d in api["drivers"]["DriverStandings"]:
        drv = d["Driver"]
        did = drv["driverId"]
        t = team_of.get(did)
        dob = date.fromisoformat(drv["dateOfBirth"])
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        out.append({
            "id": did,
            "full": f"{drv['givenName']} {drv['familyName']}",
            "first": drv["givenName"],
            "last": drv["familyName"],
            "code": drv.get("code") or drv["familyName"][:3].upper(),
            "num": drv.get("permanentNumber") or "",
            "nationality": drv.get("nationality", ""),
            "flag": FLAG.get(drv.get("nationality", ""), "🏁"),
            "dob": drv["dateOfBirth"],
            "age": age,
            "wiki": drv["url"].rsplit("/", 1)[-1],
            "pos": int(d["position"]),
            "points": int(float(d["points"])),
            "wins": int(d["wins"]),
            "team": {"id": t["id"], "name": t["name"], "pos": t["pos"]} if t else None,
        })
    return out



def commons_search(query: str, limit: int = 12) -> list:
    """Búsqueda en Wikimedia Commons: devuelve (título, url_1200) de fotos apaisadas."""
    from urllib.parse import quote as q
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search"
           f"&gsrsearch={q('filetype:bitmap ' + query)}&gsrlimit={limit}&gsrnamespace=6"
           "&prop=imageinfo&iiprop=url|size&iiurlwidth=1400")
    try:
        data = get_json(url)
    except Exception:
        return []
    out = []
    for pg in ((data.get("query") or {}).get("pages") or {}).values():
        ii = (pg.get("imageinfo") or [{}])[0]
        w, h = ii.get("width", 0), ii.get("height", 0)
        if not w or not h or w < 1100 or w / h < 1.2:
            continue
        title = (pg.get("title") or "").lower()
        if BAD_IMG.search(title):
            continue
        url_ = ii.get("thumburl") or ii.get("url")
        if url_:
            out.append((title, url_))
    return out


def best_from_queries(queries: list, dest: pathlib.Path, min_bright: int = 42) -> bool:
    """Prueba varias búsquedas y guarda la primera foto válida y luminosa."""
    if SKIP_IMAGES:
        return dest.exists() and dest.stat().st_size > 15000
    dest.parent.mkdir(parents=True, exist_ok=True)
    probe = dest.with_suffix(".tmp.webp")
    for query in queries:
        for _title, url in commons_search(query, limit=8)[:2]:
            try:
                img = get(url, timeout=60)
            except Exception:
                continue
            if len(img) < 15000:
                continue
            probe.write_bytes(img)
            if is_photo(probe) and brightness(probe) >= min_bright:
                probe.replace(dest)
                return True
    probe.unlink(missing_ok=True)
    return False


def circuit_photo(c: dict) -> str | None:
    """Foto aérea del trazado; si no hay, la imagen de la ficha de Wikipedia."""
    slug = c["id"]
    dest = ASSETS / "circuits" / f"{slug}.jpg"
    if fresh(dest) and is_photo(dest) and brightness(dest) >= 42:
        return f"assets/circuits/{slug}.jpg"
    commands = [f"{c['name']} aerial", f"{c['name']} circuit aerial",
                f"{c['locality']} circuit aerial"]
    if best_from_queries(commands, dest):
        return f"assets/circuits/{slug}.jpg"
    return wiki_best_photo([c["wiki"], f"{c['locality']}"], slug, "circuits")


TEAM_CAR_FILES = {
    "ferrari": "2026 Bahrain GP - Ferrari - Lewis Hamilton - Qualifying.jpg",
    "mercedes": "2026 Chinese GP - Mercedes - George Russell - Qualifying.jpg",
    "red_bull": "2026 Bahrain GP - Red Bull - Isack Hadjar - Race.jpg",
    "mclaren": "2026 Bahrain GP - McLaren - Oscar Piastri - FP1.jpg",
    "aston_martin": "2026 Bahrain GP - Aston Martin - Fernando Alonso - FP2.jpg",
    "alpine": "2026 Chinese GP - Alpine - Pierre Gasly - Qualifying.jpg",
    "haas": "2026 Bahrain GP - Haas - Esteban Ocon - Race.jpg",
    "audi": "2026 Chinese GP - Audi - Nico Hulkenberg - Qualifying.jpg",
    "williams": "2026 Chinese GP - Williams - Alex Albon - Qualifying.jpg",
    "rb": "2026 Chinese GP - Racing Bulls - Arvid Lindblad - Qualifying.jpg",
    "cadillac": "2026 Chinese GP - Cadillac - Sergio Perez - FP1.jpg",
}


def pinned_car_photo(slug_name: str) -> str | None:
    """Coche de equipo desde un fichero concreto de Commons, ya revisado a ojo.

    Evita que la búsqueda automática elija museos, coches históricos o primeros
    planos de patrocinadores. Si el fichero desaparece, se cae a la búsqueda.
    """
    from urllib.parse import quote as q
    name = TEAM_CAR_FILES.get(slug_name)
    if not name:
        return None
    dest = ASSETS / "teams" / f"{slug_name}-car.jpg"
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + q(name, safe="") + "?width=1600"
    probe = dest.with_suffix(".tmp.jpg")
    try:
        img = get(url, timeout=90)
        if len(img) < 15000:
            return None
        probe.write_bytes(img)
        if is_photo(probe) and brightness(probe) >= 42:
            probe.replace(dest)
            return f"assets/teams/{slug_name}-car.jpg"
    except Exception:
        pass
    finally:
        probe.unlink(missing_ok=True)
    return None


def team_car_photo(t: dict, display: str) -> str | None:
    """Monoplaza en pista, con la temporada en curso."""
    slug = t["id"]
    dest = ASSETS / "teams" / f"{slug}-car.jpg"
    if fresh(dest, 12000) and is_photo(dest) and brightness(dest) >= 42:
        return f"assets/teams/{slug}-car.jpg"
    pinned = pinned_car_photo(slug)
    if pinned:
        return pinned
    queries = [f"{display} {SEASON} Grand Prix", f"{display} Formula One {SEASON}"]
    if best_from_queries(queries, dest):
        return f"assets/teams/{slug}-car.jpg"
    return None

def commons_car_photo(team_name: str, slug_name: str) -> str | None:
    """Busca en Wikimedia Commons una foto del coche del equipo y se queda con la mejor."""
    from urllib.parse import quote as q
    dest = ASSETS / "teams" / f"{slug_name}-car.jpg"
    if fresh(dest, 12000) and is_photo(dest):
        return f"assets/teams/{slug_name}-car.jpg"
    terms = f"{team_name} Formula One {SEASON}"
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search"
           f"&gsrsearch={q('filetype:bitmap ' + terms)}&gsrlimit=10&gsrnamespace=6"
           "&prop=imageinfo&iiprop=url|size&iiurlwidth=1600")
    try:
        data = get_json(url)
    except Exception:
        return None
    pages = (data.get("query") or {}).get("pages") or {}
    candidates = []
    for pg in pages.values():
        ii = (pg.get("imageinfo") or [{}])[0]
        w, h = ii.get("width", 0), ii.get("height", 0)
        if not w or not h or w < 1200:
            continue
        if w / h < 1.25:          # interesan fotos apaisadas
            continue
        title = (pg.get("title") or "").lower()
        # solo monoplazas en pista: fuera safety cars, coches de calle y eventos
        if any(k in title for k in ("safety", "medical", "vantage", "dbx", "road", "vulcan", "logo")):
            continue
        if not any(k in title for k in ("formula", "grand prix", "gp")):
            continue
        if not usable_image(ii.get("url", "")):
            continue
        url = ii.get("thumburl") or ii.get("url")
        if url:
            candidates.append(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    probe = dest.with_suffix(".tmp.jpg")
    for url in candidates[:4]:
        try:
            img = get(url, timeout=60)
        except Exception:
            continue
        if len(img) < 12000:
            continue
        probe.write_bytes(img)
        # ni mapas ni fotos nocturnas: la cabecera necesita una imagen legible
        if is_photo(probe) and brightness(probe) >= 42:
            probe.replace(dest)
            return f"assets/teams/{slug_name}-car.jpg"
    probe.unlink(missing_ok=True)
    return None


# Títulos extra de Wikipedia para circuitos cuya página solo ofrece mapas.
CIRCUIT_SPECS = {
    "madring": (5.416, 57),
    "albert_park": (5.278, 58), "shanghai": (5.451, 56), "suzuka": (5.807, 53),
    "miami": (5.412, 57), "villeneuve": (4.361, 70), "monaco": (3.337, 78),
    "catalunya": (4.657, 66), "red_bull_ring": (4.318, 71), "silverstone": (5.891, 52),
    "spa": (7.004, 44), "hungaroring": (4.381, 70), "zandvoort": (4.259, 72),
    "monza": (5.793, 53), "baku": (6.003, 51), "sepang": (5.543, 56),
    "marina_bay": (4.940, 62), "americas": (5.513, 56), "rodriguez": (4.304, 71),
    "interlagos": (4.309, 71), "vegas": (6.201, 50), "losail": (5.419, 57),
    "yas_marina": (5.281, 58),
}

CIRCUIT_FALLBACK = {
    "marina_bay": ["Marina Bay Sands", "Singapore"],
    "americas": ["Austin, Texas", "Austin"],
    "rodriguez": ["Autódromo Hermanos Rodríguez", "Mexico City"],
    "monza": ["Monza", "Autodromo Nazionale Monza"],
    "hungaroring": ["Mogyoród", "Hungaroring"],
}

DISPLAY = {
    "ferrari": "Ferrari", "mercedes": "Mercedes", "red_bull": "Red Bull Racing",
    "mclaren": "McLaren", "aston_martin": "Aston Martin", "alpine": "Alpine",
    "haas": "Haas", "audi": "Audi", "williams": "Williams", "rb": "Racing Bulls",
    "cadillac": "Cadillac",
}

TEAM_WIKI = {
    "ferrari": "Scuderia Ferrari",
    "mercedes": "Mercedes-Benz in Formula One",
    "red_bull": "Red Bull Racing",
    "mclaren": "McLaren",
    "aston_martin": "Aston Martin in Formula One",
    "alpine": "Alpine F1 Team",
    "haas": "Haas F1 Team",
    "audi": "Audi in Formula One",
    "williams": "Williams Grand Prix Engineering",
    "rb": "Racing Bulls",
    "cadillac": "Cadillac Formula One Team",
}

# ---------------------------------------------------------------------- imágenes
def wiki_ref(title: str) -> str:
    """Título listo para la URL de la API.

    La API de Jolpica ya devuelve algunos títulos codificados (Nico_H%C3%BClkenberg);
    volver a codificarlos daba 404 y esos pilotos se quedaban sin foto ni bio.
    """
    t = (title or "").replace(" ", "_")
    return t if "%" in t else quote(t)


def driver_photo(wiki_title: str, did: str) -> str | None:
    dest = ASSETS / "drivers" / f"{did}.jpg"
    if SKIP_IMAGES:
        return f"assets/drivers/{did}.jpg" if dest.exists() else None
    if fresh(dest):
        return f"assets/drivers/{did}.jpg"
    try:
        data = get_json(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + wiki_ref(wiki_title)
        )
        src = (data.get("thumbnail") or {}).get("source")
        if src and not usable_image(src):
            src = None
        if not src:
            # sin miniatura válida en el resumen: se busca en la lista de medios de la página
            media = get_json(
                "https://en.wikipedia.org/api/rest_v1/page/media-list/" + wiki_ref(wiki_title)
            )
            for item in media.get("items", []):
                if item.get("type") != "image" or not item.get("srcset"):
                    continue
                cand = item["srcset"][0]["src"]
                if not usable_image(cand):
                    continue
                src = "https:" + cand if cand.startswith("//") else cand
                break
        if not src:
            return None
        # Wikimedia solo sirve una lista cerrada de anchos. Se pide el mayor
        # disponible: 500 px se veía blando en la cabecera de la ficha.
        no_q = src.split("?")[0]
        candidates = [re.sub(r"/\d+px-", f"/{w}px-", no_q) for w in (960, 800, 640, 500, 330)] + [no_q]
        dest.parent.mkdir(parents=True, exist_ok=True)
        for cand in candidates:
            try:
                img = get(cand, timeout=40)
            except Exception:
                continue
            if len(img) > 6000:
                dest.write_bytes(img)
                return f"assets/drivers/{did}.jpg"
        return None
    except Exception:
        return None


def driver_blurb(d: dict) -> str:
    """Ficha redactada con los datos del campeonato, sin copiar de ninguna enciclopedia."""
    team = d["team"]["name"] if d.get("team") else "la Fórmula 1"
    ordinals = {1: "líder", 2: "segundo", 3: "tercero", 4: "cuarto", 5: "quinto"}
    place = ordinals.get(d["pos"], f"{d['pos']}º")
    nat = NATIONALITY_ES.get(d["nationality"], d["nationality"]).lower()
    base = (f"{d['full']} ({nat}, {d['age']} años) pilota para {team} "
            f"en la temporada {SEASON}. Es {place} del mundial con {d['points']} puntos")
    if d["wins"] == 0:
        base += " y todavía no ha ganado una carrera este año."
    elif d["wins"] == 1:
        base += " y ha logrado una victoria."
    else:
        base += f" y suma {d['wins']} victorias."
    return base


def driver_bio(wiki_title: str) -> str:
    """Resumen en español si existe; si no, el inglés."""
    for host in ("es.wikipedia.org", "en.wikipedia.org"):
        try:
            data = get_json(
                f"https://{host}/api/rest_v1/page/summary/" + wiki_ref(wiki_title)
            )
            ext = (data.get("extract") or "").strip()
            if len(ext) > 60:
                return ext[:430]
        except Exception:
            continue
    return ""


BAD_IMG = re.compile(r"(map|layout|logo|escudo|emblem|flag_of|icon|badge|circuit_?map|track_?map)", re.I)


def fresh(path: pathlib.Path, min_size: int = 6000) -> bool:
    """¿La imagen existe, tiene tamaño y no ha caducado?"""
    if not path.exists() or path.stat().st_size < min_size:
        return False
    age_days = (time.time() - path.stat().st_mtime) / 86400
    return age_days < IMAGE_TTL_DAYS


def usable_image(url: str) -> bool:
    """Descarta mapas, escudos y SVG: solo interesan fotografías."""
    low = url.lower()
    if low.endswith((".svg", ".gif")):
        return False
    return not BAD_IMG.search(low.rsplit("/", 1)[-1])


def brightness(path: pathlib.Path) -> int:
    """Luminosidad media (0-255). Descarta fotos casi negras para cabeceras."""
    try:
        from PIL import Image
        im = Image.open(path).convert("L").resize((80, 80))
        # Pillow 14 retira getdata(); se usa get_flattened_data cuando existe
        data = getattr(im, "get_flattened_data", im.getdata)
        px = list(data())
        return int(sum(px) / len(px))
    except Exception:
        return 128


def is_photo(path: pathlib.Path) -> bool:
    """Una foto tiene miles de colores; un mapa o un escudo, unos cientos."""
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB").resize((100, 100))
        return len(im.getcolors(maxcolors=200000) or []) > 2200
    except Exception:
        return True


def wiki_best_photo(titles: list[str], slug_name: str, folder: str, width: int = 960) -> str | None:
    """Prueba varios títulos de Wikipedia y se queda con la primera foto real."""
    dest = ASSETS / folder / f"{slug_name}.jpg"
    if fresh(dest) and is_photo(dest):
        return f"assets/{folder}/{slug_name}.jpg"
    for title in titles:
        got = wiki_image(title, f"{slug_name}__try", folder, width)
        if not got:
            continue
        probe = ASSETS / folder / f"{slug_name}__try.jpg"
        if probe.exists() and is_photo(probe):
            probe.replace(dest)
            return f"assets/{folder}/{slug_name}.jpg"
        if probe.exists():
            probe.unlink()
    if dest.exists() and not is_photo(dest):
        dest.unlink()
    return None


def wiki_image(title: str, slug_name: str, folder: str, width: int = 500) -> str | None:
    """Descarga la imagen principal de una página de Wikipedia."""
    dest = ASSETS / folder / f"{slug_name}.jpg"
    if SKIP_IMAGES:
        return f"assets/{folder}/{slug_name}.jpg" if dest.exists() else None
    if fresh(dest):
        return f"assets/{folder}/{slug_name}.jpg"
    time.sleep(1.1)  # cortesía con la API de Wikipedia
    try:
        data = get_json(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + wiki_ref(title)
        )
        src = (data.get("thumbnail") or {}).get("source")
        if src and not usable_image(src):
            src = None
        if not src:
            # sin miniatura válida en el resumen: se busca en la lista de medios de la página
            media = get_json(
                "https://en.wikipedia.org/api/rest_v1/page/media-list/" + wiki_ref(title)
            )
            for item in media.get("items", []):
                if item.get("type") != "image" or not item.get("srcset"):
                    continue
                cand = item["srcset"][0]["src"]
                if not usable_image(cand):
                    continue
                src = "https:" + cand if cand.startswith("//") else cand
                break
        if not src:
            return None
        no_q = src.split("?")[0]
        cands = [re.sub(r"/\d+px-", f"/{w}px-", no_q) for w in (width, 330)]
        dest.parent.mkdir(parents=True, exist_ok=True)
        for cand in cands:
            try:
                img = get(cand, timeout=40)
            except Exception:
                continue
            if len(img) > 6000:
                dest.write_bytes(img)
                return f"assets/{folder}/{slug_name}.jpg"
        return None
    except Exception:
        return None


def wiki_extract(title: str, limit: int = 420) -> str:
    for host in ("es.wikipedia.org", "en.wikipedia.org"):
        try:
            data = get_json(f"https://{host}/api/rest_v1/page/summary/" + wiki_ref(title))
            ext = (data.get("extract") or "").strip()
            if len(ext) > 60:
                if len(ext) > limit:
                    cut = ext[:limit]
                    end = max(cut.rfind(". "), cut.rfind("; "))
                    ext = (cut[:end + 1] if end > limit * 0.55 else cut.rsplit(" ", 1)[0]) + "…"
                return ext
        except Exception:
            continue
    return ""


# ------------------------------------------------------------------------ noticias
# (medio, url, idioma, filtrar solo F1)  lo que esta en espanol va primero en portada
FEEDS = [
    ("Motorsport.com ES", "https://es.motorsport.com/rss/f1/news/", "es", False),
    ("Mundo Deportivo", "https://www.mundodeportivo.com/rss/motor", "es", True),
    ("The Race", "https://www.the-race.com/feed/", "en", False),
    ("Motorsport.com", "https://www.motorsport.com/rss/f1/news/", "en", False),
    ("Autosport", "https://www.autosport.com/rss/f1/news/", "en", False),
    ("Crash.net", "https://www.crash.net/rss/f1", "en", False),
    ("ESPN F1", "https://www.espn.com/espn/rss/f1/news", "en", False),
    ("RaceFans", "https://www.racefans.net/feed/", "en", False),
]

# Mundo Deportivo mezcla motor: solo entra lo que habla de F1.
OTHER_SERIES = re.compile(r"motogp|moto2|moto3|superbike|\bf2\b|\bf3\b|dakar|wrc|formula e|indycar", re.I)
F1_WORDS = re.compile(
    r"\bf1\b|f[oó]rmula 1|gran premio|verstappen|hamilton|leclerc|norris|piastri|"
    r"russell|antonelli|alonso|sainz|stroll|gasly|ocon|albon|tsunoda|lawson|hadjar|bearman|"
    r"hulkenberg|bortoleto|bottas|perez|colapinto|ferrari|mercedes|red bull|mclaren|aston martin|"
    r"alpine|haas|williams|sauber|audi|cadillac|fia|liberty", re.I)

# Alias que identifican cada escudería en un titular (minúsculas, sin acentos).
ALIASES = {
    "ferrari": ["ferrari", "scuderia", "maranello"],
    "mercedes": ["mercedes", "brackley", "hamilton", "russell", "antonelli"],
    "red_bull": ["red bull", "verstappen", "milton keynes", "mekies"],
    "mclaren": ["mclaren", "papaya", "norris", "piastri", "woking"],
    "aston_martin": ["aston martin", "alonso", "stroll", "newey", "silverstone verde"],
    "alpine": ["alpine", "enstone", "gasly", "colapinto"],
    "haas": ["haas", "komatsu", "bearman", "ocon"],
    "audi": ["audi", "hinwil", "sauber", "hulkenberg", "bortoleto"],
    "williams": ["williams", "vowles", "sainz", "albon", "grove"],
    "rb": ["racing bulls", "toro rosso", "alpha tauri", "alphatauri", "faenza", "hadjar", "lawson"],
    "cadillac": ["cadillac", "andretti", "lowdon", "bottas", "perez"],
}


def tag_teams(item: dict) -> list:
    blob = nrm(item["title"] + " " + item["desc"])
    hits = [tid for tid, keys in ALIASES.items() if any(k in blob for k in keys)]
    return hits


def keep_previous_rounds(calendar: list) -> None:
    """Si una ronda ya tenia resultados y la API no los devuelve hoy, se conservan.

    Jolpica limita peticiones: en una pasada pueden fallar varias rondas y sin esto
    el sitio perderia clasificaciones y resultados de carreras ya disputadas.
    """
    path = DATA / "site.json"
    try:
        prev = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if prev.get("season") != SEASON:
        return
    old_rounds = {int(r["round"]): r for r in prev.get("calendar", [])}
    filled = 0
    for race in calendar:
        old = old_rounds.get(int(race["round"]))
        if not old:
            continue
        for key in ("results", "qualifying", "sprint", "finished", "sessions"):
            if not race.get(key) and old.get(key):
                race[key] = old[key]
                filled += 1
        if old.get("winner") and not race.get("winner"):
            race["winner"] = old["winner"]
        if old.get("podium") and not race.get("podium"):
            race["podium"] = old["podium"]
    if filled:
        print(f"[data] conservadas {filled} tablas de rondas anteriores")


def parse_feed_date(pub: str):
    """Fecha de un item RSS: RFC 822 con o sin zona horaria."""
    if not pub:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S",
                "%d %b %Y %H:%M:%S %z", "%d %b %Y %H:%M:%S"):
        try:
            dt = datetime.strptime(pub.strip()[:31], fmt)
            return dt.replace(tzinfo=None)
        except Exception:
            continue
    return None


def fetch_history(seasons: int = 12) -> list:
    """Campeonatos anteriores, pilotos y constructores, desde Jolpica."""
    # lo ya descargado se conserva: si la API falla un dia, no se pierde ni un año
    prev = {}
    try:
        existing = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
        prev = {h["year"]: h for h in existing.get("history", []) if h.get("drivers")}
    except Exception:
        pass
    out = []
    for year in range(SEASON - 1, SEASON - 1 - seasons, -1):
        if year in prev:
            out.append(prev[year])
            continue
        row = {"year": year, "drivers": [], "constructors": [], "races": 0}
        time.sleep(0.5)
        lists = []
        for attempt in range(3):
            try:
                d = get_json(f"{API}/{year}/driverStandings.json?limit=40")
                lists = d["MRData"]["StandingsTable"]["StandingsLists"]
            except Exception:
                lists = []
            if lists:
                break
            time.sleep(1.2)
        if not lists:
            continue
        try:
            for e in lists[0]["DriverStandings"]:
                cs = e.get("Constructors") or [{}]
                c = cs[0]
                pos = str(e.get("position") or "").strip()
                row["drivers"].append({
                    "pos": int(pos) if pos.isdigit() else None,
                    "name": e["Driver"]["givenName"] + " " + e["Driver"]["familyName"],
                    "last": e["Driver"]["familyName"],
                    "code": e["Driver"].get("code") or "",
                    "team": c.get("name", ""),
                    "team_id": c.get("constructorId", ""),
                    "points": float(e.get("points") or 0),
                    "wins": int(e.get("wins") or 0),
                })
        except Exception:
            continue
        # años antiguos traen pilotos sin puesto numerico: se ordenan por puntos
        if any(d["pos"] is None for d in row["drivers"]):
            row["drivers"].sort(key=lambda d: (d["pos"] is None, -(d["points"]), d["name"]))
            for i, d in enumerate(row["drivers"], 1):
                d["pos"] = i
        try:
            c = get_json(f"{API}/{year}/constructorStandings.json?limit=20")
            cl = c["MRData"]["StandingsTable"]["StandingsLists"]
            if cl:
                for e in cl[0]["ConstructorStandings"]:
                    row["constructors"].append({
                        "pos": int(e["position"]),
                        "name": e["Constructor"]["name"],
                        "id": e["Constructor"]["constructorId"],
                        "points": float(e["points"]),
                        "wins": int(e["wins"]),
                    })
        except Exception:
            pass
        if not row["drivers"]:
            continue
        try:
            races = get_json(f"{API}/{year}.json?limit=1")
            row["races"] = int(races["MRData"]["total"])
        except Exception:
            pass
        ch = row["drivers"][0]
        row["champion"] = {"name": ch["name"], "last": ch["last"], "team": ch["team"],
                           "team_id": ch["team_id"], "points": ch["points"], "wins": ch["wins"]}
        row["constructor_champion"] = row["constructors"][0] if row["constructors"] else None
        row["gap"] = round(row["drivers"][0]["points"] - row["drivers"][1]["points"], 1) if len(row["drivers"]) > 1 else 0
        out.append(row)
        time.sleep(0.2)
    return out


def fetch_news(limit: int = 16) -> list:
    items, seen = [], set()
    for source, url, lang, f1_only in FEEDS:
        try:
            raw = get(url, timeout=25)
        except Exception:
            continue
        try:
            root = ET.fromstring(raw)
        except Exception:
            continue
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            if not title or not link or link in seen:
                continue
            if f1_only and (not F1_WORDS.search(title) or
                            (OTHER_SERIES.search(title) and not re.search(r"\bf1\b|f[oó]rmula 1", title, re.I))):
                continue
            seen.add(link)
            desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
            desc = re.sub(r"\s+", " ", desc).strip()[:230]
            img = None
            for tag in ("{http://search.yahoo.com/mrss/}content",
                        "{http://search.yahoo.com/mrss/}thumbnail", "enclosure"):
                el = it.find(tag)
                if el is not None:
                    img = el.get("url") or el.get("href")
                    if img:
                        break
            if not img:
                m = re.search(r'<img[^>]+src="([^"]+)"', it.findtext("description") or "")
                img = m.group(1) if m else None
            pub = (it.findtext("pubDate") or "").strip()
            dt = parse_feed_date(pub)
            # fuera lo viejo: lo de hace mas de 45 dias no es actualidad
            if dt and (datetime.now() - dt).days > 45:
                continue

            entry = {
                "title": title,
                "url": link,
                "desc": desc,
                "source": source,
                "lang": lang,
                "image": img,
                "date": dt.date().isoformat() if dt else "",
                "date_human": f"{dt.day} {MONTHS[dt.month - 1]}" if dt else "",
                "age": (lambda h: f"hace {h} h" if h < 24 else f"hace {h // 24} d")(
                    max(1, int((datetime.now().timestamp() - dt.timestamp()) / 3600))) if dt else "",
                "ts": dt.timestamp() if dt else 0,
            }
            entry["teams"] = tag_teams(entry)
            items.append(entry)
    items.sort(key=lambda x: (x["lang"] != "es", -x["ts"]))
    # Máximo 3 titulares por fuente en la portada, para no depender de un solo medio.
    # Cupo por medio: mas holgura para los que escriben en espanol.
    per_source, front = {}, []
    for it in items:
        cap = 5 if it["lang"] == "es" else 2
        n = per_source.get(it["source"], 0)
        if n < cap:
            front.append(it)
            per_source[it["source"]] = n + 1
        if len(front) >= limit:
            break
    return items, front[:limit]


# -------------------------------------------------------------------------- main
def main() -> None:
    """Ejecuta la descarga. Si la API falla, conserva los datos anteriores
    y deja que el build siga con ellos (el sitio nunca se queda sin datos)."""
    try:
        _run()
    except Exception as exc:  # noqa: BLE001
        print(f"[data] aviso: no se han podido actualizar los datos ({exc}). "
              f"Se mantiene la última copia en src/data/site.json")


def _run() -> None:
    global SEASON
    SEASON = detect_season()
    print(f"[data] temporada detectada: {SEASON}")
    today = date.today()
    api = fetch_api()
    calendar = build_calendar(api["calendar"], today)
    attach_winners(calendar, api["results"])
    attach_sessions(calendar, api["calendar"])
    attach_results(calendar, api["results"])
    attach_qualifying(calendar, api["qualifying"])
    attach_qualifying(calendar, api["sprint"])
    keep_previous_rounds(calendar)
    teams = build_teams(api, calendar)
    hist = prev_seasons([t["id"] for t in teams])
    for t in teams:
        t["prev"] = hist.get(t["id"], [])
    drivers = build_drivers(api, teams)

    stats = {}
    overrides = {"rafael_camara": "Rafael Camara"}
    for d in drivers:
        wiki = overrides.get(d["id"], d["wiki"])
        stats[d["id"]] = {"bio": driver_blurb(d), "photo": driver_photo(wiki, d["id"])}
        d.update(stats[d["id"]])

    done = [c for c in calendar if c["done"]]
    upcoming = [c for c in calendar if not c["done"]]
    if upcoming:
        upcoming[0]["is_next"] = True

    all_news, front_news = fetch_news()
    for t in teams:
        mine = [dict(n, own=True) for n in all_news if t["id"] in n["teams"]][:6]
        if len(mine) < 3:
            taken = {n["url"] for n in mine} | {n["url"] for n in front_news}
            for n in all_news:
                if len(mine) >= 3:
                    break
                if n["url"] not in taken:
                    mine.append(dict(n, own=False))
                    taken.add(n["url"])
        t["news"] = mine

    circuits = enrich_circuits(api["calendar"], calendar)
    for t in teams:
        lead = next((d for d in drivers if d["team"] and d["team"]["id"] == t["id"] and d.get("photo")), None)
        t["photo"] = lead["photo"] if lead else None
        t["photo_of"] = lead["full"] if lead else None
        t["car"] = team_car_photo(t, DISPLAY.get(t["id"], t["name"]))

    champions = championship_state(teams, drivers, len(done), len(calendar))

    site = {
        "season": SEASON,
        "champions": champions,
        "circuits": circuits,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "round": int(api["drivers"]["round"]),
        "total_races": len(calendar),
        "rounds_done": len(done),
        "calendar": calendar,
        "next_race": upcoming[0] if upcoming else None,
        "last_round": done[-1] if done else None,
        "teams": teams,
        "drivers": drivers,
        "news": front_news,
        "news_pool": len(all_news),
        "history": fetch_history(),
    }
    if site["next_race"]:
        site["next_race"]["days_until"] = (
            date.fromisoformat(site["next_race"]["date"]) - today
        ).days

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "site.json").write_text(json.dumps(site, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"[data] {SEASON}: {len(calendar)} carreras · {len(teams)} equipos · "
        f"{len(drivers)} pilotos · {len(site['news'])} noticias · "
        f"{sum(1 for d in drivers if d['photo'])} fotos"
    )


if __name__ == "__main__":
    main()
