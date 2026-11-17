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

import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "src" / "data"
ASSETS = ROOT / "assets"
SEASON = int(os.environ.get("PITLANE_SEASON", "2026"))
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


def get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_json(url: str) -> dict:
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
    try:
        results = get_json(f"{API}/{SEASON}/results.json?limit=1000")["MRData"][
            "RaceTable"]["Races"]
    except Exception:
        results = []
    return {"calendar": cal, "drivers": drivers, "teams": teams, "results": results}


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
            "locality": loc["locality"],
            "country": loc["country"],
            "flag": FLAG.get(loc["country"], "🏁"),
            "date": r["date"],
            "date_human": f"{d.day} {MONTHS[d.month - 1]} {d.year}",
            "date_long": f"{d.day} de {MONTHS_LONG[d.month - 1]} de {d.year}",
            "weekday": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][d.weekday()],
            "done": d < today,
            "is_next": False,
            "winner": None,
        })
    return out


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


# ---------------------------------------------------------------------- imágenes
def driver_photo(wiki_title: str, did: str) -> str | None:
    dest = ASSETS / "drivers" / f"{did}.jpg"
    if dest.exists() and dest.stat().st_size > 6000:
        return f"assets/drivers/{did}.jpg"
    try:
        data = get_json(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(wiki_title.replace(" ", "_"))
        )
        src = (data.get("thumbnail") or {}).get("source")
        if not src:
            return None
        # Wikimedia solo sirve una lista cerrada de anchos (250/330/500/960/1280).
        no_q = src.split("?")[0]
        candidates = [re.sub(r"/\d+px-", f"/{w}px-", no_q) for w in (500, 330, 250)] + [no_q]
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


def driver_bio(wiki_title: str) -> str:
    """Resumen en español si existe; si no, el inglés."""
    for host in ("es.wikipedia.org", "en.wikipedia.org"):
        try:
            data = get_json(
                f"https://{host}/api/rest_v1/page/summary/" + quote(wiki_title.replace(" ", "_"))
            )
            ext = (data.get("extract") or "").strip()
            if len(ext) > 60:
                return ext[:430]
        except Exception:
            continue
    return ""


# ------------------------------------------------------------------------ noticias
FEEDS = [
    ("The Race", "https://www.the-race.com/feed/"),
    ("Motorsport.com", "https://www.motorsport.com/rss/f1/news/"),
    ("Autosport", "https://www.autosport.com/rss/f1/news/"),
    ("Crash.net", "https://www.crash.net/rss/f1"),
    ("ESPN F1", "https://www.espn.com/espn/rss/f1/news"),
    ("RaceFans", "https://www.racefans.net/feed/"),
    ("Motorsport Week", "https://www.motorsportweek.com/feed/"),
]

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


def fetch_news(limit: int = 12) -> list:
    items, seen = [], set()
    for source, url in FEEDS:
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
            dt = None
            for fmt in ("%a, %d %b %Y %H:%M:%S", "%a, %d %b %Y %H:%M:%S %z"):
                try:
                    dt = datetime.strptime(pub[:len(pub.rstrip())][:31].strip(), fmt)
                    break
                except Exception:
                    continue
            entry = {
                "title": title,
                "url": link,
                "desc": desc,
                "source": source,
                "image": img,
                "date": dt.date().isoformat() if dt else "",
                "date_human": f"{dt.day} {MONTHS[dt.month - 1]}" if dt else "",
                "ts": dt.timestamp() if dt else 0,
            }
            entry["teams"] = tag_teams(entry)
            items.append(entry)
    items.sort(key=lambda x: -x["ts"])
    # Máximo 3 titulares por fuente en la portada, para no depender de un solo medio.
    per_source, front = {}, []
    for it in items:
        n = per_source.get(it["source"], 0)
        if n < 3:
            front.append(it)
            per_source[it["source"]] = n + 1
        if len(front) >= limit:
            break
    return items, front[:limit]


# -------------------------------------------------------------------------- main
def main() -> None:
    today = date.today()
    api = fetch_api()
    calendar = build_calendar(api["calendar"], today)
    attach_winners(calendar, api["results"])
    teams = build_teams(api, calendar)
    hist = prev_seasons([t["id"] for t in teams])
    for t in teams:
        t["prev"] = hist.get(t["id"], [])
    drivers = build_drivers(api, teams)

    stats = {}
    for d in drivers:
        stats[d["id"]] = {"bio": driver_bio(d["wiki"]), "photo": driver_photo(d["wiki"], d["id"])}
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

    site = {
        "season": SEASON,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "round": api["drivers"]["round"],
        "total_races": len(calendar),
        "rounds_done": len(done),
        "calendar": calendar,
        "next_race": upcoming[0] if upcoming else None,
        "last_round": done[-1] if done else None,
        "teams": teams,
        "drivers": drivers,
        "news": front_news,
        "news_pool": len(all_news),
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
