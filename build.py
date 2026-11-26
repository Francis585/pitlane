"""Generador estático de PITLANE.

Uso:  python build.py            (usa los datos de src/data/site.json)
      python build.py --fetch    (actualiza datos antes de compilar)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT / "public"
ASSETS = ROOT / "assets"

sys.path.insert(0, str(SRC))
from teams_meta import LAYOUT_LABEL, PATTERN_ORDER, TEAMS  # noqa: E402
from races_meta import DEFAULT as GP_DEFAULT, RACES as GP_THEMES  # noqa: E402

FONTS = {
    "base": "Barlow+Condensed:wght@500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600",
    "clasico": "Playfair+Display:ital,wght@0,700;1,600&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400",
    "tecnico": "Chakra+Petch:wght@600;700&family=Saira+Condensed:wght@700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;600",
    "moderno": "Barlow+Condensed:wght@600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400",
    "rebelde": "Anton&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600",
}

# país/nacionalidad → código ISO para banderas reales (los emoji no se ven en Windows)
COUNTRY_CODE = {
    "Australia": "au", "China": "cn", "Japan": "jp", "USA": "us", "Canada": "ca",
    "Monaco": "mc", "Spain": "es", "Austria": "at", "UK": "gb", "Belgium": "be",
    "Hungary": "hu", "Netherlands": "nl", "Italy": "it", "Azerbaijan": "az",
    "Malaysia": "my", "Singapore": "sg", "Mexico": "mx", "Brazil": "br",
    "Qatar": "qa", "UAE": "ae", "Germany": "de", "France": "fr", "Saudi Arabia": "sa",
    "Bahrain": "bh", "Portugal": "pt", "Turkey": "tr", "South Africa": "za",
    "Argentina": "ar", "Finland": "fi", "New Zealand": "nz", "Denmark": "dk",
    "Switzerland": "ch", "Sweden": "se", "Poland": "pl", "Russia": "ru",
    "Italian": "it", "British": "gb", "German": "de", "French": "fr", "Spanish": "es",
    "Dutch": "nl", "Mexican": "mx", "Brazilian": "br", "Australian": "au",
    "Canadian": "ca", "Japanese": "jp", "Chinese": "cn", "Monegasque": "mc",
    "Austrian": "at", "Belgian": "be", "Hungarian": "hu", "Azerbaijani": "az",
    "Singaporean": "sg", "Thai": "th", "Finnish": "fi", "Danish": "dk",
    "Swiss": "ch", "Swedish": "se", "New Zealander": "nz", "Argentine": "ar",
    "American": "us", "Portuguese": "pt", "Polish": "pl", "Russian": "ru",
    "South African": "za", "Turkish": "tr", "Saudi": "sa", "Bahraini": "bh",
}

MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
             "septiembre", "octubre", "noviembre", "diciembre"]


AUTO_COLORS = [("#00A19C", "#F5C518"), ("#E10600", "#F5F5F5"), ("#1B5FAA", "#E4002B"),
               ("#FF8000", "#00E5FF"), ("#8A1538", "#C8A24C"), ("#7B2CBF", "#22D3EE"),
               ("#1E7B4F", "#CE2939"), ("#C9A24C", "#E8EDF2")]
AUTO_LAYOUTS = ["moderno", "tecnico", "clasico", "rebelde"]
AUTO_PATTERNS = ["stripes", "grid", "arcs", "chevrons", "rays", "shield", "wings", "hex"]


def auto_meta(team: dict, index: int = 0) -> dict:
    """Ficha por defecto para una escudería que aún no está curada a mano.

    Así, si en 2027 u otro año entra un equipo nuevo, el sitio se genera igual
    sin tocar código: color, layout y patrón se asignan solos.
    """
    brand, brand2 = AUTO_COLORS[index % len(AUTO_COLORS)]
    return {
        "display": team["name"],
        "full": team["name"],
        "layout": AUTO_LAYOUTS[index % len(AUTO_LAYOUTS)],
        "brand": brand,
        "brand2": brand2,
        "ink": "#07080a",
        "pattern": AUTO_PATTERNS[index % len(AUTO_PATTERNS)],
        "font": "Barlow Condensed",
        "monogram": "".join(w[0] for w in team["name"].split()[:3]).upper(),
        "base": "—",
        "founded": "—",
        "engine": "—",
        "principal": "—",
        "titles": 0,
        "title_years": "",
        "tagline": f"{team['name']} en la temporada en curso.",
        "blurb": "Ficha generada automáticamente a partir de los datos públicos del campeonato. "
                 "Se completará con la información histórica en cuanto esté disponible.",
        "heritage": "",
        "timeline": [],
    }


def season_stats(site: dict) -> dict:
    """Victorias, podios, poles, vueltas rápidas y abandonos de la temporada."""
    drivers, teams = {}, {}

    def blank(name, tid=""):
        return {"name": name, "id": tid, "wins": 0, "podiums": 0, "poles": 0, "fl": 0,
                "dnf": 0, "races": 0, "points": 0, "best": None}

    for race in site["calendar"]:
        rows = race.get("results") or []
        for row in rows:
            d = drivers.setdefault(row["driver_id"], blank(row["driver"]))
            t = teams.setdefault(row["team_id"], blank(row["team"], row["team_id"]))
            d["races"] += 1
            d["team_id"] = row["team_id"]
            t["races"] += 1
            finished = str(row["status"]).startswith("Finished") or str(row["status"]).startswith("+")
            if not finished and row["pos_num"] > 90:
                d["dnf"] += 1
                t["dnf"] += 1
            elif not finished:
                d["dnf"] += 1
                t["dnf"] += 1
            if row["pos_num"] == 1:
                d["wins"] += 1
                t["wins"] += 1
            if row["pos_num"] <= 3:
                d["podiums"] += 1
                t["podiums"] += 1
            if str(row["fastest_rank"]) == "1":
                d["fl"] += 1
                t["fl"] += 1
            if d["best"] is None or row["pos_num"] < d["best"]:
                d["best"] = row["pos_num"]
        for q in race.get("qualifying") or []:
            if q["pos"] == "1":
                if q["driver_id"] in drivers:
                    drivers[q["driver_id"]]["poles"] += 1
                if q["team_id"] in teams:
                    teams[q["team_id"]]["poles"] += 1

    for d in site["drivers"]:
        if d["id"] in drivers:
            drivers[d["id"]]["points"] = d["points"]
            drivers[d["id"]]["team_id"] = d.get("team", {}).get("id", "")
    for t in site["teams"]:
        if t["id"] in teams:
            teams[t["id"]]["points"] = t["points"]

    ds = sorted(drivers.values(), key=lambda x: (-x["wins"], -x["podiums"], x["best"] or 99))
    ts = sorted(teams.values(), key=lambda x: (-x["wins"], -x["podiums"], x["points"] * -1))
    return {"drivers": ds, "teams": ts,
            "max_wins": max([x["wins"] for x in ds] + [1]),
            "max_team_wins": max([x["wins"] for x in ts] + [1]),
            "races": len([r for r in site["calendar"] if r.get("results")])}


def srcset_for(url: str) -> str:
    """Lista de candidatos para el atributo srcset."""
    if not url:
        return ""
    base = url.rsplit(".", 1)[0]
    return f"{base}-sm.webp 480w, {base}-md.webp 900w, {url} 1600w"


IMG_INFO: dict[str, int] = {}


def pic(url: str, alt: str = "", sizes: str = "100vw", cls: str = "",
        loading: str = "lazy", priority: bool = False) -> str:
    """<img> con srcset: el móvil descarga 480 px, el portátil la buena."""
    if not url:
        return ""
    base = url.rsplit(".", 1)[0]
    ext = url.rsplit(".", 1)[1] if "." in url else "webp"
    small, medium = f"{base}-sm.{ext}", f"{base}-md.{ext}"

    def width_of(u: str) -> int | None:
        return IMG_INFO.get(u.lstrip("/"))

    candidates = [(u, width_of(u)) for u in (small, medium, url)]
    candidates = [(u, w) for u, w in candidates if w]
    srcset = ", ".join(f"{u} {w}w" for u, w in candidates) or url
    attrs = [
        f'src="{url}"',
        f'srcset="{srcset}"',
        f'sizes="{sizes}"',
        f'alt="{alt}"',
        'width="1600" height="900"' if False else "",
        'decoding="async"',
    ]
    if cls:
        attrs.insert(0, f'class="{cls}"')
    attrs.append('fetchpriority="high"' if priority else f'loading="{loading}"')
    return "<img " + " ".join(a for a in attrs if a) + ">"


def flag_tag(code: str, cls: str = "flag-img", w: int = 20, h: int = 15) -> str:
    """Bandera nítida en cualquier pantalla, usando los anchos que sirve flagcdn."""
    allowed = [20, 40, 80, 160, 320]

    def pick(px: int) -> int:
        return next((a for a in allowed if a >= px), allowed[-1])

    one, two, three = pick(w), pick(w * 2), pick(w * 3)
    return (
        f'<img class="{cls}" src="https://flagcdn.com/w{one}/{code}.png" '
        f'srcset="https://flagcdn.com/w{one}/{code}.png 1x, '
        f'https://flagcdn.com/w{two}/{code}.png 2x, '
        f'https://flagcdn.com/w{three}/{code}.png 3x" '
        f'width="{w}" height="{h}" alt="" loading="lazy" decoding="async">'
    )


def load_site() -> dict:
    return json.loads((SRC / "data" / "site.json").read_text(encoding="utf-8"))


def _xml(text: str) -> str:
    """Escapa texto para XML/RSS."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def human_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    return f"{dt.day} de {MONTHS_ES[dt.month - 1]} de {dt.year}"


def race_week(site: dict) -> dict:
    """Devuelve el GP cuya semana está en curso, o None fuera de semana de carreras.

    La semana va del lunes anterior a la carrera hasta el día de la carrera.
    """
    today = date.today()
    for race in site["calendar"]:
        d = date.fromisoformat(race["date"])
        start = d - timedelta(days=6)
        if start <= today <= d:
            theme = GP_THEMES.get(race.get("circuit_id", ""), GP_DEFAULT)
            return {
                "active": True,
                "round": race["round"],
                "gp": race["name"],
                "city": race["locality"],
                "flag": race["flag"],
                "country": race["country"],
                "date": race["date"],
                "date_human": race["date_human"],
                "start": start.isoformat(),
                "end": d.isoformat(),
                "days": (d - today).days,
                **{k: theme[k] for k in ("brand", "brand2", "pattern", "vibe")},
            }
    return {"active": False, "brand": GP_DEFAULT["brand"], "brand2": GP_DEFAULT["brand2"],
            "pattern": GP_DEFAULT["pattern"], "vibe": GP_DEFAULT["vibe"]}


def build_moments(site: dict) -> list:
    """Últimas carreras con resultado: ganador, podio y foto del circuito."""
    photos = {c["round"]: c for c in site["circuits"]}
    out = []
    for race in site["calendar"]:
        if not race.get("winner") or not race.get("podium"):
            continue
        circ = photos.get(race["round"], {})
        out.append({
            "round": race["round"], "gp": race["name"], "winner": race["winner"],
            "team": race.get("winner_team"), "circuit": race["circuit"],
            "circuit_id": circ.get("id", ""), "photo": circ.get("photo"),
            "team_car": next((tm.get("car") for tm in site["teams"]
                              if tm["id"] == race.get("winner_team")), None),
            "podium": race["podium"],
        })
    return out[-4:][::-1]


def build_meta(site: dict) -> dict:
    """Ficha visual de cada escudería: curada si existe, generada si es nueva."""
    complete_meta = {}
    for i, t in enumerate(site["teams"]):
        base = dict(TEAMS.get(t["id"]) or auto_meta(t, i))
        base["brand"] = base.get("brand") or AUTO_COLORS[i % len(AUTO_COLORS)][0]
        base["brand2"] = base.get("brand2") or AUTO_COLORS[i % len(AUTO_COLORS)][1]
        complete_meta[t["id"]] = base

    return complete_meta


def render_all(site: dict, asset_versions: dict, complete_meta: dict) -> int:
    env = Environment(
        loader=FileSystemLoader(str(SRC / "templates")),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # slug legible para las URLs (red_bull → red-bull)
    for t in site["teams"]:
        t["slug"] = t["id"].replace("_", "-")
    for d in site["drivers"]:
        if d.get("team"):
            d["team"]["slug"] = d["team"]["id"].replace("_", "-")

    def asset_url(p):
        """URL pública del asset, en WebP si está disponible."""
        rel = str(p).lstrip("/")
        webp = OUT / rel.replace(".jpg", ".webp")
        if rel.lower().endswith(".jpg") and webp.exists():
            rel = rel.replace(".jpg", ".webp")
        return "/" + rel

    env.globals.update(
        img_url=asset_url,
        flag_code=lambda c: COUNTRY_CODE.get(str(c), "un"),
        flag_tag=flag_tag,
        pic=pic,
        srcset_for=srcset_for,
    )

    teams_by_id = {t["id"]: t for t in site["teams"]}
    drivers_by_id = {d["id"]: d for d in site["drivers"]}
    generated = human_date(site["generated"][:10])
    gp = race_week(site)
    moments = build_moments(site)
    next_circuit = next((c for c in site["circuits"]
                         if site.get("next_race") and c["round"] == site["next_race"]["round"]), None)
    upcoming_circuits = [c for c in site["circuits"] if not c["done"]][:4]

    # portada: carrusel de imágenes variadas (coches, circuitos y pilotos)
    meta_all = {t["id"]: (TEAMS.get(t["id"]) or auto_meta(t, i)) for i, t in enumerate(site["teams"])}
    slides = []
    for t in site["teams"]:
        if t.get("car"):
            slides.append({"src": t["car"], "alt": meta_all[t["id"]]["display"],
                           "label": meta_all[t["id"]]["display"], "kind": "car"})
    for c in site["circuits"][:6]:
        if c.get("photo"):
            slides.append({"src": c["photo"], "alt": c["name"], "label": c["name"], "kind": "circuit"})
    seen, hero_slides = set(), []
    for sl in slides:
        if sl["src"] in seen:
            continue
        seen.add(sl["src"])
        hero_slides.append(sl)
        if len(hero_slides) >= 6:
            break

    # mosaico de imágenes del paddock
    gallery = []
    for t in site["teams"][:4]:
        lead = next((d for d in site["drivers"]
                     if d["team"] and d["team"]["id"] == t["id"] and d.get("photo")), None)
        if lead:
            gallery.append({"src": lead["photo"], "alt": lead["full"],
                            "label": lead["full"], "sub": meta_all[t["id"]]["display"]})
    for c in site["circuits"][8:12]:
        if c.get("photo"):
            gallery.append({"src": c["photo"], "alt": c["name"], "label": c["name"],
                            "sub": c["locality"]})
    for t in site["teams"][4:8]:
        if t.get("car"):
            gallery.append({"src": t["car"], "alt": meta_all[t["id"]]["display"],
                            "label": meta_all[t["id"]]["display"], "sub": f"P{t['pos']} · {t['points']} pts"})
    sources = " · ".join(sorted({n["source"] for n in site["news"]})) or "medios especializados"
    pages = 0

    def write(rel: str, tpl: str, root: str, **ctx):
        nonlocal pages
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        html = env.get_template(tpl).render(
            site=site, meta=complete_meta, root=root, gp=gp, moments=moments,
            hero_slides=hero_slides, gallery=gallery,
            next_circuit=next_circuit, upcoming_circuits=upcoming_circuits,
            site_title="Pitlane — Fórmula 1",
            site_desc="Datos, historia y actualidad de la Fórmula 1.",
            current="/" + rel.replace("index.html", ""),
            generated_human=generated, news_sources=sources,
            font_query=FONTS[ctx.pop("font", "base")],
            img_url=asset_url,
            asset_css=asset_versions["css"], asset_js=asset_versions["js"],
            og_image=ctx.pop("og_image", OG_CARDS.get("home")),
            flag_code=lambda c: COUNTRY_CODE.get(str(c), "un"),
        flag_tag=flag_tag,
        pic=pic,
        srcset_for=srcset_for,
            **ctx,
        )
        dest.write_text(html, encoding="utf-8")
        pages += 1

    # ---------------------------------------------------------------- portada
    write("index.html", "index.html", "")

    # ------------------------------------------------------------ escuderías
    ranked = sorted(site["teams"], key=lambda t: t["pos"])
    write("escuderias/index.html", "teams.html", "../", teams=ranked)

    for i, t in enumerate(ranked):
        meta = complete_meta[t["id"]]
        prev_team = ranked[(i + 1) % len(ranked)]
        next_team = ranked[(i - 1) % len(ranked)]
        tpl = f"team_{meta['layout']}.html"
        # Los 24 pilotos no: la ficha enseña la plantilla del equipo con sus datos de temporada.
        write(
            f"escuderias/{t['slug']}.html", tpl, "../", og_image=OG_CARDS.get(t["id"]),
            team=t, tm=meta,
            drivers=[drivers_by_id[d["id"]] for d in t["drivers"] if d["id"] in drivers_by_id],
            next_team=next_team, prev_team=prev_team,
            font=meta["layout"],
        )

    # --------------------------------------------------------------- pilotos
    write("pilotos/index.html", "drivers.html", "../", drivers=site["drivers"])
    for d in site["drivers"]:
        write(f"pilotos/{d['id']}.html", "driver.html", "../", d=d,
              tm=TEAMS.get(d["team"]["id"]) if d["team"] else None,
              team=teams_by_id.get(d["team"]["id"]) if d["team"] else None,
              teammates=[x for x in site["drivers"]
                         if d["team"] and x["team"] and x["team"]["id"] == d["team"]["id"] and x["id"] != d["id"]],
              font=TEAMS.get(d["team"]["id"], {}).get("layout", "base") if d["team"] else "base")

    # ------------------------------------------------------------ estáticas
    write("circuitos/index.html", "circuits.html", "../", circuits=site["circuits"])
    for c in site["circuits"]:
        write(f"circuitos/{c['id']}.html", "circuit.html", "../", c=c,
              theme=GP_THEMES.get(c["id"], GP_DEFAULT),
              others=[o for o in site["circuits"] if o["id"] != c["id"]][:4],
              schedule=next((r.get("sessions", []) for r in site["calendar"]
                             if r["round"] == c["round"]), []))
    # resultados por carrera
    circuits_by_id = {c["id"]: c for c in site["circuits"]}
    done_races = [r for r in site["calendar"] if r.get("results")]
    write("resultados/index.html", "races.html", "../", races=done_races, circuits=circuits_by_id)
    for i, r in enumerate(done_races):
        write(f"resultados/{r['circuit_id']}.html", "race.html", "../", r=r,
              c=circuits_by_id.get(r["circuit_id"], {}),
              fastest=next((x for x in r["results"] if str(x["fastest_rank"]) == "1"), None),
              prev_race=done_races[i - 1] if i > 0 else None,
              next_race=done_races[i + 1] if i + 1 < len(done_races) else None)
    stats = season_stats(site)

    def brand_of(team_id):
        return (complete_meta.get(team_id) or {}).get("brand", "#888")

    cmp_rows = []
    for d in site["drivers"]:
        st = next((x for x in stats["drivers"] if x["name"] == d["full"]), None)
        cmp_rows.append({
            "id": d["id"], "name": d["full"], "short": d["last"], "code": d.get("code", ""),
            "team": d.get("team", {}).get("name", ""), "brand": brand_of(d.get("team", {}).get("id", "")),
            "pos": d["pos"], "points": d["points"], "wins": st["wins"] if st else 0,
            "podiums": st["podiums"] if st else 0, "poles": st["poles"] if st else 0,
            "fl": st["fl"] if st else 0, "dnf": st["dnf"] if st else 0,
            "races": st["races"] if st else 0, "best": st["best"] if st else None,
        })

    search_rows = []
    for d in site["drivers"]:
        search_rows.append({"t": d["full"], "s": (d.get("team") or {}).get("name", "") + " · piloto",
                            "u": f"/pilotos/{d['id']}.html", "k": "piloto"})
    for t in site["teams"]:
        tm = complete_meta.get(t["id"]) or {}
        search_rows.append({"t": tm.get("display", t["name"]), "s": tm.get("full", t["name"]) + " · escudería",
                            "u": f"/escuderias/{t['id']}.html", "k": "escudería"})
    for c in site["circuits"]:
        search_rows.append({"t": c["name"], "s": c.get("locality", "") + " · circuito",
                            "u": f"/circuitos/{c['id']}.html", "k": "circuito"})
    for r in site["calendar"]:
        search_rows.append({"t": r["name"], "s": f"Ronda {r['round']} · {r['date_human']}",
                            "u": f"/resultados/{r['circuit_id']}.html" if r.get("results") else f"/circuitos/{r['circuit_id']}.html",
                            "k": "gran premio"})

    write("estadisticas.html", "stats.html", "", stats=stats)
    write("comparador.html", "compare.html", "", data=json.dumps(cmp_rows, ensure_ascii=False))
    write("buscador.html", "search.html", "", data=json.dumps(search_rows, ensure_ascii=False))

    write("calendario.html", "calendar.html", "")
    write("clasificacion.html", "standings.html", "")
    write("noticias.html", "news.html", "")
    write("historico.html", "historico.html", "")
    write("metodologia.html", "method.html", "")
    write("404.html", "404.html", "")
    return pages


def make_og_cards(site: dict, meta: dict) -> dict:
    """Genera una imagen de compartir por escudería (y una general) al vuelo."""
    from PIL import Image, ImageDraw, ImageFont
    out = OUT / "assets" / "og"
    out.mkdir(parents=True, exist_ok=True)
    try:
        bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 96)
        small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 34)
        tiny = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 24)
    except Exception:
        bold = small = tiny = ImageFont.load_default()

    def card(path, title, subtitle, colour, extra=""):
        W, H = 1200, 630
        img = Image.new("RGB", (W, H), (7, 8, 10))
        d = ImageDraw.Draw(img)
        for i in range(H):  # degradado vertical
            d.line([(0, i), (W, i)], fill=(int(9 + 18 * (1 - i / H)), int(10 + 14 * (1 - i / H)),
                                          int(12 + 26 * (1 - i / H))))
        for x in range(-300, W + 300, 54):  # rayas de velocidad
            d.line([(x, 0), (x - 220, H)], fill=(19, 21, 28), width=3)
        d.rectangle([0, 0, 10, H], fill=colour)
        d.rectangle([0, H - 8, W, H], fill=colour)
        import textwrap
        d.text((64, 150), title.upper()[:18], font=bold, fill=(244, 246, 249))
        y = 300
        for line in textwrap.wrap(subtitle, 46)[:2]:
            d.text((66, y), line, font=small, fill=(176, 183, 194))
            y += 44
        if extra:
            for line in textwrap.wrap(extra, 52)[:2]:
                d.text((66, y + 6), line, font=small, fill=(140, 147, 158))
                y += 44
        d.text((66, H - 74), "PITLANE · FÓRMULA 1 " + str(site["season"]), font=tiny, fill=colour)
        img.save(out / path, "PNG", optimize=True)

    cards = {}
    card("home.png", "Pitlane", f"F1 {site['season']}: once escuderías, pilotos y circuitos",
         (255, 90, 31), f"Ronda {site['round']} de {site['total_races']}")
    cards["home"] = "/assets/og/home.png"
    for t in site["teams"]:
        m = meta[t["id"]]
        hexc = m["brand"].lstrip("#")
        rgb = tuple(int(hexc[i:i + 2], 16) for i in (0, 2, 4))
        card(f"{t['id']}.png", m["display"], f"P{t['pos']} · {t['points']} puntos · {m.get('engine', '')}",
             rgb, m.get("tagline", "")[:64])
        cards[t["id"]] = f"/assets/og/{t['id']}.png"
    return cards


def minify_css(text: str) -> str:
    """Quita comentarios y espacios sobrantes sin tocar cadenas ni url()."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    out, quote, i = [], None, 0
    while i < len(text):
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == quote and text[i - 1] != "\\":
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        else:
            out.append(ch)
        i += 1
    css = "".join(out)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};:,>])\s*", r"\1", css)
    return css.replace(";}", "}").strip()


def optimize_assets() -> dict:
    """Copia los assets, recomprime las fotos y devuelve versiones para cache-busting."""
    import hashlib
    try:
        from PIL import Image
    except Exception:
        Image = None

    if (OUT / "assets").exists():
        shutil.rmtree(OUT / "assets")
    shutil.copytree(ASSETS, OUT / "assets")

    limits = {"teams": 1600, "circuits": 1300, "drivers": 800}
    saved = 0
    if Image:
        for img in (OUT / "assets").rglob("*.jpg"):
            limit = next((v for k, v in limits.items() if k in str(img)), 1400)
            before = img.stat().st_size
            try:
                im = Image.open(img).convert("RGB")
                if im.width > limit:
                    im = im.resize((limit, round(im.height * limit / im.width)), Image.LANCZOS)
                im.save(img, "JPEG", quality=82, optimize=True, progressive=True)
                saved += before - img.stat().st_size
            except Exception:
                continue

    # versión WebP (mucho más ligera) más variantes para móvil y tablet
    if Image:
        for img in list((OUT / "assets").rglob("*.jpg")):
            try:
                im = Image.open(img).convert("RGB")
                big = img.with_suffix(".webp")
                im.save(big, "WEBP", quality=74, method=4)
                IMG_INFO[str(big.relative_to(OUT)).replace("\\", "/")] = im.width
                for suffix, width in (("-sm", 480), ("-md", 900)):
                    if im.width > width:
                        variant = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
                        out = img.with_name(img.stem + suffix + ".webp")
                        variant.save(out, "WEBP", quality=74, method=4)
                        IMG_INFO[str(out.relative_to(OUT)).replace("\\", "/")] = width
                img.unlink()  # el sitio ya solo sirve WebP
            except Exception:
                continue

    css_path = OUT / "assets" / "styles.css"
    try:
        css_path.write_text(minify_css(css_path.read_text(encoding="utf-8")), encoding="utf-8")
    except Exception:
        pass

    def version(path: pathlib.Path) -> str:
        return hashlib.md5(path.read_bytes()).hexdigest()[:10]

    return {
        "css": version(OUT / "assets" / "styles.css"),
        "js": version(OUT / "assets" / "app.js"),
        "saved_mb": round(saved / 1e6, 2),
    }


def write_ics(site: dict) -> None:
    """Calendario .ics con todas las sesiones, para suscribirse o importar."""
    from datetime import datetime, timedelta, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Pitlane//F1//ES",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:Fórmula 1 {site['season']} · Pitlane",
             "X-WR-TIMEZONE:Europe/Madrid"]
    durations = {"FP1": 60, "FP2": 60, "FP3": 60, "SQ": 45, "SPR": 60, "Q": 45, "RACE": 120}

    def esc(text: str) -> str:
        return (text.replace("\\", "\\\\").replace(",", "\\,")
                .replace(";", "\\;").replace("\n", "\\n"))

    for race in site["calendar"]:
        for ses in race.get("sessions", []):
            start = datetime.strptime(ses["iso"], "%Y-%m-%dT%H:%M:%SZ")
            end = start + timedelta(minutes=durations.get(ses["code"], 60))
            lines += [
                "BEGIN:VEVENT",
                f"UID:{site['season']}-{race['round']}-{ses['code']}@pitlane",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}",
                f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}",
                f"SUMMARY:{esc(race['name'] + ' · ' + ses['name'])}",
                f"LOCATION:{esc(race['circuit'] + ', ' + race['locality'] + ', ' + race['country'])}",
                f"DESCRIPTION:{esc('Ronda ' + str(race['round']) + ' · ' + race['name'])}",
                f"URL:https://pitlane-ruddy.vercel.app/circuitos/{race['circuit_id']}.html",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    (OUT / "calendario.ics").write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))


def write_static(site: dict) -> None:
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="12" fill="#07080a"/>'
        '<path d="M14 48V16h9l11 19V16h9v32h-9L23 29v19z" fill="#ff5a1f"/></svg>',
        encoding="utf-8")

    urls = ["", "escuderias/", "pilotos/", "circuitos/", "resultados/", "calendario.html", "clasificacion.html",
            "estadisticas.html", "comparador.html", "buscador.html",
            "noticias.html", "metodologia.html", "historico.html"]
    for t in site["teams"]:
        t.setdefault("slug", t["id"].replace("_", "-"))
    urls += [f"escuderias/{t['slug']}.html" for t in site["teams"]]
    urls += [f"pilotos/{d['id']}.html" for d in site["drivers"]]
    urls += [f"circuitos/{c['id']}.html" for c in site.get("circuits", [])]
    urls += [f"resultados/{r['circuit_id']}.html" for r in site["calendar"] if r.get("results")]
    body = "".join(
        f"<url><loc>https://pitlane-ruddy.vercel.app/{u}</loc>"
        f"<lastmod>{site['generated'][:10]}</lastmod></url>" for u in urls)
    write_ics(site)

    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',
        encoding="utf-8")
    # feed RSS de titulares (lectores de feeds, agregadores)
    from email.utils import format_datetime as _fmt_dt
    items = []
    for n in site["news"]:
        pub = ""
        try:
            from datetime import datetime as _dt
            pub = _fmt_dt(_dt.fromisoformat(n["date"] + "T09:00:00"))
        except Exception:
            pass
        desc = (n.get("desc") or "").replace("&", "&amp;").replace("<", "&lt;")
        items.append(
            "<item>"
            f"<title>{_xml(n['title'])}</title>"
            f"<link>{_xml(n['url'])}</link>"
            f"<guid isPermaLink=\"true\">{_xml(n['url'])}</guid>"
            f"<source url=\"\">{_xml(n['source'])}</source>"
            f"<pubDate>{pub}</pubDate>"
            f"<description>{desc}</description>"
            "</item>")
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">'
        "<channel>"
        "<title>Pitlane — Fórmula 1</title>"
        "<link>https://pitlane-ruddy.vercel.app/</link>"
        "<description>Titulares de Fórmula 1 recogidos automáticamente.</description>"
        "<language>es</language>"
        "<lastBuildDate>" + _fmt_dt(__import__("datetime").datetime.now()) + "</lastBuildDate>"
        '<atom:link href="https://pitlane-ruddy.vercel.app/feed.xml" rel="self" type="application/rss+xml"/>'
        + "".join(items) + "</channel></rss>")
    (OUT / "feed.xml").write_text(feed, encoding="utf-8")

    # contacto de seguridad y metadatos del proyecto
    wk = OUT / ".well-known"
    wk.mkdir(parents=True, exist_ok=True)
    (wk / "security.txt").write_text(
        "Contact: https://github.com/Francis585/pitlane/issues\n"
        "Expires: 2027-12-31T23:59:00.000Z\n"
        "Preferred-Languages: es, en\n"
        "Canonical: https://pitlane-ruddy.vercel.app/.well-known/security.txt\n"
        "Policy: https://github.com/Francis585/pitlane/security/policy\n",
        encoding="utf-8")

    (OUT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: https://pitlane-ruddy.vercel.app/sitemap.xml\n", encoding="utf-8")


LOCK = ROOT / ".build.lock"


def acquire_lock() -> bool:
    """Impide dos compilaciones a la vez (dejaban public/ a medias)."""
    if LOCK.exists():
        age = time.time() - LOCK.stat().st_mtime
        if age < 900:  # menos de 15 minutos: hay otra compilación viva
            return False
        LOCK.unlink(missing_ok=True)
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    return True


def main() -> None:
    if not acquire_lock():
        print("[build] ya hay una compilación en curso; se omite esta")
        return
    try:
        _main()
    finally:
        LOCK.unlink(missing_ok=True)


def _main() -> None:
    if "--fetch" in sys.argv:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_data.py")], check=True)
    site = load_site()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    asset_versions = optimize_assets()
    complete_meta = build_meta(site)
    global OG_CARDS
    OG_CARDS = make_og_cards(site, complete_meta)
    n = render_all(site, asset_versions, complete_meta)
    write_static(site)
    print(f"[build] {n} páginas · {len(site['teams'])} escuderías · "
          f"{len(site['drivers'])} pilotos · imágenes -{asset_versions['saved_mb']} MB")


if __name__ == "__main__":
    main()
