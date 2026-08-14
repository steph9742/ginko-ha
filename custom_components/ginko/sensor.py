# custom_components/ginko/sensor.py
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_NOM,
    CONF_NB_PASSAGES,
    CONF_ITEMS,
    CONF_ID_LIGNE,
    CONF_SENS_ALLER,
    CONF_API_KEY,
    CONF_PERSON_ENTITY,
    MODE_LIEU,
    MODE_LISTE,
    MODE_PERSON,
    MODE_LIGNE,
    MODE_SUIVI_LIGNE,
    CONF_ID_LIGNE_SUIVI,
    CONF_NUM_LIGNE_SUIVI,
    CONF_NOM_LIGNE_SUIVI,
    etat_meta,
)
from .coordinator import (
    GinkoCoordinator,
    GinkoInfoCoordinator,
    GinkoPersonProximityCoordinator,
    GinkoSuiviLigneCoordinator,
)

_LOGGER = logging.getLogger(__name__)


def _color(value: str | None) -> str | None:
    """Normalise une couleur hex API ('00A5C2') en couleur CSS ('#00A5C2')."""
    if not value:
        return None
    value = str(value).strip()
    return value if value.startswith("#") else f"#{value}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GinkoCoordinator = hass.data[DOMAIN][entry.entry_id]
    entry_data = entry.data["entry"]
    entities: list[SensorEntity] = []

    if entry_data["mode"] == MODE_LIEU:
        entities.append(GinkoLieuSensor(coordinator, entry))
    elif entry_data["mode"] == MODE_LISTE:
        for item in entry_data[CONF_ITEMS]:
            entities.append(GinkoListeSensor(coordinator, entry, item))
    elif entry_data["mode"] == MODE_PERSON:
        entities.append(GinkoPersonProximitySensor(coordinator, entry))
    elif entry_data["mode"] == MODE_LIGNE:
        entities.append(GinkoLigneEtatSensor(coordinator, entry))
        entities.append(GinkoLigneMessagesSensor(coordinator, entry))
    elif entry_data["mode"] == MODE_SUIVI_LIGNE:
        entities.append(GinkoSuiviLigneSensor(coordinator, entry))

    # Info sensors — créés une seule fois, par l'entrée "propriétaire".
    # On stocke l'entry_id du propriétaire dans hass.data pour survivre aux reloads
    # partiels (un seul entry rechargé ne perturbe pas les autres).
    info_key    = f"_info_{entry.data[CONF_API_KEY]}"
    owner_key   = f"_info_sensors_owner_{entry.data[CONF_API_KEY]}"
    info_coordinator: GinkoInfoCoordinator | None = hass.data[DOMAIN].get(info_key)
    owner = hass.data[DOMAIN].get(owner_key)
    if info_coordinator and (owner is None or owner == entry.entry_id):
        hass.data[DOMAIN][owner_key] = entry.entry_id
        entities.append(GinkoEtatLignesSensor(info_coordinator))
        entities.append(GinkoMessagesSensor(info_coordinator))

    async_add_entities(entities, True)


# ---------------------------------------------------------------------------
# Passage sensors
# ---------------------------------------------------------------------------

class GinkoLieuSensor(CoordinatorEntity[GinkoCoordinator], SensorEntity):
    """All upcoming passages at a named stop (getTempsLieu)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "passages"
    _unrecorded_attributes = frozenset({MATCH_ALL})


    def __init__(self, coordinator: GinkoCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._nom: str = entry.data["entry"][CONF_NOM]
        self._attr_unique_id = f"ginko_{entry.entry_id}_lieu_{self._nom}"
        self._attr_name = f"Ginko {self._nom}"

    @property
    def native_value(self) -> int:
        passages = self._passages()
        return len(passages) if passages else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        passages = self._passages()
        return {
            "ginko_mode": "lieu",
            "passages": passages,
            "nom_arret": self._nom,
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._nom in (self.coordinator.data or {})

    def _passages(self) -> list:
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get(self._nom, [])


class GinkoListeSensor(CoordinatorEntity[GinkoCoordinator], SensorEntity):
    """Next passage for a specific stop/line/direction (getListeTemps)."""

    _attr_native_unit_of_measurement = "s"
    _unrecorded_attributes = frozenset({MATCH_ALL})


    def __init__(
        self,
        coordinator: GinkoCoordinator,
        entry: ConfigEntry,
        item: dict,
    ) -> None:
        super().__init__(coordinator)
        self._nom: str = item[CONF_NOM]
        self._id_ligne: str = item[CONF_ID_LIGNE]
        self._sens_aller: bool = item[CONF_SENS_ALLER]
        self._key = f"{self._nom}|{self._id_ligne}|{self._sens_aller}"
        sens_label = "aller" if self._sens_aller else "retour"
        self._attr_unique_id = f"ginko_{entry.entry_id}_{self._nom}_{self._id_ligne}_{sens_label}"
        self._attr_name = f"Ginko {self._nom} {self._id_ligne} {sens_label}"

    @property
    def native_value(self) -> int | None:
        passages = self._passages()
        if not passages:
            return None
        return passages[0].get("tempsEnSeconde")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        passages = self._passages()
        if not passages:
            return {}
        first = passages[0]
        return {
            "ginko_mode": "liste",
            "passages": passages,
            "nom_arret": self._nom,
            "id_ligne": self._id_ligne,
            "sens_aller": self._sens_aller,
            "temps": first.get("tempsHTML"),
            "destination": first.get("destination"),
            "fiable": first.get("fiable"),
            "numLignePublic": first.get("numLignePublic"),
            "couleurFond": first.get("couleurFond"),
            "couleurTexte": first.get("couleurTexte"),
            "typeDeTemps": first.get("typeDeTemps"),
            "deviation": first.get("typeDeTemps") == 2,
            "modeTransport": first.get("modeTransport"),
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._key in (self.coordinator.data or {})

    def _passages(self) -> list:
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get(self._key, [])


# ---------------------------------------------------------------------------
# Person proximity sensor
# ---------------------------------------------------------------------------

class GinkoPersonProximitySensor(CoordinatorEntity[GinkoPersonProximityCoordinator], SensorEntity):
    """Arrêts les plus proches d'une entité personne (via getArretsProches)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "arrêts"
    _attr_icon = "mdi:map-marker-radius"
    _unrecorded_attributes = frozenset({MATCH_ALL})


    def __init__(self, coordinator: GinkoPersonProximityCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        person_id = entry.data["entry"][CONF_PERSON_ENTITY]
        self._attr_unique_id = f"ginko_{entry.entry_id}_person_proximity"
        self._attr_name = f"Ginko proximité {person_id.split('.')[-1]}"

    @property
    def native_value(self) -> int:
        data = self.coordinator.data or {}
        return len(data.get("arrets", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "ginko_mode":   "proximity",
            "arrets":       data.get("arrets", []),
            "person_state": data.get("person_state"),
        }


# ---------------------------------------------------------------------------
# Per-line sensors
# ---------------------------------------------------------------------------

class GinkoLigneEtatSensor(CoordinatorEntity[GinkoInfoCoordinator], SensorEntity):
    """État en temps réel d'une ligne spécifique."""

    _attr_icon = "mdi:bus-alert"
    _unrecorded_attributes = frozenset({MATCH_ALL})


    def __init__(self, coordinator: GinkoInfoCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        ed = entry.data["entry"]
        self._id_ligne   = str(ed[CONF_ID_LIGNE_SUIVI])
        self._num_ligne  = ed[CONF_NUM_LIGNE_SUIVI]
        self._attr_unique_id = f"ginko_ligne_{self._id_ligne}_etat"
        self._attr_name      = f"Ginko Ligne {self._num_ligne} État"

    @property
    def native_value(self) -> str | None:
        lg = self._get_ligne()
        if not lg:
            return None
        return etat_meta(lg.get("etat")).get("label")

    @property
    def icon(self) -> str:
        lg = self._get_ligne()
        return etat_meta(lg.get("etat") if lg else None).get("icon", self._attr_icon)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lg = self._get_ligne()
        if not lg:
            return {}
        etat = lg.get("etat")
        meta = etat_meta(etat)
        return {
            "id":                  lg.get("idLigne"),
            "num":                 lg.get("numLignePublic"),
            "etat":                etat,
            "etat_label":          meta["label"],
            "etat_description":    meta["description"],
            "couleur_etat":        meta["couleur"],
            "perturbation_active": meta["perturbation_active"],
            "perturbation_prevue": meta["perturbation_prevue"],
            "couleur_fond":        _color(lg.get("couleurFond")),
            "couleur_texte":       _color(lg.get("couleurTexte")),
        }

    def _get_ligne(self) -> dict | None:
        for lg in (self.coordinator.data or {}).get("etat_lignes", []):
            if str(lg.get("idLigne")) == self._id_ligne:
                return lg
        return None


class GinkoLigneMessagesSensor(CoordinatorEntity[GinkoInfoCoordinator], SensorEntity):
    """Messages infotrafic actifs pour une ligne spécifique."""

    _attr_icon = "mdi:message-alert"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "messages"
    _unrecorded_attributes = frozenset({MATCH_ALL})


    def __init__(self, coordinator: GinkoInfoCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        ed = entry.data["entry"]
        self._id_ligne   = str(ed[CONF_ID_LIGNE_SUIVI])
        self._num_ligne  = ed[CONF_NUM_LIGNE_SUIVI]
        self._attr_unique_id = f"ginko_ligne_{self._id_ligne}_messages"
        self._attr_name      = f"Ginko Ligne {self._num_ligne} Messages"

    @property
    def native_value(self) -> int:
        return len(self._messages())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "messages":  self._messages(),
            "num_ligne": self._num_ligne,
        }

    def _messages(self) -> list:
        num = str(self._num_ligne)
        return [
            m for m in (self.coordinator.data or {}).get("messages", [])
            if num in [str(l) for l in (m.get("lignes") or [])]
        ]


# ---------------------------------------------------------------------------
# info sensors
# ---------------------------------------------------------------------------

class GinkoEtatLignesSensor(CoordinatorEntity[GinkoInfoCoordinator], SensorEntity):
    """Number of disrupted lines + per-line state as attributes."""

    _attr_unique_id = "ginko_etat_lignes"
    _attr_name = "Ginko État Lignes"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "lignes perturbées"
    _attr_icon = "mdi:bus-alert"
    _unrecorded_attributes = frozenset({MATCH_ALL})


    @property
    def native_value(self) -> int:
        # Nombre de lignes réellement perturbées EN CE MOMENT (perturbation en
        # cours ou circulation interrompue). L'état 3 « hors service » n'est PAS
        # une perturbation !!!!! : c'est une ligne hors de sa période de fonctionnement.
        return sum(
            1 for lg in self._lignes()
            if etat_meta(lg.get("etat")).get("perturbation_active")
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lignes = self._lignes()
        detaillees = [
            {
                "id":                  lg.get("idLigne"),
                "num":                 lg.get("numLignePublic"),
                "etat":                lg.get("etat"),
                "etat_label":          etat_meta(lg.get("etat"))["label"],
                "perturbation_active": etat_meta(lg.get("etat"))["perturbation_active"],
                "perturbation_prevue": etat_meta(lg.get("etat"))["perturbation_prevue"],
                "couleur_fond":        _color(lg.get("couleurFond")),
                "couleur_texte":       _color(lg.get("couleurTexte")),
            }
            for lg in lignes
        ]
        return {
            "perturbations_en_cours": sum(
                1 for l in detaillees if l["perturbation_active"]
            ),
            "perturbations_prevues": sum(
                1 for l in detaillees if l["perturbation_prevue"]
            ),
            "lignes_perturbees": [
                l for l in detaillees
                if l["perturbation_active"] or l["perturbation_prevue"]
            ],
            "lignes": detaillees,
        }

    def _lignes(self) -> list:
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get("etat_lignes", [])


class GinkoMessagesSensor(CoordinatorEntity[GinkoInfoCoordinator], SensorEntity):
    """Number of active disruption messages + message list as attributes."""

    _attr_unique_id = "ginko_messages"
    _attr_name = "Ginko Messages"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "messages"
    _attr_icon = "mdi:message-alert"
    _unrecorded_attributes = frozenset({MATCH_ALL})


    @property
    def native_value(self) -> int:
        return len(self._messages())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"messages": self._messages()}

    def _messages(self) -> list:
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get("messages", [])


# ---------------------------------------------------------------------------
# positions bus
# ---------------------------------------------------------------------------

class GinkoSuiviLigneSensor(CoordinatorEntity[GinkoSuiviLigneCoordinator], SensorEntity):
    """Positions en temps réel des bus d'une ligne."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "bus"
    _attr_icon = "mdi:bus-clock"
    _unrecorded_attributes = frozenset({MATCH_ALL})


    def __init__(self, coordinator: GinkoSuiviLigneCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        ed = entry.data["entry"]
        self._num_ligne = str(ed[CONF_NUM_LIGNE_SUIVI])
        self._attr_unique_id = f"ginko_suivi_ligne_{entry.entry_id}"
        # Tram si le numéro de ligne commence par "T" (T1, T2…), bus sinon
        _is_tram = self._num_ligne.upper().startswith("T")
        _type    = "Tram" if _is_tram else "Bus"
        self._attr_name = f"Ginko {_type} Ligne {self._num_ligne}"

    @property
    def native_value(self) -> int:
        return len((self.coordinator.data or {}).get("buses", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "ginko_mode": "suivi",
            "num_ligne":  data.get("num_ligne", self._num_ligne),
            "buses":      data.get("buses", []),
        }
