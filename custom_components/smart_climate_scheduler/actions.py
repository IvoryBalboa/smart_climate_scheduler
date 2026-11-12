"""Action and UI text formatting for Smart Climate Scheduler."""
from __future__ import annotations

from datetime import datetime
from typing import Any


ACTION_PREFIXES: dict[str, dict[str, str]] = {
    "preheat": {
        "de": "Vorheizen",
        "en": "Preheat",
        "es": "Precalentamiento",
        "fr": "Préchauffage",
        "it": "Preriscaldamento",
        "nl": "Voorverwarmen",
        "pl": "Wstępne nagrzewanie",
    },
    "cooldown": {
        "de": "Auskühlen",
        "en": "Cooldown",
        "es": "Enfriamiento",
        "fr": "Refroidissement",
        "it": "Raffreddamento",
        "nl": "Afkoelen",
        "pl": "Ochładzanie",
    },
}


# Official Home Assistant Core climate preset_mode translations
PRESET_TRANSLATIONS: dict[str, dict[str, str]] = {
    "none": {
        "de": "Keine",
        "en": "None",
        "es": "Ninguno",
        "fr": "Aucun",
        "it": "Nessuno",
        "nl": "Geen",
        "pl": "Brak",
    },
    "home": {
        "de": "Zuhause",
        "en": "Home",
        "es": "En casa",
        "fr": "Maison",
        "it": "A casa",
        "nl": "Thuis",
        "pl": "W domu",
    },
    "away": {
        "de": "Abwesend",
        "en": "Away",
        "es": "Ausente",
        "fr": "Absent",
        "it": "Fuori casa",
        "nl": "Afwezig",
        "pl": "Poza domem",
    },
    "boost": {
        "de": "Boost",
        "en": "Boost",
        "es": "Boost",
        "fr": "Boost",
        "it": "Boost",
        "nl": "Boost",
        "pl": "Boost",
    },
    "comfort": {
        "de": "Komfort",
        "en": "Comfort",
        "es": "Confort",
        "fr": "Confort",
        "it": "Comfort",
        "nl": "Comfort",
        "pl": "Komfort",
    },
    "eco": {
        "de": "Eco",
        "en": "Eco",
        "es": "Eco",
        "fr": "Éco",
        "it": "Eco",
        "nl": "Eco",
        "pl": "Eko",
    },
    "sleep": {
        "de": "Schlafen",
        "en": "Sleep",
        "es": "Dormir",
        "fr": "Sommeil",
        "it": "Sonno",
        "nl": "Slapen",
        "pl": "Sen",
    },
    "activity": {
        "de": "Aktivität",
        "en": "Activity",
        "es": "Actividad",
        "fr": "Activité",
        "it": "Attività",
        "nl": "Activiteit",
        "pl": "Aktywność",
    },
}


UI_TEXT_TRANSLATIONS: dict[str, dict[str, str]] = {
    "empty_schedule": {
        "de": "Leerer Zeitplan (ohne Slots)",
        "en": "Empty schedule (no slots)",
        "es": "Horario vacío (sin franjas)",
        "fr": "Programme vide (sans créneaux)",
        "it": "Programma vuoto (senza fasce)",
        "nl": "Leeg schema (zonder tijdvakken)",
        "pl": "Pusty harmonogram (bez przedziałów)",
    },
    "copy_of_profile": {
        "de": "Kopie von '{profile}'",
        "en": "Copy of '{profile}'",
        "es": "Copia de '{profile}'",
        "fr": "Copie de '{profile}'",
        "it": "Copia di '{profile}'",
        "nl": "Kopie van '{profile}'",
        "pl": "Kopia '{profile}'",
    },
    "no_slots_configured": {
        "de": "(Keine Slots konfiguriert)",
        "en": "(No slots configured)",
        "es": "(No hay franjas configuradas)",
        "fr": "(Aucun créneau configuré)",
        "it": "(Nessuna fascia configurata)",
        "nl": "(Geen tijdvakken geconfigureerd)",
        "pl": "(Brak skonfigurowanych przedziałów)",
    },
    "slot_item": {
        "de": "Slot {index}: {from_time} - {to_time} ({preset})",
        "en": "Slot {index}: {from_time} - {to_time} ({preset})",
        "es": "Franja {index}: {from_time} - {to_time} ({preset})",
        "fr": "Créneau {index}: {from_time} - {to_time} ({preset})",
        "it": "Fascia {index}: {from_time} - {to_time} ({preset})",
        "nl": "Tijdvak {index}: {from_time} - {to_time} ({preset})",
        "pl": "Przedział {index}: {from_time} - {to_time} ({preset})",
    },
}


def get_localized_ui_text(key: str, lang: str = "en", **kwargs: Any) -> str:
    """Returns a localized dynamic UI text formatted with optional placeholders."""
    clean_lang = lang.lower().split("-")[0].split("_")[0] if isinstance(lang, str) and lang else "en"
    mapping = UI_TEXT_TRANSLATIONS.get(key, {})
    template = mapping.get(clean_lang, mapping.get("en", key))
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template


def _format_preset(preset: str | None, lang: str = "de") -> str:
    """Formats and translates a preset mode according to Home Assistant standards."""
    if not preset:
        preset_key = "home"
    else:
        preset_key = str(preset).lower().strip().replace(" ", "_")

    clean_lang = lang.lower().split("-")[0].split("_")[0] if isinstance(lang, str) else "de"
    if preset_key in PRESET_TRANSLATIONS:
        return PRESET_TRANSLATIONS[preset_key].get(clean_lang, PRESET_TRANSLATIONS[preset_key]["en"])

    return str(preset).replace("_", " ").title()


def calculate_next_action(
    preheat_duration: int,
    preheat_start_dt: datetime | None,
    cooldown_duration: int,
    cooldown_start_dt: datetime | None,
    is_preheat_needed: bool,
    is_cooling_down: bool,
    active_slot: dict | None,
    next_slot: dict | None,
    subsequent_slot: dict | None,
    base_preset: str,
    now_dt: datetime,
    lang: str = "de",
) -> dict[str, str | None]:
    """Determines the next scheduled action and time with localized preset labels."""
    clean_lang = lang.lower().split("-")[0].split("_")[0] if isinstance(lang, str) else "de"
    current_label = _format_preset(base_preset, clean_lang)
    next_preset_name = next_slot.get("preset") if next_slot else None
    target_preset = _format_preset(next_preset_name, clean_lang)

    preheat_start_str = preheat_start_dt.strftime("%H:%M") if preheat_start_dt else (next_slot.get("from") if next_slot else None)
    cooldown_start_str = cooldown_start_dt.strftime("%H:%M") if cooldown_start_dt else (next_slot.get("from") if next_slot else None)
    slot_from_time = next_slot.get("from") if next_slot else None

    preheat_tag = ACTION_PREFIXES["preheat"].get(clean_lang, ACTION_PREFIXES["preheat"]["en"])
    cooldown_tag = ACTION_PREFIXES["cooldown"].get(clean_lang, ACTION_PREFIXES["cooldown"]["en"])

    if preheat_duration > 0 and preheat_start_dt and preheat_start_dt > now_dt:
        return {
            "action": f"({preheat_tag}) {current_label} -> {target_preset}",
            "time": preheat_start_str,
        }

    if cooldown_duration > 0 and cooldown_start_dt and cooldown_start_dt > now_dt:
        cooldown_target = target_preset if (next_preset_name and next_preset_name != "none") else _format_preset("eco", clean_lang)
        return {
            "action": f"({cooldown_tag}) {current_label} -> {cooldown_target}",
            "time": cooldown_start_str,
        }

    if is_preheat_needed:
        return {
            "action": f"({preheat_tag}) {current_label} -> {target_preset}",
            "time": slot_from_time,
        }

    if is_cooling_down:
        cooldown_target = target_preset if (next_preset_name and next_preset_name != "none") else _format_preset("eco", clean_lang)
        return {
            "action": f"({cooldown_tag}) {current_label} -> {cooldown_target}",
            "time": slot_from_time,
        }

    if next_slot and "from" in next_slot:
        return {
            "action": f"{current_label} -> {target_preset}",
            "time": slot_from_time,
        }

    return {
        "action": "none",
        "time": None,
    }
