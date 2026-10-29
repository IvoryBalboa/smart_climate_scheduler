"""Zonen- und Anwesenheits-Logik für Smart Climate Scheduler."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.util.location import distance


def _get_zone_count(hass: HomeAssistant | None, entity_id: str | None) -> int:
    """Liest die Personenanzahl einer Zone sicher aus."""
    if not entity_id or not hass:
        return 0
    state = hass.states.get(entity_id)
    if state and state.state is not None:
        try:
            return int(state.state)
        except (ValueError, TypeError):
            return 0
    return 0


def evaluate_zones(
    hass: HomeAssistant | None,
    zone_home_entity: str,
    zone_away_near_entity: str | None,
    near_distance: float = 0.25,
) -> dict:
    """Ermittelt den Anwesenheitsstatus und berechnet die GPS-Distanzen aller Personen zur Home-Zone."""
    home_count = _get_zone_count(hass, zone_home_entity)
    away_near_count = _get_zone_count(hass, zone_away_near_entity) if zone_away_near_entity else 0

    near = False
    person_distances = {}
    min_dist = None

    if hass:
        persons = [
            state for state in hass.states.async_all("person")
            if state.attributes.get("latitude") is not None and state.attributes.get("longitude") is not None
        ]
        if persons:
            home_state = hass.states.get(zone_home_entity)
            if home_state and home_state.attributes.get("latitude") is not None:
                home_lat = home_state.attributes.get("latitude")
                home_lon = home_state.attributes.get("longitude")
                
                for p in persons:
                    lat = p.attributes.get("latitude")
                    lon = p.attributes.get("longitude")
                    dist_m = distance(home_lat, home_lon, lat, lon)
                    if dist_m is not None:
                        # In Kilometer umrechnen und auf 3 Nachkommastellen runden
                        person_distances[p.entity_id] = round(dist_m / 1000.0, 3)
                
                if person_distances:
                    min_dist = min(person_distances.values())
                    if min_dist < near_distance:
                        near = True  # <-- Hier war das kleingeschriebene 'true'

    is_home = (home_count > 0) or near
    is_away_near = (not is_home) and (away_near_count > 0)
    is_away = (not is_home) and (not is_away_near)

    return {
        "home_count": home_count,
        "away_near_count": away_near_count,
        "is_home": is_home,
        "is_away_near": is_away_near,
        "is_away": is_away,
        "distances": person_distances,
        "min_distance_km": min_dist,
    }

