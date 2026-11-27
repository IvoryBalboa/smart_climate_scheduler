"""Zentrale Hilfs-, Geräte- und Matrix-Funktionen für den Smart Climate Scheduler (Version 4.0.0)."""
from __future__ import annotations

import json
import logging
import math
import re
import time as time_mod
from datetime import datetime, time, timedelta
from typing import Any, Callable
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import callback as ha_callback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_ANOMALY_DETECTION_ENABLED,
    CONF_CLIMATE_ENTITIES,
    CONF_CLIMATE_ENTITY,
    CONF_COOLDOWN_ENABLED,
    CONF_CUSTOM_PRESETS,
    CONF_DEFAULT_PRESET,
    CONF_ENABLE_CLIMATE_ENTITY,
    CONF_ENABLE_SELF_LEARNING,
    CONF_PREHEAT_ENABLED,
    CONF_ROOM_TEMP_SENSOR,
    CONF_WINDOW_CLOSE_DELAY_MINUTES,
    CONF_WINDOW_OPEN_DELAY_MINUTES,
    CONF_WINDOW_PAUSE_ENABLED,
    CONF_WINDOW_SENSORS,
    CUSTOM_PRESET_COLOR_MAP,
    CUSTOM_PRESET_PALETTE,
    DEFAULT_ANOMALY_DETECTION_ENABLED,
    DEFAULT_COOLDOWN_ENABLED,
    DEFAULT_CUSTOM_PRESETS,
    DEFAULT_ENABLE_CLIMATE_ENTITY,
    DEFAULT_ENABLE_SELF_LEARNING,
    DEFAULT_FALLBACK_PRESET,
    DEFAULT_PREHEAT_ENABLED,
    DEFAULT_WINDOW_CLOSE_DELAY_MINUTES,
    DEFAULT_WINDOW_OPEN_DELAY_MINUTES,
    DEFAULT_WINDOW_PAUSE_ENABLED,
    DOMAIN,
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
    STARTUP_GRACE_SECONDS,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)

MAX_MATRIX_ADJUSTMENT_RATIO = 0.15  # Maximal ±15% Korrektur pro Lernschritt


def is_hass_starting(hass) -> bool:
    """Prüft defensiv (auch bei Test-Mocks), ob Home Assistant aktuell noch hochfährt."""
    if hass is None:
        return False
    state = getattr(hass, "state", None)
    if state is not None:
        state_str = getattr(state, "value", state)
        if isinstance(state_str, str):
            lower = state_str.lower()
            if lower in ("starting", "not_running"):
                return True
            if lower in ("running", "stopping", "final_write", "stopped"):
                return False
    is_running = getattr(hass, "is_running", None)
    if isinstance(is_running, bool):
        return not is_running
    return False


def get_startup_grace_state(hass) -> dict[str, Any]:
    """Liefert bzw. initialisiert den domain-weiten Startup-Karenz-Status."""
    if hass is None or not isinstance(getattr(hass, "data", None), dict):
        return {}
    return hass.data.setdefault(f"{DOMAIN}_startup_state", {})


def is_in_startup_grace(hass, now_monotonic: float | None = None) -> bool:
    """True, solange Home Assistant startet oder die 90s-Start-Karenzzeit noch läuft."""
    if hass is None:
        return False
    if is_hass_starting(hass):
        return True
    hass_data = getattr(hass, "data", None)
    if not isinstance(hass_data, dict):
        return False
    grace_state = hass_data.get(f"{DOMAIN}_startup_state")
    if not isinstance(grace_state, dict):
        return False
    grace_until = grace_state.get("grace_until")
    if isinstance(grace_until, (int, float)):
        now_val = time_mod.monotonic() if now_monotonic is None else now_monotonic
        return now_val < grace_until
    return False


def register_startup_grace_callback(
    hass,
    entry_id: str,
    callback: Callable[[], Any],
    on_started_callback: Callable[[], Any] | None = None,
) -> None:
    """Registriert Raum-Callbacks für den sofortigen Start-Sync sowie die Nachprüfung nach 90s."""
    if hass is None or not entry_id:
        return
    if not (is_hass_starting(hass) or is_in_startup_grace(hass)):
        return

    grace_state = get_startup_grace_state(hass)
    if not isinstance(grace_state, dict):
        return
    callbacks = grace_state.setdefault("callbacks", {})
    callbacks[entry_id] = callback
    if on_started_callback is not None and is_hass_starting(hass):
        started_cbs = grace_state.setdefault("on_started_callbacks", {})
        started_cbs[entry_id] = on_started_callback

    async def _run_started_callbacks() -> None:
        started_map = grace_state.get("on_started_callbacks")
        if not isinstance(started_map, dict) or not started_map:
            return
        pending = list(started_map.values())
        started_map.clear()
        for cb in pending:
            try:
                res = cb()
                if hasattr(res, "__await__"):
                    await res
            except Exception as err:
                _LOGGER.debug("Fehler beim HA-Start-Sync: %s", err)

    async def _run_grace_expired_callbacks() -> None:
        grace_state["grace_until"] = None
        grace_state["timer_handle"] = None
        for cb in list(grace_state.get("callbacks", {}).values()):
            try:
                res = cb()
                if hasattr(res, "__await__"):
                    await res
            except Exception as err:
                _LOGGER.debug("Fehler beim Post-Startup-Check: %s", err)

    def _schedule_post_grace_timer() -> None:
        old_handle = grace_state.get("timer_handle")
        if old_handle is not None and hasattr(old_handle, "cancel"):
            try:
                old_handle.cancel()
            except Exception:
                pass
            grace_state["timer_handle"] = None

        loop = getattr(hass, "loop", None)
        call_later = getattr(loop, "call_later", None)
        if callable(call_later):
            @ha_callback
            def _on_timer() -> None:
                grace_state["timer_handle"] = None
                if hasattr(hass, "async_create_task"):
                    hass.async_create_task(_run_grace_expired_callbacks())

            grace_state["timer_handle"] = call_later(STARTUP_GRACE_SECONDS, _on_timer)

    if is_hass_starting(hass) and not grace_state.get("listener_registered"):
        grace_state["listener_registered"] = True
        grace_state["started_fired"] = False

        @ha_callback
        def _on_ha_started(_event=None) -> None:
            # One-time listener is automatically removed by HA when the event fires;
            # clear event_unsub so clear_startup_grace_state never tries to remove it again.
            grace_state["started_fired"] = True
            grace_state["event_unsub"] = None
            hass_data = getattr(hass, "data", None)
            if not isinstance(hass_data, dict) or hass_data.get(f"{DOMAIN}_startup_state") is not grace_state:
                return
            grace_state["grace_until"] = time_mod.monotonic() + STARTUP_GRACE_SECONDS
            if grace_state.get("on_started_callbacks") and hasattr(hass, "async_create_task"):
                hass.async_create_task(_run_started_callbacks())
            _schedule_post_grace_timer()

        bus = getattr(hass, "bus", None)
        listen_once = getattr(bus, "async_listen_once", None)
        if callable(listen_once):
            event_unsub = listen_once(EVENT_HOMEASSISTANT_STARTED, _on_ha_started)
            if not grace_state.get("started_fired"):
                grace_state["event_unsub"] = event_unsub
        else:
            _on_ha_started()
    elif is_in_startup_grace(hass) and grace_state.get("grace_until") is not None and not grace_state.get("timer_handle"):
        _schedule_post_grace_timer()


def unregister_startup_grace_callback(hass, entry_id: str) -> None:
    """Entfernt die Startup-Check-Callbacks eines entladenen Config Entrys."""
    if hass is None or not isinstance(getattr(hass, "data", None), dict):
        return
    grace_state = hass.data.get(f"{DOMAIN}_startup_state")
    if not isinstance(grace_state, dict):
        return
    callbacks = grace_state.get("callbacks")
    if isinstance(callbacks, dict):
        callbacks.pop(entry_id, None)
    started_cbs = grace_state.get("on_started_callbacks")
    if isinstance(started_cbs, dict):
        started_cbs.pop(entry_id, None)


def clear_startup_grace_state(hass) -> None:
    """Bereinigt Timer und Listener des Startup-Grace-Trackers beim vollständigen Entladen."""
    if hass is None or not isinstance(getattr(hass, "data", None), dict):
        return
    grace_state = hass.data.pop(f"{DOMAIN}_startup_state", None)
    if not isinstance(grace_state, dict):
        return
    timer_handle = grace_state.pop("timer_handle", None)
    if timer_handle is not None and hasattr(timer_handle, "cancel"):
        try:
            timer_handle.cancel()
        except Exception:
            pass
    event_unsub = grace_state.pop("event_unsub", None)
    if (
        callable(event_unsub)
        and not grace_state.get("started_fired")
        and is_hass_starting(hass)
    ):
        try:
            event_unsub()
        except (ValueError, Exception):
            pass


def parse_time(time_str: str | None) -> time | None:
    """Wandelt einen Zeit-String im Format HH:MM:SS oder HH:MM in ein time-Objekt um."""
    if not time_str:
        return None
    try:
        parts = [int(p) for p in str(time_str).split(":")]
        if len(parts) == 2:
            return time(parts[0], parts[1])
        elif len(parts) == 3:
            return time(parts[0], parts[1], parts[2])
    except (ValueError, AttributeError, IndexError):
        pass
    return None


def safe_float(
    val: Any,
    default: float = 1.0,
    allow_zero_or_negative: bool = False,
) -> float:
    """Sicheres Parsen von Float-Werten mit Schutz vor None, Leerstrings, NaN und Inf."""
    if val is None or val == "":
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        if not allow_zero_or_negative and f <= 0:
            return default
        return round(f, 3)
    except (ValueError, TypeError):
        return default


def get_config_entry_slug(config_entry) -> str:
    name = (
        (config_entry.data.get("name") or config_entry.data.get("room_name"))
        if hasattr(config_entry, "data") and isinstance(config_entry.data, dict)
        else None
    ) or getattr(config_entry, "title", None) or "thermostat"
    try:
        from homeassistant.util import slugify
        return slugify(name)
    except Exception:
        import re
        return re.sub(r"[^\w]+", "_", str(name).lower().strip()).strip("_") or "thermostat"


ENTITY_SLUG_SUFFIXES: dict[str, dict[str, str]] = {
    # Switches
    "automatic": {
        "de": "automatik",
        "en": "auto",
        "es": "automatico",
        "fr": "automatique",
        "it": "automatico",
        "nl": "automatisch",
        "pl": "automatyczny",
    },
    "self_learning": {
        "de": "adaptives_lernen",
        "en": "self_learning",
        "es": "aprendizaje_adaptativo",
        "fr": "apprentissage_adaptatif",
        "it": "apprendimento_adattivo",
        "nl": "zelflerend",
        "pl": "samouczenie",
    },
    "preheat": {
        "de": "vorheizen",
        "en": "preheat",
        "es": "precalentamiento",
        "fr": "prechauffage",
        "it": "preriscaldamento",
        "nl": "voorverwarmen",
        "pl": "wstepne_nagrzewanie",
    },
    "cooldown": {
        "de": "auskuehlen",
        "en": "cooldown",
        "es": "enfriamiento",
        "fr": "refroidissement",
        "it": "raffreddamento",
        "nl": "afkoelen",
        "pl": "ochladzanie",
    },
    "hvac_off_on_target": {
        "de": "abschaltung_bei_zieltemperatur",
        "en": "turn_off_at_target",
        "es": "apagar_en_temperatura_objetivo",
        "fr": "arret_temperature_cible",
        "it": "spegni_alla_temperatura_desiderata",
        "nl": "uitschakelen_bij_doeltemperatuur",
        "pl": "wylacz_przy_temp_docelowej",
    },
    "opportunistic_heating": {
        "de": "opportunistisches_mitheizen",
        "en": "opportunistic_heating",
        "es": "calefaccion_oportunista",
        "fr": "chauffage_opportuniste",
        "it": "riscaldamento_opportunistico",
        "nl": "opportunistische_verwarming",
        "pl": "ogrzewanie_oportunistyczne",
    },
    "weather_forecast_preheat": {
        "de": "wettervorhersage_vorheizen",
        "en": "weather_forecast_preheat",
        "es": "pronostico_tiempo_precalentamiento",
        "fr": "previsions_meteo_prechauffage",
        "it": "previsioni_meteo_preriscaldamento",
        "nl": "weersverwachting_voorverwarmen",
        "pl": "prognoza_pogody_nagrzewanie",
    },
    "preheat_ignores_away": {
        "de": "vorheizen_bei_abwesenheit",
        "en": "preheat_ignores_away",
        "es": "precalentamiento_en_ausencia",
        "fr": "prechauffage_en_absence",
        "it": "preriscaldamento_in_assenza",
        "nl": "voorverwarmen_bij_afwezigheid",
        "pl": "nagrzewanie_podczas_nieobecnosci",
    },
    # Sensors
    "schedule": {
        "de": "zeitplan",
        "en": "schedule",
        "es": "horario",
        "fr": "programme",
        "it": "programma",
        "nl": "schema",
        "pl": "harmonogram",
    },
    "heating_rate": {
        "de": "aufheizrate",
        "en": "heating_rate",
        "es": "tasa_calentamiento",
        "fr": "taux_chauffe",
        "it": "tasso_riscaldamento",
        "nl": "opwarmsnelheid",
        "pl": "wskaznik_nagrzewania",
    },
    "cooling_rate": {
        "de": "abkuehlrate",
        "en": "cooling_rate",
        "es": "tasa_enfriamiento",
        "fr": "taux_refroidissement",
        "it": "tasso_raffreddamento",
        "nl": "afkoelsnelheid",
        "pl": "wskaznik_ochladzania",
    },
    "next_action": {
        "de": "naechste_aktion",
        "en": "next_action",
        "es": "proxima_accion",
        "fr": "action_suivante",
        "it": "prossima_azione",
        "nl": "volgende_actie",
        "pl": "nastepna_akcja",
    },
    # Binary sensors
    "binary_preheat": {
        "de": "vorheizen",
        "en": "preheat",
        "es": "precalentamiento",
        "fr": "prechauffage",
        "it": "preriscaldamento",
        "nl": "voorverwarmen",
        "pl": "wstepne_nagrzewanie",
    },
    "binary_cooldown": {
        "de": "abkuehlen",
        "en": "cooldown",
        "es": "enfriamiento",
        "fr": "refroidissement",
        "it": "raffreddamento",
        "nl": "afkoelen",
        "pl": "ochladzanie",
    },
    "binary_anomaly": {
        "de": "anomalie",
        "en": "anomaly",
        "es": "anomalia",
        "fr": "anomalie",
        "it": "anomalia",
        "nl": "afwijking",
        "pl": "anomalia",
    },
    "binary_heating_demand": {
        "de": "heizbedarf",
        "en": "heating_demand",
        "es": "demanda_calefaccion",
        "fr": "demande_chauffage",
        "it": "richiesta_riscaldamento",
        "nl": "warmtevraag",
        "pl": "zapotrzebowanie_ciepla",
    },
    # Debug sensor
    "diagnostics": {
        "de": "diagnose",
        "en": "diagnostics",
        "es": "diagnostico",
        "fr": "diagnostic",
        "it": "diagnosi",
        "nl": "diagnose",
        "pl": "diagnostyka",
    },
    # Select entity
    "schedule_profile": {
        "de": "zeitplan_profil",
        "en": "schedule_profile",
        "es": "perfil_horario",
        "fr": "profil_programme",
        "it": "profilo_programma",
        "nl": "schemaprofiel",
        "pl": "profil_harmonogramu",
    },
    # Optional virtual climate entity
    "room_thermostat": {
        "de": "thermostat",
        "en": "thermostat",
        "es": "termostato",
        "fr": "thermostat",
        "it": "termostato",
        "nl": "thermostaat",
        "pl": "termostat",
    },
}

# Legacy key aliases for backwards compatibility
ENTITY_SLUG_KEY_ALIASES: dict[str, str] = {
    "automatik": "automatic",
    "adaptives_lernen": "self_learning",
    "vorheizen": "preheat",
    "auskuehlen": "cooldown",
    "abschaltung_bei_zieltemperatur": "hvac_off_on_target",
    "opportunistisches_mitheizen": "opportunistic_heating",
    "wettervorhersage_vorheizen": "weather_forecast_preheat",
    "zeitplan": "schedule",
    "aufheizrate": "heating_rate",
    "abkuehlrate": "cooling_rate",
    "naechste_aktion": "next_action",
    "binary_vorheizen": "binary_preheat",
    "binary_abkuehlen": "binary_cooldown",
    "binary_anomalie": "binary_anomaly",
    "binary_heizbedarf": "binary_heating_demand",
    "diagnose": "diagnostics",
    "zeitplan_profil": "schedule_profile",
}


def get_ha_language(hass) -> str:
    """Returns the 2-letter language code configured in Home Assistant."""
    if not hass:
        return "de"
    config = getattr(hass, "config", None)
    lang = getattr(config, "language", "de") if config else "de"
    if isinstance(lang, str) and lang:
        return lang.split("-")[0].split("_")[0].lower()
    return "de"


def get_localized_slug_suffix(key: str, lang: str = "de") -> str:
    """Returns the localized entity_id slug suffix for the given key and language."""
    clean_lang = lang.lower().split("-")[0].split("_")[0] if isinstance(lang, str) else "de"
    canonical_key = ENTITY_SLUG_KEY_ALIASES.get(key, key)
    mapping = ENTITY_SLUG_SUFFIXES.get(canonical_key, {})
    return mapping.get(clean_lang, mapping.get("en", key))


def get_device_info(config_entry) -> DeviceInfo:
    """Erzeugt eine einheitliche DeviceInfo-Struktur für alle Entitäten eines Config Entrys."""
    name = config_entry.data.get("name", "thermostat")
    return DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=name,
        manufacturer="Smart Climate Scheduler",
        model="Smart Climate Scheduler Hub",
        sw_version=VERSION,
    )


def get_climate_entities(config_entry: Any) -> list[str]:
    """Gibt die normalisierte, deduplizierte Liste aller konfigurierten Thermostate zurück."""
    if not config_entry:
        return []
    options = getattr(config_entry, "options", None) or {}
    data = getattr(config_entry, "data", None) or {}

    raw_list = options.get(CONF_CLIMATE_ENTITIES)
    if raw_list is None:
        raw_list = data.get(CONF_CLIMATE_ENTITIES)

    candidates: list[str] = []
    if isinstance(raw_list, (list, tuple, set)):
        for item in raw_list:
            if isinstance(item, str) and item.strip():
                candidates.append(item.strip())
    elif isinstance(raw_list, str) and raw_list.strip():
        candidates.extend([p.strip() for p in raw_list.split(",") if p.strip()])

    legacy_single = options.get(CONF_CLIMATE_ENTITY)
    if legacy_single is None:
        legacy_single = data.get(CONF_CLIMATE_ENTITY)
    if isinstance(legacy_single, str) and legacy_single.strip():
        legacy_str = legacy_single.strip()
        if not candidates:
            candidates.append(legacy_str)

    deduped: list[str] = []
    seen: set[str] = set()
    for ent_id in candidates:
        if ent_id not in seen:
            seen.add(ent_id)
            deduped.append(ent_id)
    return deduped


def get_primary_climate_entity(config_entry: Any) -> str:
    """Gibt das primäre (erste) Thermostat aus der Gruppenliste zurück."""
    entities = get_climate_entities(config_entry)
    return entities[0] if entities else ""


def is_climate_entity_enabled(config_entry: Any) -> bool:
    """Gibt zurück, ob die optionale Raum-Climate-Entität für diesen Raum aktiviert ist."""
    if not config_entry:
        return DEFAULT_ENABLE_CLIMATE_ENTITY
    options = getattr(config_entry, "options", None) or {}
    data = getattr(config_entry, "data", None) or {}
    return bool(
        options.get(
            CONF_ENABLE_CLIMATE_ENTITY,
            data.get(CONF_ENABLE_CLIMATE_ENTITY, DEFAULT_ENABLE_CLIMATE_ENTITY),
        )
    )


def get_own_climate_entity_ids(
    hass: Any,
    config_entry: Any | None = None,
    candidate_name: str | None = None,
) -> set[str]:
    """Ermittelt alle eigenen virtuellen SCS-Climate-Entity-IDs zur Verhinderung von Selbstreferenzen."""
    own_ids: set[str] = set()
    lang = get_ha_language(hass)
    suffix = get_localized_slug_suffix("room_thermostat", lang)

    if hass:
        # 1. Aus laufender Domain-Registry (bereits erstellte Climate-Entitäten)
        domain_map = getattr(hass, "data", {}).get(DOMAIN, {}) if isinstance(getattr(hass, "data", None), dict) else {}
        for eid, store in domain_map.items():
            if not isinstance(store, dict) or str(eid).startswith("_"):
                continue
            cl_ent = store.get("climate_entity")
            if cl_ent and getattr(cl_ent, "entity_id", None):
                own_ids.add(str(cl_ent.entity_id).strip().lower())

        # 2. Aus der Home-Assistant Entity-Registry für unsere Domain
        try:
            from homeassistant.helpers import entity_registry as er

            ent_reg = er.async_get(hass)
            if ent_reg and hasattr(ent_reg, "entities"):
                entities_attr = getattr(ent_reg, "entities", {})
                entries_iter = entities_attr.values() if isinstance(entities_attr, dict) else []
                for reg_entry in entries_iter:
                    if (
                        getattr(reg_entry, "platform", None) == DOMAIN
                        and getattr(reg_entry, "domain", None) == "climate"
                        and getattr(reg_entry, "entity_id", None)
                    ):
                        own_ids.add(str(reg_entry.entity_id).strip().lower())
            if ent_reg and config_entry and hasattr(ent_reg, "async_get_entity_id"):
                reg_id = ent_reg.async_get_entity_id("climate", DOMAIN, f"{config_entry.entry_id}_climate")
                if isinstance(reg_id, str) and reg_id.strip():
                    own_ids.add(reg_id.strip().lower())
        except Exception:
            pass

    # 3. Vorhergesagte Entity-ID aus dem aktuellen ConfigEntry oder Raumnamen
    if config_entry is not None:
        slug = get_config_entry_slug(config_entry)
        own_ids.add(f"climate.{slug}_{suffix}".lower())
    if isinstance(candidate_name, str) and candidate_name.strip():
        try:
            from homeassistant.util import slugify as ha_slugify

            cand_slug = ha_slugify(candidate_name.strip())
        except Exception:
            cand_slug = re.sub(r"[^a-z0-9]+", "_", candidate_name.strip().lower()).strip("_")
        if cand_slug:
            own_ids.add(f"climate.{cand_slug}_{suffix}".lower())

    return own_ids


async def async_cleanup_virtual_climate_entity(hass: Any, config_entry: Any) -> None:
    """Entfernt eine zuvor angelegte virtuelle Climate-Entität sauber aus der Entity-Registry, wenn die Option aus ist."""
    if not hass or not config_entry:
        return
    try:
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        if not ent_reg or not hasattr(ent_reg, "async_get_entity_id"):
            return
        unique_id = f"{config_entry.entry_id}_climate"
        ent_id = ent_reg.async_get_entity_id("climate", DOMAIN, unique_id)
        if isinstance(ent_id, str) and ent_id.strip() and hasattr(ent_reg, "async_remove"):
            ent_reg.async_remove(ent_id)
            _LOGGER.info(
                "Optionale Climate-Entität '%s' aus Entity Registry entfernt (Option deaktiviert).",
                ent_id,
            )
    except Exception as err:
        _LOGGER.debug("Fehler beim Entfernen der optionalen Climate-Entität: %s", err)


def slugify_preset_id(raw_name: str, existing_ids: set[str] | None = None) -> str:
    """Erzeugt eine eindeutige, ENUM-konforme Kleinbuchstaben-ID ([a-z0-9_]) für eigene Presets."""
    s = str(raw_name or "").strip().lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    if not s or s == "none":
        s = "preset"
    base = s[:36]
    if existing_ids is None:
        return base
    candidate = base
    idx = 2
    while candidate in existing_ids or candidate == "none":
        candidate = f"{base}_{idx}"
        idx += 1
    return candidate


def _clamp_preset_temp(raw_temp: Any, default: float = 20.0) -> float:
    """Klemmt Zieltemperaturen auf [5.0, 30.0] und rundet exakt auf 0.1 °C."""
    try:
        val = float(raw_temp)
        if math.isnan(val) or math.isinf(val):
            return round(default, 1)
    except (ValueError, TypeError):
        return round(default, 1)
    return round(max(MIN_TARGET_TEMP, min(MAX_TARGET_TEMP, val)), 1)


def _normalize_hex_color(raw_color: Any, index: int = 0) -> str:
    if isinstance(raw_color, str):
        c = raw_color.strip().lower()
        if c in CUSTOM_PRESET_COLOR_MAP:
            return CUSTOM_PRESET_COLOR_MAP[c]
        if re.fullmatch(r"#[0-9a-f]{6}", c):
            return c
    return CUSTOM_PRESET_PALETTE[index % len(CUSTOM_PRESET_PALETTE)]


def normalize_custom_presets(
    raw_presets: Any,
    fallback_to_default: bool = True,
) -> list[dict[str, Any]]:
    """Validiert und normalisiert die freie Preset-Liste eines Raums (0.1 °C Schritte)."""
    if isinstance(raw_presets, str):
        try:
            raw_presets = json.loads(raw_presets)
        except Exception:
            raw_presets = None

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    if isinstance(raw_presets, list):
        for idx, entry in enumerate(raw_presets):
            if not isinstance(entry, dict):
                continue
            raw_name = str(entry.get("name") or entry.get("label") or entry.get("id") or "").strip()
            if not raw_name:
                continue
            raw_id = str(entry.get("id") or "").strip().lower()
            clean_id = slugify_preset_id(raw_id or raw_name, seen_ids)
            seen_ids.add(clean_id)
            temp_val = _clamp_preset_temp(entry.get("temperature"), 20.0)
            color_val = _normalize_hex_color(entry.get("color"), idx)
            items.append(
                {
                    "id": clean_id,
                    "name": raw_name[:40],
                    "temperature": temp_val,
                    "color": color_val,
                }
            )

    if not items and fallback_to_default:
        return [dict(p) for p in DEFAULT_CUSTOM_PRESETS]
    return items


def get_custom_presets(config_entry: Any) -> list[dict[str, Any]]:
    """Liest die konfigurierten eigenen Raum-Presets (mit Starter-Defaults bei Direkttemperatur)."""
    if not config_entry:
        return [dict(p) for p in DEFAULT_CUSTOM_PRESETS]
    options = getattr(config_entry, "options", None) or {}
    data = getattr(config_entry, "data", None) or {}
    raw = options.get(CONF_CUSTOM_PRESETS)
    if raw is None:
        raw = data.get(CONF_CUSTOM_PRESETS)
    if raw is None:
        return [dict(p) for p in DEFAULT_CUSTOM_PRESETS]
    normalized = normalize_custom_presets(raw, fallback_to_default=False)
    return normalized if normalized else [dict(p) for p in DEFAULT_CUSTOM_PRESETS]


def get_custom_presets_map(config_entry: Any) -> dict[str, dict[str, Any]]:
    """Liefert ein Dict {preset_id: {id, name, temperature, color}}."""
    return {p["id"]: p for p in get_custom_presets(config_entry)}


def get_preset_labels_map(config_entry: Any) -> dict[str, str]:
    """Liefert die Anzeigenamen-Zuordnung der konfigurierten Raum-Presets."""
    if not config_entry:
        return {}
    return {p["id"]: p["name"] for p in get_custom_presets(config_entry)}


def resolve_preset_key(
    preset_name: str | None,
    config_entry: Any = None,
    fallback_preset: str | None = None,
) -> str:
    """Löst einen Preset-Key robust gegen die Raum-Presets auf und fängt gelöschte Presets sicher ab."""
    key = str(preset_name or "none").strip().lower()
    if key == "none":
        return "none"
    custom_list = get_custom_presets(config_entry)
    valid_ids = {p["id"] for p in custom_list}
    if key in valid_ids:
        return key
    if fallback_preset and str(fallback_preset).strip().lower() in valid_ids:
        return str(fallback_preset).strip().lower()
    options = getattr(config_entry, "options", None) or {} if config_entry else {}
    data = getattr(config_entry, "data", None) or {} if config_entry else {}
    def_p = str(options.get(CONF_DEFAULT_PRESET, data.get(CONF_DEFAULT_PRESET, DEFAULT_FALLBACK_PRESET)) or "").strip().lower()
    if def_p in valid_ids:
        return def_p
    return custom_list[0]["id"] if custom_list else "eco"


def get_room_temp_sensor(config_entry: Any) -> str | None:
    """Liest die optionale externe Raumtemperatursensor-Entität."""
    if not config_entry:
        return None
    options = getattr(config_entry, "options", None) or {}
    data = getattr(config_entry, "data", None) or {}
    raw = options.get(CONF_ROOM_TEMP_SENSOR)
    if raw is None:
        raw = data.get(CONF_ROOM_TEMP_SENSOR)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def get_room_temp_with_timestamp(
    hass: Any,
    config_entry: Any,
    climate_entities: list[str] | None = None,
) -> tuple[float | None, str | None, datetime | None]:
    """Ermittelt die Raumtemperatur für SCS-Thermik/Hysterese: externer Sensor (Vorrang) oder Mittelwert der Thermostate."""
    states_mgr = getattr(hass, "states", None) if hass else None
    if not states_mgr:
        return None, None, None

    ext_sensor = get_room_temp_sensor(config_entry)
    if ext_sensor:
        st = states_mgr.get(ext_sensor)
        if st and getattr(st, "state", None) not in ("unavailable", "unknown", "None", None, ""):
            try:
                val = float(st.state)
                if not math.isnan(val) and not math.isinf(val):
                    return round(val, 2), ext_sensor, getattr(st, "last_updated", None)
            except (ValueError, TypeError):
                pass

    entities = climate_entities if climate_entities is not None else get_climate_entities(config_entry)
    temps: list[float] = []
    sources: list[str] = []
    timestamps: list[datetime] = []
    for ent_id in entities:
        st = states_mgr.get(ent_id)
        if not st or str(getattr(st, "state", "") or "").strip().lower() in ("unavailable", "unknown", "none"):
            continue
        attrs = getattr(st, "attributes", None) or {}
        raw_t = attrs.get("current_temperature")
        if raw_t is None:
            continue
        try:
            f_val = float(raw_t)
            if not math.isnan(f_val) and not math.isinf(f_val):
                temps.append(f_val)
                sources.append(ent_id)
                lu = getattr(st, "last_updated", None)
                if isinstance(lu, datetime):
                    timestamps.append(lu)
        except (ValueError, TypeError):
            continue

    if not temps:
        return None, None, None

    mean_temp = round(sum(temps) / len(temps), 2)
    src_label = sources[0] if len(sources) == 1 else "thermostat_group"
    latest_ts = max(timestamps) if timestamps else None
    return mean_temp, src_label, latest_ts


def get_room_current_temperature(
    hass: Any,
    config_entry: Any,
    climate_entities: list[str] | None = None,
) -> tuple[float | None, str | None]:
    """Ermittelt aktuelle Raumtemperatur + aktive Quelle (externer Sensor oder Thermostat-Gruppe)."""
    temp, src, _ = get_room_temp_with_timestamp(hass, config_entry, climate_entities)
    return temp, src


def get_group_hvac_heating(hass: Any, climate_entities: list[str]) -> tuple[bool, bool, str | None]:
    """Prüft Verfügbarkeit & Heizaktivität über alle Thermostate einer Raumgruppe."""
    states_mgr = getattr(hass, "states", None) if hass else None
    if not states_mgr or not climate_entities:
        return False, False, None

    any_available = False
    any_heating = False
    first_mode: str | None = None
    for ent_id in climate_entities:
        st = states_mgr.get(ent_id)
        if not st:
            continue
        st_str = str(getattr(st, "state", "") or "").strip().lower()
        if st_str in ("unavailable", "unknown", "none", ""):
            continue
        any_available = True
        if first_mode is None:
            first_mode = st_str
        attrs = getattr(st, "attributes", None) or {}
        hvac_act = attrs.get("hvac_action")
        if hvac_act is not None and str(hvac_act).strip() != "":
            if str(hvac_act).strip().lower() == "heating":
                any_heating = True
        elif st_str == "heat":
            any_heating = True

    return any_available, any_heating, ("heat" if any_heating else first_mode)


def get_window_sensors(config_entry: Any) -> list[str]:
    """Liest die konfigurierten optionalen Fenster-/Tür-Sensoren eines Raums."""
    if not config_entry:
        return []
    options = getattr(config_entry, "options", None) or {}
    data = getattr(config_entry, "data", None) or {}
    raw = options.get(CONF_WINDOW_SENSORS)
    if raw is None:
        raw = data.get(CONF_WINDOW_SENSORS)
    result: list[str] = []
    if isinstance(raw, (list, tuple, set)):
        for item in raw:
            if isinstance(item, str) and item.strip() and item.strip() not in result:
                result.append(item.strip())
    elif isinstance(raw, str) and raw.strip():
        for part in raw.split(","):
            p = part.strip()
            if p and p not in result:
                result.append(p)
    return result


def convert_legacy_seconds_to_delay_minutes(raw_seconds: Any, default_minutes: int) -> int:
    """Konvertiert veraltete Sekunden-Verzögerungen aus v3.x sauber in ganze Minuten (0..60)."""
    if raw_seconds is None or raw_seconds == "":
        return default_minutes
    try:
        sec = float(raw_seconds)
        if math.isnan(sec) or math.isinf(sec):
            return default_minutes
        if sec <= 0:
            return 0
        return max(1, min(60, int(round(sec / 60.0))))
    except (ValueError, TypeError):
        return default_minutes


def get_window_delays(config_entry: Any) -> tuple[int, int, bool]:
    """Gibt (open_delay_minutes, close_delay_minutes, window_pause_enabled) zurück (ganze Minuten 0..60)."""
    if not config_entry:
        return (
            DEFAULT_WINDOW_OPEN_DELAY_MINUTES,
            DEFAULT_WINDOW_CLOSE_DELAY_MINUTES,
            DEFAULT_WINDOW_PAUSE_ENABLED,
        )
    options = getattr(config_entry, "options", None) or {}
    data = getattr(config_entry, "data", None) or {}

    def _parse_delay_minutes(min_key: str, legacy_sec_key: str, default: int) -> int:
        raw = options.get(min_key)
        if raw is None:
            raw = data.get(min_key)
        if raw is not None:
            try:
                return max(0, min(60, int(round(float(raw)))))
            except (ValueError, TypeError):
                return default
        # Rückfall für noch nicht migrierte v3-Strukturen in Tests/Alt-Konfigs
        legacy_raw = options.get(legacy_sec_key)
        if legacy_raw is None:
            legacy_raw = data.get(legacy_sec_key)
        if legacy_raw is not None:
            return convert_legacy_seconds_to_delay_minutes(legacy_raw, default)
        return default

    open_delay = _parse_delay_minutes(
        CONF_WINDOW_OPEN_DELAY_MINUTES,
        "window_open_delay_seconds",
        DEFAULT_WINDOW_OPEN_DELAY_MINUTES,
    )
    close_delay = _parse_delay_minutes(
        CONF_WINDOW_CLOSE_DELAY_MINUTES,
        "window_close_delay_seconds",
        DEFAULT_WINDOW_CLOSE_DELAY_MINUTES,
    )
    pause_enabled = bool(
        options.get(
            CONF_WINDOW_PAUSE_ENABLED,
            data.get(CONF_WINDOW_PAUSE_ENABLED, DEFAULT_WINDOW_PAUSE_ENABLED),
        )
    )
    return open_delay, close_delay, pause_enabled


def is_sensor_window_open(state_obj: Any) -> bool:
    """Prüft, ob ein Fenster-/Tür-Binary-Sensor als geöffnet gilt."""
    if not state_obj:
        return False
    st_val = str(getattr(state_obj, "state", "") or "").strip().lower()
    return st_val in ("on", "open", "true", "1", "detected", "tilted")


def get_raw_window_open(
    hass: Any,
    config_entry: Any,
    climate_entities: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """Prüft unverzögert, ob mindestens ein konfigurierter Fenster-/Tür-Sensor 'offen' meldet."""
    states_mgr = getattr(hass, "states", None) if hass else None
    if not states_mgr:
        return False, []

    open_sources: list[str] = []
    for ws_id in get_window_sensors(config_entry):
        st = states_mgr.get(ws_id)
        if is_sensor_window_open(st):
            open_sources.append(ws_id)

    return bool(open_sources), open_sources


def clear_window_debounce_timer(domain_data: dict[str, Any] | None) -> None:
    """Bricht einen laufenden Fenster-Entprell-Timer sauber ab."""
    if not isinstance(domain_data, dict):
        return
    w_state = domain_data.get("window_state")
    if not isinstance(w_state, dict):
        return
    handle = w_state.pop("timer_handle", None)
    if handle is not None:
        if callable(handle):
            try:
                handle()
            except Exception:
                pass
        elif hasattr(handle, "cancel"):
            try:
                handle.cancel()
            except Exception:
                pass


def evaluate_window_debounce(
    domain_data: dict[str, Any] | None,
    raw_open: bool,
    open_delay_seconds: int,
    close_delay_seconds: int,
    now_mono: float | None = None,
    now_dt: datetime | None = None,
    schedule_fn: Callable[[float], Any] | None = None,
) -> dict[str, Any]:
    """Entprellungs-Zustandsautomat für verzögerte Fenster-Auf- und Fenster-Zu-Reaktion."""
    now_m = time_mod.monotonic() if now_mono is None else float(now_mono)
    cur_dt = now_dt or datetime.now()

    if not isinstance(domain_data, dict):
        return {
            "raw_open": bool(raw_open),
            "effective_open": bool(raw_open),
            "pending_action": None,
            "pending_until": None,
            "pending_until_mono": None,
            "transition": None,
        }

    w_state = domain_data.setdefault(
        "window_state",
        {
            "raw_open": bool(raw_open),
            "effective_open": False,
            "pending_action": None,
            "pending_until": None,
            "pending_until_mono": None,
            "timer_handle": None,
            "saved_hvac_modes": {},
            "initialized": False,
        },
    )

    open_delay = max(0, int(open_delay_seconds))
    close_delay = max(0, int(close_delay_seconds))
    prev_effective = bool(w_state.get("effective_open", False))
    transition: str | None = None

    if not w_state.get("initialized"):
        w_state["initialized"] = True
        w_state["raw_open"] = bool(raw_open)
        if not raw_open or open_delay == 0:
            w_state["effective_open"] = bool(raw_open)
            w_state["pending_action"] = None
            w_state["pending_until"] = None
            w_state["pending_until_mono"] = None
            if raw_open:
                transition = "opened"
            return {
                "raw_open": bool(raw_open),
                "effective_open": bool(w_state["effective_open"]),
                "pending_action": None,
                "pending_until": None,
                "pending_until_mono": None,
                "transition": transition,
            }

    w_state["raw_open"] = bool(raw_open)

    if raw_open != prev_effective:
        target_action = "pause" if raw_open else "resume"
        delay_sec = open_delay if raw_open else close_delay

        if delay_sec <= 0:
            clear_window_debounce_timer(domain_data)
            w_state["effective_open"] = bool(raw_open)
            w_state["pending_action"] = None
            w_state["pending_until"] = None
            w_state["pending_until_mono"] = None
            transition = "opened" if raw_open else "closed"
        else:
            pending_until_mono = w_state.get("pending_until_mono")
            if w_state.get("pending_action") != target_action or pending_until_mono is None:
                clear_window_debounce_timer(domain_data)
                until_mono = now_m + delay_sec
                until_dt = cur_dt + timedelta(seconds=delay_sec)
                w_state["pending_action"] = target_action
                w_state["pending_until_mono"] = until_mono
                w_state["pending_until"] = until_dt.isoformat()
                if callable(schedule_fn):
                    w_state["timer_handle"] = schedule_fn(delay_sec)
            elif now_m >= float(pending_until_mono):
                clear_window_debounce_timer(domain_data)
                w_state["effective_open"] = bool(raw_open)
                w_state["pending_action"] = None
                w_state["pending_until"] = None
                w_state["pending_until_mono"] = None
                transition = "opened" if raw_open else "closed"
    else:
        # Rohzustand entspricht bereits dem effektiven Zustand -> laufende Gegen-Verzögerung abbrechen
        if w_state.get("pending_action") is not None:
            clear_window_debounce_timer(domain_data)
            w_state["pending_action"] = None
            w_state["pending_until"] = None
            w_state["pending_until_mono"] = None

    return {
        "raw_open": bool(w_state.get("raw_open", False)),
        "effective_open": bool(w_state.get("effective_open", False)),
        "pending_action": w_state.get("pending_action"),
        "pending_until": w_state.get("pending_until"),
        "pending_until_mono": w_state.get("pending_until_mono"),
        "transition": transition,
    }


def get_effective_window_open(
    domain_data: dict[str, Any] | None,
    hass: Any = None,
    config_entry: Any = None,
) -> bool:
    """Liest den wirksamen (ggf. entprellten) Fenster-Offen-Zustand eines Raums."""
    if isinstance(domain_data, dict):
        w_state = domain_data.get("window_state")
        if isinstance(w_state, dict) and w_state.get("initialized"):
            return bool(w_state.get("effective_open", False))
    if hass and config_entry:
        raw_open, _ = get_raw_window_open(hass, config_entry)
        open_delay, _, _ = get_window_delays(config_entry)
        if not raw_open:
            return False
        if open_delay == 0 or not get_window_sensors(config_entry):
            return True
    return False


def get_preset_temperature(
    climate_state: Any,
    preset_name: str | None,
    config_entry: Any = None,
    custom_presets: list[dict[str, Any]] | None = None,
) -> float:
    """Ermittelt die Zieltemperatur für ein Raum-Preset aus der konfigurierten Preset-Liste."""
    if not preset_name:
        return 20.0

    p_clean = str(preset_name).strip()
    p_lower = p_clean.lower()

    preset_list = custom_presets
    if preset_list is None and config_entry is not None:
        preset_list = get_custom_presets(config_entry)

    if isinstance(preset_list, list) and preset_list:
        for item in preset_list:
            if str(item.get("id", "")).strip().lower() == p_lower:
                return _clamp_preset_temp(item.get("temperature"), 20.0)
        if config_entry is not None:
            resolved_key = resolve_preset_key(p_lower, config_entry)
            for item in preset_list:
                if str(item.get("id", "")).strip().lower() == resolved_key:
                    return _clamp_preset_temp(item.get("temperature"), 20.0)

    if climate_state is not None:
        attrs = getattr(climate_state, "attributes", None) or {}
        attr_key = f"{p_clean}_temperature"
        if attr_key in attrs:
            try:
                return round(float(attrs[attr_key]), 1)
            except (ValueError, TypeError):
                pass

    defaults = {
        "comfort": 21.0,
        "home": 21.0,
        "eco": 18.0,
        "sleep": 17.0,
        "away": 15.5,
        "boost": 23.0,
        "none": 20.0,
    }
    return defaults.get(p_lower, 20.0)


def get_outside_temperature(
    hass,
    outside_sensor: str | None = None,
    outside_weather_entity: str | None = None,
) -> float | None:
    """Ermittelt die Außentemperatur: Sensor hat Vorrang vor Wetter-Entität ('temperature'-Attribut)."""
    val, _ = get_resolved_outside_info(hass, outside_sensor, outside_weather_entity)
    return val


def get_resolved_outside_info(
    hass,
    outside_sensor: str | None = None,
    outside_weather_entity: str | None = None,
) -> tuple[float | None, str | None]:
    """Ermittelt die Außentemperatur und die aktive Quell-Entität (Sensor vor Wetter-Entität)."""
    if not hass:
        return None, None

    # 1. Höchste Priorität: Direkter Sensor (Zustand ist numerisch)
    if outside_sensor:
        st = hass.states.get(outside_sensor)
        if st and st.state not in ("unavailable", "unknown", "None", None):
            try:
                return float(st.state), outside_sensor
            except (ValueError, TypeError):
                pass

    # 2. Fallback: Wetter-Entität (Nutzt das Attribut 'temperature')
    if outside_weather_entity:
        st = hass.states.get(outside_weather_entity)
        if st and st.state not in ("unavailable", "unknown", "None", None):
            temp_attr = st.attributes.get("temperature")
            if temp_attr is not None:
                try:
                    return float(temp_attr), outside_weather_entity
                except (ValueError, TypeError):
                    pass

    return None, None


def parse_datetime(dt_val: Any) -> datetime | None:
    """Parst einen ISO-8601 Zeitstempel oder datetime-Objekt."""
    if not dt_val:
        return None
    if isinstance(dt_val, datetime):
        return dt_val
    try:
        dt_str = str(dt_val)
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


async def async_get_hourly_forecast(hass, weather_entity: str | None) -> list[dict]:
    """Ermittelt die stündliche Wettervorhersage (modern per weather.get_forecasts oder Attribut)."""
    if not hass or not weather_entity:
        return []

    # Schutz vor Warning in homeassistant.helpers.service / helpers/target.py:176:
    # Service Call nur ausführen, wenn die Entität in Home Assistant registriert und verfügbar ist!
    if hasattr(hass, "states"):
        st = hass.states.get(weather_entity)
        if not st or st.state in ("unavailable", "unknown", "None", None):
            _LOGGER.debug(
                "Wetter-Entität '%s' nicht verfügbar (Status: %s) - überspringe weather.get_forecasts",
                weather_entity,
                st.state if st else "None",
            )
            return []

    forecast_items = []

    # 1. Moderner Weg: weather.get_forecasts Service Call (Home Assistant 2023.12+)
    try:
        if hasattr(hass, "services") and hass.services.has_service("weather", "get_forecasts"):
            res = await hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
            if isinstance(res, dict) and weather_entity in res:
                raw_fc = res[weather_entity].get("forecast")
                if isinstance(raw_fc, list):
                    forecast_items = raw_fc
    except Exception as e:
        _LOGGER.debug("weather.get_forecasts Service Call fehlgeschlagen für %s: %s", weather_entity, e)

    # 2. Abwärtskompatibler Fallback: Attribut 'forecast' des Wetter-States
    if not forecast_items and hasattr(hass, "states"):
        st = hass.states.get(weather_entity)
        if st and isinstance(st.attributes.get("forecast"), list):
            forecast_items = st.attributes.get("forecast", [])

    parsed_forecast = []
    for item in forecast_items:
        if not isinstance(item, dict):
            continue
        dt = parse_datetime(item.get("datetime"))
        temp = item.get("temperature")
        if dt is not None and temp is not None:
            try:
                parsed_forecast.append({
                    "datetime": dt,
                    "temperature": float(temp),
                })
            except (ValueError, TypeError):
                continue

    return parsed_forecast


def get_forecast_temperature_for_window(
    forecast_list: list[dict] | None,
    window_start: datetime,
    window_end: datetime,
) -> float | None:
    """Berechnet das arithmetische Mittel der prognostizierten Außentemperaturen im Vorheiz-Zeitfenster."""
    if not forecast_list or window_start >= window_end:
        return None

    matching_temps = []
    for item in forecast_list:
        raw_dt = item.get("datetime")
        temp = item.get("temperature")
        if not raw_dt or temp is None:
            continue

        dt = parse_datetime(raw_dt) if isinstance(raw_dt, str) else raw_dt
        if not isinstance(dt, datetime):
            continue

        if window_start.tzinfo and not dt.tzinfo:
            dt = dt.replace(tzinfo=window_start.tzinfo)
        elif not window_start.tzinfo and dt.tzinfo:
            dt = dt.replace(tzinfo=None)

        if window_start <= dt <= window_end:
            matching_temps.append(float(temp))

    if not matching_temps:
        mid_time = window_start + (window_end - window_start) / 2
        closest_diff = None
        closest_temp = None
        for item in forecast_list:
            raw_dt = item.get("datetime")
            temp = item.get("temperature")
            if not raw_dt or temp is None:
                continue
            dt = parse_datetime(raw_dt) if isinstance(raw_dt, str) else raw_dt
            if not isinstance(dt, datetime):
                continue
            if mid_time.tzinfo and not dt.tzinfo:
                dt = dt.replace(tzinfo=mid_time.tzinfo)
            elif not mid_time.tzinfo and dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            diff = abs((dt - mid_time).total_seconds())
            if diff <= 7200:
                if closest_diff is None or diff < closest_diff:
                    closest_diff = diff
                    closest_temp = float(temp)
        if closest_temp is not None:
            return round(closest_temp, 2)
        return None

    return round(sum(matching_temps) / len(matching_temps), 2)


# ---------------------------------------------------------------------------
# Zentrale Matrix-, EMA- & Raten-Berechnungsfunktionen (Aufheizen & Abkühlen)
# ---------------------------------------------------------------------------


def normalize_temp_key(raw_temp: Any) -> str:
    """Vereinheitlicht einen Außentemperatur-Schlüssel auf Ganzzahl-String (z. B. '5', '-2') oder 'default'."""
    if raw_temp is None or str(raw_temp).strip().lower() in ("default", "none", ""):
        return "default"
    try:
        return str(int(round(float(raw_temp))))
    except (ValueError, TypeError):
        return str(raw_temp).strip()


def normalize_matrix(raw_matrix: dict | None) -> dict[str, float]:
    """Normalisiert eine Außentemperatur-Matrix auf positive Float-Durchschnittswerte."""
    if not isinstance(raw_matrix, dict):
        return {}

    normalized: dict[str, float] = {}
    for key, val in raw_matrix.items():
        k_str = str(key)
        try:
            if isinstance(val, (int, float)):
                f_val = float(val)
                if not math.isnan(f_val) and not math.isinf(f_val) and f_val > 0:
                    normalized[k_str] = round(f_val, 3)
            elif isinstance(val, list):
                pos_vals = []
                for x in val:
                    fx = float(x)
                    if not math.isnan(fx) and not math.isinf(fx) and fx > 0:
                        pos_vals.append(fx)
                if pos_vals:
                    normalized[k_str] = round(sum(pos_vals) / len(pos_vals), 3)
        except (ValueError, TypeError):
            continue
    return normalized


def calculate_overall_average(
    matrix: dict[str, float] | None,
    fallback_rate: float = 1.0,
    already_normalized: bool = False,
) -> float:
    """Bildet aus allen Werten einer Matrix den Gesamt-Durchschnitt."""
    safe_fallback = safe_float(fallback_rate, 1.0)
    norm = matrix if (already_normalized and isinstance(matrix, dict)) else normalize_matrix(matrix)
    valid_vals = [v for v in norm.values() if isinstance(v, (int, float)) and v > 0]
    if not valid_vals:
        return round(safe_fallback, 3)
    return round(sum(valid_vals) / len(valid_vals), 3)


def update_matrix_with_rate(
    matrix: dict | None,
    outside_temp: float | None,
    rate: float,
    fallback_rate: float = 1.0,
    max_adjustment_ratio: float = MAX_MATRIX_ADJUSTMENT_RATIO,
) -> tuple[dict[str, float], float, float]:
    """Ordnet einen gemessenen Ratenwert der Außentemperatur-Matrix zu (max. ±5% Korrektur)."""
    norm_matrix = normalize_matrix(matrix)
    safe_fallback = safe_float(fallback_rate, 1.0)

    try:
        rate_val = float(rate)
    except (ValueError, TypeError):
        rate_val = 0.0

    if math.isnan(rate_val) or rate_val <= 0:
        overall = calculate_overall_average(norm_matrix, safe_fallback, already_normalized=True)
        return norm_matrix, 0.0, overall

    bucket_key = normalize_temp_key(outside_temp)

    if bucket_key in norm_matrix and norm_matrix[bucket_key] > 0:
        old_avg = norm_matrix[bucket_key]
        min_allowed = old_avg * (1.0 - max_adjustment_ratio)
        max_allowed = old_avg * (1.0 + max_adjustment_ratio)
        candidate_avg = (old_avg + rate_val) / 2.0

        if rate_val >= max_allowed:
            new_bucket_avg = round(max_allowed, 3)
        elif rate_val <= min_allowed:
            new_bucket_avg = round(min_allowed, 3)
        else:
            new_bucket_avg = round(max(min_allowed, min(max_allowed, candidate_avg)), 3)
    else:
        new_bucket_avg = round(rate_val, 3)

    norm_matrix[bucket_key] = new_bucket_avg
    overall_avg = calculate_overall_average(norm_matrix, safe_fallback, already_normalized=True)
    return norm_matrix, new_bucket_avg, overall_avg


def apply_ema(new_rate: float, current_ema: float | None, alpha: float = 0.35) -> float:
    """Glättet einen Ratenwert mit exponentiellem gleitendem Durchschnitt (EMA)."""
    if current_ema is None or current_ema <= 0:
        return round(new_rate, 3)
    smoothed = (alpha * new_rate) + ((1.0 - alpha) * current_ema)
    return round(smoothed, 3)


def get_effective_rate(
    entry_data: dict,
    outside_temp: float | None,
    fallback_rate: float = 1.0,
    learning_enabled: bool = True,
    matrix_key: str = "averages",
    avg_key: str = "average",
) -> float:
    """Ermittelt die geltende Rate (Matrix-Wert mit stetiger linearer Interpolation, Ausreißer-Dämpfung und festen Plausibilitätsgrenzen)."""
    is_cooling = (matrix_key == "cooling_averages")
    safe_fallback = safe_float(fallback_rate, 0.2 if is_cooling else 1.0)
    if not learning_enabled:
        return round(safe_fallback, 3)

    raw_matrix = entry_data.get(matrix_key, {})
    matrix = raw_matrix if isinstance(raw_matrix, dict) else {}

    # Numerische Buckets für stetige Interpolation aufbereiten
    numeric_buckets: dict[int, float] = {}
    for k, v in matrix.items():
        try:
            if isinstance(v, (int, float)) and v > 0 and not math.isnan(v):
                numeric_buckets[int(round(float(k)))] = float(v)
        except (ValueError, TypeError):
            continue

    # Wenn die Matrix noch komplett leer ist (Kaltstart vor allererster Messung), Fallback nutzen
    if not numeric_buckets and not matrix.get("default"):
        return round(safe_fallback, 3)

    # Globaler Referenzwert rein aus gelernten Daten berechnen (ohne Fallback-Verfälschung)
    stored_avg = entry_data.get(avg_key)
    if isinstance(stored_avg, (int, float)) and stored_avg > 0 and not math.isnan(stored_avg):
        global_avg = float(stored_avg)
    elif numeric_buckets:
        global_avg = sum(numeric_buckets.values()) / float(len(numeric_buckets))
    else:
        computed_avg = calculate_overall_average(matrix, safe_fallback, already_normalized=True)
        global_avg = computed_avg if computed_avg > 0 else safe_fallback

    local_rate: float | None = None

    if outside_temp is not None and numeric_buckets:
        try:
            t_out = float(outside_temp)
            sorted_keys = sorted(numeric_buckets.keys())

            if t_out <= sorted_keys[0]:
                local_rate = numeric_buckets[sorted_keys[0]]
            elif t_out >= sorted_keys[-1]:
                local_rate = numeric_buckets[sorted_keys[-1]]
            else:
                # Stetige lineare Interpolation zwischen den zwei nächstliegenden Stützpunkten
                k_low = max(k for k in sorted_keys if k <= t_out)
                k_high = min(k for k in sorted_keys if k >= t_out)
                if k_low == k_high:
                    local_rate = numeric_buckets[k_low]
                else:
                    weight = (t_out - k_low) / float(k_high - k_low)
                    local_rate = (1.0 - weight) * numeric_buckets[k_low] + weight * numeric_buckets[k_high]
        except (ValueError, TypeError):
            pass

    # Falls Außentemperatur nicht zuordenbar, 'default' oder Gesamtmittelwert nutzen
    if local_rate is None or local_rate <= 0:
        default_val = matrix.get("default")
        if isinstance(default_val, (int, float)) and default_val > 0:
            local_rate = float(default_val)
        else:
            local_rate = global_avg

    # Ausreißer-Schutz und Glättung:
    # Weicht ein einzelner Bucket drastisch (>40%) nach unten vom Gesamt-Durchschnitt ab,
    # wird er mit dem Gesamtschnitt stabilisiert
    if global_avg > 0:
        if not is_cooling:
            if local_rate < 0.6 * global_avg:
                local_rate = 0.5 * local_rate + 0.5 * global_avg
            elif local_rate > 2.5 * global_avg:
                local_rate = 0.6 * local_rate + 0.4 * global_avg
        else:
            if local_rate < 0.5 * global_avg:
                local_rate = 0.5 * local_rate + 0.5 * global_avg
            elif local_rate > 2.5 * global_avg:
                local_rate = 0.6 * local_rate + 0.4 * global_avg

    # Feste physikalische Plausibilitätsgrenzen (unabhängig von der Fallback-Rate)
    if is_cooling:
        min_floor = 0.02
        max_cap = 1.50
    else:
        min_floor = 0.10
        max_cap = 3.00

    clamped_rate = max(min_floor, min(max_cap, local_rate))
    return round(clamped_rate, 3)


async def async_set_matrix_entry(
    store: dict,
    raw_temp: Any,
    raw_rate: Any,
    fallback_rate: float,
    is_cooling: bool = False,
) -> tuple[str, float, float]:
    """Setzt oder aktualisiert einen Eintrag in der Aufheiz- oder Abkühl-Matrix inkl. Persistenz."""
    temp_key = normalize_temp_key(raw_temp)
    min_r, max_r, def_r = (0.01, 2.0, 0.2) if is_cooling else (0.05, 5.0, 1.0)
    matrix_key = "cooling_averages" if is_cooling else "averages"
    avg_key = "cooling_average" if is_cooling else "average"

    clamped_rate = round(max(min_r, min(max_r, safe_float(raw_rate, def_r))), 3)
    averages = dict(store.get(matrix_key, {}))
    averages[temp_key] = clamped_rate
    store[matrix_key] = averages

    overall_avg = calculate_overall_average(averages, fallback_rate, already_normalized=True)
    store[avg_key] = overall_avg

    storage = store.get("storage")
    if storage:
        await storage.async_save_data({
            matrix_key: averages,
            avg_key: overall_avg,
        })

    return temp_key, clamped_rate, overall_avg


async def async_delete_matrix_entry(
    store: dict,
    raw_temp: Any,
    fallback_rate: float,
    is_cooling: bool = False,
) -> tuple[str, float | None]:
    """Entfernt einen Eintrag aus der Aufheiz- oder Abkühl-Matrix inkl. Persistenz."""
    temp_key = normalize_temp_key(raw_temp)
    matrix_key = "cooling_averages" if is_cooling else "averages"
    avg_key = "cooling_average" if is_cooling else "average"

    averages = dict(store.get(matrix_key, {}))
    if temp_key not in averages:
        return temp_key, None

    averages.pop(temp_key)
    store[matrix_key] = averages

    overall_avg = calculate_overall_average(averages, fallback_rate, already_normalized=True)
    store[avg_key] = overall_avg

    storage = store.get("storage")
    if storage:
        await storage.async_save_data({
            matrix_key: averages,
            avg_key: overall_avg,
        })

    return temp_key, overall_avg


def get_target_hvac_mode(climate_state: Any) -> str:
    """Ermittelt den passenden Heiz-Modus für ein Climate Entity (heat, auto, etc.)."""
    if not climate_state:
        return "heat"
    attrs = getattr(climate_state, "attributes", None) or {}
    supported_modes = attrs.get("hvac_modes") or []
    if "heat" in supported_modes:
        return "heat"
    if "auto" in supported_modes:
        return "auto"
    if "heat_cool" in supported_modes:
        return "heat_cool"
    return "heat"


async def async_sync_entity_registry_disabled(hass: Any, config_entry: Any) -> None:
    """Synchronisiert den Deaktiviert-Status in der Entity Registry basierend auf den Optionen."""
    if not hass or not config_entry:
        return
    try:
        from homeassistant.helpers import entity_registry as er
        ent_reg = er.async_get(hass)

        def _sync_entity(domain_plat: str, unique_id: str, is_active: bool) -> None:
            ent_id = ent_reg.async_get_entity_id(domain_plat, DOMAIN, unique_id)
            if not ent_id:
                return
            reg_entry = ent_reg.async_get(ent_id)
            if not reg_entry:
                return
            if not is_active and not reg_entry.disabled:
                ent_reg.async_update_entity(ent_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
                _LOGGER.info("Sensor '%s' in Entity Registry deaktiviert (Option ausgeschaltet).", ent_id)
            elif is_active and reg_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
                ent_reg.async_update_entity(ent_id, disabled_by=None)
                _LOGGER.info("Sensor '%s' in Entity Registry reaktiviert (Option eingeschaltet).", ent_id)

        # 1. Vorheizen (binary_sensor.<entry_id>_preheat)
        preheat_on = bool(
            config_entry.options.get(
                CONF_PREHEAT_ENABLED,
                config_entry.data.get(CONF_PREHEAT_ENABLED, DEFAULT_PREHEAT_ENABLED),
            )
        )
        _sync_entity("binary_sensor", f"{config_entry.entry_id}_preheat", preheat_on)

        # 2. Auskühlen (binary_sensor.<entry_id>_cooldown)
        cooldown_on = bool(
            config_entry.options.get(
                CONF_COOLDOWN_ENABLED,
                config_entry.data.get(CONF_COOLDOWN_ENABLED, DEFAULT_COOLDOWN_ENABLED),
            )
        )
        _sync_entity("binary_sensor", f"{config_entry.entry_id}_cooldown", cooldown_on)

        # 3. Selbstlernen (sensor.<entry_id>_heating_rate, sensor.<entry_id>_cooling_rate)
        learning_on = bool(
            config_entry.options.get(
                CONF_ENABLE_SELF_LEARNING,
                config_entry.data.get(CONF_ENABLE_SELF_LEARNING, DEFAULT_ENABLE_SELF_LEARNING),
            )
        )
        _sync_entity("sensor", f"{config_entry.entry_id}_heating_rate", learning_on)
        _sync_entity("sensor", f"{config_entry.entry_id}_cooling_rate", learning_on)

        # 4. Anomalie- & Hardware-Wächter (binary_sensor.<entry_id>_anomaly)
        anomaly_on = bool(
            config_entry.options.get(
                CONF_ANOMALY_DETECTION_ENABLED,
                config_entry.data.get(CONF_ANOMALY_DETECTION_ENABLED, DEFAULT_ANOMALY_DETECTION_ENABLED),
            )
        )
        _sync_entity("binary_sensor", f"{config_entry.entry_id}_anomaly", anomaly_on)
    except Exception as err:
        _LOGGER.debug("Fehler beim Synchronisieren der Entity-Registry Deaktivierung: %s", err)


async def async_sync_device_registry_version(hass: Any, config_entry: Any) -> str:
    """Synchronisiert die Firmware-Anzeige (sw_version) in der Home Assistant Device Registry direkt mit manifest.json."""
    live_version = VERSION
    if not hass or not config_entry:
        return live_version

    try:
        from homeassistant.loader import async_get_integration
        integration = await async_get_integration(hass, DOMAIN)
        if integration and getattr(integration, "version", None):
            live_version = str(integration.version)
    except Exception:
        live_version = VERSION

    try:
        from homeassistant.helpers import device_registry as dr
        dev_reg = dr.async_get(hass)
        if dev_reg:
            devices_to_check: list[Any] = []
            if hasattr(dr, "async_entries_for_config_entry"):
                entries = dr.async_entries_for_config_entry(dev_reg, config_entry.entry_id)
                if isinstance(entries, (list, tuple, set)):
                    devices_to_check.extend(entries)
            if not devices_to_check and hasattr(dev_reg, "async_get_device_by_identifier"):
                dev = dev_reg.async_get_device_by_identifier((DOMAIN, config_entry.entry_id))
                if dev:
                    devices_to_check.append(dev)

            target_ident = (DOMAIN, config_entry.entry_id)
            for device in devices_to_check:
                idents = getattr(device, "identifiers", None) or set()
                if not idents or target_ident in idents:
                    if getattr(device, "sw_version", None) != live_version:
                        dev_reg.async_update_device(
                            device.id,
                            sw_version=live_version,
                            manufacturer="Smart Climate Scheduler",
                            model="Smart Climate Scheduler Hub",
                        )
    except Exception as err:
        _LOGGER.debug("Fehler beim Synchronisieren der Device-Registry Version: %s", err)

    return live_version


def get_profiles_and_active(config_entry: Any) -> tuple[dict[str, dict[str, list[dict]]], str]:
    """Extrahiert alle Zeitplan-Profile und den Namen des aktiven Profils (mit automatischer Migration von 'schedule')."""
    if not config_entry:
        return {"Standard": {}}, "Standard"

    options = getattr(config_entry, "options", {}) or {}
    data = getattr(config_entry, "data", {}) or {}

    raw_profiles = options.get("profiles") or data.get("profiles")
    if isinstance(raw_profiles, dict) and raw_profiles:
        profiles = {str(k): (v if isinstance(v, dict) else {}) for k, v in raw_profiles.items()}
    else:
        # Fallback / Migration: Einzelzeitplan 'schedule' wird als 'Standard'-Profil übernommen
        legacy_schedule = options.get("schedule") or data.get("schedule") or {}
        profiles = {"Standard": legacy_schedule if isinstance(legacy_schedule, dict) else {}}

    if not profiles:
        profiles = {"Standard": {}}

    active_profile = options.get("active_profile") or data.get("active_profile") or "Standard"
    if active_profile not in profiles:
        active_profile = list(profiles.keys())[0]

    return profiles, str(active_profile)


def async_write_ha_state_if_enabled(entity: Any) -> None:
    """Schreibt den Zustand der Entität nur dann, wenn sie existiert, hass hat und NICHT deaktiviert ist."""
    if entity is None:
        return
    if getattr(entity, "hass", None) is None:
        return
    # In Home Assistant ist `entity.enabled` False, wenn die Entität in der Entity Registry deaktiviert ist.
    if getattr(entity, "enabled", True) is False:
        return
    entity.async_write_ha_state()


def resolve_entry_entity_id(
    hass: Any,
    entry_obj: Any,
    entity_domain: str,
    unique_suffix: str,
    fallback_suffix: str | None = None,
    runtime_key: str | None = None,
) -> str:
    """Löst die aktuelle entity_id eines Config-Entry-Objekts robust auf (Entity Registry -> Laufzeit -> Slug-Fallback)."""
    entry_id = getattr(entry_obj, "entry_id", None) if entry_obj else None
    prefix = f"{entity_domain}."

    # 1. Primär: Home Assistant Entity Registry über stabile unique_id (<entry_id>_<unique_suffix>)
    if hass and entry_id:
        try:
            from homeassistant.helpers import entity_registry as er

            ent_reg = er.async_get(hass)
            if ent_reg and hasattr(ent_reg, "async_get_entity_id"):
                reg_eid = ent_reg.async_get_entity_id(entity_domain, DOMAIN, f"{entry_id}_{unique_suffix}")
                if isinstance(reg_eid, str) and reg_eid.strip().startswith(prefix):
                    return reg_eid.strip()
        except Exception:
            pass

    # 2. Laufzeit-Referenz (HA aktualisiert entity.entity_id bei Umbenennungen automatisch)
    domain_data = hass.data.get(DOMAIN, {}).get(entry_id) if (hass and entry_id and getattr(hass, "data", None)) else None
    if isinstance(domain_data, dict) and runtime_key:
        runtime_ent = domain_data.get(runtime_key)
        runtime_eid = getattr(runtime_ent, "entity_id", None) if runtime_ent else None
        if isinstance(runtime_eid, str) and runtime_eid.strip().startswith(prefix):
            return runtime_eid.strip()

    if hass and entry_id and unique_suffix == "schedule" and getattr(hass, "data", None):
        for sensor in hass.data.get(f"{DOMAIN}_sensors", []):
            if getattr(sensor, "config_entry", None) and sensor.config_entry.entry_id == entry_id:
                if getattr(sensor, "_attr_translation_key", None) == "schedule":
                    s_eid = getattr(sensor, "entity_id", None)
                    if isinstance(s_eid, str) and s_eid.strip().startswith(prefix):
                        return s_eid.strip()

    # 3. Lokalisierter Slug-Fallback
    lang = get_ha_language(hass)
    slug = get_config_entry_slug(entry_obj)
    loc_suffix = get_localized_slug_suffix(fallback_suffix or unique_suffix, lang)
    return f"{entity_domain}.{slug}_{loc_suffix}"



