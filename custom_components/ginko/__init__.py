# custom_components/ginko/__init__.py
from __future__ import annotations

import logging
import os

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from .const import (
    DOMAIN, CONF_API_KEY, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL,
    CONF_NB_PASSAGES, CONF_MAX_STOPS, DEFAULT_MAX_STOPS,
    MODE_PERSON, MODE_LIGNE, MODE_SUIVI_LIGNE,
    CONF_PERSON_ENTITY, CONF_ID_LIGNE_SUIVI, CONF_NUM_LIGNE_SUIVI,
    DEFAULT_SCAN_INTERVAL_SUIVI,
)
from .coordinator import (
    GinkoCoordinator,
    GinkoInfoCoordinator,
    GinkoPersonProximityCoordinator,
    GinkoSuiviLigneCoordinator,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

_CARD_URL   = "/ginko_card"
_CARD_FILES = ["ginko-card.js", "ginko-card-editor.js"]
async def _register_lovelace_resources(hass: HomeAssistant, version: str) -> None:
    store = Store(hass, 1, "lovelace_resources")
    data: dict = await store.async_load() or {}
    items: list[dict] = data.get("items", [])

    changed = 0
    for fname in _CARD_FILES:
        base = f"{_CARD_URL}/{fname}"
        url = f"{base}?v={version}"
        existing = next(
            (item for item in items if str(item.get("url", "")).split("?")[0] == base),
            None,
        )
        if existing is None:
            items.append({"id": f"ginko_{fname}", "type": "module", "url": url})
            changed += 1
        elif existing.get("url") != url:
            existing["url"] = url
            changed += 1

    if changed:
        data["items"] = items
        await store.async_save(data)
        _LOGGER.info("Ginko: %d ressource(s) Lovelace mise(s) à jour (v%s)", changed, version)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Sert les fichiers JS et enregistre la carte dans Lovelace."""
    # Les fichiers JS de la carte sont dans ginko/lovelace/.
    # (L'URL publique reste /ginko_card pour ne pas casser les dashboards existants.)
    card_dir = hass.config.path("custom_components", "ginko", "lovelace")
    if not os.path.isdir(card_dir):
        _LOGGER.warning(
            "Ginko: dossier JS introuvable (ginko/lovelace/) — "
            "la carte Lovelace ne sera pas disponible."
        )
        return True

    try:
        await hass.http.async_register_static_paths([
            StaticPathConfig(_CARD_URL, card_dir, cache_headers=True)
        ])
        _LOGGER.debug("Ginko: carte Lovelace servie depuis %s", card_dir)
    except Exception:
        _LOGGER.exception("Ginko: erreur lors de l'enregistrement du chemin statique")

    try:
        integration = await async_get_integration(hass, DOMAIN)
        version = str(integration.version or "0")
    except Exception:
        version = "0"

    try:
        for fname in _CARD_FILES:
            add_extra_js_url(hass, f"{_CARD_URL}/{fname}?v={version}")
    except Exception:
        _LOGGER.exception("Ginko: erreur lors de l'injection JS (add_extra_js_url)")

    try:
        await _register_lovelace_resources(hass, version)
    except Exception:
        _LOGGER.exception("Ginko: erreur lors de l'enregistrement des ressources Lovelace")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    entry_data = entry.data["entry"]

    # Shared info coordinator — created once per api_key, needed for all modes
    info_key = f"_info_{entry.data[CONF_API_KEY]}"
    if info_key not in hass.data[DOMAIN]:
        info_coord = GinkoInfoCoordinator(hass, entry.data[CONF_API_KEY])
        await info_coord.async_config_entry_first_refresh()
        hass.data[DOMAIN][info_key] = info_coord

    if entry_data.get("mode") == MODE_LIGNE:
        # Pas de coordinator propre — réutilise le GinkoInfoCoordinator partagé
        hass.data[DOMAIN][entry.entry_id] = hass.data[DOMAIN][info_key]
    elif entry_data.get("mode") == MODE_SUIVI_LIGNE:
        suivi_scan = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SUIVI),
        )
        coordinator = GinkoSuiviLigneCoordinator(
            hass,
            entry.data[CONF_API_KEY],
            entry_data[CONF_ID_LIGNE_SUIVI],
            entry_data[CONF_NUM_LIGNE_SUIVI],
            scan_interval=suivi_scan,
        )
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id] = coordinator
    elif entry_data.get("mode") == MODE_PERSON:
        nb_passages = entry.options.get(
            CONF_NB_PASSAGES, entry_data.get(CONF_NB_PASSAGES, 3)
        )
        max_stops = entry.options.get(
            CONF_MAX_STOPS, entry_data.get(CONF_MAX_STOPS, DEFAULT_MAX_STOPS)
        )
        coordinator = GinkoPersonProximityCoordinator(
            hass,
            entry.data[CONF_API_KEY],
            entry_data[CONF_PERSON_ENTITY],
            nb_passages=nb_passages,
            max_stops=max_stops,
            scan_interval=scan_interval,
        )
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id] = coordinator
    else:
        coordinator = GinkoCoordinator(
            hass,
            entry.data[CONF_API_KEY],
            [entry_data],
            scan_interval=scan_interval,
        )
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        mode = entry.data.get("entry", {}).get("mode")
        if mode == MODE_LIGNE:
            # Le coordinator est partagé (GinkoInfoCoordinator) — ne pas le fermer ici
            hass.data[DOMAIN].pop(entry.entry_id, None)
        else:
            coordinator = hass.data[DOMAIN].pop(entry.entry_id)
            await coordinator.async_shutdown()

        api_key   = entry.data[CONF_API_KEY]
        # Si on était le propriétaire des info sensors, libérer le verrou
        # pour que la prochaine entrée configurée puisse les recréer.
        owner_key = f"_info_sensors_owner_{api_key}"
        if hass.data[DOMAIN].get(owner_key) == entry.entry_id:
            hass.data[DOMAIN].pop(owner_key, None)

        info_key = f"_info_{api_key}"
        remaining = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id and e.data.get(CONF_API_KEY) == api_key
        ]
        if not remaining:
            info_coord: GinkoInfoCoordinator = hass.data[DOMAIN].pop(info_key, None)
            if info_coord:
                await info_coord.async_shutdown()

    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
