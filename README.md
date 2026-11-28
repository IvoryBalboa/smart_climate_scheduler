# Smart Climate Scheduler (v4.0.0)

[![GitHub Release](https://img.shields.io/github/v/release/IvoryBalboa/smart_climate_scheduler?style=for-the-badge&color=amber)](https://github.com/IvoryBalboa/smart_climate_scheduler/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Hassfest Validation](https://img.shields.io/github/actions/workflow/status/IvoryBalboa/smart_climate_scheduler/validate.yml?branch=main&label=Hassfest&style=for-the-badge)](https://github.com/IvoryBalboa/smart_climate_scheduler/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

**Smart Climate Scheduler** ist eine universelle, adaptive Heizungs- und Raumklima-Automatisierung für Home Assistant. Sie kombiniert einen komfortablen, vollintegrierten Wochen-Zeitplaner mit einer selbstlernenden thermodynamischen Berechnung, Thermostat-Gruppen, Fenster-/Tür-Pausierung und eigenen Raum-Presets – komplett unabhängig von Drittanbieter-Wrappern.

> ### 🔥 Universelle Thermostat-Steuerung (v4.0.0)
> **Smart Climate Scheduler v4.0.0 arbeitet vollständig autark mit jedem Home Assistant `climate.*`-Thermostat – ganz ohne zusätzliche Wrapper-Integrationen.**
>
> * Kompatibel mit **Zigbee2MQTT**, **ZHA**, **Matter**, **Homematic**, **Z-Wave**, **Shelly TRV**, **ESPHome** und allen weiteren Standard-`climate`-Entitäten.
> * **Direkte Sollwert- & HVAC-Steuerung**: Regelt Zieltemperaturen (`climate.set_temperature`) und Heizmodus (`heat` / `off`) direkt für einzelne Thermostate oder synchronisierte Thermostat-Gruppen.
> * **Automatische Migration von v3**: Bestehende v3-Raumkonfigurationen werden beim Upgrade auf v4.0.0 automatisch übernommen und bereinigt.

---

## 🎯 Was macht der Smart Climate Scheduler?

Herkömmliche Thermostat-Zeitpläne schalten starr zu einer festgelegten Uhrzeit ein – beispielsweise um **07:00 Uhr** morgens auf Komforttemperatur (21 °C).
* **Das Problem**: Im tiefen Winter bei -10 °C Außentemperatur braucht ein Raum oft 90 Minuten zum Aufheizen – um 07:00 Uhr ist es noch kalt. Im milden Frühjahr bei +12 °C reichen dagegen oft schon 20 Minuten. Zudem heizt die Heizung bis zur letzten Minute vor dem Verlassen des Hauses auf voller Leistung, obwohl die Restwärme noch lange vorhalten würde.
* **Die Lösung**: Smart Climate Scheduler lernt kontinuierlich die reale Wärmekapazität deines Raumes (**Aufheizrate in Kelvin pro Stunde, K/h**) und den Wärmeverlust (**Abkühlrate in Kelvin pro Stunde, K/h**) – und das differenziert nach der jeweiligen Außentemperatur.

### ⏱️ Das 2-Phasen-Prinzip:
1. **Intelligentes Vorheizen (Preheat)**: Wenn dein Zeitplan um 07:00 Uhr 21 °C vorsieht, startet die Heizung bei frostigem Wetter automatisch früher (z. B. um 05:45 Uhr), damit der Raum **punktgenau um 07:00 Uhr** warm ist.
2. **Vorzeitiges Absenken (Cooldown)**: Geht der Zeitplan um 22:00 Uhr in den Nachtmodus, schaltet die Integration die Solltemperatur bereits um 21:25 Uhr auf Eco zurück. Der Raum kühlt dank Gebäudeträgheit nur unmerklich ab, spart aber wertvolle Heizenergie.

---

## ✨ Alle Kern-Features im Überblick

### 1. 🌡️ Universelle Steuerung, eigene Presets & Thermostat-Gruppen
* **Freie Raum-Presets**: Jeder Raum definiert seine eigene Preset-Liste mit individuellem Namen, Zieltemperatur (`5,0–30,0 °C`) und Farbe – pflegbar im Options-Flow oder direkt inline auf der Lovelace-Karte.
* **Synchronisierte Thermostat-Gruppen**: Verknüpfe ein oder mehrere `climate.*`-Thermostate pro Raum. Alle Geräte werden synchron geregelt; fällt ein Thermostat kurzzeitig aus, arbeiten die übrigen nahtlos weiter.
* **Optionaler externer Raumtemperatursensor**: Ein separater Temperatursensor (`sensor` mit `device_class=temperature`) speist ausschließlich die interne SCS-Thermik, Hysterese und Abschaltung – ohne Kalibrierungsdaten an die Thermostate zu senden. Ist kein externer Sensor gesetzt, nutzt SCS den Mittelwert der verfügbaren Gruppenthermostate.

### 2. 🪟 Fenster- & Tür-Erkennung mit Minuten-Verzögerung
* **Strikte Kontakt-Auswahl**: Optionale Fenster- und Türsensoren (`binary_sensor` mit `device_class=window` oder `door`) pausieren die Heizung automatisch beim Lüften (`hvac_mode: off`) und stellen den vorherigen Zustand nach dem Schließen sauber wieder her.
* **Getrennte Auf-/Zu-Verzögerungen in Minuten**: Konfiguriere getrennt, wie viele Minuten ein Fenster oder eine Tür geöffnet sein muss, bevor pausiert wird (Standard: **1 Min**), und wie viele Minuten nach dem Schließen gewartet wird, bevor wieder geheizt wird (Standard: **2 Min**).

### 3. 📅 Integrierte Zeitpläne (Schedules) & Profile mit Kopierfunktion
* **Direkt in der Integration**: Keine externen Scheduler-Addons, YAML-Konfigurationen oder Hilfssensoren nötig.
* **Flexible Zeitfenster (Slots) & Profile**: Verwalte mehrere Zeitplan-Profile (z. B. *Standard*, *Homeoffice*, *Urlaub*) mit individuellen Zeitfenstern je Wochentag (Mo–So).
* **Kopierfunktion für Tage**: Übertrage Tagespläne mit einem Klick auf Mo–Fr, Sa–So oder einzelne Wochentage.

### 4. 🔥 Dual-Matrix Thermik-Lernengine & opportunistisches Mitheizen
* **Aufheiz- & Abkühl-Matrix (K/h)**: Misst fortlaufend die reale Aufheiz- und Abkühlgeschwindigkeit je Außentemperatur-Cluster mit Rolling Average und ±5%-Ausreißerfilter.
* **Rein interne SCS-Hysterese & Mitheizen**: Bei aktivem zentralem Brenner-Sensor überwindet SCS das Regel-Totband rein intern per temporärem Sollwert-Kickstart und stellt sofort nach dem Öffnen des Ventils (`hvac_action=heating`), bei Brenner-Aus oder Fensteröffnung die reguläre Zieltemperatur wieder her.
* **Brenner-sensitiver Anomalie-Wächter**: Warnt über einen eigenen Diagnose-Binärsensor (`_anomaly`) bei nicht verfügbaren Thermostaten, eingefrorenen Sensoren oder ausbleibender Erwärmung trotz aktivem Ventil und Brenner.

### 5. 📍 Zonen-, Distanz- & Anwesenheitserkennung
* Erkennt die Anwesenheit von Bewohnern über Home-Assistant-Personen/Zonen (`home`, `away`) und GPS-Distanzen (`near_distance`).
* Konfigurierbare Presets für *Unterwegs (nah)* und *Abwesend* sowie Option **„Vorheizen trotz Abwesenheit“**.

### 6. 🎨 Eingebettete Lovelace-Karten (Raum-Timeline & Multi-Raum-Übersicht)
* **Automatisch integriert**: Beide Karten (`custom:smart-climate-scheduler-card` & `custom:smart-climate-scheduler-overview-card`) werden direkt mit der Integration ausgeliefert und automatisch im Home Assistant Frontend registriert.
* **Interaktive 24h-Zeitleiste**: Wochentag-Tabs (Mo–So), Drag-&-Drop-Slots, Live-Thermik-Vorschau, Inline-Verwaltung eigener Presets, Profilwechsel, Fenster-Countdown und Schnell-Overrides.
* **Multi-Raum-Übersicht**: Filter (Alle, Automatik An, Heizt, Override, Warnungen), manuelle oder dynamische Sortierung sowie Sammelaktionen für alle angezeigten Räume.

---

## 📦 Installation

### Methode 1: Über HACS (Empfohlen)
1. Öffne Home Assistant und gehe zu **HACS** > **Integrationen**.
2. Klicke oben rechts auf das Menü (⋮) und wähle **Benutzerdefinierte Repositories**.
3. Trage deine Repository-URL ein:
   ```text
   https://github.com/IvoryBalboa/smart_climate_scheduler
   ```
4. Wähle als Kategorie: **Integration**.
5. Klicke auf **Hinzufügen**, suche nach **Smart Climate Scheduler**, klicke auf **Herunterladen** und starte Home Assistant neu.

### Methode 2: Manuelle Installation
1. Lade das Release-ZIP `smart_climate_scheduler_v4.0.0.zip` herunter.
2. Entpacke den Ordner `smart_climate_scheduler` in dein Home Assistant Verzeichnis:
   ```text
   /config/custom_components/smart_climate_scheduler/
   ```
3. Starte Home Assistant neu über *Entwicklerwerkzeuge > Neustart*.

---

## ⚙️ Schnelleinrichtung (Config Flow)

1. Navigiere in Home Assistant zu **Einstellungen** > **Geräte & Dienste** > **Integration hinzufügen**.
2. Suche nach **Smart Climate Scheduler**.
3. Folge dem Einrichtungsassistenten:
   * **Thermostate (`climate.*`)**: Wähle ein oder mehrere Thermostate für den Raum (z. B. `climate.wohnzimmer_trv`).
   * **Externer Raumtemperatursensor (Optional)**: Wähle einen Temperatursensor (`device_class=temperature`) für die interne SCS-Thermik.
   * **Fenster-/Türsensoren (Optional)**: Wähle einen oder mehrere Kontakte (`device_class=window` oder `door`) samt Auf-/Zu-Verzögerung in Minuten.
   * **Außentemperatur**: Wähle deinen Außentemperatursensor (`device_class=temperature`) oder eine Wetter-Entität (`weather.*`).
   * **Brenner-/Heizaktiv-Sensor (Optional)**: Sensor, der anzeigt, ob die zentrale Heizung aktiv Wärme liefert.
   * **Presets & Zeitpläne**: Passe deine Raum-Presets und Zeitfenster direkt im Options-Flow oder bequem über die eingebettete Lovelace-Karte an.

---

## 🎨 Lovelace-Karten zum Dashboard hinzufügen

Nach der Installation und einem Home Assistant Neustart stehen **„Smart Climate Scheduler Card“** und **„Smart Climate Scheduler Overview Card“** automatisch im Dashboard-Editor (*Karte hinzufügen*) zur Verfügung:

```yaml
type: custom:smart-climate-scheduler-card
config_entry: <DEINE_CONFIG_ENTRY_ID>
snap_minutes: 15
show_override_bar: true
```

```yaml
type: custom:smart-climate-scheduler-overview-card
title: Heizungs-Übersicht
show_mini_timeline: true
show_bulk_actions: true
```

---

## 💡 Entitäten & Praxis-Tipps

Die Integration erzeugt für jeden konfigurierten Raum ein sauberes Set an echten Home Assistant Entitäten:

| Entität | Typ | Funktion & Details | Dashboard-Empfehlung |
| :--- | :--- | :--- | :--- |
| `switch.<name>_automatic` | Schalter | Hauptschalter für die Zeitplan-Automatik des Raumes | **Auf Dashboard anzeigen** |
| `sensor.<name>_schedule` | Sensor | Aktives Soll-Preset mit Attributen `active_slot`, `next_slot` & `thermostats` | **Auf Dashboard anzeigen** |
| `select.<name>_profile` | Auswahl | Aktives Zeitplan-Profil des Raumes | **Auf Dashboard anzeigen** |
| `sensor.<name>_heating_rate` | Sensor (K/h) | Gemessene & gelernte Aufheizrate in K/h | **Diagnose / Charts** |
| `sensor.<name>_cooling_rate` | Sensor (K/h) | Gemessene & gelernte Abkühlrate in K/h | **Diagnose / Charts** |
| `sensor.<name>_next_action` | Sensor | Nächste geplante Aktion (`preheat`, `cooldown`, etc.) mit Attribut `time` | **Auf Dashboard anzeigen** |
| `binary_sensor.<name>_preheat` | Binärsensor | `on`, wenn intelligente Vorheizung aktiv ist | **Trigger für Automationen** |
| `binary_sensor.<name>_cooldown` | Binärsensor | `on`, wenn vorzeitiges Absenken aktiv ist | **Statusanzeige** |
| `binary_sensor.<name>_anomaly` | Binärsensor | Diagnose-Problem-Sensor (Thermostat offline, keine Erwärmung, Sensor eingefroren) | **Benachrichtigungen** |
| `sensor.<name>_debug` | Sensor | Internzustand & Diagnoseparameter (Kategorie Diagnose) | *Standardmäßig deaktiviert* |

---

## 🎛️ Verfügbare Dienste (Services)

### 1. `smart_climate_scheduler.set_override`
Aktiviert einen temporären Override für ein Zimmer:
```yaml
action: smart_climate_scheduler.set_override
data:
  device_id: <DEVICE_ID_DES_RAUMS>
  preset: boost
  duration:
    hours: 2
```

### 2. `smart_climate_scheduler.remove_override`
Beendet einen laufenden Override vorzeitig:
```yaml
action: smart_climate_scheduler.remove_override
data:
  device_id: <DEVICE_ID_DES_RAUMS>
  override_id: party_mode
```

### 3. `smart_climate_scheduler.set_manual_heating_rate`
Setzt die Basis-Aufheizrate für gut gedämmte oder träge Räume (z. B. Fußbodenheizung):
```yaml
action: smart_climate_scheduler.set_manual_heating_rate
data:
  device_id: <DEVICE_ID_DES_RAUMS>
  rate: 0.8
```

### 4. `smart_climate_scheduler.reset_heating_rates`
Setzt den Lernspeicher des Raumes zurück auf die Standardwerte:
```yaml
action: smart_climate_scheduler.reset_heating_rates
data:
  device_id: <DEVICE_ID_DES_RAUMS>
```

---

## 📝 Changelog

<!-- CURRENT_CHANGELOG_START -->
Alle Änderungen findest du im [CHANGELOG.md](CHANGELOG.md). Highlights in **v4.0.0** (*Universelle Thermostat-Steuerung ohne Better Thermostat, strikte Entity-Picker & Minuten-Verzögerungen*):
* **Vollständig universelle Direkttemperatur-Steuerung (ohne Better Thermostat)**: Sämtliche Abhängigkeiten und Bezüge zu *Better Thermostat* (`better_thermostat` in `manifest.json`, `control_mode`, `climate.set_preset_mode`, `tolerance_entity`, `bt_preset_*_temperatures`, `external_temp_ema`) wurden entfernt. Smart Climate Scheduler steuert nun universell beliebige Home-Assistant-Thermostate (z. B. Zigbee2MQTT, ZHA, Matter, Homematic, Z-Wave, Shelly TRV) direkt über `climate.set_temperature` und `climate.set_hvac_mode` (`heat` / `off`).
* **Eigene Raum-Presets & synchronisierte Thermostat-Gruppen**: Jeder Raum verwaltet seine komplett eigene Preset-Liste (`custom_presets` mit Name, Zieltemperatur und Farbe) im Options-Flow oder direkt inline in der Lovelace-Karte und regelt beliebig viele verknüpfte `climate.*`-Entitäten synchron als Gruppe.
* **Rein interne SCS-Hysterese & opportunistisches Mitheizen per Pro-Ventil-Kickstart**: Hysterese (`fallback_tolerance`) und opportunistisches Mitheizen arbeiten komplett autark innerhalb des Smart Climate Scheduler – ohne externe Toleranz-Entität. Bei laufendem Brenner hebt SCS den Sollwert pro Ventil individuell an (`kickstart_boost` oder Raum-Hysterese, mit automatischer stufenweiser Eskalation um `+0,5 K` bei trägen TRVs bis max. `+3,0 K`) und stellt den regulären Zielwert für jedes Ventil direkt nach eigener Ventilöffnung (`hvac_action=heating`), Brenner-Aus oder Fensteröffnung wieder her.
<!-- CURRENT_CHANGELOG_END -->

---

## 📄 Lizenz

Dieses Projekt ist unter der **MIT-Lizenz** lizenziert – siehe [LICENSE](LICENSE) für Details.

Entwickelt für die Home Assistant Community von **@IvoryBalboa**.
