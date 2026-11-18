# Changelog

Jede veröffentlichte Versionsnummer besitzt hier einen eigenen, eigenständigen Changelog-Eintrag. Dieser wird beim Build automatisch für HACS (`README.md`) und das GitHub Release übernommen.

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

## v2.5.0 – Better Thermostat Toleranz-Entität & 0-K-Mitheizen

- Automatische Geräteerkennung der `number.*`-Toleranz-Entität von Better Thermostat (mit optionaler manueller Auswahl im Config-/Options-Flow).
- Persistentes Sichern und temporäres Setzen der Toleranz auf `0` K bei aktivem Brenner und geschlossenen Fenstern, mit Wiederherstellung beim Wechsel auf `heating`.
- Korrektur der Zwei-Punkt-Regelung bei `tolerance = 0` sowie direkte Überwachung von Toleranzänderungen.

## v2.4.9 – Vorheizen & Auskühlen separat pro Slot steuerbar

- Jeder Zeitplan-Slot erhält eigene Checkboxen für **„Vor Slot-Start vorheizen“** und **„Vor Slot-Ende auskühlen“** (globale Raum-Schalter bleiben Hauptschalter).
- Eigenes Top-Level-Attribut `profile` am Haupt- und Diagnose-Sensor inklusive Übersetzungen in allen 7 Sprachen.
- Fenster- & Tür-Erkennung (`window_open` / `door_open`) pausiert opportunistisches Mitheizen und bricht aktive Kickstarts sofort ab.
