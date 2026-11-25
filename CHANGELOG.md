# Changelog

Jede veröffentlichte Versionsnummer besitzt hier einen eigenen, eigenständigen Changelog-Eintrag. Dieser wird beim Build automatisch für HACS (`README.md`) und das GitHub Release übernommen.

## v3.3.0 – Anomalie- & Hardware-Wächter (brenner-sensitiv)

- **Brenner-sensitive Heizüberwachung („Keine Erwärmung“)**: Erkennt automatisch, wenn ein Thermostat über den konfigurierbaren Schwellwert (Standard: **45 Minuten**, 0–240 Min. im Config- & Options-Flow anpassbar) aktiv heizt, die Temperatur jedoch nicht um mindestens `+0,15 °C` steigt – bei konfiguriertem zentralem Brenner-Sensor (`heating_active_sensor`) strikt erst dann, wenn auch der Brenner tatsächlich aktiv ist (bei Nachtabsenkung/Brenner-Aus erfolgt kein Fehlalarm, ebenso bei geöffnetem Fenster).
- **Thermostat-Ausfall & eingefrorener Temperatursensor**: Meldet `unavailable`/`unknown` am Thermostat (nach Ablauf der 90s-Start-Karenzzeit) sowie eingefrorene Sensoren (`>= 180 Min.` unveränderte Temperatur bei Heizbedarf bzw. `last_updated`, oder `>= 360 Min.` im Leerlauf).
- **Neuer Diagnose-Problem-Sensor (`BinarySensorDeviceClass.PROBLEM`)**: Stellt pro Raum eine lokalisierte Diagnose-Entität (`_anomaly` / `_anomalie`) inklusive Brenner-Kontext, Heizdauer ohne Anstieg, `ΔT` und Entity-Registry-Synchronisation bereit.
- **Lovelace-Warnbadge & Übersichtskarten-Filter**: Beide eingebetteten Karten (`smart-climate-scheduler-card` & `smart-climate-scheduler-overview-card`) zeigen Live-Warnbadges (`⚠️`), Detailbanner und einen eigenen `Warnungen`-Filter inklusive Prioritäts-Sortierung in allen 7 Sprachen.

## v3.2.0 – Multi-Raum Sammelaktionen, Filter & Sortierung

- **Filter- & Sortierleiste in der Multi-Raum-Übersichtskarte (`custom:smart-climate-scheduler-overview-card`)**: Räume lassen sich direkt über Schnellfilter mit Live-Zählern (**Alle**, **Automatik An**, **Heizt / Thermik**, **Override**) eingrenzen sowie nach **Name (A–Z)**, **Aktive Phase zuerst** oder **Größte Abweichung (ΔT)** sortieren (Standard-Filter und -Sortierung auch im Karten-Editor konfigurierbar).
- **Sammelaktionen für gefilterte Räume**: Direkt aus dem Kartenkopf lassen sich **Alle Automatik An/Aus**, **Sammel-Override** (Preset + Dauer), **Aktive Overrides stoppen** sowie **gemeinsame Zeitplan-Profile** auf alle aktuell angezeigten Räume gleichzeitig anwenden.
- **Robuste Entity-Registry-Auflösung & `entry_id`-Steuerung**: Automatik-Schalter, Zeitplan-Sensor und Profil-Auswahl werden per `unique_id` aus der Home-Assistant-Entity-Registry aufgelöst und Einzel- sowie Sammel-Schaltungen der Automatik laufen direkt über `entry_id` (`smart_climate_scheduler/set_automation`), sodass auch umbenannte Entitäten jederzeit zuverlässig funktionieren.
- **7-Sprachen-Lokalisierung & Live-Simulator**: Vollständige Übersetzungen aller Filter-, Sortier- und Sammelaktions-Texte sowie interaktive Live-Vorschau beider Lovelace-Karten im Web-Tab.

## v3.1.0 – Konfigurierbare Abwesenheits-Presets, Live-Thermik-Vorschau & Multi-Raum-Übersicht

- **Konfigurierbares `away`- und `away_near`-Preset pro Raum**: Im Config- und Options-Flow lassen sich nun getrennte Ziel-Presets für „Unterwegs (nah)“ (`away_near_preset`, Standard `eco`) und „Abwesend“ (`away_preset`, Standard `away`) je Raum festlegen und live über `debug_info.settings` einsehen.
- **Live-Vorschau für Vorheizen & Auskühlen auf der 24h-Zeitleiste**: Für den heutigen Tag stellt die Timeline-Karte berechnete Vorheiz- und Auskühl-Fenster direkt als gestreifte Vorschau-Segmente inklusive Tooltip auf der Zeitleiste dar (über den Karten-Editor ein-/ausschaltbar).
- **Neue Multi-Raum-Übersichtskarte (`custom:smart-climate-scheduler-overview-card`)**: Eigenständige Lovelace-Karte mit Raumauswahl (leer = alle Räume), Ist-/Soll-Temperatur, aktivem Preset, Phasen-Badge, kompakter 24h-Mini-Zeitleiste, direktem Automatik-Schalter sowie per Klick aufklappbarer Mini-Steuerung (nächste Aktion, Profilwechsel & Schnell-Override).

## v3.0.1 – Home Assistant 2026.12 Kompatibilität & OptionsFlow-Fix

- **Kompatibilität mit Home Assistant 2026.10–2026.12 (`DeviceEntry.config_entry_id`)**: Bei der Auflösung von `device_id`- und `area_id`-Service-Zielen wird ausschließlich `device.config_entry_id` genutzt, sobald das Attribut existiert (auch wenn es `None` ist) – das abgekündigte Property `DeviceEntry.config_entries` wird nicht mehr berührt.
- **Kein Doppel-Reload im Options-Flow**: Beim Speichern über den Options-Flow wird `entry.data` nur noch bei tatsächlichen Änderungen aktualisiert und ein verfrühter Zwischen-Reload im `update_listener` unterdrückt, sodass genau ein sauberer Integrations-Reload erfolgt.
- **Bereinigung für Home Assistant 2025.1+**: Die Mindestversion in `hacs.json` wurde auf `2025.1.0` angehoben und der entfernte `hass.http.register_static_path`-Fallback zugunsten von `async_register_static_paths` entfernt.

## v3.0.0 – Eingebettete 24h-Timeline Lovelace-Karte & Toleranz-Steuerung

### 🎨 Neue interaktive 24h-Timeline Lovelace-Karte (`custom:smart-climate-scheduler-card`)
Die Integration bringt nun eine **direkt eingebettete Custom Lovelace Card** mit, die beim Start von Home Assistant automatisch als Frontend-Modul (`/smart_climate_scheduler_files/smart-climate-scheduler-card.js`) registriert wird – eine manuelle Einrichtung von Dashboard-Ressourcen ist nicht erforderlich.

- **Einfache Auswahl per `config_entry`**: Im visuellen Karten-Editor (und per `getStubConfig`) wird direkt das gewünschte **Raum-Config-Entry** ausgewählt – stabil auch bei umbenannten Entitäten.
- **24h-Zeitleiste & Wochentag-Tabs (Mo–So)**: Farblich nach Preset (`comfort`, `eco`, `home`, `sleep`, `boost`, `away`) abgesetzte Zeitblöcke inklusive Live-Zeitmarker.
- **Klick & Drag-&-Drop Bearbeitung**: Auf freie Fläche klicken, um neue Slots anzulegen; linke/rechte Ränder ziehen oder Blöcke verschieben (konfigurierbares 5-, 15- oder 30-Minuten-Raster).
- **Inline-Slot-Inspektor**: Startzeit, Endzeit, Preset sowie **„Vor Start vorheizen“** und **„Vor Ende auskühlen“** direkt pro Slot umschalten und speichern.
- **Tag kopieren**: Tagespläne mit einem Klick auf Mo–Fr, Sa–So oder einzelne Wochentage übertragen.
- **Profile, Automatik & Schnell-Override direkt auf dem Dashboard**: Zeitplan-Profile wechseln, anlegen, umbenennen oder löschen, Raum-Automatik schalten sowie temporäre Overrides (Preset + Dauer) starten oder vorzeitig beenden.
- **Nahtlose WebSocket-Synchronisation**: Änderungen aus der Lovelace-Karte werden sofort gespeichert und aktiv angewendet, ohne die Integration neu zu laden (`smart_climate_scheduler/list_entries`, `get_schedule`, `save_day_slots`, `copy_day_slots`, `manage_profile`).

### 🔥 Better Thermostat Toleranz-Steuerung & Zwei-Punkt-Fix
- **Toleranz-Entität (`number.*`)**: Automatische Erkennung über das verknüpfte Thermostat-Gerät (oder optionale manuelle Auswahl im Config-/Options-Flow).
- **Opportunistisches Mitheizen mit 0 K Toleranz**: Bei aktivem Brenner, aktiver Automatik & Mitheizen sowie geschlossenen Fenstern wird der Originalwert der Toleranz persistent gesichert, auf `0` gesetzt und sofort wiederhergestellt, sobald `hvac_action` auf `heating` springt (inkl. Sicherheits-Wiederherstellung bei Brenner-Aus, Fenster-Offen oder Neustart).
- **Zweipunkt-Regelung**: `tolerance = 0` wird korrekt ausgewertet und Änderungen an der verknüpften Toleranz-Entität lösen unmittelbar eine Neubewertung (inkl. Umschalten auf `heat`) aus.
- **Vorheiz-Haltephase bei früher Zielerreichung**: Wird während des aktiven Vorheizens die Zieltemperatur bereits vor Slot-Start erreicht, schaltet der Vorheizen-Sensor auf `Aus` und das Lernen endet, das Ziel-Preset wird jedoch sauber bis zum Slot-Beginn gehalten statt auf das vorherige Preset zurückzufallen (inkl. Beachtung von `Vorheizen ignoriert Abwesenheit`).
- **90s-Start-Karenzzeit für verzögerte Thermostate & Brenner-Sensoren**: Während des Hochfahrens von Home Assistant und für 90 Sekunden nach `EVENT_HOMEASSISTANT_STARTED` werden noch nicht bereite Thermostate (z. B. Better Thermostat) und Heizungs-Sensoren nur auf `DEBUG` protokolliert; sobald die Entität bereit ist, greift der Zeitplan sofort, und erst nach Ablauf der 90 Sekunden werden dauerhaft fehlende/nicht verfügbare Entitäten als `WARNING` gemeldet.

## v2.5.0 – Better Thermostat Toleranz-Entität & 0-K-Mitheizen

- Automatische Geräteerkennung der `number.*`-Toleranz-Entität von Better Thermostat (mit optionaler manueller Auswahl im Config-/Options-Flow).
- Persistentes Sichern und temporäres Setzen der Toleranz auf `0` K bei aktivem Brenner und geschlossenen Fenstern, mit Wiederherstellung beim Wechsel auf `heating`.
- Korrektur der Zwei-Punkt-Regelung bei `tolerance = 0` sowie direkte Überwachung von Toleranzänderungen.

## v2.4.9 – Vorheizen & Auskühlen separat pro Slot steuerbar

- Jeder Zeitplan-Slot erhält eigene Checkboxen für **„Vor Slot-Start vorheizen“** und **„Vor Slot-Ende auskühlen“** (globale Raum-Schalter bleiben Hauptschalter).
- Eigenes Top-Level-Attribut `profile` am Haupt- und Diagnose-Sensor inklusive Übersetzungen in allen 7 Sprachen.
- Fenster- & Tür-Erkennung (`window_open` / `door_open`) pausiert opportunistisches Mitheizen und bricht aktive Kickstarts sofort ab.
