# custom_components/ginko/const.py
from __future__ import annotations

DOMAIN = "ginko"

CONF_API_KEY = "api_key"
CONF_MODE = "mode"
CONF_NOM = "nom"
CONF_NB_PASSAGES = "nb_passages"
CONF_ITEMS = "items"
CONF_ID_LIGNE = "id_ligne"
CONF_SENS_ALLER = "sens_aller"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_SCAN_INTERVAL = "scan_interval"

SCAN_INTERVAL_AUTO      = 0   # détection automatique (tram 10 s / bus 30 s)
SCAN_INTERVAL_TRAM      = 10  # tram : recalcul API toutes les 10 s
SCAN_INTERVAL_BUS_LIEU  = 30  # bus en mode lieu / proximité : recalcul API toutes les 30 s
SCAN_INTERVAL_BUS_SUIVI = 15  # bus en mode suivi position

DEFAULT_SCAN_INTERVAL = SCAN_INTERVAL_AUTO   # 0 = auto par défaut
MIN_SCAN_INTERVAL     = 0                    # 0 = auto
MAX_SCAN_INTERVAL     = 300

MODE_LIEU        = "lieu"
MODE_LISTE       = "liste"
MODE_PERSON      = "person_proximity"
MODE_LIGNE       = "ligne"
MODE_SUIVI_LIGNE = "suivi_ligne"

DEFAULT_SCAN_INTERVAL_SUIVI = SCAN_INTERVAL_AUTO  # 0 = auto (tram 10 s / bus 15 s)

CONF_ID_LIGNE_SUIVI  = "id_ligne"
CONF_NUM_LIGNE_SUIVI = "num_ligne"
CONF_NOM_LIGNE_SUIVI = "nom_ligne"

CONF_PERSON_ENTITY = "person_entity_id"
CONF_MAX_STOPS     = "max_stops"
DEFAULT_MAX_STOPS  = 5

# État d'une ligne renvoyé par /TR/getEtatLignes.do (champ « etat »).
# Correspondance officielle avec les pictos/couleurs de l'app Ginko :
#   0 — pas de couleur / pas de picto : aucune information sur l'état
#       (ex. lignes TAD, transport à la demande)
#   1 — vert (check)      : la ligne fonctionne normalement
#   2 — bleu (info)       : une information concerne la ligne (nouveauté, évolution)
#   3 — gris (croix)      : la ligne ne circule pas en ce moment, selon sa période
#                           de fonctionnement (hors horaires / hors service)
#   4 — gris (attention)  : une perturbation est prévue dans le futur
#   5 — orange (attention): une perturbation est en cours
#   6 — rouge (croix)     : la circulation de la ligne est totalement interrompue
ETAT_LABELS = {
    0: "Pas d'information",
    1: "Normal",
    2: "Information",
    3: "Hors service",
    4: "Perturbation prévue",
    5: "Perturbation en cours",
    6: "Circulation interrompue",
}

# Métadonnées d'affichage par état : libellé long, couleur (hex), icône mdi,
# et drapeaux utiles pour filtrer/compter.
#   perturbation_active  : perturbation réellement en cours ou ligne interrompue
#   perturbation_prevue  : perturbation planifiée dans le futur
ETAT_META = {
    0: {
        "label": "Pas d'information",
        "description": "Aucune information sur l'état (ex. lignes à la demande).",
        "couleur": None,
        "icon": "mdi:bus",
        "perturbation_active": False,
        "perturbation_prevue": False,
    },
    1: {
        "label": "Normal",
        "description": "La ligne fonctionne normalement.",
        "couleur": "#2E7D32",
        "icon": "mdi:check-circle",
        "perturbation_active": False,
        "perturbation_prevue": False,
    },
    2: {
        "label": "Information",
        "description": "Une information concerne la ligne (nouveauté, évolution).",
        "couleur": "#1976D2",
        "icon": "mdi:information",
        "perturbation_active": False,
        "perturbation_prevue": False,
    },
    3: {
        "label": "Hors service",
        "description": "La ligne ne circule pas en ce moment, selon sa période de fonctionnement.",
        "couleur": "#9E9E9E",
        "icon": "mdi:close-circle",
        "perturbation_active": False,
        "perturbation_prevue": False,
    },
    4: {
        "label": "Perturbation prévue",
        "description": "Une perturbation est prévue dans le futur.",
        "couleur": "#9E9E9E",
        "icon": "mdi:alert",
        "perturbation_active": False,
        "perturbation_prevue": True,
    },
    5: {
        "label": "Perturbation en cours",
        "description": "Une perturbation est en cours.",
        "couleur": "#F57C00",
        "icon": "mdi:alert",
        "perturbation_active": True,
        "perturbation_prevue": False,
    },
    6: {
        "label": "Circulation interrompue",
        "description": "La circulation de la ligne est totalement interrompue.",
        "couleur": "#D32F2F",
        "icon": "mdi:close-octagon",
        "perturbation_active": True,
        "perturbation_prevue": False,
    },
}


def etat_meta(etat: int | None) -> dict:
    """Renvoie les métadonnées d'un état, avec repli sûr si l'état est inconnu."""
    if etat in ETAT_META:
        return ETAT_META[etat]
    return {
        "label": "Inconnu",
        "description": "État non reconnu.",
        "couleur": None,
        "icon": "mdi:help-circle",
        "perturbation_active": False,
        "perturbation_prevue": False,
    }
