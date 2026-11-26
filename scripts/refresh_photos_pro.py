"""Refresca las fotos de coches y pilotos desde Wikimedia Commons.

Busca fotos de Gran Premio (coche en pista, piloto con mono) en lugar de
retratos de estudio o primeros planos de patrocinadores. Guarda un informe en
JSON para poder revisar qué se ha elegido.

Uso:  python scripts/refresh_photos_pro.py [--drivers] [--teams] [--force]
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
UA = {"User-Agent": "PitlaneBot/1.0 (sitio informativo no oficial de F1)"}

TEAMS = {
    "ferrari": ("Ferrari", ["Ferrari"]),
    "mercedes": ("Mercedes", ["Mercedes"]),
    "red_bull": ("Red Bull Racing", ["Red Bull"]),
    "mclaren": ("McLaren", ["McLaren"]),
    "aston_martin": ("Aston Martin", ["Aston Martin"]),
    "alpine": ("Alpine", ["Alpine"]),
    "haas": ("Haas", ["Haas"]),
    "audi": ("Audi", ["Audi"]),
    "williams": ("Williams", ["Williams"]),
    "rb": ("Racing Bulls", ["Racing Bulls", "RB"]),
    "cadillac": ("Cadillac", ["Cadillac"]),
}

DRIVERS = {
    "antonelli": ("Andrea Kimi Antonelli", "Antonelli"),
    "max_verstappen": ("Max Verstappen", "Verstappen"),
    "hamilton": ("Lewis Hamilton", "Hamilton"),
    "russell": ("George Russell", "Russell"),
    "norris": ("Lando Norris", "Norris"),
    "leclerc": ("Charles Leclerc", "Leclerc"),
    "piastri": ("Oscar Piastri", "Piastri"),
    "hadjar": ("Isack Hadjar", "Hadjar"),
    "lawson": ("Liam Lawson", "Lawson"),
    "gasly": ("Pierre Gasly", "Gasly"),
    "arvid_lindblad": ("Arvid Lindblad", "Lindblad"),
    "colapinto": ("Franco Colapinto", "Colapinto"),
    "bearman": ("Oliver Bearman", "Bearman"),
    "bortoleto": ("Gabriel Bortoleto", "Bortoleto"),
    "hulkenberg": ("Nico Hülkenberg", "Hülkenberg"),
    "sainz": ("Carlos Sainz", "Sainz"),
    "ocon": ("Esteban Ocon", "Ocon"),
    "alonso": ("Fernando Alonso", "Alonso"),
    "albon": ("Alexander Albon", "Albon"),
    "tsunoda": ("Yuki Tsunoda", "Tsunoda"),
    "ryo_hirakawa": ("Ryo Hirakawa", "Hirakawa"),
    "stroll": ("Lance Stroll", "Stroll"),
    "bottas": ("Valtteri Bottas", "Bottas"),
    "perez": ("Sergio Pérez", "Pérez"),
    "rafael_camara": ("Rafael Camara", "Camara"),
}


def get(url: str, timeout: int = 60, retries: int = 3) -> bytes:
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + i * 3)
    raise last  # type: ignore[misc]


def search(terms: str, limit: int = 12) -> list[dict]:
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search"
           f"&gsrsearch={urllib.parse.quote('filetype:bitmap ' + terms)}&gsrlimit={limit}"
           "&gsrnamespace=6&prop=imageinfo&iiprop=url|size|extmetadata&iiurlwidth=1600")
    try:
        data = json.loads(get(url, timeout=40))
    except Exception:
        return []
    out = []
    for pg in (data.get("query") or {}).get("pages", {}).values():
        ii = (pg.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata") or {}
        out.append({
            "title": pg.get("title", ""),
            "w": ii.get("width", 0), "h": ii.get("height", 0),
            "url": ii.get("thumburl") or ii.get("url"),
            "license": (meta.get("LicenseShortName") or {}).get("value", ""),
        })
    return out


def save(url: str, dest: Path) -> bool:
    try:
        raw = get(url)
    except Exception:
        return False
    if len(raw) < 15000:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.jpg")
    tmp.write_bytes(raw)
    try:
        im = Image.open(tmp)
        im.verify()
        im = Image.open(tmp).convert("RGB")
        # recorte cuadrado-ish para las tarjetas de piloto
        im.save(dest, "JPEG", quality=88, optimize=True, progressive=True)
    except Exception:
        tmp.unlink(missing_ok=True)
        return False
    tmp.unlink(missing_ok=True)
    return True


def pick_team(display: str, keys: list[str], season: int) -> list[dict]:
    cands: list[dict] = []
    queries = [
        f"{display} {season} Grand Prix",
        f"{display} {season - 1} Grand Prix",
        f"{display} Formula One {season - 1}",
    ]
    for q in queries:
        for c in search(q, 12):
            t = c["title"].lower()
            if c["w"] < 1200 or c["h"] < 600:
                continue
            if c["w"] / max(c["h"], 1) < 1.3:
                continue
            if any(k in t for k in ("logo", "map", "safety", "medical", "helmet", "garage",
                                     "paddock", "pit lane", "pitlane", "poster", "ticket")):
                continue
            if not any(k.lower() in t for k in keys):
                continue
            if c["url"] and c["url"] not in [x["url"] for x in cands]:
                cands.append(c)
        if len(cands) >= 4:
            break
    return cands


def pick_driver(name: str, last: str, season: int) -> list[dict]:
    cands: list[dict] = []
    for q in (f"{name} {season} Grand Prix", f"{name} {season - 1} Grand Prix",
              f"{name} {season - 1} Formula One", f"{name} Formula One"):
        for c in search(q, 12):
            t = c["title"].lower()
            if c["w"] < 900 or c["h"] < 900:
                continue
            ratio = c["w"] / max(c["h"], 1)
            if not 0.55 <= ratio <= 1.6:
                continue
            if last.lower() not in t:
                continue
            if any(k in t for k in ("signature", "autograph", "logo", "helmet", "car", "statue")):
                continue
            if c["url"] and c["url"] not in [x["url"] for x in cands]:
                cands.append(c)
        if len(cands) >= 3:
            break
    return cands


def main() -> None:
    do_drivers = "--drivers" in sys.argv or "--all" in sys.argv or len(sys.argv) == 1
    do_teams = "--teams" in sys.argv or "--all" in sys.argv or len(sys.argv) == 1
    season = 2026
    report = {"teams": {}, "drivers": {}}

    if do_teams:
        for tid, (display, keys) in TEAMS.items():
            dest = ASSETS / "teams" / f"{tid}-car.jpg"
            cands = pick_team(display, keys, season)
            saved = None
            for c in cands[:4]:
                if save(c["url"], dest):
                    saved = c
                    break
            report["teams"][tid] = {"saved": bool(saved), "file": str(dest.relative_to(ROOT)),
                                    "title": saved["title"] if saved else "",
                                    "license": saved["license"] if saved else ""}
            print(f"[team] {tid:<14} {'OK  ' + saved['title'][:70] if saved else 'sin foto'}", flush=True)
            time.sleep(0.6)

    if do_drivers:
        for did, (name, last) in DRIVERS.items():
            dest = ASSETS / "drivers" / f"{did}.jpg"
            cands = pick_driver(name, last, season)
            saved = None
            for c in cands[:4]:
                if save(c["url"], dest):
                    saved = c
                    break
            report["drivers"][did] = {"saved": bool(saved), "file": str(dest.relative_to(ROOT)),
                                      "title": saved["title"] if saved else "",
                                      "license": saved["license"] if saved else ""}
            print(f"[driver] {did:<16} {'OK  ' + saved['title'][:64] if saved else 'sin foto'}", flush=True)
            time.sleep(0.6)

    out = ROOT / "src" / "data" / "photos_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("informe:", out)


if __name__ == "__main__":
    main()
