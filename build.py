"""Generador estático de PITLANE.

Uso:  python build.py            (usa los datos de src/data/site.json)
      python build.py --fetch    (actualiza datos antes de compilar)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT / "public"
ASSETS = ROOT / "assets"

sys.path.insert(0, str(SRC))
from teams_meta import LAYOUT_LABEL, PATTERN_ORDER, TEAMS  # noqa: E402

FONTS = {
    "base": "Barlow+Condensed:wght@500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600",
    "clasico": "Playfair+Display:ital,wght@0,700;1,600&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400",
    "tecnico": "Chakra+Petch:wght@600;700&family=Saira+Condensed:wght@700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;600",
    "moderno": "Barlow+Condensed:wght@600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400",
    "rebelde": "Anton&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600",
}

MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
             "septiembre", "octubre", "noviembre", "diciembre"]


def load_site() -> dict:
    return json.loads((SRC / "data" / "site.json").read_text(encoding="utf-8"))


def human_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    return f"{dt.day} de {MONTHS_ES[dt.month - 1]} de {dt.year}"


def render_all(site: dict) -> int:
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

    teams_by_id = {t["id"]: t for t in site["teams"]}
    drivers_by_id = {d["id"]: d for d in site["drivers"]}
    generated = human_date(site["generated"][:10])
    sources = " · ".join(sorted({n["source"] for n in site["news"]})) or "medios especializados"
    pages = 0

    def write(rel: str, tpl: str, root: str, **ctx):
        nonlocal pages
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        html = env.get_template(tpl).render(
            site=site, meta=TEAMS, root=root,
            site_title="Pitlane — Fórmula 1",
            site_desc="Datos, historia y actualidad de la Fórmula 1.",
            current="/" + rel.replace("index.html", ""),
            generated_human=generated, news_sources=sources,
            font_query=FONTS[ctx.pop("font", "base")],
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
        meta = TEAMS[t["id"]]
        prev_team = ranked[(i + 1) % len(ranked)]
        next_team = ranked[(i - 1) % len(ranked)]
        tpl = f"team_{meta['layout']}.html"
        # Los 24 pilotos no: la ficha enseña la plantilla del equipo con sus datos de temporada.
        write(
            f"escuderias/{t['slug']}.html", tpl, "../",
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
    write("calendario.html", "calendar.html", "")
    write("clasificacion.html", "standings.html", "")
    write("noticias.html", "news.html", "")
    write("metodologia.html", "method.html", "")
    return pages


def write_static(site: dict) -> None:
    if (OUT / "assets").exists():
        shutil.rmtree(OUT / "assets")
    shutil.copytree(ASSETS, OUT / "assets")
    (OUT / "assets" / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="12" fill="#07080a"/>'
        '<path d="M14 48V16h9l11 19V16h9v32h-9L23 29v19z" fill="#ff5a1f"/></svg>',
        encoding="utf-8")

    urls = ["", "escuderias/", "pilotos/", "calendario.html", "clasificacion.html",
            "noticias.html", "metodologia.html"]
    for t in site["teams"]:
        t.setdefault("slug", t["id"].replace("_", "-"))
    urls += [f"escuderias/{t['slug']}.html" for t in site["teams"]]
    urls += [f"pilotos/{d['id']}.html" for d in site["drivers"]]
    body = "".join(
        f"<url><loc>https://pitlane-f1-pied.vercel.app/{u}</loc>"
        f"<lastmod>{site['generated'][:10]}</lastmod></url>" for u in urls)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',
        encoding="utf-8")
    (OUT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: https://pitlane-f1-pied.vercel.app/sitemap.xml\n", encoding="utf-8")


def main() -> None:
    if "--fetch" in sys.argv:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_data.py")], check=True)
    site = load_site()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    n = render_all(site)
    write_static(site)
    print(f"[build] {n} páginas · {len(site['teams'])} escuderías · {len(site['drivers'])} pilotos")


if __name__ == "__main__":
    main()
