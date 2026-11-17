# Pitlane

Sitio independiente sobre la Fórmula 1: las once escuderías, su historia, su plantilla y su actualidad,
más calendario y clasificación de la temporada en curso. Sin relación con la FIA, la FOM ni ningún equipo.

**En producción:** https://pitlane-ruddy.vercel.app  

## Cero mantenimiento entre temporadas

- La temporada se detecta sola: el año en curso si la API ya publica calendario, el anterior en pretemporada.
- Las escuderías que no estén curadas en `src/teams_meta.py` reciben ficha, color, layout y patrón automáticos.
- Cada circuito desconocido usa la paleta neutra de `src/races_meta.py`.
- Las imágenes caducan a los 10 días y se vuelven a descargar, así se renuevan con las fotos nuevas.
- Si la API falla, la descarga avisa y el sitio se compila con los últimos datos guardados.

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
| Fotos de circuitos | Wikipedia, con filtro automático que descarta mapas y escudos |

## Semana de Gran Premio

Mientras dura la semana de una carrera (del lunes anterior al día del GP), el sitio cambia de acento:
el color y el patrón salen de `src/races_meta.py` para ese circuito, aparece una cinta con el GP y el
calendario resalta la cita. Fuera de esa ventana vuelve solo al tema neutro — y si el HTML es más
antiguo que el calendario, `app.js` retira el tema en el navegador.

## Personalización por escudería

Cada equipo tiene su propio tratamiento visual, no solo un cambio de color:

- **Herencia editorial** — Ferrari, Williams: fondo cálido, serif, composición centrada.
- **Panel de datos** — Mercedes, Red Bull, Audi: rejilla técnica, monoespaciada, tabla de datos.
- **Cartel contemporáneo** — McLaren, Aston Martin, Alpine: color a sangre y tipografía a gritos.
- **Brutalismo de garaje** — Haas, Racing Bulls, Cadillac: bordes duros, números enormes, rayas.

Además de los colores, cada escudería lleva un patrón propio (`stripe`, `hex`, `arcs`, `chevrons`,
`rays`, `grid`, `shield`, `wings`) y su propia tipografía de titular.

El layout se declara en `src/teams_meta.py` (`"layout": "clasico" | "tecnico" | "moderno" | "rebelde"`),
la identidad visual en `brand`, `brand2` y `font`.

## Despliegue

Static en Vercel (`outputDirectory: public`). El flujo de trabajo
`.github/workflows/refresh.yml` reconstruye y publica a diario.

## Aviso

Proyecto personal, informativo y no oficial. Las marcas citadas pertenecen a sus titulares.
