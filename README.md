# Smart Climate Scheduler (v3.0.0)

[![GitHub Release](https://img.shields.io/github/v/release/IvoryBalboa/smart_climate_scheduler?style=for-the-badge&color=amber)](https://github.com/IvoryBalboa/smart_climate_scheduler/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Hassfest Validation](https://img.shields.io/github/actions/workflow/status/IvoryBalboa/smart_climate_scheduler/validate.yml?branch=main&label=Hassfest&style=for-the-badge)](https://github.com/IvoryBalboa/smart_climate_scheduler/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

**Smart Climate Scheduler** ist eine intelligente, adaptive Heizungs- und Raumklima-Automatisierung für Home Assistant. Sie kombiniert einen komfortablen, vollintegrierten Wochen-Zeitplaner mit einer selbstlernenden thermodynamischen Berechnung, damit deine Räume immer zur gewünschten Uhrzeit exakt die richtige Wohlfühltemperatur haben.

> ### 💡 Erweiterung für Better Thermostat
> **Smart Climate Scheduler ist primär als leistungsstarke Zeitplan- und Thermik-Erweiterung für die beliebte Home Assistant Integration [Better Thermostat](https://github.com/kartoteket/better-thermostat) konzipiert.**
> 
> * **Better Thermostat** übernimmt die Raumkalibrierung, externe Temperatursensoren, Fenster-Offen-Erkennung und TRV-Ansteuerung.
> * **Smart Climate Scheduler** steuert die übergeordnete Wochen-Planung, das adaptive Vorheizen (Preheat), vorzeitige Absenken (Cooldown) und schaltet dynamisch die Presets (`comfort`, `eco`, `sleep`, `away`, `boost`) von Better Thermostat.
>
> ℹ️ **Hinweis für reguläre Thermostate (z. B. Zigbee / Z-Wave TRVs):**  
> Da Smart Climate Scheduler nativ auf der Preset-Architektur und den Solltemperatur-Tabellen von Better Thermostat aufsetzt (`climate.set_preset_mode`), empfehlen wir dringend, herkömmliche Thermostate (z. B. über ZHA, Zigbee2MQTT, Homematic, Shelly TRV) zuerst in **Better Thermostat** einzubinden und die resultierende `climate.*`-Entität hier zu nutzen. *(Ein universeller Standalone-Modus mit direkter `climate.set_temperature`-Steuerung für Thermostate ohne Presets ist für ein zukünftiges Update auf der Roadmap notiert).*

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

### 1. 🤝 Perfektes Zusammenspiel mit Better Thermostat
* **Native Preset-Steuerung**: Schaltet direkt die Better Thermostat Presets (`comfort`, `eco`, `sleep`, `away`, `boost`, `none`).
* **Automatische Temperatur-Übernahme**: Liest die in Better Thermostat hinterlegten Solltemperaturen je Preset (`bt_preset_heat_temperatures`) automatisch aus – keine doppelte Pflege von Zieltemperaturen.
* **Präzise Sensor-Glättung**: Nutzt das Better Thermostat Attribut `external_temp_ema` (geglättete Temperatur externer Sensoren) für hochstabile Vorheiz- und Lernberechnungen.

### 2. 📅 Integrierte Zeitpläne (Schedules) mit Kopierfunktion
* **Direkt in der Integration**: Du benötigst keine externen Scheduler-Addons, YAML-Konfigurationen oder Hilfssensoren. Die Zeitpläne werden direkt in der Integration gepflegt.
* **Flexible Zeitfenster (Slots)**: Teile jeden Tag in beliebige Zeitfenster mit individuellen Start-/Endzeiten und zugeordneten Presets ein.
* **Kopierfunktion für Tage**: 
  * Ein erstellter Zeitplan (z. B. für Montag) kann mit einem Klick auf alle weiteren Wochentage übertragen werden.
  * Wochenend-Tage lassen sich duplizieren oder anpassen.
  * Dies spart viel Zeit bei der Ersteinrichtung und bei saisonalen Anpassungen.
* **Wochentags-Modus**: Individuelle Tagespläne für jeden Wochentag (Mo, Di, Mi, Do, Fr, Sa, So) mit komfortabler Übertragung per Kopierfunktion.

### 3. 🔥 Dual-Matrix Thermik-Lernengine (K/h)
* **Aufheiz-Matrix**: Erfasst bei aktiver Heizung kontinuierlich die tatsächliche Aufheizgeschwindigkeit des Raumes in Kelvin pro Stunde (K/h), sortiert nach Außentemperatur-Clustern (z. B. `< -5 °C`, `0 °C`, `+5 °C`, `+12 °C`).
* **Abkühl-Matrix**: Misst, wie schnell der Raum bei inaktiver Heizung Wärme verliert (in K/h).
* **Rolling Average mit ±5%-Ausreißerfilter**: Messungen werden geglättet; extreme Spikes (z. B. durch kurzes Stoßlüften) verfälschen die gelernten Daten nicht.
* **Automatischer Fallback**: Liegen für einen Außentemperaturbereich noch keine Messwerte vor, greift die Integration stabil auf den hinterlegten Standardwert (Default: 1,0 K/h) zurück.

### 4. 📍 Zonen-, Distanz- & Anwesenheitserkennung
* Erkennt automatisch die Anwesenheit von Bewohnern über konfigurierte Zonen (`home`, `away`) und GPS-Distanzen.
* Bei Abwesenheit wird energieeffizient auf das `away`- oder `eco`-Preset gewechselt.
* Nähert sich eine Person dem Zuhause (`near_distance`), kann die Vorheizung bereits vor dem eigentlichen Eintreffen starten.

### 5. 🎛️ Temporäre Overrides (Party-, Gäste- & Home-Office-Modus)
* Manuelle Abweichungen vom regulären Zeitplan können jederzeit per Service-Aufruf oder Dashboard-Schalter aktiviert werden:
  * Dauer-Override: z. B. *"Heize für die nächsten 2 Stunden auf Boost"*.
  * Zeitfenster-Override: z. B. *"Halte bis 23:00 Uhr die Komfort-Temperatur"*.
* Nach Ablauf der gewählten Zeitspanne kehrt das System automatisch in den regulären Zeitplan zurück.

### 6. 🎨 Eingebettete Lovelace-Karte (24h-Zeitleiste & Drag-&-Drop)
* **Automatisch integriert**: Die benutzerdefinierte Lovelace-Karte **`smart-climate-scheduler-card`** wird direkt mit der Integration ausgeliefert und automatisch im Home Assistant Frontend registriert – es ist kein HACS-Frontend-Download nötig.
* **Raumauswahl über `config_entry`**: Im visuellen Karten-Editor wählst du direkt den gewünschten Raum (**Config Entry**) aus – unabhängig von umbenannten Sensor-IDs.
* **Interaktive 24h-Zeitleiste**: Wochentag-Tabs (Mo–So), farbcodierte Zeitblöcke, neue Slots per Klick anlegen sowie Start-/Endzeiten per Drag-&-Drop im 5-, 15- oder 30-Minuten-Raster anpassen.
* **Komplette Steuerung auf dem Dashboard**: Vorheizen & Auskühlen pro Slot schalten, Tagespläne mit einem Klick auf Mo–Fr / Sa–So / einzelne Tage kopieren, Profile wechseln oder neu anlegen, Automatik ein-/ausschalten und Schnell-Overrides direkt starten.

### 7. 🎚️ Volle Kontrolle: Automatik-Schalter, Toleranz-Steuerung & Matrix-Pflege
* **Schalter `switch.<name>_automatic`**: Aktiviert oder pausiert die gesamte Automatik für den Raum bequem vom Dashboard aus.
* **Better Thermostat Toleranz-Steuerung**: Verknüpft (automatisch per Gerät oder optional gewählt) die Toleranz-Entität (`number.*`), setzt sie bei opportunistischem Mitheizen temporär auf `0` K und stellt den Originalwert beim Heizstart (`heating`) zuverlässig wieder her.
* **Lernen konfigurieren (Options-Flow)**: Wer feste Aufheiz- oder Abkühlwerte bevorzugt, schaltet das adaptive Lernen in den Integrations-Optionen (*Einstellungen > Geräte & Dienste > Smart Climate Scheduler > Konfigurieren*) ab. Die Vorheizung rechnet dann stabil mit den vorgegebenen Standard-Raten.
* **Dienste zur Matrix-Pflege**: Einzelne K/h-Werte pro Außentemperatur können jederzeit gezielt per Home Assistant Service eingesehen, manuell gesetzt oder zurückgesetzt werden.

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
1. Lade das Release-ZIP `smart_climate_scheduler_v3.0.0.zip` herunter.
2. Entpacke den Ordner `smart_climate_scheduler` in dein Home Assistant Verzeichnis:
   ```text
   /config/custom_components/smart_climate_scheduler/
   ```
3. Starte Home Assistant neu über *Entwicklerwerkzeuge > Neustart*.

---

## ⚙️ Schnelleinrichtung (Config Flow)

1. **Voraussetzung**: Richte zunächst deine Räume in **Better Thermostat** ein (oder verknüpfe ein Thermostat mit Preset-Unterstützung).
2. Navigiere in Home Assistant zu **Einstellungen** > **Geräte & Dienste** > **Integration hinzufügen**.
3. Suche nach **Smart Climate Scheduler**.
4. Folge dem Einrichtungsassistenten:
   * **Klimagerät (`climate.*`)**: Wähle dein Better Thermostat (z. B. `climate.better_thermostat_wohnzimmer`).
   * **Außentemperatur**: Wähle deinen Außensensor (`sensor.*_temperature`) oder deinen Wetterdienst (`weather.*`).
   * **Brenner-/Heizaktiv-Sensor (Optional)**: Sensor, der anzeigt, ob der Heizkörper aktiv warm wird.
   * **Zeitpläne einrichten**: Richte deine Zeitfenster direkt im Assistenten oder bequem über die integrierte Lovelace-Karte ein.

---

## 🎨 Lovelace-Karte zum Dashboard hinzufügen

Nach der Installation und einem Home Assistant Neustart steht die Karte **„Smart Climate Scheduler Card“** automatisch im Dashboard-Editor (*Karte hinzufügen*) zur Verfügung:

1. Öffne dein Dashboard und wähle **Dashboard bearbeiten > + Karte hinzufügen**.
2. Suche nach **Smart Climate Scheduler Card** und wähle im visuellen Editor den gewünschten **Raum / Config Entry** aus.
3. Optional per YAML-Konfiguration einbinden:
   ```yaml
   type: custom:smart-climate-scheduler-card
   config_entry: <DEINE_CONFIG_ENTRY_ID>
   snap_minutes: 15
   show_override_bar: true
   ```

> 💡 **Tipp:** Auf der 24h-Zeitleiste legst du per Klick auf freie Fläche neue Zeit-Slots an, verschiebst oder skalierst Blöcke per Drag-&-Drop an den Rändern und passt im unteren Inspektor Start/Ende, Preset sowie *Vor Start vorheizen* und *Vor Ende auskühlen* an.

---

## 💡 Entitäten & Praxis-Tipps

Die Integration erzeugt für jeden konfigurierten Raum ein sauberes Set an echten Home Assistant Entitäten:

| Entität | Typ | Funktion & Details | Dashboard-Empfehlung |
| :--- | :--- | :--- | :--- |
| `switch.<name>_automatic` | Schalter | Hauptschalter für die Zeitplan-Automatik des Raumes | **Auf Dashboard anzeigen** |
| `sensor.<name>_schedule` | Sensor | Aktives Soll-Preset (`comfort`, `eco`, etc.) mit Attributen `active_slot` & `next_slot` | **Auf Dashboard anzeigen** |
| `sensor.<name>_heating_rate` | Sensor (K/h) | Gemessene & gelernte Aufheizrate in K/h (Attribute: `averages`-Matrix & `average`) | **Diagnose / Charts** |
| `sensor.<name>_cooling_rate` | Sensor (K/h) | Gemessene & gelernte Abkühlrate in K/h (Attribute: `averages`-Matrix & `average`) | **Diagnose / Charts** |
| `sensor.<name>_next_action` | Sensor | Nächste geplante Aktion (`preheat`, `cooldown`, etc.) mit Attribut `time` | **Auf Dashboard anzeigen** |
| `binary_sensor.<name>_preheat` | Binärsensor | `on`, wenn intelligente Vorheizung aktiv ist (Attribute: `duration_minutes`, `start_time`) | **Trigger für Automationen** |
| `binary_sensor.<name>_cooldown` | Binärsensor | `on`, wenn vorzeitiges Absenken aktiv ist (Attribute: `duration_minutes`, `start_time`) | **Statusanzeige** |
| `sensor.<name>_debug` | Sensor | Internzustand & Diagnoseparameter (Kategorie Diagnose) | *Standardmäßig deaktiviert* |

> ℹ️ **Praxis-Tipps:**
> * **Lernen anpassen**: Das adaptive Lernen wird nicht über einen Schalter, sondern zentral in den **Integrations-Optionen** (*Einstellungen > Geräte & Dienste > Smart Climate Scheduler > Konfigurieren*) über das Häkchen *Lernen aktivieren* gesteuert.
> * **Vorheizdauer ablesen**: Die berechnete Vorheizzeit in Minuten steht direkt als Attribut `duration_minutes` am Binärsensor `binary_sensor.<name>_preheat` zur Verfügung.
> * **Entitäten umbenennen**: Du kannst die technische `entity_id` jederzeit unter *Einstellungen > Geräte & Dienste > Entitäten > Zahnrad* an dein persönliches Schema anpassen.

---

## 🎛️ Verfügbare Dienste (Services)

Die Dienste nutzen ein übersichtliches, verpflichtendes **Geräte-Feld** (`device_id`), sodass im Home Assistant Aktions-Picker direkt der jeweilige Raum als Pflichtfeld ausgewählt wird (ohne Checkbox und ohne Entitäten-Picker):

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

## 🗺️ Roadmap & Zukünftige Erweiterungen

Für zukünftige Versionen sind folgende Erweiterungen vorgemerkt:

- [ ] **Universeller Standalone-Thermostat-Modus (Direkte Temperatursteuerung)**:
  - Automatischer Fallback auf `climate.set_temperature` für Thermostate ohne Home Assistant Preset-Unterstützung (z. B. reine Zigbee-/Z-Wave-TRVs ohne Better Thermostat).
  - Frei konfigurierbare Sollwert-Temperaturen für Presets (`comfort`, `eco`, `sleep`, `away`, `boost`) direkt im Options-Flow, falls kein Better Thermostat vorgeschaltet ist.
  - Erweiterte Heizerkennung bei modulierenden Ventilen ohne `hvac_action` (z. B. über Ventilöffnung > 0 %).

---

## 📝 Changelog

<!-- CURRENT_CHANGELOG_START -->
Alle Änderungen findest du im [CHANGELOG.md](CHANGELOG.md). Highlights in **v3.0.0** (*Eingebettete 24h-Timeline Lovelace-Karte & Toleranz-Steuerung*):
* **Einfache Auswahl per `config_entry`**: Im visuellen Karten-Editor (und per `getStubConfig`) wird direkt das gewünschte **Raum-Config-Entry** ausgewählt – stabil auch bei umbenannten Entitäten.
* **24h-Zeitleiste & Wochentag-Tabs (Mo–So)**: Farblich nach Preset (`comfort`, `eco`, `home`, `sleep`, `boost`, `away`) abgesetzte Zeitblöcke inklusive Live-Zeitmarker.
* **Klick & Drag-&-Drop Bearbeitung**: Auf freie Fläche klicken, um neue Slots anzulegen; linke/rechte Ränder ziehen oder Blöcke verschieben (konfigurierbares 5-, 15- oder 30-Minuten-Raster).
<!-- CURRENT_CHANGELOG_END -->

---

## 📄 Lizenz

Dieses Projekt ist unter der **MIT-Lizenz** lizenziert – siehe [LICENSE](LICENSE) für Details.

Entwickelt für die Home Assistant Community von **@IvoryBalboa**.
