# -*- coding: utf-8 -*-
"""French geography normalization for Crab-1 reward.

Purpose: the city/location ground truth in this project is inconsistent across
datasets — the eval set stores *communes* (PARIS, LYON, VILLEJUIF), while the
training lake stores a mix of *departments* (Val-de-Marne, Yvelines) and even
whole *regions* (Auvergne-Rhône-Alpes, Occitanie). The only granularity every
label can be mapped to truthfully is the **department**.

The official registry (recherche-entreprises.api.gouv.fr) returns the exact
`siege.departement` code for a company (e.g. "75", "2B", "971"). We use that as
the source of truth to derive the department for both the ground truth and the
agent's own registry lookup. No commune→department pairs are fabricated: a
department code either comes straight from the registry, or from parsing a
string that already *is* a department name/code.

`resolve_to_dept_code(s)` maps any string that is a department name, a
department code, or the special case "Paris" to its 2-3 char department code.
Communes that are not also department names (e.g. "Villejuif") do NOT resolve
here — that is intentional: we score at department granularity, so the teacher
and student emit department names (from the registry), which round-trip cleanly.
"""

import re
import unicodedata

# Canonical department code -> department name (métropole incl. Corsica 2A/2B,
# DOM 971-976, and the main COM codes). Names are the usual INSEE labels.
DEPT_NAME = {
    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes", "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes",
    "09": "Ariège", "10": "Aube", "11": "Aude", "12": "Aveyron",
    "13": "Bouches-du-Rhône", "14": "Calvados", "15": "Cantal", "16": "Charente",
    "17": "Charente-Maritime", "18": "Cher", "19": "Corrèze", "2A": "Corse-du-Sud",
    "2B": "Haute-Corse", "21": "Côte-d'Or", "22": "Côtes-d'Armor", "23": "Creuse",
    "24": "Dordogne", "25": "Doubs", "26": "Drôme", "27": "Eure",
    "28": "Eure-et-Loir", "29": "Finistère", "30": "Gard", "31": "Haute-Garonne",
    "32": "Gers", "33": "Gironde", "34": "Hérault", "35": "Ille-et-Vilaine",
    "36": "Indre", "37": "Indre-et-Loire", "38": "Isère", "39": "Jura",
    "40": "Landes", "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire",
    "44": "Loire-Atlantique", "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne",
    "48": "Lozère", "49": "Maine-et-Loire", "50": "Manche", "51": "Marne",
    "52": "Haute-Marne", "53": "Mayenne", "54": "Meurthe-et-Moselle", "55": "Meuse",
    "56": "Morbihan", "57": "Moselle", "58": "Nièvre", "59": "Nord",
    "60": "Oise", "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dôme",
    "64": "Pyrénées-Atlantiques", "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales",
    "67": "Bas-Rhin", "68": "Haut-Rhin", "69": "Rhône", "70": "Haute-Saône",
    "71": "Saône-et-Loire", "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie",
    "75": "Paris", "76": "Seine-Maritime", "77": "Seine-et-Marne", "78": "Yvelines",
    "79": "Deux-Sèvres", "80": "Somme", "81": "Tarn", "82": "Tarn-et-Garonne",
    "83": "Var", "84": "Vaucluse", "85": "Vendée", "86": "Vienne",
    "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne", "90": "Territoire de Belfort",
    "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne", "95": "Val-d'Oise",
    "971": "Guadeloupe", "972": "Martinique", "973": "Guyane",
    "974": "La Réunion", "975": "Saint-Pierre-et-Miquelon", "976": "Mayotte",
    "977": "Saint-Barthélemy", "978": "Saint-Martin",
    "984": "Terres australes et antarctiques françaises",
    "986": "Wallis-et-Futuna", "987": "Polynésie française", "988": "Nouvelle-Calédonie",
}

# INSEE region code -> region name (used only for optional sanity logging).
REGION_NAME = {
    "01": "Guadeloupe", "02": "Martinique", "03": "Guyane", "04": "La Réunion",
    "06": "Mayotte", "11": "Île-de-France", "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté", "28": "Normandie", "32": "Hauts-de-France",
    "44": "Grand Est", "52": "Pays de la Loire", "53": "Bretagne",
    "75": "Nouvelle-Aquitaine", "76": "Occitanie", "84": "Auvergne-Rhône-Alpes",
    "93": "Provence-Alpes-Côte d'Azur", "94": "Corse",
}

# département code -> region name (métropole + DOM).
_DEPT_TO_REGION = {}
for _c in list(DEPT_NAME):
    pass  # filled below via explicit table


def _strip(s: str) -> str:
    """Lowercase, strip accents, collapse separators to single spaces."""
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.sub(r"[\s\-'’_.]+", " ", s)
    return s.strip()


# Normalized department name -> code (inverse of DEPT_NAME). Built once.
_CODE_BY_NAME = {_strip(name): code for code, name in DEPT_NAME.items()}


def resolve_to_dept_code(s):
    """Return the 2-3 char department code for a string, or None.

    Deliberately strict, to avoid false positives: a *region* name like
    "Auvergne-Rhône-Alpes" or "Pays de la Loire" contains a department name as a
    substring ("Rhône", "Loire") and must NOT resolve to that department. So we
    accept only two unambiguous forms:

      * an exact department code — "75", "2A", "971"
      * an exact department name — "Val-de-Marne", "Rhône", "Paris"

    Everything else (regions, bare communes, postal codes) returns None. This is
    fine because the authoritative expected department comes from the registry
    (``department_code``), and the teacher/student emit clean department names.
    """
    if not s:
        return None
    raw = str(s).strip()

    # Exact department-code form: 2A/2B, 2-digit, or 3-digit DOM/COM.
    if re.fullmatch(r"2[ab]|\d{2,3}", raw, flags=re.IGNORECASE):
        code = raw.upper()
        if code in DEPT_NAME:
            return code

    # Exact department-name match (accent/case/separator-insensitive).
    return _CODE_BY_NAME.get(_strip(raw))


def resolve_to_region(s):
    """Return the region name for a string, or None.

    Accepts a department name/code (-> its region), the special commune "Paris"
    (-> Île-de-France), or a region name (-> itself). A bare commune that is not
    a department returns None.
    """
    if not s:
        return None
    dep = resolve_to_dept_code(s)
    if dep:
        return region_from_dept(dep)
    norm = _strip(s)
    for rname in set(list(REGION_NAME.values()) + list(_DEPT_TO_REGION.values())):
        if _strip(rname) == norm:
            return rname
    return None


def dept_name(code):
    """Human-readable department name for a code (or the code if unknown)."""
    return DEPT_NAME.get(str(code).upper(), str(code)) if code else None


def region_from_dept(code):
    """Region name for a department code, or None."""
    return _DEPT_TO_REGION.get(str(code).upper()) if code else None


# ---- Build département -> region table (explicit, truthful) -----------------
def _fill_regions():
    reg = {
        "Île-de-France": ["75", "77", "78", "91", "92", "93", "94", "95"],
        "Centre-Val de Loire": ["18", "28", "36", "37", "41", "45"],
        "Bourgogne-Franche-Comté": ["21", "25", "39", "58", "70", "71", "89", "90"],
        "Normandie": ["14", "27", "50", "61", "76"],
        "Hauts-de-France": ["02", "59", "60", "62", "80"],
        "Grand Est": ["08", "10", "51", "52", "54", "55", "57", "67", "68", "88"],
        "Pays de la Loire": ["44", "49", "53", "72", "85"],
        "Bretagne": ["22", "29", "35", "56"],
        "Nouvelle-Aquitaine": ["16", "17", "19", "23", "24", "33", "40", "47",
                                "64", "79", "86", "87"],
        "Occitanie": ["09", "11", "12", "30", "31", "32", "34", "46", "48",
                      "65", "66", "81", "82"],
        "Auvergne-Rhône-Alpes": ["01", "03", "07", "15", "26", "38", "42", "43",
                                 "63", "69", "73", "74"],
        "Provence-Alpes-Côte d'Azur": ["04", "05", "06", "13", "83", "84"],
        "Corse": ["2A", "2B"],
        "Guadeloupe": ["971"], "Martinique": ["972"], "Guyane": ["973"],
        "La Réunion": ["974"], "Mayotte": ["976"],
    }
    for region, codes in reg.items():
        for c in codes:
            _DEPT_TO_REGION[c] = region


_fill_regions()
