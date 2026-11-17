"""Paleta y personalidad de cada gran premio.

Se usa para la «semana de Gran Premio»: mientras dura la semana de ese GP, las partes
globales del sitio (portada, calendario, clasificación, noticias) adoptan el color y el
patrón de ese circuito. Fuera de la semana, el sitio vuelve a su tema neutro.

La clave es el `circuitId` de la API, así que sobrevive a cambios de calendario.
"""

RACES = {
    "albert_park": {
        "gp": "Australia", "city": "Melbourne", "brand": "#00A19C", "brand2": "#FFC72C",
        "pattern": "arcs", "vibe": "Verde lago y sol austral",
    },
    "shanghai": {
        "gp": "China", "city": "Shanghái", "brand": "#D7282F", "brand2": "#F4D35E",
        "pattern": "grid", "vibe": "Rojo lacado y oro imperial",
    },
    "suzuka": {
        "gp": "Japón", "city": "Suzuka", "brand": "#E4002B", "brand2": "#F5F5F5",
        "pattern": "rays", "vibe": "Rojo hinomaru sobre blanco",
    },
    "miami": {
        "gp": "Miami", "city": "Miami", "brand": "#FF2E93", "brand2": "#00E5FF",
        "pattern": "stripes", "vibe": "Neón pastel de South Beach",
    },
    "villeneuve": {
        "gp": "Canadá", "city": "Montreal", "brand": "#E63946", "brand2": "#F1FAEE",
        "pattern": "arcs", "vibe": "Rojo maple y niebla del San Lorenzo",
    },
    "monaco": {
        "gp": "Mónaco", "city": "Monte Carlo", "brand": "#C8A24C", "brand2": "#E10600",
        "pattern": "shield", "vibe": "Oro, mármol y lujo portuario",
    },
    "catalunya": {
        "gp": "Barcelona", "city": "Barcelona", "brand": "#F5A623", "brand2": "#D64545",
        "pattern": "grid", "vibe": "Naranja y sol mediterráneo",
    },
    "red_bull_ring": {
        "gp": "Austria", "city": "Spielberg", "brand": "#E10600", "brand2": "#F5F5F5",
        "pattern": "chevrons", "vibe": "Rojo alpino entre montañas",
    },
    "silverstone": {
        "gp": "Gran Bretaña", "city": "Silverstone", "brand": "#1B5FAA", "brand2": "#E4002B",
        "pattern": "stripes", "vibe": "Azul y rojo de la Union Jack",
    },
    "spa": {
        "gp": "Bélgica", "city": "Spa", "brand": "#F5C518", "brand2": "#E10600",
        "pattern": "rays", "vibe": "Amarillo y rojo entre pinos",
    },
    "hungaroring": {
        "gp": "Hungría", "city": "Budapest", "brand": "#1E7B4F", "brand2": "#CE2939",
        "pattern": "chevrons", "vibe": "Verde y rojo del Danubio",
    },
    "zandvoort": {
        "gp": "Países Bajos", "city": "Zandvoort", "brand": "#FF6B00", "brand2": "#21468B",
        "pattern": "stripes", "vibe": "Naranja de la marea neerlandesa",
    },
    "monza": {
        "gp": "Italia", "city": "Monza", "brand": "#008C45", "brand2": "#CD212A",
        "pattern": "shield", "vibe": "Verde, blanco y rojo al rojo vivo",
    },
    "madring": {
        "gp": "Madrid", "city": "Madrid", "brand": "#E4572E", "brand2": "#F5C518",
        "pattern": "grid", "vibe": "Terrazo madrileño y oro",
    },
    "baku": {
        "gp": "Azerbaiyán", "city": "Bakú", "brand": "#00B5A5", "brand2": "#E4002B",
        "pattern": "arcs", "vibe": "Verde mar Caspio y granada",
    },
    "sepang": {
        "gp": "Malasia", "city": "Kuala Lumpur", "brand": "#F5C518", "brand2": "#0B0B0B",
        "pattern": "rays", "vibe": "Amarillo y negro bajo el calor",
    },
    "marina_bay": {
        "gp": "Singapur", "city": "Marina Bay", "brand": "#E4002B", "brand2": "#00E5FF",
        "pattern": "grid", "vibe": "Neón nocturno de Marina Bay",
    },
    "americas": {
        "gp": "Estados Unidos", "city": "Austin", "brand": "#1B4B9A", "brand2": "#E4002B",
        "pattern": "stripes", "vibe": "Azul tejano y rojo de barra",
    },
    "rodriguez": {
        "gp": "México", "city": "Ciudad de México", "brand": "#006847", "brand2": "#CE1126",
        "pattern": "arcs", "vibe": "Verde, blanco y rojo de altura",
    },
    "interlagos": {
        "gp": "Brasil", "city": "São Paulo", "brand": "#FFDF00", "brand2": "#009C3B",
        "pattern": "chevrons", "vibe": "Amarillo y verde de Interlagos",
    },
    "vegas": {
        "gp": "Las Vegas", "city": "Las Vegas", "brand": "#B026FF", "brand2": "#00E5FF",
        "pattern": "rays", "vibe": "Neón violeta en el Strip",
    },
    "losail": {
        "gp": "Catar", "city": "Lusail", "brand": "#8A1538", "brand2": "#C8A24C",
        "pattern": "grid", "vibe": "Granate y oro del desierto",
    },
    "yas_marina": {
        "gp": "Abu Dabi", "city": "Yas Marina", "brand": "#00A19C", "brand2": "#E8B93B",
        "pattern": "arcs", "vibe": "Turquesa y oro al atardecer",
    },
}

DEFAULT = {"gp": "Fórmula 1", "city": "", "brand": "#ff5a1f", "brand2": "#e8e8e8",
           "pattern": "stripes", "vibe": "Tema neutro"}
