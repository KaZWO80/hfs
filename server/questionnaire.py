"""Definition des Fragebogens zum Haushaltsführungsschaden (HFS).

Die Inhalte entsprechen dem Word-Fragebogen in ``unterlagen/``.
Das Frontend lädt diese Definition über ``GET /api/fragebogen``,
damit Fragen und Excel-Zuordnung nur an einer Stelle gepflegt werden.
"""

# Tätigkeiten: key, Bezeichnung im Fragebogen, Zeile im Excel-Blatt "HFS"
# (Spalte B = wöchentlicher Aufwand), Hinweis für ein Detailfeld.
TAETIGKEITEN = [
    {"key": "staubsaugen", "label": "Staubsaugen", "hfs_row": 10},
    {"key": "boden_wischen", "label": "Boden wischen", "hfs_row": 11},
    {"key": "fenster_putzen", "label": "Fenster putzen", "hfs_row": 12},
    {"key": "staub_wischen", "label": "Staub wischen", "hfs_row": 13},
    {"key": "bad_putzen", "label": "Bad putzen", "hfs_row": 14},
    {"key": "bad_feucht", "label": "Bad feucht reinigen", "hfs_row": 15},
    {"key": "aufraeumen", "label": "Aufräumen", "hfs_row": 16},
    {"key": "geschirr_abwaschen", "label": "Geschirr abwaschen", "hfs_row": 17},
    {"key": "geschirr_abtrocknen", "label": "Geschirr abtrocknen", "hfs_row": 18},
    {"key": "geschirr_einraeumen", "label": "Geschirr einräumen", "hfs_row": 19},
    {"key": "kochen", "label": "Kochen", "hfs_row": 20},
    # Excel trennt "Wäsche waschen" (21) und "Wäsche aufhängen" (22);
    # der Fragebogen fragt beides zusammen ab -> Zeile 21.
    {"key": "waesche_waschen", "label": "Wäsche waschen und aufhängen", "hfs_row": 21},
    {"key": "waesche_buegeln", "label": "Wäsche bügeln", "hfs_row": 23},
    {"key": "betten_machen", "label": "Betten machen", "hfs_row": 24},
    {"key": "einkaufen", "label": "Einkaufen", "hfs_row": 25},
    {"key": "muell", "label": "Müll entsorgen", "hfs_row": 26},
    {"key": "autopflege", "label": "Autopflege", "hfs_row": 27},
    {"key": "gartenpflege", "label": "Gartenpflege", "hfs_row": 28, "detail": "konkret:"},
    {"key": "kinderbetreuung", "label": "Kinderbetreuung", "hfs_row": 29, "detail": "von:"},
    {"key": "betreuung_angehoerige", "label": "Betreuung naher Angehöriger", "hfs_row": 30, "detail": "von:"},
    {"key": "korrespondenz", "label": "Korrespondenz mit Ämtern, Stellen", "hfs_row": 31},
    {"key": "haustier", "label": "Versorgung Haustier", "hfs_row": 32, "detail": "Art:"},
    {"key": "sonstiges", "label": "Sonstiges, nicht aufgeführt", "hfs_row": 34, "detail": "was:"},
]

GERAETE = [
    {"key": "mikrowelle", "label": "Mikrowelle"},
    {"key": "staubsauger", "label": "Staubsauger"},
    {"key": "staubsauger_roboter", "label": "Staubsauger-Roboter"},
    {"key": "kuechenmaschine", "label": "Küchenmaschine"},
    {"key": "waschmaschine", "label": "Waschmaschine"},
    {"key": "trockner", "label": "Trockner"},
    {"key": "spuelmaschine", "label": "Spülmaschine"},
    {"key": "rasenmaeher", "label": "Rasenmäher"},
    {"key": "aufsitz_rasenmaeher", "label": "Aufsitz-Rasenmäher"},
    {"key": "heckenschere", "label": "elektrische Heckenschere"},
    {"key": "rasensprenger", "label": "Rasensprenger"},
]

TAETIGKEIT_KEYS = {t["key"] for t in TAETIGKEITEN}
GERAET_KEYS = {g["key"] for g in GERAETE}

# Das Excel-Blatt "HFS" hat vier Zeilen (2-5) für gestaffelte Beeinträchtigung.
MAX_STAFFELN = 4


def definition() -> dict:
    return {
        "taetigkeiten": [
            {k: v for k, v in t.items() if k != "hfs_row"} for t in TAETIGKEITEN
        ],
        "geraete": GERAETE,
        "max_staffeln": MAX_STAFFELN,
    }
