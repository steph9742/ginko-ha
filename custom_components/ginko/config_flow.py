# custom_components/ginko/config_flow.py
from __future__ import annotations

import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_MODE,
    CONF_NOM,
    CONF_NB_PASSAGES,
    CONF_ITEMS,
    CONF_ID_LIGNE,
    CONF_SENS_ALLER,
    CONF_SCAN_INTERVAL,
    CONF_PERSON_ENTITY,
    CONF_MAX_STOPS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_MAX_STOPS,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    SCAN_INTERVAL_AUTO,
    MODE_LIEU,
    MODE_LISTE,
    MODE_PERSON,
    MODE_LIGNE,
    CONF_ID_LIGNE_SUIVI,
    CONF_NUM_LIGNE_SUIVI,
    CONF_NOM_LIGNE_SUIVI,
    MODE_SUIVI_LIGNE,
    DEFAULT_SCAN_INTERVAL_SUIVI,
)

BASE_URL = "https://api.ginko.voyage"


async def _validate_api_key(api_key: str) -> str | None:
    """Return None if valid, else an error key."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/TR/getEtatLignes.do",
                params={"apiKey": api_key},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return "cannot_connect"
                data = await resp.json()
                if not data.get("ok"):
                    return "invalid_api_key"
    except aiohttp.ClientError:
        return "cannot_connect"
    except Exception:
        return "unknown"
    return None


class GinkoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ginko."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key: str = ""
        self._mode: str = ""
        self._name: str = ""
        self._items: list[dict] = []
        self._nb_passages: int = 3
        # liste mode state
        self._lignes_options: list[dict] = []    # toutes les lignes [{value: id, label}]
        self._lignes_info: dict[str, dict] = {}  # id -> objet ligne complet
        self._lignes_filtered: list[dict] = []   # lignes filtrées pour l'arrêt courant
        self._pending_nom: str = ""
        self._pending_ligne_id: str = ""
        # autocomplete arrêts
        self._arrets_options: list[dict] = []    # [{value: nom, label: nom}]
        # données en attente avant le step scan
        self._pending_entry_data: dict = {}
        self._pending_entry_title: str = ""

    async def async_step_reauth(self, entry_data: dict | None = None) -> FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            error = await _validate_api_key(api_key)
            if error:
                errors["base"] = error
            else:
                entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_API_KEY: api_key}
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): TextSelector(),
            }),
            errors=errors,
        )

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            error = await _validate_api_key(api_key)
            if error:
                errors["base"] = error
            else:
                self._api_key = api_key
                return await self.async_step_mode()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): TextSelector(),
            }),
            errors=errors,
        )

    async def async_step_mode(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            self._mode = user_input[CONF_MODE]
            self._name = user_input.get("name", "").strip()
            if self._mode == MODE_LIEU:
                return await self.async_step_lieu()
            if self._mode == MODE_PERSON:
                return await self.async_step_person()
            if self._mode == MODE_LIGNE:
                return await self.async_step_ligne()
            if self._mode == MODE_SUIVI_LIGNE:
                return await self.async_step_suivi_ligne()
            return await self.async_step_liste()

        return self.async_show_form(
            step_id="mode",
            data_schema=vol.Schema({
                vol.Required(CONF_MODE, default=MODE_LIEU): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": MODE_LIEU,        "label": "Arrêt par nom (toutes les lignes)"},
                            {"value": MODE_LISTE,       "label": "Arrêt par ligne et direction"},
                            {"value": MODE_PERSON,      "label": "Arrêts proches d'une personne"},
                            {"value": MODE_LIGNE,       "label": "Infotrafic d'une ligne"},
                            {"value": MODE_SUIVI_LIGNE, "label": "Positions des véhicules d'une ligne"},
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional("name", default=""): TextSelector(),
            }),
        )

    async def async_step_person(self, user_input: dict | None = None) -> FlowResult:
        """Étape — sélection d'une entité personne + paramètres."""
        if user_input is not None:
            person_id = user_input[CONF_PERSON_ENTITY]
            nb        = int(user_input[CONF_NB_PASSAGES])
            max_stops = int(user_input[CONF_MAX_STOPS])
            self._pending_entry_title = self._name or f"Ginko — {person_id.split('.')[-1]}"
            self._pending_entry_data  = {
                CONF_API_KEY: self._api_key,
                "entry": {
                    "mode":             MODE_PERSON,
                    CONF_PERSON_ENTITY: person_id,
                    CONF_NB_PASSAGES:   nb,
                    CONF_MAX_STOPS:     max_stops,
                },
            }
            return await self.async_step_scan_config()

        return self.async_show_form(
            step_id="person",
            data_schema=vol.Schema({
                vol.Required(CONF_PERSON_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="person")
                ),
                vol.Required(CONF_NB_PASSAGES, default=3): NumberSelector(
                    NumberSelectorConfig(min=1, max=5, step=1, mode=NumberSelectorMode.SLIDER)
                ),
                vol.Required(CONF_MAX_STOPS, default=DEFAULT_MAX_STOPS): NumberSelector(
                    NumberSelectorConfig(min=1, max=10, step=1, mode=NumberSelectorMode.SLIDER)
                ),
            }),
        )

    async def async_step_lieu(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            nom = str(user_input[CONF_NOM]).strip()
            nb = int(user_input[CONF_NB_PASSAGES])
            self._pending_entry_title = self._name or f"Ginko — {nom}"
            self._pending_entry_data  = {
                CONF_API_KEY: self._api_key,
                "entry": {"mode": MODE_LIEU, CONF_NOM: nom, CONF_NB_PASSAGES: nb},
            }
            return await self.async_step_scan_config()

        await self._ensure_arrets()
        return self.async_show_form(
            step_id="lieu",
            data_schema=vol.Schema({
                vol.Required(CONF_NOM): SelectSelector(
                    SelectSelectorConfig(
                        options=self._arrets_options or [{"value": "", "label": "Chargement..."}],
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
                vol.Required(CONF_NB_PASSAGES, default=3): NumberSelector(
                    NumberSelectorConfig(min=1, max=5, step=1, mode=NumberSelectorMode.BOX)
                ),
            }),
        )

    async def async_step_ligne(self, user_input: dict | None = None) -> FlowResult:
        """Sélection d'une ligne à surveiller (état + messages infotrafic)."""
        # Charger les lignes si pas encore fait
        if not self._lignes_options:
            lignes = await self._fetch_lignes()
            seen_pub: set[str] = set()
            for lg in lignes:
                pub = lg.get("numLignePublic", "")
                if pub in seen_pub:
                    continue
                seen_pub.add(pub)
                label = f"{pub} — {lg.get('libellePublic', '')}"
                lid = str(lg.get("id", ""))
                self._lignes_options.append({"value": lid, "label": label})
                self._lignes_info[lid] = lg

        if user_input is not None:
            lid = user_input["id_ligne"]
            ligne = self._lignes_info.get(lid, {})
            num = ligne.get("numLignePublic", lid)
            nom = ligne.get("libellePublic", "")
            title = self._name or f"Ginko Ligne {num}"
            return self.async_create_entry(
                title=title,
                data={
                    CONF_API_KEY: self._api_key,
                    "entry": {
                        "mode":              MODE_LIGNE,
                        CONF_ID_LIGNE_SUIVI: lid,
                        CONF_NUM_LIGNE_SUIVI: num,
                        CONF_NOM_LIGNE_SUIVI: nom,
                    },
                },
            )

        options = self._lignes_options or [{"value": "", "label": "Chargement..."}]
        return self.async_show_form(
            step_id="ligne",
            data_schema=vol.Schema({
                vol.Required("id_ligne"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_suivi_ligne(self, user_input: dict | None = None) -> FlowResult:
        """Sélection de la ligne dont on veut suivre les positions des bus."""
        if not self._lignes_options:
            lignes = await self._fetch_lignes()
            seen_pub: set[str] = set()
            for lg in lignes:
                pub = lg.get("numLignePublic", "")
                if pub in seen_pub:
                    continue
                seen_pub.add(pub)
                lid = str(lg.get("id", ""))
                self._lignes_options.append({"value": lid, "label": f"{pub} — {lg.get('libellePublic', '')}"})
                self._lignes_info[lid] = lg

        if user_input is not None:
            self._pending_ligne_id = user_input["id_ligne"]
            if user_input.get("scan_auto", True):
                return self._create_suivi_entry(scan=0)
            return await self.async_step_suivi_scan()

        options = self._lignes_options or [{"value": "", "label": "Chargement..."}]
        return self.async_show_form(
            step_id="suivi_ligne",
            data_schema=vol.Schema({
                vol.Required("id_ligne"): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required("scan_auto", default=True): BooleanSelector(),
            }),
        )

    async def async_step_suivi_scan(self, user_input: dict | None = None) -> FlowResult:
        """Étape optionnelle — intervalle manuel pour le suivi position."""
        if user_input is not None:
            scan = max(10, min(300, int(user_input[CONF_SCAN_INTERVAL])))
            return self._create_suivi_entry(scan=scan)

        return self.async_show_form(
            step_id="suivi_scan",
            data_schema=vol.Schema({
                vol.Required(CONF_SCAN_INTERVAL, default=15): NumberSelector(
                    NumberSelectorConfig(
                        min=10, max=300, step=5,
                        mode=NumberSelectorMode.SLIDER,
                        unit_of_measurement="s",
                    )
                ),
            }),
        )

    def _create_suivi_entry(self, scan: int) -> FlowResult:
        lid   = self._pending_ligne_id
        ligne = self._lignes_info.get(lid, {})
        num   = ligne.get("numLignePublic", lid)
        nom   = ligne.get("libellePublic", "")
        title = self._name or f"Ginko Bus L{num}"
        return self.async_create_entry(
            title=title,
            data={
                CONF_API_KEY: self._api_key,
                CONF_SCAN_INTERVAL: scan,
                "entry": {
                    "mode":               MODE_SUIVI_LIGNE,
                    CONF_ID_LIGNE_SUIVI:  lid,
                    CONF_NUM_LIGNE_SUIVI: num,
                    CONF_NOM_LIGNE_SUIVI: nom,
                },
            },
        )

    async def async_step_scan_config(self, user_input: dict | None = None) -> FlowResult:
        """Choix automatique / manuel de l'intervalle de rafraîchissement."""
        if user_input is not None:
            if user_input.get("scan_auto", True):
                return self._finalize_entry(scan=0)
            return await self.async_step_scan_manual()

        return self.async_show_form(
            step_id="scan_config",
            data_schema=vol.Schema({
                vol.Required("scan_auto", default=True): BooleanSelector(),
            }),
        )

    async def async_step_scan_manual(self, user_input: dict | None = None) -> FlowResult:
        """Saisie de l'intervalle manuel."""
        if user_input is not None:
            scan = max(10, int(user_input[CONF_SCAN_INTERVAL]))
            return self._finalize_entry(scan=scan)

        return self.async_show_form(
            step_id="scan_manual",
            data_schema=vol.Schema({
                vol.Required(CONF_SCAN_INTERVAL, default=30): NumberSelector(
                    NumberSelectorConfig(
                        min=10, max=300, step=5,
                        mode=NumberSelectorMode.SLIDER,
                        unit_of_measurement="s",
                    )
                ),
            }),
        )

    def _finalize_entry(self, scan: int) -> FlowResult:
        data = dict(self._pending_entry_data)
        data[CONF_SCAN_INTERVAL] = scan
        return self.async_create_entry(title=self._pending_entry_title, data=data)

    async def _fetch_arrets(self) -> list[dict]:
        """Charge la liste complète des arrêts (stable, mise en cache dans _arrets_options)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{BASE_URL}/DR/getArrets.do",
                    params={"apiKey": self._api_key},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        return data.get("objets", [])
        except aiohttp.ClientError as err:
            _LOGGER.warning("Ginko: impossible de charger les arrêts : %s", err)
        except Exception:
            _LOGGER.exception("Ginko: erreur inattendue dans _fetch_arrets")
        return []

    async def _ensure_arrets(self) -> None:
        """Charge et déduplique les arrêts si pas encore fait."""
        if self._arrets_options:
            return
        arrets = await self._fetch_arrets()
        seen: set[str] = set()
        for a in arrets:
            nom = a.get("nom", "")
            if nom and nom not in seen:
                seen.add(nom)
                self._arrets_options.append({"value": nom, "label": nom})

    async def _fetch_lignes(self) -> list[dict]:
        """Fetch all lines from /DR/getLignes.do and populate _lignes_options/_lignes_info."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{BASE_URL}/DR/getLignes.do",
                    params={"apiKey": self._api_key},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        return data.get("objets", [])
        except aiohttp.ClientError as err:
            _LOGGER.warning("Ginko: impossible de charger les lignes : %s", err)
        except Exception:
            _LOGGER.exception("Ginko: erreur inattendue dans _fetch_lignes")
        return []

    async def _resolve_all_id_arrets(self, nom: str, session: aiohttp.ClientSession) -> list[str]:
        """Retourne TOUS les idArret uniques pour un nom d'arrêt.

        Un arrêt physique peut avoir plusieurs quais, chacun avec son propre
        idArret — généralement un par sens. getTempsLieu retourne les passages
        de tous ces quais ; on collecte tous les idArret distincts afin d'appeler
        getVariantesDesservantArret pour chaque quai et obtenir les deux sens.
        """
        try:
            async with session.get(
                f"{BASE_URL}/TR/getTempsLieu.do",
                params={"apiKey": self._api_key, "nom": nom, "nb": 3},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                if data.get("ok"):
                    objets = data.get("objets", [])
                    stops = objets if isinstance(objets, list) else [objets]
                    seen: set[str] = set()
                    ids: list[str] = []
                    for stop in stops:
                        for passage in stop.get("listeTemps", []):
                            id_a = passage.get("idArret")
                            if id_a and str(id_a) not in seen:
                                seen.add(str(id_a))
                                ids.append(str(id_a))
                    return ids
        except aiohttp.ClientError as err:
            _LOGGER.warning("Ginko: impossible de résoudre les idArret pour %s : %s", nom, err)
        except Exception:
            _LOGGER.exception("Ginko: erreur inattendue dans _resolve_all_id_arrets")
        return []

    async def _fetch_lines_for_stop(self, nom: str) -> None:
        """Récupère les lignes desservant l'arrêt via getVariantesDesservantArret.do.

        Appelle l'endpoint pour CHAQUE idArret du nom (un par quai/sens) et
        fusionne les résultats — garantit que les deux directions apparaissent.
        """
        try:
            async with aiohttp.ClientSession() as session:
                id_arrets = await self._resolve_all_id_arrets(nom, session)

                all_lignes: list[dict] = []
                seen_lg_ids: set[str] = set()
                for id_arret in id_arrets:
                    async with session.get(
                        f"{BASE_URL}/DR/getVariantesDesservantArret.do",
                        params={"apiKey": self._api_key, "idArret": id_arret},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        data = await resp.json()
                        if data.get("ok"):
                            for lg in data.get("objets", []):
                                lid = str(lg.get("id", ""))
                                if lid and lid not in seen_lg_ids:
                                    seen_lg_ids.add(lid)
                                    all_lignes.append(lg)
                                else:
                                    # Fusionner les variantes du même idLigne (les deux sens)
                                    existing = next(
                                        (x for x in all_lignes if str(x.get("id")) == lid), None
                                    )
                                    if existing is not None:
                                        existing_v = {
                                            str(v.get("sensAller")) for v in existing.get("variantes", [])
                                        }
                                        for v in lg.get("variantes", []):
                                            if str(v.get("sensAller")) not in existing_v:
                                                existing.setdefault("variantes", []).append(v)
                                                existing_v.add(str(v.get("sensAller")))

                if all_lignes:
                    seen_pub: set[str] = set()
                    self._lignes_filtered = []
                    for lg in all_lignes:
                        pub = lg.get("numLignePublic", "")
                        if pub in seen_pub:
                            continue
                        seen_pub.add(pub)
                        lid = str(lg.get("id", ""))
                        label = f"{pub} — {lg.get('libellePublic', '')}"
                        self._lignes_filtered.append({"value": lid, "label": label})
                        self._lignes_info[lid] = lg
                    return
        except Exception:
            _LOGGER.exception("Ginko: erreur _fetch_lines_for_stop pour %s", nom)

        # Fallback : toutes les lignes dédupliquées
        if not self._lignes_options:
            lignes = await self._fetch_lignes()
            for lg in lignes:
                label = f"{lg['numLignePublic']} — {lg['libellePublic']}"
                self._lignes_options.append({"value": lg["id"], "label": label})
                self._lignes_info[lg["id"]] = lg
        seen_pub: set[str] = set()
        deduped: list[dict] = []
        for opt in self._lignes_options:
            pub = self._lignes_info.get(opt["value"], {}).get("numLignePublic", opt["value"])
            if pub not in seen_pub:
                seen_pub.add(pub)
                deduped.append(opt)
        self._lignes_filtered = deduped

    async def async_step_liste(self, user_input: dict | None = None) -> FlowResult:
        """Étape 1/3 — saisie du nom de l'arrêt."""
        is_first = len(self._items) == 0
        self._lignes_filtered = []  # reset pour ce nouvel arrêt

        if user_input is not None:
            self._pending_nom = user_input[CONF_NOM].strip()
            if is_first:
                self._nb_passages = int(user_input[CONF_NB_PASSAGES])
            # Récupère les lignes qui passent à cet arrêt
            await self._fetch_lines_for_stop(self._pending_nom)
            return await self.async_step_liste_ligne()

        await self._ensure_arrets()
        schema_fields: dict = {
            vol.Required(CONF_NOM): SelectSelector(
                SelectSelectorConfig(
                    options=self._arrets_options or [{"value": "", "label": "Chargement..."}],
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            )
        }
        if is_first:
            schema_fields[vol.Required(CONF_NB_PASSAGES, default=3)] = NumberSelector(
                NumberSelectorConfig(min=1, max=5, step=1, mode=NumberSelectorMode.BOX)
            )
        return self.async_show_form(step_id="liste", data_schema=vol.Schema(schema_fields))

    async def async_step_liste_ligne(self, user_input: dict | None = None) -> FlowResult:
        """Étape 2/3 — choix de la ligne parmi celles qui desservent l'arrêt."""
        if user_input is not None:
            self._pending_ligne_id = user_input["ligne"]
            return await self.async_step_liste_sens()

        options = self._lignes_filtered or self._lignes_options
        nb = len(options)
        desc = (
            f"**{nb}** ligne(s) desservent l'arrêt **{self._pending_nom}**."
            if nb
            else f"Aucune ligne trouvée pour **{self._pending_nom}** — vérifiez l'orthographe."
        )
        return self.async_show_form(
            step_id="liste_ligne",
            data_schema=vol.Schema({
                vol.Required("ligne"): SelectSelector(
                    SelectSelectorConfig(
                        options=options or [{"value": "", "label": "Aucun résultat"}],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            description_placeholders={"info": desc},
        )

    async def async_step_liste_sens(self, user_input: dict | None = None) -> FlowResult:
        """Step 2/2 for liste mode: choose direction (built from variantes)."""
        ligne = self._lignes_info.get(self._pending_ligne_id, {})
        variantes = ligne.get("variantes", [])

        # Build unique aller / retour options from variantes
        seen: set[str] = set()
        sens_options: list[dict] = []
        for v in variantes:
            key = "true" if v["sensAller"] else "false"
            if key in seen:
                continue
            seen.add(key)
            arrow = "→" if v["sensAller"] else "←"
            dest = v.get("destination", "")
            prec = v.get("precisionDestination", "")
            label = f"{arrow} {dest}"
            if prec:
                label += f" ({prec})"
            sens_options.append({"value": key, "label": label})

        if not sens_options:  # fallback if API gave no variantes
            sens_options = [
                {"value": "true",  "label": "→ Aller"},
                {"value": "false", "label": "← Retour"},
            ]

        if user_input is not None:
            sens_aller  = user_input["sens"] == "true"
            add_another = user_input.get("add_another", False)
            self._items.append({
                CONF_NOM:       self._pending_nom,
                CONF_ID_LIGNE:  self._pending_ligne_id,
                CONF_SENS_ALLER: sens_aller,
            })

            if add_another:
                return await self.async_step_liste()

            first_nom = self._items[0][CONF_NOM]
            self._pending_entry_title = self._name or f"Ginko — {first_nom} (liste)"
            self._pending_entry_data  = {
                CONF_API_KEY: self._api_key,
                "entry": {
                    "mode": MODE_LISTE,
                    CONF_ITEMS: self._items,
                    CONF_NB_PASSAGES: self._nb_passages,
                },
            }
            return await self.async_step_scan_config()

        ligne_label = ligne.get("numLignePublic", self._pending_ligne_id)
        nb_deja = len(self._items)
        desc = (
            f"Ligne sélectionnée : **{ligne_label}** — {ligne.get('libellePublic', '')}."
            if nb_deja == 0
            else f"**{nb_deja}** entrée(s) déjà ajoutée(s). Ligne : **{ligne_label}**."
        )

        return self.async_show_form(
            step_id="liste_sens",
            data_schema=vol.Schema({
                vol.Required("sens", default=sens_options[0]["value"]): SelectSelector(
                    SelectSelectorConfig(
                        options=sens_options,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional("add_another", default=False): BooleanSelector(),
            }),
            description_placeholders={"info": desc},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return GinkoOptionsFlow(config_entry)


class GinkoOptionsFlow(config_entries.OptionsFlow):
    """Options flow to modify an existing Ginko entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self._nb_passages: int = config_entry.data["entry"].get(CONF_NB_PASSAGES, 3)
        self._items: list[dict] = list(config_entry.data["entry"].get(CONF_ITEMS, []))
        self._scan_interval: int = config_entry.options.get(
            CONF_SCAN_INTERVAL,
            config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        self._add_item_pending: bool = False

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        mode     = self._entry.data["entry"]["mode"]
        is_suivi = mode == MODE_SUIVI_LIGNE

        if user_input is not None:
            if not is_suivi:
                self._nb_passages = int(user_input[CONF_NB_PASSAGES])
            self._add_item_pending = bool(user_input.get("add_item", False))
            scan_auto = bool(user_input.get("scan_auto", True))
            if scan_auto:
                self._scan_interval = 0
                return await self._save_options()
            # Manuel → step suivant pour le slider
            return await self.async_step_options_scan()

        schema_fields: dict = {}
        if not is_suivi:
            schema_fields[vol.Required(CONF_NB_PASSAGES, default=self._nb_passages)] = NumberSelector(
                NumberSelectorConfig(min=1, max=5, step=1, mode=NumberSelectorMode.BOX)
            )
        schema_fields[vol.Required("scan_auto", default=self._scan_interval == 0)] = BooleanSelector()
        if mode == MODE_LISTE:
            schema_fields[vol.Optional("add_item", default=False)] = BooleanSelector()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_fields),
        )

    async def async_step_options_scan(self, user_input: dict | None = None) -> FlowResult:
        """Étape optionnelle — intervalle de rafraîchissement manuel."""
        mode     = self._entry.data["entry"]["mode"]
        is_suivi = mode == MODE_SUIVI_LIGNE
        default  = self._scan_interval if self._scan_interval > 0 else (15 if is_suivi else 30)

        if user_input is not None:
            self._scan_interval = max(10, int(user_input[CONF_SCAN_INTERVAL]))
            return await self._save_options()

        return self.async_show_form(
            step_id="options_scan",
            data_schema=vol.Schema({
                vol.Required(CONF_SCAN_INTERVAL, default=default): NumberSelector(
                    NumberSelectorConfig(
                        min=10, max=MAX_SCAN_INTERVAL, step=5,
                        mode=NumberSelectorMode.SLIDER,
                        unit_of_measurement="s",
                    )
                ),
            }),
        )

    async def _save_options(self) -> FlowResult:
        """Sauvegarde nb_passages + scan_interval et redirige si besoin."""
        new_data = dict(self._entry.data)
        new_data["entry"] = {**self._entry.data["entry"], CONF_NB_PASSAGES: self._nb_passages}
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)
        if self._add_item_pending:
            return await self.async_step_add_item()
        return self.async_create_entry(title="", data={CONF_SCAN_INTERVAL: self._scan_interval})

    async def async_step_add_item(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            self._items.append({
                CONF_NOM: user_input[CONF_NOM].strip(),
                CONF_ID_LIGNE: user_input[CONF_ID_LIGNE].strip(),
                CONF_SENS_ALLER: bool(user_input[CONF_SENS_ALLER]),
            })
            if user_input.get("add_another"):
                return await self.async_step_add_item()

            new_data = dict(self._entry.data)
            new_data["entry"] = {
                **self._entry.data["entry"],
                CONF_ITEMS: self._items,
                CONF_NB_PASSAGES: self._nb_passages,
            }
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_item",
            data_schema=vol.Schema({
                vol.Required(CONF_NOM): TextSelector(),
                vol.Required(CONF_ID_LIGNE): TextSelector(),
                vol.Required(CONF_SENS_ALLER, default=True): BooleanSelector(),
                vol.Optional("add_another", default=False): BooleanSelector(),
            }),
        )
