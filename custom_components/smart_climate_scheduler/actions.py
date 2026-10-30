"""Aktions- und Text-Formatierung für Smart Climate Scheduler."""
from __future__ import annotations

from datetime import datetime


def _format_preset(preset: str | None) -> str:
    """Formatiert einen Preset-Namen für die Anzeige."""
    if not preset:
        return "Home"
    return preset.replace("_", " ").title()


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
) -> dict[str, str | None]:
    """Ermittelt Aktion und Zeit für die nächste Planänderung."""
    current_label = _format_preset(base_preset)
    next_preset_name = next_slot.get("preset") if next_slot else None
    target_preset = _format_preset(next_preset_name)

    preheat_start_str = preheat_start_dt.strftime("%H:%M") if preheat_start_dt else (next_slot.get("from") if next_slot else None)
    cooldown_start_str = cooldown_start_dt.strftime("%H:%M") if cooldown_start_dt else (next_slot.get("from") if next_slot else None)
    slot_from_time = next_slot.get("from") if next_slot else None

    if preheat_duration > 0 and preheat_start_dt and preheat_start_dt > now_dt:
        return {
            "action": f"(Preheat) {current_label} -> {target_preset}",
            "time": preheat_start_str,
        }

    if cooldown_duration > 0 and cooldown_start_dt and cooldown_start_dt > now_dt:
        cooldown_target = target_preset if (next_preset_name and next_preset_name != "none") else "Eco"
        return {
            "action": f"(Cooldown) {current_label} -> {cooldown_target}",
            "time": cooldown_start_str,
        }

    if is_preheat_needed:
        subsequent_preset = subsequent_slot.get("preset", "home") if subsequent_slot else "home"
        subsequent_label = _format_preset(subsequent_preset)
        to_time = next_slot.get("to") if next_slot else None
        return {
            "action": f"{target_preset} -> {subsequent_label}",
            "time": to_time,
        }

    if is_cooling_down:
        if next_preset_name and next_preset_name != "none":
            subsequent_preset = subsequent_slot.get("preset", "home") if subsequent_slot else "home"
            subsequent_label = _format_preset(subsequent_preset)
            to_time = next_slot.get("to") if next_slot else None
            return {
                "action": f"{target_preset} -> {subsequent_label}",
                "time": to_time,
            }
        return {
            "action": f"Eco -> {target_preset}",
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
