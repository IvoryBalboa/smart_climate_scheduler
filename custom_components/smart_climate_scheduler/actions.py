"""Aktions- und Text-Formatierung für Smart Climate Scheduler."""
from __future__ import annotations

from datetime import datetime


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


PRESET_TRANSLATIONS: dict[str, dict[str, str]] = {
    "home": {
        "de": "Zuhause",
        "en": "Home",
        "es": "En casa",
        "fr": "Présent",
        "it": "In casa",
        "nl": "Thuis",
        "pl": "W domu",
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
    "sleep": {
        "de": "Schlafen",
        "en": "Sleep",
        "es": "Noche",
        "fr": "Nuit",
        "it": "Notte",
        "nl": "Slapen",
        "pl": "Sen",
    },
    "away": {
        "de": "Abwesend",
        "en": "Away",
        "es": "Ausente",
        "fr": "Absent",
        "it": "Fuori casa",
        "nl": "Weg",
        "pl": "Poza domem",
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
    "boost": {
        "de": "Boost",
        "en": "Boost",
        "es": "Boost",
        "fr": "Boost",
        "it": "Boost",
        "nl": "Boost",
        "pl": "Boost",
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
    "none": {
        "de": "Keins",
        "en": "None",
        "es": "Ninguno",
        "fr": "Aucun",
        "it": "Nessuno",
        "nl": "Geen",
        "pl": "Brak",
    },
}


def _format_preset(preset: str | None, lang: str = "de") -> str:
    """Formatiert und übersetzt einen Preset-Namen für die Anzeige."""
    if not preset:
        preset_key = "home"
    else:
        preset_key = str(preset).lower().strip().replace(" ", "_")

    clean_lang = lang.lower().split("-")[0].split("_")[0] if isinstance(lang, str) else "de"
    if preset_key in PRESET_TRANSLATIONS:
        return PRESET_TRANSLATIONS[preset_key].get(clean_lang, PRESET_TRANSLATIONS[preset_key]["de"])

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
    """Ermittelt Aktion und Zeit für die nächste Planänderung mit übersetzten Presets."""
    clean_lang = lang.lower().split("-")[0].split("_")[0] if isinstance(lang, str) else "de"
    current_label = _format_preset(base_preset, clean_lang)
    next_preset_name = next_slot.get("preset") if next_slot else None
    target_preset = _format_preset(next_preset_name, clean_lang)

    preheat_start_str = preheat_start_dt.strftime("%H:%M") if preheat_start_dt else (next_slot.get("from") if next_slot else None)
    cooldown_start_str = cooldown_start_dt.strftime("%H:%M") if cooldown_start_dt else (next_slot.get("from") if next_slot else None)
    slot_from_time = next_slot.get("from") if next_slot else None

    preheat_tag = ACTION_PREFIXES["preheat"].get(clean_lang, ACTION_PREFIXES["preheat"]["de"])
    cooldown_tag = ACTION_PREFIXES["cooldown"].get(clean_lang, ACTION_PREFIXES["cooldown"]["de"])

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
        subsequent_preset = subsequent_slot.get("preset", "home") if subsequent_slot else "home"
        subsequent_label = _format_preset(subsequent_preset, clean_lang)
        to_time = next_slot.get("to") if next_slot else None
        return {
            "action": f"{target_preset} -> {subsequent_label}",
            "time": to_time,
        }

    if is_cooling_down:
        if next_preset_name and next_preset_name != "none":
            subsequent_preset = subsequent_slot.get("preset", "home") if subsequent_slot else "home"
            subsequent_label = _format_preset(subsequent_preset, clean_lang)
            to_time = next_slot.get("to") if next_slot else None
            return {
                "action": f"{target_preset} -> {subsequent_label}",
                "time": to_time,
            }
        eco_label = _format_preset("eco", clean_lang)
        return {
            "action": f"{eco_label} -> {target_preset}",
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
