"""Refresco puntual: fotos aéreas de circuitos y coches que salieron flojos."""
import importlib
import json
import pathlib
import shutil
import sys

sys.path.insert(0, "C:/Users/Usuario/Desktop/pitlane/scripts")
import fetch_data as fd
importlib.reload(fd)

ROOT = pathlib.Path("C:/Users/Usuario/Desktop/pitlane")
SITE = ROOT / "src" / "data" / "site.json"

data = json.loads(SITE.read_text(encoding="utf-8"))

# 1) circuitos: foto aérea real
shutil.rmtree(ROOT / "assets" / "circuits", ignore_errors=True)
for c in data["circuits"]:
    photo = fd.circuit_photo({"id": c["id"], "name": c["name"], "locality": c["locality"],
                              "gp": c["gp"], "wiki": c["wiki"]})
    c["photo"] = photo
    print("circuito", c["id"], bool(photo), flush=True)

# 2) coches con foto mejor: fuera pit lane y camiones
EXTRA = {
    "rb": ["Racing Bulls 2026 Grand Prix on track", "Racing Bulls F1 2026", "VCARB 2026"],
    "mclaren": ["McLaren 2026 Grand Prix on track", "McLaren MCL40 2026", "McLaren 2026 F1"],
}
for tid, queries in EXTRA.items():
    dest = ROOT / "assets" / "teams" / f"{tid}-car.jpg"
    dest.unlink(missing_ok=True)
    ok = fd.best_from_queries(queries, dest, min_bright=55)
    print("coche", tid, ok, flush=True)
    for t in data["teams"]:
        if t["id"] == tid:
            t["car"] = f"assets/teams/{tid}-car.jpg" if ok else t.get("car")

SITE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("LISTO", flush=True)
