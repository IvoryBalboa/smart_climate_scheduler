"""Zeitleisten- und Slot-Logik für Smart Climate Scheduler."""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from .const import DAYS
from .helpers import parse_time

_LOGGER = logging.getLogger(__name__)


def format_slot(slot: dict | None, slot_date: str | None = None) -> dict | None:
    """Entfernt 'day', flacht 'data' ab, formatiert Zeiten auf HH:MM und fügt das Datum hinzu."""
    if not slot:
        return None

    formatted = {k: v for k, v in slot.items() if k != "day"}
    if "data" in formatted and isinstance(formatted["data"], dict):
        preset = formatted["data"].get("preset")
        del formatted["data"]
        if preset:
            formatted["preset"] = preset

    if "from" in formatted and formatted["from"]:
        formatted["from"] = formatted["from"][:5]
    if "to" in formatted and formatted["to"]:
        formatted["to"] = formatted["to"][:5]

    if slot_date and "date" not in formatted:
        formatted["date"] = slot_date

    return formatted


def get_active_override(hass, config_entry, now_dt: datetime) -> tuple[str | None, dict | None]:
    """Prüft, ob aktuell ein Override aktiv ist, und bereinigt abgelaufene einmalige Overrides automatisch."""
    if not hass:
        return None, None
    domain = "smart_climate_scheduler"
    store = hass.data.get(domain, {}).get(config_entry.entry_id, {})
    overrides = store.get("overrides", {})
    now_time = now_dt.time()

    expired_ids = []
    active_ov_id = None
    active_ov_data = None

    for ov_id, ov_data in list(overrides.items()):
        try:
            start_val = ov_data.get("start")
            end_val = ov_data.get("end")
            if not start_val or not end_val:
                continue

            if "T" in str(start_val):
                ov_start = datetime.fromisoformat(start_val)
                ov_end = datetime.fromisoformat(end_val)
                if now_dt.tzinfo and ov_start.tzinfo is None:
                    ov_start = ov_start.replace(tzinfo=now_dt.tzinfo)
                if now_dt.tzinfo and ov_end.tzinfo is None:
                    ov_end = ov_end.replace(tzinfo=now_dt.tzinfo)

                if ov_start <= now_dt < ov_end:
                    active_ov_id = ov_id
                    active_ov_data = ov_data
                    break
                elif now_dt >= ov_end:
                    expired_ids.append(ov_id)
            else:
                ov_start = parse_time(start_val[:5])
                ov_end = parse_time(end_val[:5])
                if ov_start and ov_end:
                    is_active = False
                    if ov_start <= ov_end:
                        if ov_start <= now_time < ov_end:
                            is_active = True
                    else:
                        if now_time >= ov_start or now_time < ov_end:
                            is_active = True
                    
                    if is_active:
                        active_ov_id = ov_id
                        active_ov_data = ov_data
                        break
                    elif now_time >= ov_end and ov_start <= ov_end:
                        expired_ids.append(ov_id)
        except Exception as e:
            _LOGGER.error("Fehler beim Verarbeiten des Overrides %s: %s", ov_id, e)

    if expired_ids:
        updated = False
        for ov_id in expired_ids:
            if ov_id in overrides:
                overrides.pop(ov_id)
                updated = True
                _LOGGER.info("Abgelaufener einmaliger Override '%s' wurde automatisch gelöscht.", ov_id)
        if updated and "store" in store:
            def _save_and_update(hass_obj, store_obj, ovs, entry_id):
                hass_obj.async_create_task(store_obj.async_save(ovs))
                for s in hass_obj.data.get(f"{domain}_sensors", []):
                    if getattr(s, "config_entry", None) and s.config_entry.entry_id == entry_id:
                        s.async_write_ha_state()
            hass.async_create_task(_save_and_update(hass, store["store"], overrides, config_entry.entry_id))

    return active_ov_id, active_ov_data


def get_day_slots_with_fallbacks(config_entry, check_date) -> list[dict]:
    """Erzeugt eine lückenlose, überschneidungsfreie Liste von Slots für den Tag mittels Intervall-Overlay."""
    schedule = config_entry.options.get("schedule")
    if not schedule and "schedule" in config_entry.data:
        schedule = config_entry.data.get("schedule", {})
    if not isinstance(schedule, dict):
        schedule = {}

    day_name = DAYS[check_date.weekday()]
    raw_slots = schedule.get(day_name, [])

    # Standard-Fallback-Preset aus options oder data auslesen (mit Fallback auf "sleep")
    options = config_entry.options
    data = config_entry.data
    default_preset = options.get("default_preset", data.get("default_preset", "sleep"))

    intervals = [{"start": 0, "end": 1440, "preset": default_preset, "is_fallback": True}]

    parsed_user_slots = []
    for slot in raw_slots:
        from_t = parse_time(slot.get("from"))
        to_t = parse_time(slot.get("to"))
        if from_t and to_t:
            start_min = from_t.hour * 60 + from_t.minute
            end_min = to_t.hour * 60 + to_t.minute
            if end_min <= start_min:
                end_min = 1440
            duration = end_min - start_min
            if duration > 0:
                parsed_user_slots.append({
                    "start": start_min,
                    "end": end_min,
                    "preset": slot.get("preset", "none"),
                    "duration": duration,
                })

    parsed_user_slots.sort(key=lambda x: x["duration"], reverse=True)

    for u_slot in parsed_user_slots:
        u_start = u_slot["start"]
        u_end = u_slot["end"]
        u_preset = u_slot["preset"]

        new_intervals = []
        for interval in intervals:
            i_start = interval["start"]
            i_end = interval["end"]
            
            overlap_start = max(u_start, i_start)
            overlap_end = min(u_end, i_end)

            if overlap_start < overlap_end:
                if i_start < overlap_start:
                    new_intervals.append({
                        "start": i_start,
                        "end": overlap_start,
                        "preset": interval["preset"],
                        "is_fallback": interval.get("is_fallback", False)
                    })
                new_intervals.append({
                    "start": overlap_start,
                    "end": overlap_end,
                    "preset": u_preset,
                    "is_fallback": False
                })
                if overlap_end < i_end:
                    new_intervals.append({
                        "start": overlap_end,
                        "end": i_end,
                        "preset": interval["preset"],
                        "is_fallback": interval.get("is_fallback", False)
                    })
            else:
                new_intervals.append(interval)
        
        intervals = new_intervals

    intervals.sort(key=lambda x: x["start"])

    complete_slots = []
    for interval in intervals:
        start_m = interval["start"]
        end_m = interval["end"]
        
        start_h, start_m_rem = divmod(start_m, 60)
        end_h, end_m_rem = divmod(end_m, 60)
        
        from_str = f"{start_h:02d}:{start_m_rem:02d}"
        to_str = f"{end_h:02d}:{end_m_rem:02d}" if end_m < 1440 else "00:00"
        
        slot_dict = {
            "from": from_str,
            "to": to_str,
            "preset": interval["preset"],
        }
        if interval.get("is_fallback"):
            slot_dict["is_fallback"] = True
        complete_slots.append(slot_dict)

    return complete_slots


def get_current_and_next_slot(hass, config_entry, now_dt: datetime) -> tuple[dict | None, str, dict | None, str, dict | None]:
    """Ermittelt den aktuellen, den nächsten und den nachfolgenden Slot unter Berücksichtigung von Overrides."""
    domain = "smart_climate_scheduler"
    
    timeline = []
    for day_offset in range(2):
        check_date = now_dt.date() + timedelta(days=day_offset)
        day_slots = get_day_slots_with_fallbacks(config_entry, check_date)
        for s in day_slots:
            from_t = parse_time(s["from"])
            to_t = parse_time(s["to"])
            if not from_t or not to_t:
                continue
            
            start_dt = datetime.combine(check_date, from_t)
            if now_dt.tzinfo:
                start_dt = start_dt.replace(tzinfo=now_dt.tzinfo)
            
            end_dt = datetime.combine(check_date, to_t)
            if to_t <= from_t:
                end_dt += timedelta(days=1)
            if now_dt.tzinfo:
                end_dt = end_dt.replace(tzinfo=now_dt.tzinfo)
            
            timeline.append({
                "start": start_dt,
                "end": end_dt,
                "preset": s.get("preset", "none"),
                "is_fallback": s.get("is_fallback", False),
                "from_str": s["from"][:5],
                "to_str": s["to"][:5],
                "date": check_date.strftime("%Y-%m-%d"),
            })

    store = hass.data.get(domain, {}).get(config_entry.entry_id, {}) if hass else {}
    overrides = store.get("overrides", {})
    
    override_intervals = []
    for o_id, o_data in overrides.items():
        start_val = o_data.get("start", "")
        end_val = o_data.get("end", "")
        preset = o_data.get("preset")
        if not start_val or not end_val:
            continue
        try:
            if "T" in str(start_val):
                ov_start = datetime.fromisoformat(start_val)
                ov_end = datetime.fromisoformat(end_val)
                if now_dt.tzinfo:
                    if ov_start.tzinfo is None:
                        ov_start = ov_start.replace(tzinfo=now_dt.tzinfo)
                    if ov_end.tzinfo is None:
                        ov_end = ov_end.replace(tzinfo=now_dt.tzinfo)
                if ov_end > now_dt - timedelta(days=1):
                    override_intervals.append({
                        "start": ov_start,
                        "end": ov_end,
                        "preset": preset,
                        "is_override": True,
                        "override_id": o_id,
                        "from_str": ov_start.strftime("%H:%M"),
                        "to_str": ov_end.strftime("%H:%M"),
                        "date": ov_start.strftime("%Y-%m-%d"),
                    })
            else:
                start_str = start_val[:5]
                end_str = end_val[:5]
                t_start = parse_time(start_str)
                t_end = parse_time(end_str)
                if t_start and t_end:
                    ov_start = datetime.combine(now_dt.date(), t_start)
                    ov_end = datetime.combine(now_dt.date(), t_end)
                    if ov_end < ov_start:
                        ov_end += timedelta(days=1)
                    if now_dt.tzinfo:
                        ov_start = ov_start.replace(tzinfo=now_dt.tzinfo)
                        ov_end = ov_end.replace(tzinfo=now_dt.tzinfo)
                    if ov_end > now_dt - timedelta(days=1):
                        override_intervals.append({
                            "start": ov_start,
                            "end": ov_end,
                            "preset": preset,
                            "is_override": True,
                            "override_id": o_id,
                            "from_str": start_str,
                            "to_str": end_str,
                            "date": ov_start.strftime("%Y-%m-%d"),
                        })
        except Exception as e:
            _LOGGER.error("Fehler bei Override %s: %s", o_id, e)

    for ov in override_intervals:
        u_start = ov["start"]
        u_end = ov["end"]
        
        new_timeline = []
        inserted = False
        for item in timeline:
            i_start = item["start"]
            i_end = item["end"]
            
            overlap_start = max(u_start, i_start)
            overlap_end = min(u_end, i_end)

            if overlap_start < overlap_end:
                if i_start < overlap_start:
                    new_timeline.append({**item, "end": overlap_start, "to_str": overlap_start.strftime("%H:%M")})
                if not inserted:
                    new_timeline.append(ov)
                    inserted = True
                if overlap_end < i_end:
                    new_timeline.append({**item, "start": overlap_end, "from_str": overlap_end.strftime("%H:%M")})
            else:
                new_timeline.append(item)
        if not inserted:
            new_timeline.append(ov)
        timeline = new_timeline

    existing_override_ids = {item.get("override_id") for item in timeline if item.get("is_override")}
    for ov in override_intervals:
        if ov.get("override_id") not in existing_override_ids:
            timeline.append(ov)

    timeline.sort(key=lambda x: x["start"])

    merged_timeline = []
    for item in timeline:
        if not merged_timeline:
            merged_timeline.append(item)
        else:
            last = merged_timeline[-1]
            if not last.get("is_override") and not item.get("is_override") and last["preset"] == item["preset"] and last["end"] == item["start"]:
                last["end"] = item["end"]
                last["to_str"] = item["to_str"]
            else:
                merged_timeline.append(item)
    timeline = merged_timeline

    active_idx = -1
    for idx, item in enumerate(timeline):
        if item["start"] <= now_dt < item["end"]:
            active_idx = idx
            break

    if active_idx == -1 and timeline:
        active_idx = 0

    active_item = timeline[active_idx]
    active_slot = {
        "from": active_item["from_str"],
        "to": active_item["to_str"],
        "preset": active_item["preset"],
    }
    if active_item.get("is_fallback"):
        active_slot["is_fallback"] = True
    if active_item.get("is_override"):
        active_slot["is_override"] = True
        active_slot["override_id"] = active_item.get("override_id")
    active_date = active_item["date"]

    next_idx = (active_idx + 1) % len(timeline)
    next_item = timeline[next_idx]
    next_slot = {
        "from": next_item["from_str"],
        "to": next_item["to_str"],
        "preset": next_item["preset"],
    }
    if next_item.get("is_fallback"):
        next_slot["is_fallback"] = True
    if next_item.get("is_override"):
        next_slot["is_override"] = True
        next_slot["override_id"] = next_item.get("override_id")
    next_date = next_item["date"]

    subsequent_idx = (next_idx + 1) % len(timeline)
    subsequent_item = timeline[subsequent_idx]
    subsequent_slot = {
        "from": subsequent_item["from_str"],
        "to": subsequent_item["to_str"],
        "preset": subsequent_item["preset"],
    }
    if subsequent_item.get("is_fallback"):
        subsequent_slot["is_fallback"] = True
    if subsequent_item.get("is_override"):
        subsequent_slot["is_override"] = True
        subsequent_slot["override_id"] = subsequent_item.get("override_id")

    return active_slot, active_date, next_slot, next_date, subsequent_slot