# custom_components/ginko/services.py
from __future__ import annotations

import time
import unicodedata

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN, CONF_API_KEY
from .coordinator import _api_get

SERVICE_CHERCHER_ARRET = "chercher_arret"
SERVICE_GET_HORAIRES = "get_horaires"

ARRETS_CACHE_TTL = 3600
HORAIRES_CACHE_TTL = 20

CHERCHER_ARRET_SCHEMA = vol.Schema({
    vol.Required("recherche"): cv.string,
    vol.Optional("limite", default=10): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
})

GET_HORAIRES_SCHEMA = vol.Schema({
    vol.Required("nom"): cv.string,
    vol.Optional("nb", default=3): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
})


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def _api_key(hass: HomeAssistant) -> str:
    for entry in hass.config_entries.async_entries(DOMAIN):
        key = entry.data.get(CONF_API_KEY)
        if key:
            return key
    raise ServiceValidationError("Aucune entrée Ginko configurée : clé API introuvable.")


def _cache(hass: HomeAssistant) -> dict:
    return hass.data.setdefault(DOMAIN, {}).setdefault("_services_cache", {
        "arrets": None, "arrets_ts": 0.0, "horaires": {},
    })


async def _get(hass: HomeAssistant, path: str, params: dict):
    try:
        return await _api_get(hass, _api_key(hass), path, params, timeout=15)
    except ConfigEntryAuthFailed as err:
        raise ServiceValidationError(f"Clé API Ginko refusée : {err}") from err
    except UpdateFailed as err:
        raise HomeAssistantError(str(err)) from err


async def _arrets(hass: HomeAssistant) -> list[dict]:
    cache = _cache(hass)
    now = time.monotonic()
    if cache["arrets"] is not None and now - cache["arrets_ts"] < ARRETS_CACHE_TTL:
        return cache["arrets"]

    raw = await _get(hass, "/DR/getArrets.do", {})
    arrets: dict[str, dict] = {}
    for a in raw if isinstance(raw, list) else []:
        nom = a.get("nom")
        if not nom:
            continue
        entry = arrets.setdefault(nom, {
            "nom": nom,
            "latitude": a.get("latitude"),
            "longitude": a.get("longitude"),
            "accessible": False,
            "quais": 0,
        })
        entry["quais"] += 1
        if a.get("accessibilite") == 1:
            entry["accessible"] = True

    cache["arrets"] = sorted(arrets.values(), key=lambda x: _normalize(x["nom"]))
    cache["arrets_ts"] = now
    return cache["arrets"]


async def _chercher_arret(call: ServiceCall) -> ServiceResponse:
    hass = call.hass
    query = _normalize(call.data["recherche"])
    limite = call.data["limite"]
    arrets = await _arrets(hass)

    if not query:
        return {"arrets": arrets[:limite]}

    starts, contains = [], []
    for a in arrets:
        n = _normalize(a["nom"])
        if n.startswith(query):
            starts.append(a)
        elif query in n:
            contains.append(a)
    return {"arrets": (starts + contains)[:limite]}


async def _get_horaires(call: ServiceCall) -> ServiceResponse:
    hass = call.hass
    nom = call.data["nom"].strip()
    nb = call.data["nb"]
    if not nom:
        raise ServiceValidationError("Le nom de l'arrêt est vide.")

    cache = _cache(hass)["horaires"]
    key = (_normalize(nom), nb)
    now = time.monotonic()
    hit = cache.get(key)
    if hit and now - hit["ts"] < HORAIRES_CACHE_TTL:
        return hit["data"]

    raw = await _get(hass, "/TR/getTempsLieu.do", {"nom": nom, "nb": nb})
    quais = raw if isinstance(raw, list) else [raw]
    passages: list = []
    nom_exact = nom
    for q in quais:
        if not isinstance(q, dict):
            continue
        nom_exact = q.get("nomExact") or nom_exact
        passages.extend(p for p in q.get("listeTemps", []) if isinstance(p, dict))

    passages.sort(key=lambda p: p.get("tempsEnSeconde") if p.get("tempsEnSeconde") is not None else 10**9)
    data = {"nom": nom_exact, "nb_passages": len(passages), "passages": passages}
    cache[key] = {"ts": now, "data": data}
    return data


def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_GET_HORAIRES):
        return
    hass.services.async_register(
        DOMAIN, SERVICE_CHERCHER_ARRET, _chercher_arret,
        schema=CHERCHER_ARRET_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_HORAIRES, _get_horaires,
        schema=GET_HORAIRES_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
