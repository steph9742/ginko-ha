# custom_components/ginko/coordinator.py
from __future__ import annotations
import asyncio
import logging, math
from datetime import timedelta
import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import SCAN_INTERVAL_TRAM, SCAN_INTERVAL_BUS_LIEU, SCAN_INTERVAL_BUS_SUIVI

_LOGGER = logging.getLogger(__name__)
BASE_URL = "https://api.ginko.voyage"
MAX_PASSAGES_PER_REQUEST = 45

def _chunk_list(lst, size):
    return [lst[i:i+size] for i in range(0, len(lst), size)]


async def _api_get(hass: HomeAssistant, api_key: str, path: str, params: dict, timeout: int = 10):
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{BASE_URL}{path}",
            params={**params, "apiKey": api_key},
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            if not data.get("ok"):
                msg = str(data.get("msg", "unknown"))
                if "clé" in msg.lower():
                    raise ConfigEntryAuthFailed(msg)
                raise UpdateFailed(f"API error: {msg}")
            return data["objets"]
    except aiohttp.ClientError as err:
        raise UpdateFailed(f"Network error: {err}") from err


class GinkoCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api_key, entries, scan_interval: int = 0):
        self.api_key = api_key
        self.entries = entries
        # 0 = auto-détection (tram 10 s / bus 30 s) ; sinon intervalle fixe imposé
        self._manual_interval: int | None = scan_interval if scan_interval > 0 else None
        initial = scan_interval if scan_interval > 0 else SCAN_INTERVAL_BUS_LIEU
        super().__init__(hass, _LOGGER, name="Ginko", update_interval=timedelta(seconds=initial))

    async def _get(self, path, params):
        return await _api_get(self.hass, self.api_key, path, params)

    async def _async_update_data(self):
        results = {}
        for entry in self.entries:
            if entry["mode"] == "lieu":
                results[entry["nom"]] = await self._fetch_temps_lieu(entry)
            elif entry["mode"] == "liste":
                data = await self._fetch_liste_temps(entry)
                for item, result in zip(entry["items"], data):
                    key = f"{item['nom']}|{item['id_ligne']}|{item['sens_aller']}"
                    # API returns {nomExact, listeTemps, latitude, longitude}
                    results[key] = result.get("listeTemps", []) if isinstance(result, dict) else []

        # Auto-ajuste l'intervalle si aucun override utilisateur
        if self._manual_interval is None:
            has_tram = any(
                p.get("modeTransport") == 1
                for passages in results.values()
                for p in (passages if isinstance(passages, list) else [])
                if isinstance(p, dict)
            )
            target = timedelta(seconds=SCAN_INTERVAL_TRAM if has_tram else SCAN_INTERVAL_BUS_LIEU)
            if self.update_interval != target:
                self.update_interval = target
                _LOGGER.debug(
                    "Ginko: intervalle auto → %ds (%s)",
                    target.seconds, "tram" if has_tram else "bus",
                )

        return results

    async def _fetch_temps_lieu(self, entry):
        raw = await self._get("/TR/getTempsLieu.do", {"nom": entry["nom"], "nb": min(entry["nb_passages"], 5)})
        # API peut retourner un dict unique OU une liste de dicts
        # Chaque stop a la forme {nomExact, listeTemps, latitude, longitude}
        if isinstance(raw, dict):
            return raw.get("listeTemps", [])
        passages = []
        for stop in raw:
            if isinstance(stop, dict):
                passages.extend(stop.get("listeTemps", []))
        return passages

    async def _fetch_liste_temps(self, entry):
        items = entry["items"]
        nb = min(entry["nb_passages"], 5)
        max_per_chunk = math.floor(MAX_PASSAGES_PER_REQUEST / nb)
        if len(items) <= max_per_chunk:
            return await self._call_liste_temps(items, nb)
        chunks = _chunk_list(items, max_per_chunk)
        results = []
        for chunk in chunks:
            results.extend(await self._call_liste_temps(chunk, nb))
        return results

    async def _call_liste_temps(self, items, nb):
        return await self._get("/TR/getListeTemps.do", {
            "listeNoms":      "~".join(i["nom"]      for i in items),
            "listeIdLignes":  "~".join(i["id_ligne"] for i in items),
            "listeSensAller": "~".join("1" if i["sens_aller"] else "0" for i in items),
            "preserverOrdre": "true",  # keep order so zip() aligns correctly
            "nb": nb,
        })

    async def fetch_etat_lignes(self):
        return await self._get("/TR/getEtatLignes.do", {})

    async def fetch_messages(self, id_lignes=None):
        params = {}
        if id_lignes:
            params["idLignes"] = "~".join(id_lignes)
        return await self._get("/TR/getMessages.do", params)

    async def fetch_arrets_proches(self, latitude, longitude):
        return await self._get("/DR/getArretsProches.do", {"latitude": latitude, "longitude": longitude})


class GinkoPersonProximityCoordinator(DataUpdateCoordinator):
    """Coordinator: arrêts proches d'une entité personne (getArretsProches + getTempsLieu)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        person_entity_id: str,
        nb_passages: int = 3,
        max_stops: int = 5,
        scan_interval: int = 0,
    ) -> None:
        self.api_key = api_key
        self._person_entity_id = person_entity_id
        self._nb_passages = nb_passages
        self._max_stops = max_stops
        self._manual_interval: int | None = scan_interval if scan_interval > 0 else None
        initial = scan_interval if scan_interval > 0 else SCAN_INTERVAL_BUS_LIEU
        super().__init__(
            hass, _LOGGER, name="Ginko Person Proximity",
            update_interval=timedelta(seconds=initial),
        )

    async def _get(self, path: str, params: dict):
        return await _api_get(self.hass, self.api_key, path, params)

    async def _async_update_data(self) -> dict:
        person = self.hass.states.get(self._person_entity_id)
        if not person:
            raise UpdateFailed(f"Entité personne introuvable : {self._person_entity_id}")

        lat = person.attributes.get("latitude")
        lng = person.attributes.get("longitude")
        if lat is None or lng is None:
            return {"arrets": [], "person_state": person.state}

        # Arrêts proches
        try:
            arrets_raw = await self._get("/DR/getArretsProches.do", {
                "latitude": lat, "longitude": lng,
            })
        except UpdateFailed:
            return {"arrets": [], "person_state": person.state}

        if not isinstance(arrets_raw, list):
            arrets_raw = []

        # Déduplication par nom (comme recommandé par l'API)
        seen: set[str] = set()
        unique: list[dict] = []
        for a in arrets_raw:
            nom = a.get("nomExact") or a.get("nom", "")
            if nom and nom not in seen:
                seen.add(nom)
                unique.append(a)

        # Passages pour chaque arrêt (limité à max_stops)
        result: list[dict] = []
        for arret in unique[:self._max_stops]:
            nom      = arret.get("nomExact") or arret.get("nom", "")
            distance = arret.get("distance")
            try:
                raw = await self._get("/TR/getTempsLieu.do", {
                    "nom": nom, "nb": self._nb_passages,
                })
                passages: list = []
                if isinstance(raw, dict):
                    passages = raw.get("listeTemps", [])
                elif isinstance(raw, list):
                    for stop in raw:
                        if isinstance(stop, dict):
                            passages.extend(stop.get("listeTemps", []))
            except ConfigEntryAuthFailed:
                raise
            except Exception:
                passages = []

            result.append({
                "nom":      nom,
                "distance": round(float(distance)) if distance is not None else None,
                "passages": passages,
            })

        data = {"arrets": result, "person_state": person.state}

        # Auto-ajuste l'intervalle si aucun override utilisateur
        if self._manual_interval is None:
            has_tram = any(
                p.get("modeTransport") == 1
                for arret in result
                for p in arret.get("passages", [])
                if isinstance(p, dict)
            )
            target = timedelta(seconds=SCAN_INTERVAL_TRAM if has_tram else SCAN_INTERVAL_BUS_LIEU)
            if self.update_interval != target:
                self.update_interval = target
                _LOGGER.debug(
                    "Ginko Person: intervalle auto → %ds (%s)",
                    target.seconds, "tram" if has_tram else "bus",
                )

        return data


class GinkoSuiviLigneCoordinator(DataUpdateCoordinator):
    """Suit les positions des bus en circulation sur une ligne.

    Algorithme :
      1. getLignes → variantes (directions) de la ligne
      2. getDetailsVariante → liste ORDONNÉE des arrêts par variante
      3. getListeTemps (toutes les 15 s) sur tous les arrêts × variantes
      4. Pour chaque numVehicule : garde le tempsEnSeconde minimal
         → prochain arrêt du bus ; arrêt précédent dans la liste = vient de quitter
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        id_ligne: str,
        num_ligne: str,
        scan_interval: int = 0,
    ) -> None:
        self.api_key = api_key
        self._id_ligne  = str(id_ligne)
        self._num_ligne = str(num_ligne)
        # {idVariante: {sens_aller, destination, arrets: [FormArret]}}
        self._variantes: dict[str, dict] = {}
        # Détection tram : les lignes tram de Besançon commencent par "T" (T1, T2…)
        _is_tram = str(num_ligne).upper().startswith("T")
        auto_interval = SCAN_INTERVAL_TRAM if _is_tram else SCAN_INTERVAL_BUS_SUIVI
        initial = scan_interval if scan_interval > 0 else auto_interval
        _LOGGER.debug(
            "Ginko Suivi L%s : %s → intervalle %ds",
            num_ligne, "tram" if _is_tram else "bus", initial,
        )
        super().__init__(
            hass, _LOGGER, name="Ginko Suivi Ligne",
            update_interval=timedelta(seconds=initial),
        )

    async def _get(self, path: str, params: dict):
        return await _api_get(self.hass, self.api_key, path, params, timeout=15)

    # ------------------------------------------------------------------

    async def _load_variantes(self) -> None:
        """Charge une fois les arrêts ordonnés par variante."""
        try:
            lignes = await self._get("/DR/getLignes.do", {})
            if not isinstance(lignes, list):
                return
            ligne = next(
                (l for l in lignes if str(l.get("id")) == self._id_ligne), None
            )
            if not ligne:
                _LOGGER.warning("Ginko Suivi: ligne %s introuvable dans getLignes", self._id_ligne)
                return

            for v in ligne.get("variantes", []):
                id_v = str(v.get("id", ""))
                if not id_v:
                    continue
                try:
                    arrets = await self._get("/DR/getDetailsVariante.do", {
                        "idLigne":    self._id_ligne,
                        "idVariante": id_v,
                    })
                    if isinstance(arrets, list) and arrets:
                        self._variantes[id_v] = {
                            "sens_aller":  bool(v.get("sensAller", True)),
                            "destination": v.get("destination", ""),
                            "arrets":      arrets,
                        }
                        _LOGGER.debug(
                            "Ginko Suivi L%s — variante %s (%s) : %d arrêts",
                            self._num_ligne, id_v, v.get("destination", ""), len(arrets),
                        )
                except Exception as err:
                    _LOGGER.warning("Ginko Suivi: getDetailsVariante %s : %s", id_v, err)
        except Exception as err:
            _LOGGER.warning("Ginko Suivi: _load_variantes : %s", err)

    async def _liste_temps_variante(
        self, arrets: list[dict], sens_aller: bool, nb: int = 2
    ) -> dict[str, dict]:
        """getListeTemps paginé pour une variante.

        Retourne un dict {nom_arret: result} indexé par nomExact de l'API.
        L'API peut omettre des arrêts sans passage (preserverOrdre ne garantit
        pas un résultat par arrêt), donc on ne peut pas se fier à un zip positionnel.
        """
        noms = [a.get("nom", "") for a in arrets]
        chunk_size = max(1, MAX_PASSAGES_PER_REQUEST // nb)
        results_by_name: dict[str, dict] = {}

        for i in range(0, len(noms), chunk_size):
            chunk = noms[i : i + chunk_size]
            try:
                objets = await _api_get(self.hass, self.api_key, "/TR/getListeTemps.do", {
                    "listeNoms":      "~".join(chunk),
                    "listeIdLignes":  "~".join([self._id_ligne] * len(chunk)),
                    "listeSensAller": "~".join(["1" if sens_aller else "0"] * len(chunk)),
                    "preserverOrdre": "true",
                    "nb":             nb,
                }, timeout=15)
                if isinstance(objets, dict):
                    objets = [objets]
                if isinstance(objets, list):
                    for obj in objets:
                        if isinstance(obj, dict):
                            nom = obj.get("nomExact") or obj.get("nom", "")
                            if nom:
                                results_by_name[nom] = obj
            except ConfigEntryAuthFailed:
                raise
            except Exception as err:
                _LOGGER.debug("Ginko Suivi: liste temps chunk : %s", err)

        return results_by_name

    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        if not self._variantes:
            await self._load_variantes()
        if not self._variantes:
            return {"num_ligne": self._num_ligne, "buses": []}

        # Meilleure entrée par bus : {f"{numVehicule}_{sensAller}": {...}}
        best: dict[str, dict] = {}

        for id_v, v_info in self._variantes.items():
            arrets     = v_info["arrets"]
            sens_aller = v_info["sens_aller"]
            results_by_name = await self._liste_temps_variante(arrets, sens_aller)

            for idx, arret in enumerate(arrets):
                nom    = arret.get("nom", "")
                result = results_by_name.get(nom)
                if not isinstance(result, dict):
                    continue
                for passage in result.get("listeTemps", []):
                    if not isinstance(passage, dict):
                        continue
                    num_v = passage.get("numVehicule")
                    temps = passage.get("tempsEnSeconde")
                    if num_v is None or temps is None:
                        continue   # bus théorique sans GPS
                    key = f"{num_v}_{sens_aller}"
                    entry = {
                        "num_vehicule": num_v,
                        "sens_aller":   sens_aller,
                        "destination":  v_info["destination"],
                        "id_variante":  id_v,
                        "arret_idx":    idx,
                        "arret_nom":    arret.get("nom", ""),
                        "temps":        temps,
                    }
                    if key not in best or temps < best[key]["temps"]:
                        best[key] = entry

        # Déduplique par véhicule : un même numVehicule peut apparaître dans les
        # deux sens (variante aller + variante retour) si l'API le remonte sur
        # plusieurs arrêts. On ne garde que l'entrée au temps le plus court
        # (= position réelle du véhicule, pas une copie fantôme).
        dedup: dict[str, dict] = {}
        for data in best.values():
            vid = str(data["num_vehicule"])
            if vid not in dedup or data["temps"] < dedup[vid]["temps"]:
                dedup[vid] = data

        # Calcul des positions
        buses: list[dict] = []
        for data in dedup.values():
            arrets    = self._variantes.get(data["id_variante"], {}).get("arrets", [])
            idx       = data["arret_idx"]
            prochain  = data["arret_nom"]
            precedent = arrets[idx - 1].get("nom", "") if idx > 0 else None

            if data["temps"] <= 30:
                statut = "a_quai"
            elif idx == 0:
                statut = "depart"
            else:
                statut = "en_route"

            buses.append({
                "id":              data["num_vehicule"],
                "sens":            "aller" if data["sens_aller"] else "retour",
                "terminus":        data["destination"],
                "prochain_arret":  prochain,
                "arret_precedent": precedent,
                "statut":          statut,
                "dans_sec":        data["temps"],
            })

        buses.sort(key=lambda x: x["dans_sec"])
        _LOGGER.debug("Ginko Suivi L%s : %d bus positionnés", self._num_ligne, len(buses))
        return {"num_ligne": self._num_ligne, "buses": buses}


class GinkoInfoCoordinator(DataUpdateCoordinator):
    """Coordinator for line states and disruption messages (60 s refresh)."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        self.api_key = api_key
        super().__init__(
            hass, _LOGGER, name="Ginko Info",
            update_interval=timedelta(seconds=60),
        )

    async def _get(self, path: str, params: dict):
        return await _api_get(self.hass, self.api_key, path, params)

    async def _async_update_data(self) -> dict:
        etat, messages = await asyncio.gather(
            self._get("/TR/getEtatLignes.do", {}),
            self._get("/TR/getMessages.do", {}),
        )
        return {"etat_lignes": etat, "messages": messages}
