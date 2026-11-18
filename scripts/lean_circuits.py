"""Descarga rápida de fotos aéreas de circuitos: una búsqueda y una descarga por circuito."""
import importlib
import json
import pathlib
import sys
import time

sys.path.insert(0, "C:/Users/Usuario/Desktop/pitlane/scripts")
import fetch_data as fd
importlib.reload(fd)

ROOT = pathlib.Path("C:/Users/Usuario/Desktop/pitlane")
SITE = ROOT / "src" / "data" / "site.json"
data = json.loads(SITE.read_text(encoding="utf-8"))

for c in data["circuits"]:
    dest = ROOT / "assets" / "circuits" / f"{c['id']}.jpg"
    if dest.exists() and dest.stat().st_size > 15000:
        continue
    got = None
    for query in (f"{c['name']} aerial", f"{c['locality']} circuit aerial"):
        results = fd.commons_search(query, limit=6)
        if not results:
            time.sleep(1.0)
            continue
        for _title, url in results[:2]:
            try:
                img = fd.get(url, timeout=45)
            except Exception:
                continue
            if len(img) < 15000:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            probe = dest.with_suffix(".probe.webp")
            probe.write_bytes(img)
            if fd.is_photo(probe) and fd.brightness(probe) >= 40:
                probe.replace(dest)
                got = True
                break
            probe.unlink(missing_ok=True)
        if got:
            break
        time.sleep(1.0)
    print("circuito", c["id"], bool(got), flush=True)
    time.sleep(0.6)

# guardar rutas en los datos
for c in data["circuits"]:
    dest = ROOT / "assets" / "circuits" / f"{c['id']}.jpg"
    if dest.exists():
        c["photo"] = f"assets/circuits/{c['id']}.jpg"

SITE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("fin: ", sum(1 for c in data["circuits"] if c.get("photo")), "con foto")
