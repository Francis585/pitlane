# Pitlane

Sitio independiente sobre la Fórmula 1: las once escuderías, su historia, su plantilla y su actualidad,
más calendario y clasificación de la temporada en curso. Sin relación con la FIA, la FOM ni ningún equipo.

**En producción:** https://pitlane-ruddy.vercel.app

## Cómo funciona

Todo el contenido se genera automáticamente en cada compilación. No hay base de datos ni CMS.

```
scripts/fetch_data.py   →  descarga datos, fotos y titulares, y escribe src/data/site.json
build.py                →  renderiza 43 páginas estáticas con Jinja2 en public/
assets/                 →  CSS y JS sin dependencias
src/teams_meta.py       →  ficha curada de cada escudería (color, tipografía, layout, historia)
src/templates/          →  plantillas: base, portada, cuatro layouts de equipo, piloto, calendario…
```

```bash
python build.py --fetch     # actualiza datos y compila
python build.py             # solo compila con los datos ya descargados
```

## Fuentes

| Dato | Fuente |
|---|---|
| Calendario, clasificaciones, resultados | [Jolpica F1 API](https://api.jolpi.ca/ergast/) |
| Retratos y biografías | Wikipedia / Wikimedia Commons (CC BY-SA) |
| Titulares | RSS de The Race, Motorsport.com, Autosport, Crash.net, ESPN, RaceFans y Motorsport Week |

## Personalización por escudería

Cada equipo tiene su propio tratamiento visual, no solo un cambio de color:

- **Herencia editorial** — Ferrari, Williams: fondo cálido, serif, composición centrada.
- **Panel de datos** — Mercedes, Red Bull, Audi: rejilla técnica, monoespaciada, tabla de datos.
- **Cartel contemporáneo** — McLaren, Aston Martin, Alpine: color a sangre y tipografía a gritos.
- **Brutalismo de garaje** — Haas, Racing Bulls, Cadillac: bordes duros, números enormes, rayas.

El layout se declara en `src/teams_meta.py` (`"layout": "clasico" | "tecnico" | "moderno" | "rebelde"`),
la identidad visual en `brand`, `brand2` y `font`.

## Despliegue

Static en Vercel (`outputDirectory: public`). El flujo de trabajo
`.github/workflows/refresh.yml` reconstruye y publica a diario.

## Aviso

Proyecto personal, informativo y no oficial. Las marcas citadas pertenecen a sus titulares.
