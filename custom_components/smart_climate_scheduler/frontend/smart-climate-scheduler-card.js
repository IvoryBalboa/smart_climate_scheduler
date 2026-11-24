/**
 * Smart Climate Scheduler Card (v3.0.0)
 * Embedded interactive 24h timeline Lovelace card for Home Assistant.
 * Self-contained ES module with Shadow DOM & zero external dependencies.
 */

const CARD_TAG = "smart-climate-scheduler-card";
const EDITOR_TAG = "smart-climate-scheduler-card-editor";
const DOMAIN = "smart_climate_scheduler";
const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const DEFAULT_PRESETS = ["none", "home", "away", "boost", "comfort", "eco", "sleep", "activity"];

const I18N = {
  de: {
    daysShort: ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    daysFull: ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
    automatic: "Automatik",
    profile: "Profil",
    copyDay: "Tag kopieren",
    quickOverride: "Schnell-Override",
    cancelOverride: "Override aus",
    baseTrack: "Basis",
    preheating: "Vorheizen aktiv",
    coolingDown: "Auskühlen aktiv",
    overrideActive: "Override aktiv",
    targetTemp: "Soll",
    start: "Start",
    end: "Ende",
    preset: "Preset",
    preheatSlot: "Vor Start vorheizen",
    cooldownSlot: "Vor Ende auskühlen",
    save: "Speichern",
    delete: "Löschen",
    addSlot: "+ Slot",
    noSlots: "Keine Slots für diesen Tag — auf die Zeitleiste klicken oder „+ Slot“ nutzen.",
    clickHint: "Tipp: Auf freie Fläche klicken für neuen Slot · Ränder ziehen für Zeiten · Anklicken zum Bearbeiten",
    copyTitle: "Slots kopieren nach:",
    workdays: "Mo–Fr",
    weekend: "Sa–So",
    allDays: "Alle",
    applyCopy: "Kopieren",
    cancel: "Abbrechen",
    overrideTitle: "Temporären Override starten",
    duration: "Dauer",
    startOverride: "Aktivieren",
    saved: "Gespeichert",
    selectRoom: "Bitte einen Smart Climate Scheduler Raum (Config Entry) auswählen.",
    loading: "Lade Zeitplan...",
    newProfile: "Neues Profil",
    profileName: "Profilname",
    createProfile: "Anlegen",
    renameProfile: "Umbenennen",
    deleteProfile: "Profil löschen",
    copyOf: "Kopie von",
    empty: "Leer",
    editorEntity: "Raum / Config Entry (Smart Climate Scheduler)",
    editorName: "Anzeigename (optional)",
    editorSnap: "Zeitraster beim Ziehen",
    editorShowOverride: "Schnell-Override-Leiste anzeigen",
    minutes: "Min",
  },
  en: {
    daysShort: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    daysFull: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    automatic: "Automatic",
    profile: "Profile",
    copyDay: "Copy day",
    quickOverride: "Quick override",
    cancelOverride: "Stop override",
    baseTrack: "Base",
    preheating: "Preheating",
    coolingDown: "Cooling down",
    overrideActive: "Override active",
    targetTemp: "Target",
    start: "Start",
    end: "End",
    preset: "Preset",
    preheatSlot: "Preheat before start",
    cooldownSlot: "Cooldown before end",
    save: "Save",
    delete: "Delete",
    addSlot: "+ Slot",
    noSlots: "No slots for this day — click the timeline or use “+ Slot”.",
    clickHint: "Tip: Click empty track to add · Drag edges to resize · Click block to edit",
    copyTitle: "Copy slots to:",
    workdays: "Mon–Fri",
    weekend: "Sat–Sun",
    allDays: "All",
    applyCopy: "Copy",
    cancel: "Cancel",
    overrideTitle: "Start temporary override",
    duration: "Duration",
    startOverride: "Activate",
    saved: "Saved",
    selectRoom: "Please select a Smart Climate Scheduler room (Config Entry).",
    loading: "Loading schedule...",
    newProfile: "New profile",
    profileName: "Profile name",
    createProfile: "Create",
    renameProfile: "Rename",
    deleteProfile: "Delete profile",
    copyOf: "Copy of",
    empty: "Empty",
    editorEntity: "Room / Config Entry (Smart Climate Scheduler)",
    editorName: "Display name (optional)",
    editorSnap: "Drag snap grid",
    editorShowOverride: "Show quick override controls",
    minutes: "min",
  },
  fr: {
    daysShort: ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
    daysFull: ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"],
    automatic: "Automatique",
    profile: "Profil",
    copyDay: "Copier le jour",
    quickOverride: "Dérogation rapide",
    cancelOverride: "Arrêter",
    baseTrack: "Base",
    preheating: "Préchauffage",
    coolingDown: "Refroidissement",
    overrideActive: "Dérogation active",
    targetTemp: "Cible",
    start: "Début",
    end: "Fin",
    preset: "Préréglage",
    preheatSlot: "Préchauffer avant début",
    cooldownSlot: "Refroidir avant fin",
    save: "Enregistrer",
    delete: "Supprimer",
    addSlot: "+ Créneau",
    noSlots: "Aucun créneau — cliquez sur la chronologie ou sur « + Créneau ».",
    clickHint: "Astuce : cliquez pour ajouter · glissez les bords · cliquez un bloc",
    copyTitle: "Copier vers :",
    workdays: "Lun–Ven",
    weekend: "Sam–Dim",
    allDays: "Tous",
    applyCopy: "Copier",
    cancel: "Annuler",
    overrideTitle: "Démarrer une dérogation",
    duration: "Durée",
    startOverride: "Activer",
    saved: "Enregistré",
    selectRoom: "Veuillez sélectionner un espace Smart Climate Scheduler (Config Entry).",
    loading: "Chargement...",
    newProfile: "Nouveau profil",
    profileName: "Nom du profil",
    createProfile: "Créer",
    renameProfile: "Renommer",
    deleteProfile: "Supprimer profil",
    copyOf: "Copie de",
    empty: "Vide",
    editorEntity: "Pièce / Config Entry (Smart Climate Scheduler)",
    editorName: "Nom affiché (optionnel)",
    editorSnap: "Grille temporelle",
    editorShowOverride: "Afficher la dérogation rapide",
    minutes: "min",
  },
  es: {
    daysShort: ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
    daysFull: ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
    automatic: "Automático",
    profile: "Perfil",
    copyDay: "Copiar día",
    quickOverride: "Anulación rápida",
    cancelOverride: "Detener",
    baseTrack: "Base",
    preheating: "Precalentando",
    coolingDown: "Enfriando",
    overrideActive: "Anulación activa",
    targetTemp: "Objetivo",
    start: "Inicio",
    end: "Fin",
    preset: "Modo",
    preheatSlot: "Precalentar antes",
    cooldownSlot: "Enfriar antes del fin",
    save: "Guardar",
    delete: "Eliminar",
    addSlot: "+ Franja",
    noSlots: "Sin franjas — haz clic en la línea o usa «+ Franja».",
    clickHint: "Consejo: clic para añadir · arrastra bordes · clic en bloque para editar",
    copyTitle: "Copiar a:",
    workdays: "Lun–Vie",
    weekend: "Sáb–Dom",
    allDays: "Todos",
    applyCopy: "Copiar",
    cancel: "Cancelar",
    overrideTitle: "Iniciar anulación temporal",
    duration: "Duración",
    startOverride: "Activar",
    saved: "Guardado",
    selectRoom: "Selecciona una habitación de Smart Climate Scheduler (Config Entry).",
    loading: "Cargando horario...",
    newProfile: "Nuevo perfil",
    profileName: "Nombre del perfil",
    createProfile: "Crear",
    renameProfile: "Renombrar",
    deleteProfile: "Eliminar perfil",
    copyOf: "Copia de",
    empty: "Vacío",
    editorEntity: "Habitación / Config Entry",
    editorName: "Nombre (opcional)",
    editorSnap: "Intervalo de ajuste",
    editorShowOverride: "Mostrar anulación rápida",
    minutes: "min",
  },
  it: {
    daysShort: ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"],
    daysFull: ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"],
    automatic: "Automatico",
    profile: "Profilo",
    copyDay: "Copia giorno",
    quickOverride: "Override rapido",
    cancelOverride: "Termina",
    baseTrack: "Base",
    preheating: "Preriscaldamento",
    coolingDown: "Raffreddamento",
    overrideActive: "Override attivo",
    targetTemp: "Target",
    start: "Inizio",
    end: "Fine",
    preset: "Preset",
    preheatSlot: "Preriscalda prima",
    cooldownSlot: "Raffredda prima della fine",
    save: "Salva",
    delete: "Elimina",
    addSlot: "+ Fascia",
    noSlots: "Nessuna fascia — clicca sulla linea o usa «+ Fascia».",
    clickHint: "Suggerimento: clicca per aggiungere · trascina i bordi · clicca per modificare",
    copyTitle: "Copia su:",
    workdays: "Lun–Ven",
    weekend: "Sab–Dom",
    allDays: "Tutti",
    applyCopy: "Copia",
    cancel: "Annulla",
    overrideTitle: "Avvia override temporaneo",
    duration: "Durata",
    startOverride: "Attiva",
    saved: "Salvato",
    selectRoom: "Seleziona una stanza Smart Climate Scheduler (Config Entry).",
    loading: "Caricamento...",
    newProfile: "Nuovo profilo",
    profileName: "Nome profilo",
    createProfile: "Crea",
    renameProfile: "Rinomina",
    deleteProfile: "Elimina profilo",
    copyOf: "Copia di",
    empty: "Vuoto",
    editorEntity: "Stanza / Config Entry",
    editorName: "Nome visualizzato (opzionale)",
    editorSnap: "Griglia di trascinamento",
    editorShowOverride: "Mostra override rapido",
    minutes: "min",
  },
  nl: {
    daysShort: ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"],
    daysFull: ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"],
    automatic: "Automatisch",
    profile: "Profiel",
    copyDay: "Dag kopiëren",
    quickOverride: "Snelle override",
    cancelOverride: "Stoppen",
    baseTrack: "Basis",
    preheating: "Voorverwarmen",
    coolingDown: "Afkoelen",
    overrideActive: "Override actief",
    targetTemp: "Doel",
    start: "Start",
    end: "Einde",
    preset: "Preset",
    preheatSlot: "Voorverwarmen vóór start",
    cooldownSlot: "Afkoelen vóór einde",
    save: "Opslaan",
    delete: "Verwijderen",
    addSlot: "+ Blok",
    noSlots: "Geen tijdvakken — klik op de tijdlijn of gebruik «+ Blok».",
    clickHint: "Tip: klik om toe te voegen · sleep randen · klik om te bewerken",
    copyTitle: "Kopiëren naar:",
    workdays: "Ma–Vr",
    weekend: "Za–Zo",
    allDays: "Alle",
    applyCopy: "Kopiëren",
    cancel: "Annuleren",
    overrideTitle: "Tijdelijke override starten",
    duration: "Duur",
    startOverride: "Activeren",
    saved: "Opgeslagen",
    selectRoom: "Selecteer een Smart Climate Scheduler kamer (Config Entry).",
    loading: "Laden...",
    newProfile: "Nieuw profiel",
    profileName: "Profielnaam",
    createProfile: "Aanmaken",
    renameProfile: "Hernoemen",
    deleteProfile: "Profiel verwijderen",
    copyOf: "Kopie van",
    empty: "Leeg",
    editorEntity: "Kamer / Config Entry",
    editorName: "Weergavenaam (optioneel)",
    editorSnap: "Sleep-raster",
    editorShowOverride: "Toon snelle override",
    minutes: "min",
  },
  pl: {
    daysShort: ["Pn", "Wt", "Śr", "Cz", "Pt", "Sb", "Nd"],
    daysFull: ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"],
    automatic: "Automatyka",
    profile: "Profil",
    copyDay: "Kopiuj dzień",
    quickOverride: "Szybki override",
    cancelOverride: "Zakończ",
    baseTrack: "Baza",
    preheating: "Nagrzewanie",
    coolingDown: "Ochładzanie",
    overrideActive: "Aktywny override",
    targetTemp: "Cel",
    start: "Start",
    end: "Koniec",
    preset: "Tryb",
    preheatSlot: "Nagrzej przed startem",
    cooldownSlot: "Ochłodź przed końcem",
    save: "Zapisz",
    delete: "Usuń",
    addSlot: "+ Przedział",
    noSlots: "Brak przedziałów — kliknij oś czasu lub «+ Przedział».",
    clickHint: "Wskazówka: kliknij puste miejsce · przeciągnij krawędzie · kliknij blok",
    copyTitle: "Kopiuj do:",
    workdays: "Pn–Pt",
    weekend: "Sb–Nd",
    allDays: "Wszystkie",
    applyCopy: "Kopiuj",
    cancel: "Anuluj",
    overrideTitle: "Uruchom tymczasowy override",
    duration: "Czas trwania",
    startOverride: "Aktywuj",
    saved: "Zapisano",
    selectRoom: "Wybierz pokój Smart Climate Scheduler (Config Entry).",
    loading: "Ładowanie...",
    newProfile: "Nowy profil",
    profileName: "Nazwa profilu",
    createProfile: "Utwórz",
    renameProfile: "Zmień nazwę",
    deleteProfile: "Usuń profil",
    copyOf: "Kopia",
    empty: "Pusty",
    editorEntity: "Pokój / Config Entry",
    editorName: "Nazwa (opcjonalnie)",
    editorSnap: "Siatka czasu",
    editorShowOverride: "Pokaż szybki override",
    minutes: "min",
  },
};

function getTexts(lang) {
  const code = String(lang || "en").split(/[-_]/)[0].toLowerCase();
  return I18N[code] || I18N.en;
}

const PRESET_COLORS = {
  comfort: { bg: "#d97706", bgMuted: "rgba(217, 119, 6, 0.72)", border: "#fbbf24", text: "#111827" },
  boost: { bg: "#ea580c", bgMuted: "rgba(234, 88, 12, 0.78)", border: "#fb923c", text: "#ffffff" },
  home: { bg: "#059669", bgMuted: "rgba(5, 150, 105, 0.75)", border: "#34d399", text: "#ffffff" },
  eco: { bg: "#0d9488", bgMuted: "rgba(13, 148, 136, 0.70)", border: "#2dd4bf", text: "#ffffff" },
  sleep: { bg: "#4f46e5", bgMuted: "rgba(79, 70, 229, 0.72)", border: "#818cf8", text: "#ffffff" },
  away: { bg: "#475569", bgMuted: "rgba(71, 85, 105, 0.72)", border: "#94a3b8", text: "#ffffff" },
  activity: { bg: "#0284c7", bgMuted: "rgba(2, 132, 199, 0.75)", border: "#38bdf8", text: "#ffffff" },
  none: { bg: "#64748b", bgMuted: "rgba(100, 116, 139, 0.65)", border: "#cbd5e1", text: "#ffffff" },
};

function getPresetColor(preset) {
  const key = String(preset || "none").toLowerCase().trim();
  return PRESET_COLORS[key] || { bg: "#d97706", bgMuted: "rgba(217, 119, 6, 0.72)", border: "#fbbf24", text: "#111827" };
}

function parseMinutes(hhmm) {
  if (!hhmm || typeof hhmm !== "string") return 0;
  const parts = hhmm.split(":").map((x) => parseInt(x, 10));
  if (parts.length < 2 || Number.isNaN(parts[0]) || Number.isNaN(parts[1])) return 0;
  return Math.max(0, Math.min(1440, parts[0] * 60 + parts[1]));
}

function formatMinutes(totalMin, forSave = false) {
  const clamped = Math.max(0, Math.min(1440, Math.round(totalMin)));
  if (clamped >= 1440) {
    return forSave ? "23:59:00" : "24:00";
  }
  const h = Math.floor(clamped / 60);
  const m = clamped % 60;
  const base = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  return forSave ? `${base}:00` : base;
}

function snapMinutes(minVal, step = 15) {
  const s = Math.max(1, Number(step) || 15);
  return Math.max(0, Math.min(1440, Math.round(minVal / s) * s));
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function getTodayKey() {
  // JS getDay(): 0=Sun..6=Sat -> map to DAYS index (0=monday..6=sunday)
  const jsDay = new Date().getDay();
  return DAYS[(jsDay + 6) % 7];
}

function computeGapSegments(daySlots) {
  const intervals = (Array.isArray(daySlots) ? daySlots : [])
    .map((slot) => {
      const s = parseMinutes(slot.from);
      const e = slot.to?.startsWith("23:59") ? 1440 : parseMinutes(slot.to);
      return [s, e];
    })
    .filter(([s, e]) => e > s)
    .sort((a, b) => a[0] - b[0]);

  const gaps = [];
  let cursor = 0;
  for (const [s, e] of intervals) {
    if (s > cursor) {
      gaps.push({ startMin: cursor, endMin: s });
    }
    if (e > cursor) {
      cursor = e;
    }
  }
  if (cursor < 1440) {
    gaps.push({ startMin: cursor, endMin: 1440 });
  }
  return gaps;
}

const ICONS = {
  gear: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>',
  copy: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>',
  bolt: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>',
  plus: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>',
};

class SmartClimateSchedulerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._data = null;
    this._loading = false;
    this._error = null;
    this._toast = null;
    this._toastTimer = null;
    this._selectedDay = getTodayKey();
    this._selectedSlotIdx = null;
    this._draftSlot = null;
    this._activePanel = null; // null | 'copy' | 'override' | 'profile'
    this._copyTargets = new Set();
    this._overridePreset = "boost";
    this._overrideDurationMin = 60;
    this._dragState = null;
    this._suppressNextTrackClick = false;
    this._lastStateSig = null;
    this._fetchPending = false;
    this._boundPointerMove = (ev) => this._onPointerMove(ev);
    this._boundPointerUp = (ev) => this._onPointerUp(ev);
  }

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  static getStubConfig(hass) {
    let firstConfigEntry = "";
    if (hass && hass.entities) {
      const regMatch = Object.values(hass.entities).find(
        (e) => e?.platform === DOMAIN && e?.config_entry_id
      );
      if (regMatch?.config_entry_id) {
        firstConfigEntry = regMatch.config_entry_id;
      }
    }
    if (!firstConfigEntry && hass && hass.states) {
      const candidates = Object.keys(hass.states).filter(
        (eid) =>
          eid.startsWith("sensor.") &&
          hass.states[eid]?.attributes?.active_slot !== undefined
      );
      if (candidates.length > 0 && hass.entities?.[candidates[0]]?.config_entry_id) {
        firstConfigEntry = hass.entities[candidates[0]].config_entry_id;
      }
    }
    return {
      config_entry: firstConfigEntry,
      snap_minutes: 15,
      show_override_bar: true,
    };
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this._config = {
      snap_minutes: 15,
      show_override_bar: true,
      compact: false,
      ...config,
    };
    this._data = null;
    this._selectedSlotIdx = null;
    this._draftSlot = null;
    this._lastStateSig = null;
    if (this._hass) {
      this._fetchSchedule(true);
    } else {
      this._render();
    }
  }

  getCardSize() {
    return 3;
  }

  set hass(hass) {
    const prevHass = this._hass;
    this._hass = hass;
    if (!hass) return;

    if (!this._data && !this._fetchPending) {
      this._fetchSchedule(true);
      return;
    }

    // Track relevant entity states cleanly without resetting active drag/edits
    if (this._data && !this._dragState) {
      const watchedIds = [
        this._data.schedule_entity_id,
        this._data.climate_entity,
        this._data.automation_switch_entity_id,
        this._data.profile_select_entity_id,
      ].filter(Boolean);

      const sig = watchedIds
        .map((id) => {
          const st = hass.states?.[id];
          if (!st) return `${id}:missing`;
          const attrs = st.attributes || {};
          return `${id}:${st.state}:${attrs.current_temperature}:${attrs.temperature}:${attrs.hvac_action}:${attrs.profile}:${attrs.preset_mode}`;
        })
        .join("|");

      if (sig !== this._lastStateSig) {
        this._lastStateSig = sig;
        if (prevHass) {
          this._fetchSchedule(false);
        } else {
          this._render();
        }
      }
    }
  }

  async _fetchSchedule(showLoading = false) {
    if (!this._hass || this._fetchPending) return;
    this._fetchPending = true;
    if (showLoading && !this._data) {
      this._loading = true;
      this._render();
    }
    try {
      const payload = { type: `${DOMAIN}/get_schedule` };
      const targetEntryId = this._config?.config_entry || this._config?.entry_id;
      if (targetEntryId) {
        payload.config_entry = targetEntryId;
      } else if (this._config?.entity) {
        payload.entity_id = this._config.entity;
      }

      const res = await this._hass.callWS(payload);
      this._data = res;
      this._error = null;
      if (
        this._selectedSlotIdx !== null &&
        (!this._getDaySlots()[this._selectedSlotIdx] || this._activePanel)
      ) {
        if (!this._getDaySlots()[this._selectedSlotIdx]) {
          this._selectedSlotIdx = null;
          this._draftSlot = null;
        }
      }
    } catch (err) {
      this._error = err?.message || String(err || "Error loading schedule");
    } finally {
      this._loading = false;
      this._fetchPending = false;
      this._render();
    }
  }

  _showToast(msg) {
    this._toast = msg;
    if (this._toastTimer) clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toast = null;
      this._render();
    }, 2200);
  }

  _getLang() {
    return this._data?.language || this._hass?.language || "de";
  }

  _t() {
    return getTexts(this._getLang());
  }

  _getPresetLabel(preset) {
    const labels = this._data?.preset_labels || {};
    if (labels[preset]) return labels[preset];
    const lower = String(preset || "").toLowerCase();
    return labels[lower] || preset || "Eco";
  }

  _getPresetTemp(preset) {
    const temps = this._data?.preset_temperatures || {};
    if (temps[preset] !== undefined) return temps[preset];
    const lower = String(preset || "").toLowerCase();
    return temps[lower];
  }

  _getActiveProfileName() {
    return this._data?.active_profile || "Standard";
  }

  _getDaySlots(dayKey = this._selectedDay) {
    const prof = this._getActiveProfileName();
    const allProfiles = this._data?.profiles || {};
    const schedule = allProfiles[prof] || {};
    const list = schedule[dayKey];
    return Array.isArray(list) ? list : [];
  }

  _getLiveStatus() {
    const d = this._data || {};
    const st = this._hass?.states || {};
    const clSt = d.climate_entity ? st[d.climate_entity] : null;
    const swSt = d.automation_switch_entity_id ? st[d.automation_switch_entity_id] : null;
    const schSt = d.schedule_entity_id ? st[d.schedule_entity_id] : null;

    const automationOn = swSt ? swSt.state === "on" : Boolean(d.automation_enabled);
    const curTemp = clSt?.attributes?.current_temperature ?? d.current_temperature;
    const tgtTemp = d.target_temperature ?? clSt?.attributes?.temperature;
    const activePreset = (schSt && !["unknown", "unavailable"].includes(schSt.state)) ? schSt.state : d.active_preset;
    const preheating = Boolean(d.preheat?.is_preheating);
    const coolingDown = Boolean(d.cooldown?.is_cooling_down);
    const hvacAction = clSt?.attributes?.hvac_action ?? d.hvac_action;

    return {
      automationOn,
      curTemp,
      tgtTemp,
      activePreset,
      preheating,
      coolingDown,
      hvacAction,
    };
  }

  async _saveDaySlots(dayKey, slots) {
    if (!this._hass || !this._data) return false;
    let ok = false;
    try {
      const res = await this._hass.callWS({
        type: `${DOMAIN}/save_day_slots`,
        entry_id: this._data.entry_id,
        profile: this._getActiveProfileName(),
        day: dayKey,
        slots,
      });
      this._data = res;
      this._error = null;
      this._showToast(this._t().saved);
      ok = true;
    } catch (err) {
      this._error = err?.message || "Save failed";
    }
    this._render();
    return ok;
  }

  async _handleToggleAuto() {
    if (!this._hass || !this._data?.automation_switch_entity_id) return;
    const { automationOn } = this._getLiveStatus();
    await this._hass.callService("switch", automationOn ? "turn_off" : "turn_on", {
      entity_id: this._data.automation_switch_entity_id,
    });
    setTimeout(() => this._fetchSchedule(false), 250);
  }

  async _handleSwitchProfile(profileName) {
    if (!this._hass || !this._data) return;
    try {
      const res = await this._hass.callWS({
        type: `${DOMAIN}/manage_profile`,
        entry_id: this._data.entry_id,
        action: "switch",
        profile: profileName,
      });
      this._data = res;
      this._selectedSlotIdx = null;
      this._draftSlot = null;
      this._showToast(this._t().saved);
    } catch (err) {
      this._error = err?.message || "Profile switch failed";
    }
    this._render();
  }

  async _handleCopyDaySubmit() {
    if (!this._hass || !this._data || this._copyTargets.size === 0) return;
    try {
      const res = await this._hass.callWS({
        type: `${DOMAIN}/copy_day_slots`,
        entry_id: this._data.entry_id,
        profile: this._getActiveProfileName(),
        source_day: this._selectedDay,
        target_days: Array.from(this._copyTargets),
      });
      this._data = res;
      this._activePanel = null;
      this._copyTargets.clear();
      this._showToast(this._t().saved);
    } catch (err) {
      this._error = err?.message || "Copy failed";
    }
    this._render();
  }

  async _handleStartOverride() {
    if (!this._hass || !this._data) return;
    try {
      await this._hass.callService(DOMAIN, "set_override", {
        entry_id: this._data.entry_id,
        preset: this._overridePreset,
        duration: { minutes: Number(this._overrideDurationMin) || 60 },
      });
      this._activePanel = null;
      setTimeout(() => this._fetchSchedule(false), 200);
    } catch (err) {
      this._error = err?.message || "Override failed";
      this._render();
    }
  }

  async _handleCancelOverride(overrideId) {
    if (!this._hass || !this._data) return;
    try {
      const data = { entry_id: this._data.entry_id };
      if (overrideId) data.override_id = overrideId;
      await this._hass.callService(DOMAIN, "remove_override", data);
      setTimeout(() => this._fetchSchedule(false), 200);
    } catch (err) {
      this._error = err?.message || "Remove override failed";
      this._render();
    }
  }

  async _handleProfileAction(action, payload) {
    if (!this._hass || !this._data) return;
    try {
      const res = await this._hass.callWS({
        type: `${DOMAIN}/manage_profile`,
        entry_id: this._data.entry_id,
        action,
        ...payload,
      });
      this._data = res;
      this._activePanel = null;
      this._selectedSlotIdx = null;
      this._draftSlot = null;
      this._showToast(this._t().saved);
    } catch (err) {
      this._error = err?.message || "Profile update failed";
    }
    this._render();
  }

  _selectSlot(idx) {
    const slots = this._getDaySlots();
    if (idx === null || idx < 0 || idx >= slots.length) {
      this._selectedSlotIdx = null;
      this._draftSlot = null;
    } else {
      const s = slots[idx];
      this._selectedSlotIdx = idx;
      this._draftSlot = {
        from: String(s.from || "08:00:00").slice(0, 5),
        to: String(s.to || "12:00:00").slice(0, 5),
        preset: s.preset || "comfort",
        preheat: s.preheat !== false,
        cooldown: s.cooldown !== false,
      };
    }
    this._render();
  }

  async _addNewSlotAt(startMin, endMin) {
    const slots = this._getDaySlots().map((s) => ({ ...s }));
    const presets = this._data?.supported_presets || DEFAULT_PRESETS;
    const defaultNewPreset = presets.includes("comfort")
      ? "comfort"
      : presets.find((p) => p !== "none" && p !== this._data?.default_preset) || presets[0] || "comfort";

    const newSlot = {
      from: formatMinutes(startMin, true),
      to: formatMinutes(endMin, true),
      preset: defaultNewPreset,
      preheat: true,
      cooldown: true,
    };
    slots.push(newSlot);
    slots.sort((a, b) => String(a.from).localeCompare(String(b.from)));
    await this._saveDaySlots(this._selectedDay, slots);
    const newIdx = this._getDaySlots().findIndex(
      (s) => s.from === newSlot.from && s.to === newSlot.to && s.preset === newSlot.preset
    );
    this._selectSlot(newIdx >= 0 ? newIdx : 0);
  }

  _onTrackClick(ev) {
    if (this._suppressNextTrackClick) {
      this._suppressNextTrackClick = false;
      return;
    }
    if (this._dragState?.moved) return;
    if (ev.target.closest(".slot-block")) return;
    const track = ev.currentTarget;
    const rect = track.getBoundingClientRect();
    if (!rect.width) return;
    const ratio = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
    const snap = Number(this._config?.snap_minutes) || 15;
    let startMin = snapMinutes(ratio * 1440, snap);
    if (startMin > 1320) startMin = 1320;
    const endMin = Math.min(1440, startMin + 120);
    if (endMin - startMin < 15) return;
    this._addNewSlotAt(startMin, endMin);
  }

  _startDrag(ev, idx, mode) {
    ev.stopPropagation();
    ev.preventDefault();
    const track = this.shadowRoot.querySelector(".timeline-track");
    if (!track) return;
    const rect = track.getBoundingClientRect();
    const slots = this._getDaySlots();
    const slot = slots[idx];
    if (!slot || !rect.width) return;

    const origStart = parseMinutes(slot.from);
    const origEnd = slot.to?.startsWith("23:59") ? 1440 : parseMinutes(slot.to);
    const wasSelected = this._selectedSlotIdx === idx;
    this._selectedSlotIdx = idx;
    this._draftSlot = {
      from: formatMinutes(origStart, false),
      to: formatMinutes(origEnd, false),
      preset: slot.preset,
      preheat: slot.preheat !== false,
      cooldown: slot.cooldown !== false,
    };

    this._dragState = {
      idx,
      mode, // 'left' | 'right' | 'move'
      wasSelected,
      startX: ev.clientX,
      trackWidth: rect.width,
      origStart,
      origEnd,
      curStart: origStart,
      curEnd: origEnd,
      moved: false,
    };

    window.addEventListener("pointermove", this._boundPointerMove);
    window.addEventListener("pointerup", this._boundPointerUp);
    window.addEventListener("pointercancel", this._boundPointerUp);
    this._render();
  }

  _onPointerMove(ev) {
    const ds = this._dragState;
    if (!ds) return;
    const dx = ev.clientX - ds.startX;
    if (Math.abs(dx) > 4) ds.moved = true;
    const deltaMin = (dx / ds.trackWidth) * 1440;
    const snap = Number(this._config?.snap_minutes) || 15;
    const minLen = Math.max(15, snap);

    if (ds.mode === "left") {
      let nextStart = snapMinutes(ds.origStart + deltaMin, snap);
      nextStart = Math.max(0, Math.min(ds.origEnd - minLen, nextStart));
      ds.curStart = nextStart;
    } else if (ds.mode === "right") {
      let nextEnd = snapMinutes(ds.origEnd + deltaMin, snap);
      nextEnd = Math.min(1440, Math.max(ds.origStart + minLen, nextEnd));
      ds.curEnd = nextEnd;
    } else if (ds.mode === "move") {
      const duration = ds.origEnd - ds.origStart;
      let nextStart = snapMinutes(ds.origStart + deltaMin, snap);
      nextStart = Math.max(0, Math.min(1440 - duration, nextStart));
      ds.curStart = nextStart;
      ds.curEnd = nextStart + duration;
    }

    if (this._draftSlot) {
      this._draftSlot.from = formatMinutes(ds.curStart, false);
      this._draftSlot.to = formatMinutes(ds.curEnd, false);
    }

    // Lightweight live DOM update during drag for 60fps smoothness
    const block = this.shadowRoot.querySelector(`.slot-block[data-idx="${ds.idx}"]`);
    const tooltip = this.shadowRoot.querySelector(".drag-tooltip");
    if (block) {
      const leftPct = (ds.curStart / 1440) * 100;
      const widthPct = ((ds.curEnd - ds.curStart) / 1440) * 100;
      block.style.left = `${leftPct}%`;
      block.style.width = `${widthPct}%`;
      const timeEl = block.querySelector(".slot-time");
      if (timeEl) {
        timeEl.textContent = `${formatMinutes(ds.curStart, false)} - ${formatMinutes(ds.curEnd, false)}`;
      }
    }
    if (tooltip) {
      const centerPct = ((ds.curStart + ds.curEnd) / 2 / 1440) * 100;
      tooltip.style.left = `${Math.max(8, Math.min(92, centerPct))}%`;
      tooltip.textContent = `${formatMinutes(ds.curStart, false)} – ${formatMinutes(ds.curEnd, false)}`;
      tooltip.style.display = "block";
    }
    const startInput = this.shadowRoot.querySelector("#insp-start");
    const endInput = this.shadowRoot.querySelector("#insp-end");
    if (startInput) startInput.value = formatMinutes(ds.curStart, false).replace("24:00", "23:59");
    if (endInput) endInput.value = formatMinutes(ds.curEnd, false).replace("24:00", "23:59");
  }

  async _onPointerUp() {
    window.removeEventListener("pointermove", this._boundPointerMove);
    window.removeEventListener("pointerup", this._boundPointerUp);
    window.removeEventListener("pointercancel", this._boundPointerUp);

    const ds = this._dragState;
    this._dragState = null;
    if (!ds) return;

    if (ds.moved) {
      this._suppressNextTrackClick = true;
      setTimeout(() => {
        this._suppressNextTrackClick = false;
      }, 150);
    }

    if (!ds.moved) {
      this._suppressNextTrackClick = true;
      setTimeout(() => {
        this._suppressNextTrackClick = false;
      }, 150);
      if (ds.wasSelected) {
        this._selectSlot(null);
      } else {
        this._selectSlot(ds.idx);
      }
      return;
    }

    const slots = this._getDaySlots().map((s) => ({ ...s }));
    if (slots[ds.idx]) {
      slots[ds.idx].from = formatMinutes(ds.curStart, true);
      slots[ds.idx].to = formatMinutes(ds.curEnd, true);
      const updated = slots[ds.idx];
      slots.sort((a, b) => String(a.from).localeCompare(String(b.from)));
      await this._saveDaySlots(this._selectedDay, slots);
      const newIdx = this._getDaySlots().findIndex(
        (s) => s.from === updated.from && s.to === updated.to && s.preset === updated.preset
      );
      this._selectSlot(newIdx >= 0 ? newIdx : 0);
    } else {
      this._render();
    }
  }

  async _handleSaveInspector() {
    if (this._selectedSlotIdx === null || !this._draftSlot) return;
    const fromMin = parseMinutes(this._draftSlot.from);
    const toMin = this._draftSlot.to === "23:59" || this._draftSlot.to === "24:00" ? 1440 : parseMinutes(this._draftSlot.to);
    if (fromMin >= toMin) {
      this._error = "Startzeit muss vor der Endzeit liegen.";
      this._render();
      return;
    }
    const slots = this._getDaySlots().map((s) => ({ ...s }));
    if (!slots[this._selectedSlotIdx]) return;
    const edited = {
      from: formatMinutes(fromMin, true),
      to: formatMinutes(toMin, true),
      preset: this._draftSlot.preset,
      preheat: Boolean(this._draftSlot.preheat),
      cooldown: Boolean(this._draftSlot.cooldown),
    };
    slots[this._selectedSlotIdx] = edited;
    slots.sort((a, b) => String(a.from).localeCompare(String(b.from)));
    const ok = await this._saveDaySlots(this._selectedDay, slots);
    if (ok) {
      this._selectSlot(null);
    }
  }

  async _handleDeleteInspector() {
    if (this._selectedSlotIdx === null) return;
    const slots = this._getDaySlots().map((s) => ({ ...s }));
    slots.splice(this._selectedSlotIdx, 1);
    this._selectedSlotIdx = null;
    this._draftSlot = null;
    await this._saveDaySlots(this._selectedDay, slots);
  }

  _render() {
    if (!this.shadowRoot) return;
    const t = this._t();

    if (!this._data) {
      this.shadowRoot.innerHTML = `
        <style>${this._getStyles()}</style>
        <ha-card>
          <div class="empty-card">
            ${this._loading ? escapeHtml(t.loading) : escapeHtml(this._error || t.selectRoom)}
          </div>
        </ha-card>
      `;
      return;
    }

    const d = this._data;
    const live = this._getLiveStatus();
    const roomTitle = this._config?.name || d.room_name || "Smart Climate Scheduler";
    const activeProfile = this._getActiveProfileName();
    const profileNames = Object.keys(d.profiles || { Standard: {} });
    const daySlots = this._getDaySlots(this._selectedDay);
    const presets = Array.from(new Set([...(d.supported_presets || DEFAULT_PRESETS), ...DEFAULT_PRESETS]));
    const activeOverrides = Object.entries(d.overrides || {});
    const isToday = this._selectedDay === getTodayKey();
    const nowDt = new Date();
    const nowMin = nowDt.getHours() * 60 + nowDt.getMinutes();
    const nowPct = (nowMin / 1440) * 100;

    const statusParts = [];
    if (live.curTemp !== null && live.curTemp !== undefined) {
      statusParts.push(`${Number(live.curTemp).toFixed(1)} °C`);
    }
    if (live.tgtTemp !== null && live.tgtTemp !== undefined) {
      statusParts.push(`${t.targetTemp} ${Number(live.tgtTemp).toFixed(1)} °C`);
    }
    const presetLabel = this._getPresetLabel(live.activePreset);
    let phaseSuffix = "";
    if (live.preheating) phaseSuffix = ` (${t.preheating})`;
    else if (live.coolingDown) phaseSuffix = ` (${t.coolingDown})`;
    statusParts.push(`${presetLabel}${phaseSuffix}`);

    const basePresetKey = d.default_preset || "eco";
    const basePresetColor = getPresetColor(basePresetKey);
    const basePresetLabel = this._getPresetLabel(basePresetKey);
    const baseTemp = this._getPresetTemp(basePresetKey);
    const baseTempText = baseTemp !== undefined ? ` ${Number(baseTemp).toFixed(1).replace(/\.0$/, "")}°` : "";
    const baseShortText = `${basePresetLabel}${baseTempText}`;
    const baseTooltip = `${t.baseTrack}: ${basePresetLabel}${baseTemp !== undefined ? ` (${Number(baseTemp).toFixed(1)} °C)` : ""}`;

    const gapBlocksHtml = computeGapSegments(daySlots)
      .map((gap) => {
        const leftPct = (gap.startMin / 1440) * 100;
        const widthPct = ((gap.endMin - gap.startMin) / 1440) * 100;
        const gapTimeStr = `${formatMinutes(gap.startMin, false)}–${formatMinutes(gap.endMin, false)}`;
        const showGapText = widthPct >= 11;
        const showGapLabelOnly = !showGapText && widthPct >= 5.5;
        return `
          <div
            class="gap-block"
            style="left:${leftPct}%;width:${widthPct}%;background:${basePresetColor.bg}24;border-color:${basePresetColor.border}42;"
            title="${escapeHtml(`${gapTimeStr} · ${baseTooltip}`)}"
          >
            ${showGapText ? `<span class="gap-label">${escapeHtml(baseShortText)}</span>` : showGapLabelOnly ? `<span class="gap-label">${escapeHtml(basePresetLabel)}</span>` : ""}
          </div>
        `;
      })
      .join("");

    const slotBlocksHtml = daySlots
      .map((slot, idx) => {
        const sMin = parseMinutes(slot.from);
        const eMin = slot.to?.startsWith("23:59") ? 1440 : parseMinutes(slot.to);
        const leftPct = (sMin / 1440) * 100;
        const widthPct = Math.max(1.2, ((eMin - sMin) / 1440) * 100);
        const isSel = idx === this._selectedSlotIdx;
        const col = getPresetColor(slot.preset);
        const pLabel = this._getPresetLabel(slot.preset);
        const timeStr = `${formatMinutes(sMin, false)}-${formatMinutes(eMin, false)}`;
        const showFullText = widthPct >= 9.5;
        const showLabelOnly = !showFullText && widthPct >= 4.5;

        return `
          <div
            class="slot-block ${isSel ? "selected" : ""}"
            data-idx="${idx}"
            style="left:${leftPct}%;width:${widthPct}%;background:${isSel ? col.bg : col.bgMuted};border-color:${isSel ? "#ffffff" : col.border};color:${col.text};"
            title="${escapeHtml(`${timeStr} · ${pLabel}`)}"
          >
            <div class="drag-handle left" data-idx="${idx}" data-handle="left" aria-hidden="true"><span></span></div>
            <div class="slot-content">
              ${showFullText ? `<span class="slot-time tabular">${escapeHtml(timeStr)}</span>` : ""}
              ${(showFullText || showLabelOnly) ? `<span class="slot-label">${escapeHtml(pLabel)}</span>` : ""}
            </div>
            <div class="slot-flags">
              ${slot.preheat !== false ? `<span class="flag-dot preheat" title="${escapeHtml(t.preheatSlot)}">▲</span>` : ""}
              ${slot.cooldown !== false ? `<span class="flag-dot cooldown" title="${escapeHtml(t.cooldownSlot)}">▼</span>` : ""}
            </div>
            <div class="drag-handle right" data-idx="${idx}" data-handle="right" aria-hidden="true"><span></span></div>
          </div>
        `;
      })
      .join("");

    const dayTabsHtml = DAYS.map((dayKey, i) => {
      const count = (d.profiles?.[activeProfile]?.[dayKey] || []).length;
      const active = dayKey === this._selectedDay;
      return `
        <button class="day-tab ${active ? "active" : ""}" data-day="${dayKey}" type="button">
          <span>${escapeHtml(t.daysShort[i])}</span>
          ${count > 0 ? `<span class="day-indicator" title="${count}"></span>` : ""}
        </button>
      `;
    }).join("");

    const inspectorHtml = this._renderInspector(t, presets);
    const panelHtml = this._renderActivePanel(t, presets, profileNames, activeProfile);

    this.shadowRoot.innerHTML = `
      <style>${this._getStyles()}</style>
      <ha-card>
        <div class="card-root">
          <!-- Compact Header -->
          <div class="header">
            <div class="header-left">
              <div class="header-inline">
                <span class="room-title">${escapeHtml(roomTitle)}</span>
                <span class="status-line tabular">
                  ${statusParts.map((p) => `<span>${escapeHtml(p)}</span>`).join('<span class="sep">·</span>')}
                </span>
              </div>
              ${
                activeOverrides.length > 0
                  ? `<div class="override-banner">
                      <span>${escapeHtml(t.overrideActive)}: ${escapeHtml(this._getPresetLabel(activeOverrides[0][1]?.preset))}</span>
                      <button class="btn-inline-cancel" data-cancel-override="${escapeHtml(activeOverrides[0][0])}" type="button">${escapeHtml(t.cancelOverride)}</button>
                    </div>`
                  : ""
              }
            </div>
            <label class="auto-switch" title="${escapeHtml(t.automatic)}">
              <input id="auto-toggle" type="checkbox" ${live.automationOn ? "checked" : ""} />
              <span class="switch-track"><span class="switch-thumb"></span></span>
              <span class="switch-label">${escapeHtml(t.automatic)}</span>
            </label>
          </div>

          <div class="divider"></div>

          <!-- Compact Icon Toolbar -->
          <div class="toolbar">
            <div class="profile-group">
              <select id="profile-select" class="ctrl-select" aria-label="${escapeHtml(t.profile)}">
                ${profileNames
                  .map(
                    (pName) =>
                      `<option value="${escapeHtml(pName)}" ${pName === activeProfile ? "selected" : ""}>${escapeHtml(t.profile)}: ${escapeHtml(pName)}</option>`
                  )
                  .join("")}
              </select>
              <button class="btn-icon ${this._activePanel === "profile" ? "active" : ""}" id="btn-profile-manage" type="button" title="${escapeHtml(t.newProfile)}" aria-label="${escapeHtml(t.newProfile)}">${ICONS.gear}</button>
            </div>

            <div class="action-buttons">
              ${this._toast ? `<span class="toast-msg">${escapeHtml(this._toast)}</span>` : ""}
              <button class="btn-icon ${this._activePanel === "copy" ? "active" : ""}" id="btn-copy-day" type="button" title="${escapeHtml(t.copyDay)}" aria-label="${escapeHtml(t.copyDay)}">${ICONS.copy}</button>
              ${
                this._config?.show_override_bar !== false
                  ? `<button class="btn-icon ${this._activePanel === "override" ? "active" : ""}" id="btn-override" type="button" title="${escapeHtml(t.quickOverride)}" aria-label="${escapeHtml(t.quickOverride)}">${ICONS.bolt}</button>`
                  : ""
              }
              <button class="btn-icon" id="btn-add-slot" type="button" title="${escapeHtml(t.addSlot)}" aria-label="${escapeHtml(t.addSlot)}">${ICONS.plus}</button>
            </div>
          </div>

          ${panelHtml}

          <!-- Weekday Tabs -->
          <div class="day-tabs" role="tablist">
            ${dayTabsHtml}
          </div>

          <!-- Compact 24h Interactive Timeline -->
          <div class="timeline-wrap">
            <div class="timeline-track-shell">
              <div class="drag-tooltip tabular" style="display:none;"></div>
              ${
                isToday
                  ? `<div class="now-marker" style="left:${nowPct}%;">
                      <span class="now-label tabular">${escapeHtml(formatMinutes(nowMin, false))}</span>
                    </div>`
                  : ""
              }
              <div class="timeline-track" role="region" aria-label="24h Timeline">
                ${gapBlocksHtml}
                ${slotBlocksHtml}
              </div>
              <div class="hour-ruler tabular">
                <span>00</span>
                <span>04</span>
                <span>08</span>
                <span>12</span>
                <span>16</span>
                <span>20</span>
                <span>24</span>
              </div>
            </div>
          </div>

          ${this._error ? `<div class="error-banner">${escapeHtml(this._error)}</div>` : ""}

          ${inspectorHtml}
        </div>
      </ha-card>
    `;

    this._bindEvents();
  }

  _renderActivePanel(t, presets, profileNames, activeProfile) {
    if (this._activePanel === "copy") {
      return `
        <div class="popover-panel">
          <div class="popover-title">${escapeHtml(t.copyTitle)}</div>
          <div class="chip-row">
            ${DAYS.map((dKey, i) => {
              const disabled = dKey === this._selectedDay;
              const checked = this._copyTargets.has(dKey);
              return `
                <button
                  type="button"
                  class="day-chip ${checked ? "active" : ""}"
                  data-copy-day="${dKey}"
                  ${disabled ? "disabled" : ""}
                >${escapeHtml(t.daysShort[i])}</button>
              `;
            }).join("")}
            <button type="button" class="day-chip quick" id="copy-workdays">${escapeHtml(t.workdays)}</button>
            <button type="button" class="day-chip quick" id="copy-weekend">${escapeHtml(t.weekend)}</button>
            <button type="button" class="day-chip quick" id="copy-all">${escapeHtml(t.allDays)}</button>
          </div>
          <div class="popover-actions">
            <button type="button" class="btn-outline" id="panel-cancel">${escapeHtml(t.cancel)}</button>
            <button type="button" class="btn-primary" id="copy-submit" ${this._copyTargets.size === 0 ? "disabled" : ""}>${escapeHtml(t.applyCopy)}</button>
          </div>
        </div>
      `;
    }

    if (this._activePanel === "override") {
      return `
        <div class="popover-panel">
          <div class="popover-title">${escapeHtml(t.overrideTitle)}</div>
          <div class="override-controls">
            <select id="ov-preset" class="ctrl-select">
              ${presets
                .filter((p) => p !== "none")
                .map((p) => `<option value="${escapeHtml(p)}" ${p === this._overridePreset ? "selected" : ""}>${escapeHtml(this._getPresetLabel(p))}</option>`)
                .join("")}
            </select>
            <div class="chip-row">
              ${[30, 60, 120, 240]
                .map(
                  (mins) =>
                    `<button type="button" class="day-chip ${Number(this._overrideDurationMin) === mins ? "active" : ""}" data-ov-min="${mins}">${mins >= 60 ? `${mins / 60}h` : `${mins}m`}</button>`
                )
                .join("")}
              <input id="ov-custom-min" class="ctrl-input tabular" type="number" min="5" max="720" step="5" value="${Number(this._overrideDurationMin) || 60}" />
              <span class="unit-label">${escapeHtml(t.minutes)}</span>
            </div>
            <div class="popover-actions">
              <button type="button" class="btn-outline" id="panel-cancel">${escapeHtml(t.cancel)}</button>
              <button type="button" class="btn-primary" id="ov-submit">${escapeHtml(t.startOverride)}</button>
            </div>
          </div>
        </div>
      `;
    }

    if (this._activePanel === "profile") {
      return `
        <div class="popover-panel">
          <div class="popover-title">${escapeHtml(t.newProfile)} / ${escapeHtml(t.renameProfile)}</div>
          <div class="profile-manage-row">
            <input id="prof-new-name" class="ctrl-input wide" type="text" placeholder="${escapeHtml(t.profileName)}" value="" />
            <button type="button" class="btn-primary" id="prof-create">${escapeHtml(t.createProfile)}</button>
            <button type="button" class="btn-outline" id="prof-rename">${escapeHtml(t.renameProfile)}</button>
            ${
              profileNames.length > 1
                ? `<button type="button" class="btn-danger" id="prof-delete">${escapeHtml(t.deleteProfile)}</button>`
                : ""
            }
            <button type="button" class="btn-outline" id="panel-cancel">${escapeHtml(t.cancel)}</button>
          </div>
        </div>
      `;
    }

    return "";
  }

  _renderInspector(t, presets) {
    if (this._selectedSlotIdx !== null && this._draftSlot) {
      const ds = this._draftSlot;
      const startVal = ds.from === "24:00" ? "23:59" : ds.from;
      const endVal = ds.to === "24:00" ? "23:59" : ds.to;
      return `
        <div class="divider"></div>
        <div class="inspector">
          <div class="insp-fields">
            <label class="insp-field">
              <span>${escapeHtml(t.start)}</span>
              <input id="insp-start" class="ctrl-input tabular" type="time" value="${escapeHtml(startVal)}" />
            </label>
            <label class="insp-field">
              <span>${escapeHtml(t.end)}</span>
              <input id="insp-end" class="ctrl-input tabular" type="time" value="${escapeHtml(endVal)}" />
            </label>
            <label class="insp-field">
              <span>${escapeHtml(t.preset)}</span>
              <select id="insp-preset" class="ctrl-select">
                ${presets
                  .map((p) => {
                    const pTemp = this._getPresetTemp(p);
                    const label = `${this._getPresetLabel(p)}${pTemp !== undefined ? ` (${Number(pTemp).toFixed(1)} °C)` : ""}`;
                    return `<option value="${escapeHtml(p)}" ${p === ds.preset ? "selected" : ""}>${escapeHtml(label)}</option>`;
                  })
                  .join("")}
              </select>
            </label>
          </div>

          <div class="insp-flags">
            <label class="insp-check">
              <input id="insp-preheat" type="checkbox" ${ds.preheat ? "checked" : ""} />
              <span>${escapeHtml(t.preheatSlot)}</span>
            </label>
            <label class="insp-check">
              <input id="insp-cooldown" type="checkbox" ${ds.cooldown ? "checked" : ""} />
              <span>${escapeHtml(t.cooldownSlot)}</span>
            </label>
          </div>

          <div class="insp-actions">
            <button id="insp-delete" class="btn-outline danger" type="button">${escapeHtml(t.delete)}</button>
            <button id="insp-save" class="btn-primary" type="button">${escapeHtml(t.save)}</button>
          </div>
        </div>
      `;
    }

    return "";
  }

  _bindEvents() {
    const root = this.shadowRoot;
    if (!root) return;

    root.querySelector("#auto-toggle")?.addEventListener("change", () => this._handleToggleAuto());

    root.querySelector("#profile-select")?.addEventListener("change", (ev) => {
      this._handleSwitchProfile(ev.target.value);
    });

    root.querySelector("#btn-profile-manage")?.addEventListener("click", () => {
      this._activePanel = this._activePanel === "profile" ? null : "profile";
      this._render();
    });

    root.querySelector("#btn-copy-day")?.addEventListener("click", () => {
      this._copyTargets.clear();
      this._activePanel = this._activePanel === "copy" ? null : "copy";
      this._render();
    });

    root.querySelector("#btn-override")?.addEventListener("click", () => {
      this._activePanel = this._activePanel === "override" ? null : "override";
      this._render();
    });

    root.querySelector("#btn-add-slot")?.addEventListener("click", () => {
      const existing = this._getDaySlots();
      let startMin = 360;
      if (existing.length > 0) {
        const lastEnd = parseMinutes(existing[existing.length - 1].to);
        if (lastEnd < 1380) startMin = Math.min(1320, lastEnd);
      }
      this._addNewSlotAt(startMin, Math.min(1440, startMin + 120));
    });

    root.querySelectorAll("[data-cancel-override]").forEach((btn) => {
      btn.addEventListener("click", () => this._handleCancelOverride(btn.dataset.cancelOverride));
    });

    root.querySelectorAll(".day-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._selectedDay = btn.dataset.day;
        this._selectedSlotIdx = null;
        this._draftSlot = null;
        this._render();
      });
    });

    root.querySelector(".timeline-track")?.addEventListener("click", (ev) => this._onTrackClick(ev));

    root.querySelectorAll(".slot-block").forEach((block) => {
      const idx = parseInt(block.dataset.idx, 10);
      block.addEventListener("pointerdown", (ev) => {
        const handleEl = ev.target.closest("[data-handle]");
        const mode = handleEl ? handleEl.dataset.handle : "move";
        this._startDrag(ev, idx, mode);
      });
    });

    root.querySelectorAll("[data-select-slot]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._selectSlot(parseInt(btn.dataset.selectSlot, 10));
      });
    });

    // Inspector fields
    root.querySelector("#insp-start")?.addEventListener("change", (ev) => {
      if (this._draftSlot) this._draftSlot.from = ev.target.value;
    });
    root.querySelector("#insp-end")?.addEventListener("change", (ev) => {
      if (this._draftSlot) this._draftSlot.to = ev.target.value;
    });
    root.querySelector("#insp-preset")?.addEventListener("change", (ev) => {
      if (this._draftSlot) this._draftSlot.preset = ev.target.value;
    });
    root.querySelector("#insp-preheat")?.addEventListener("change", (ev) => {
      if (this._draftSlot) this._draftSlot.preheat = ev.target.checked;
    });
    root.querySelector("#insp-cooldown")?.addEventListener("change", (ev) => {
      if (this._draftSlot) this._draftSlot.cooldown = ev.target.checked;
    });
    root.querySelector("#insp-save")?.addEventListener("click", () => this._handleSaveInspector());
    root.querySelector("#insp-delete")?.addEventListener("click", () => this._handleDeleteInspector());

    // Copy panel
    root.querySelector("#panel-cancel")?.addEventListener("click", () => {
      this._activePanel = null;
      this._render();
    });
    root.querySelectorAll("[data-copy-day]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const day = btn.dataset.copyDay;
        if (this._copyTargets.has(day)) this._copyTargets.delete(day);
        else this._copyTargets.add(day);
        this._render();
      });
    });
    root.querySelector("#copy-workdays")?.addEventListener("click", () => {
      this._copyTargets = new Set(DAYS.slice(0, 5).filter((d) => d !== this._selectedDay));
      this._render();
    });
    root.querySelector("#copy-weekend")?.addEventListener("click", () => {
      this._copyTargets = new Set(DAYS.slice(5, 7).filter((d) => d !== this._selectedDay));
      this._render();
    });
    root.querySelector("#copy-all")?.addEventListener("click", () => {
      this._copyTargets = new Set(DAYS.filter((d) => d !== this._selectedDay));
      this._render();
    });
    root.querySelector("#copy-submit")?.addEventListener("click", () => this._handleCopyDaySubmit());

    // Override panel
    root.querySelector("#ov-preset")?.addEventListener("change", (ev) => {
      this._overridePreset = ev.target.value;
    });
    root.querySelectorAll("[data-ov-min]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._overrideDurationMin = parseInt(btn.dataset.ovMin, 10);
        this._render();
      });
    });
    root.querySelector("#ov-custom-min")?.addEventListener("input", (ev) => {
      this._overrideDurationMin = parseInt(ev.target.value, 10) || 60;
    });
    root.querySelector("#ov-submit")?.addEventListener("click", () => this._handleStartOverride());

    // Profile panel
    root.querySelector("#prof-create")?.addEventListener("click", () => {
      const name = root.querySelector("#prof-new-name")?.value?.trim();
      if (name) {
        this._handleProfileAction("create", {
          new_name: name,
          source_profile: this._getActiveProfileName(),
        });
      }
    });
    root.querySelector("#prof-rename")?.addEventListener("click", () => {
      const name = root.querySelector("#prof-new-name")?.value?.trim();
      if (name) {
        this._handleProfileAction("rename", {
          profile: this._getActiveProfileName(),
          new_name: name,
        });
      }
    });
    root.querySelector("#prof-delete")?.addEventListener("click", () => {
      this._handleProfileAction("delete", {
        profile: this._getActiveProfileName(),
      });
    });
  }

  _getStyles() {
    return `
      :host {
        display: block;
        --scs-accent: #f59e0b;
        --scs-accent-hover: #d97706;
        --scs-bg: var(--card-background-color, #1c212b);
        --scs-surface: var(--secondary-background-color, rgba(255, 255, 255, 0.04));
        --scs-border: var(--divider-color, rgba(255, 255, 255, 0.1));
        --scs-text: var(--primary-text-color, #f1f5f9);
        --scs-muted: var(--secondary-text-color, #94a3b8);
        --scs-danger: #ef4444;
      }
      ha-card {
        overflow: hidden;
      }
      .card-root {
        padding: 10px 12px;
        color: var(--scs-text);
        font-family: var(--ha-font-family-body, system-ui, -apple-system, sans-serif);
        display: flex;
        flex-direction: column;
        gap: 7px;
      }
      .tabular {
        font-variant-numeric: tabular-nums;
      }
      .divider {
        height: 1px;
        background: var(--scs-border);
        margin: 0 -12px;
      }
      .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
      .header-left {
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .header-inline {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 4px 8px;
        min-width: 0;
      }
      .room-title {
        font-size: 1rem;
        font-weight: 600;
        line-height: 1.2;
        color: var(--scs-text);
        white-space: nowrap;
      }
      .status-line {
        font-size: 0.78rem;
        color: var(--scs-muted);
        display: inline-flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 4px;
      }
      .sep {
        opacity: 0.55;
      }
      .override-banner {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.74rem;
        color: #fbbf24;
        font-weight: 500;
      }
      .btn-inline-cancel {
        background: transparent;
        border: 1px solid rgba(251, 191, 36, 0.45);
        color: #fbbf24;
        border-radius: 5px;
        padding: 1px 6px;
        font-size: 0.7rem;
        cursor: pointer;
      }
      .auto-switch {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        cursor: pointer;
        user-select: none;
        flex-shrink: 0;
      }
      .auto-switch input {
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
      }
      .switch-track {
        width: 36px;
        height: 20px;
        border-radius: 999px;
        background: var(--scs-border);
        position: relative;
        transition: background 150ms ease;
      }
      .auto-switch input:checked + .switch-track {
        background: var(--scs-accent);
      }
      .switch-thumb {
        position: absolute;
        top: 2px;
        left: 2px;
        width: 16px;
        height: 16px;
        border-radius: 50%;
        background: #ffffff;
        transition: transform 150ms ease;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
      }
      .auto-switch input:checked + .switch-track .switch-thumb {
        transform: translateX(16px);
      }
      .switch-label {
        font-size: 0.78rem;
        font-weight: 500;
      }
      .toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
      }
      .profile-group,
      .action-buttons {
        display: flex;
        align-items: center;
        gap: 5px;
      }
      .profile-group {
        min-width: 0;
        flex: 1;
      }
      .ctrl-select,
      .ctrl-input {
        background: var(--scs-surface);
        color: var(--scs-text);
        border: 1px solid var(--scs-border);
        border-radius: 7px;
        padding: 3px 8px;
        font-size: 0.78rem;
        font-family: inherit;
        min-height: 30px;
        box-sizing: border-box;
        max-width: 100%;
      }
      .ctrl-input.wide {
        flex: 1;
        min-width: 120px;
      }
      .btn-outline,
      .btn-primary,
      .btn-danger,
      .btn-icon {
        border-radius: 7px;
        padding: 4px 10px;
        font-size: 0.78rem;
        font-weight: 500;
        cursor: pointer;
        min-height: 30px;
        white-space: nowrap;
        transition: background 140ms ease, border-color 140ms ease, opacity 140ms ease;
      }
      .btn-icon {
        width: 30px;
        height: 30px;
        padding: 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: var(--scs-surface);
        color: var(--scs-muted);
        border: 1px solid var(--scs-border);
        flex-shrink: 0;
      }
      .btn-icon:hover {
        color: var(--scs-text);
        border-color: var(--scs-accent);
      }
      .btn-outline {
        background: var(--scs-surface);
        color: var(--scs-text);
        border: 1px solid var(--scs-border);
      }
      .btn-outline:hover {
        border-color: var(--scs-accent);
      }
      .btn-outline.active,
      .btn-icon.active {
        border-color: var(--scs-accent);
        background: rgba(245, 158, 11, 0.14);
        color: var(--scs-accent);
      }
      .btn-outline.danger {
        color: var(--scs-danger);
      }
      .btn-outline.danger:hover {
        border-color: var(--scs-danger);
        background: rgba(239, 68, 68, 0.12);
      }
      .btn-primary {
        background: var(--scs-accent);
        color: #111827;
        border: 1px solid var(--scs-accent);
        font-weight: 600;
      }
      .btn-primary:hover:not(:disabled) {
        background: var(--scs-accent-hover);
      }
      .btn-primary:disabled {
        opacity: 0.45;
        cursor: not-allowed;
      }
      .btn-danger {
        background: rgba(239, 68, 68, 0.14);
        color: var(--scs-danger);
        border: 1px solid rgba(239, 68, 68, 0.4);
      }
      .day-tabs {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: 2px;
        background: var(--scs-surface);
        padding: 2px;
        border-radius: 8px;
        border: 1px solid var(--scs-border);
      }
      .day-tab {
        position: relative;
        background: transparent;
        color: var(--scs-muted);
        border: 1px solid transparent;
        border-radius: 6px;
        min-height: 27px;
        font-size: 0.76rem;
        font-weight: 500;
        cursor: pointer;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 1px;
        transition: all 140ms ease;
      }
      .day-tab:hover {
        color: var(--scs-text);
      }
      .day-tab.active {
        background: rgba(245, 158, 11, 0.18);
        border-color: rgba(245, 158, 11, 0.55);
        color: var(--scs-accent);
        font-weight: 600;
      }
      .day-indicator {
        width: 10px;
        height: 2px;
        border-radius: 2px;
        background: currentColor;
        opacity: 0.65;
      }
      .timeline-wrap {
        display: flex;
        flex-direction: column;
        padding-top: 12px;
      }
      .timeline-track-shell {
        position: relative;
      }
      .drag-tooltip {
        position: absolute;
        top: -22px;
        transform: translateX(-50%);
        background: #0f172a;
        color: #f8fafc;
        border: 1px solid rgba(245, 158, 11, 0.6);
        border-radius: 5px;
        padding: 1px 6px;
        font-size: 0.7rem;
        font-weight: 600;
        pointer-events: none;
        z-index: 20;
        white-space: nowrap;
      }
      .now-marker {
        position: absolute;
        top: -2px;
        bottom: 16px;
        width: 2px;
        background: #f8fafc;
        pointer-events: none;
        z-index: 10;
        box-shadow: 0 0 5px rgba(255, 255, 255, 0.5);
      }
      .now-label {
        position: absolute;
        top: -14px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 0.68rem;
        font-weight: 600;
        color: var(--scs-text);
        white-space: nowrap;
      }
      .timeline-track {
        position: relative;
        height: 38px;
        border-radius: 8px;
        background: rgba(148, 163, 184, 0.12);
        border: 1px solid var(--scs-border);
        overflow: hidden;
        cursor: crosshair;
        touch-action: pan-y;
      }
      .gap-block {
        position: absolute;
        top: 3px;
        bottom: 3px;
        border-radius: 6px;
        border: 1px dashed transparent;
        box-sizing: border-box;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 4px;
        overflow: hidden;
        cursor: crosshair;
        user-select: none;
        z-index: 2;
      }
      .gap-label {
        font-size: 0.68rem;
        font-weight: 500;
        color: var(--scs-muted);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        pointer-events: none;
      }
      .slot-block {
        position: absolute;
        top: 3px;
        bottom: 3px;
        border-radius: 6px;
        border: 1.5px solid transparent;
        box-sizing: border-box;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 6px;
        cursor: grab;
        user-select: none;
        touch-action: none;
        z-index: 5;
        transition: box-shadow 120ms ease;
      }
      .slot-block:active {
        cursor: grabbing;
      }
      .slot-block.selected {
        z-index: 8;
        box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.35);
      }
      .slot-content {
        display: flex;
        flex-direction: column;
        min-width: 0;
        overflow: hidden;
        pointer-events: none;
        line-height: 1.08;
      }
      .slot-time {
        font-size: 0.65rem;
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .slot-label {
        font-size: 0.7rem;
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .slot-flags {
        display: flex;
        gap: 1px;
        font-size: 0.58rem;
        opacity: 0.85;
        pointer-events: none;
      }
      .drag-handle {
        position: absolute;
        top: -2px;
        bottom: -2px;
        width: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: ew-resize;
        touch-action: none;
        z-index: 9;
      }
      .drag-handle.left {
        left: -4px;
      }
      .drag-handle.right {
        right: -4px;
      }
      .drag-handle span {
        width: 4px;
        height: 22px;
        border-radius: 3px;
        background: rgba(255, 255, 255, 0.82);
        opacity: 0;
        transition: opacity 120ms ease;
      }
      .slot-block.selected .drag-handle span,
      .slot-block:hover .drag-handle span {
        opacity: 1;
      }
      .hour-ruler {
        display: flex;
        justify-content: space-between;
        font-size: 0.68rem;
        color: var(--scs-muted);
        margin-top: 2px;
        padding: 0 2px;
      }
      .toast-msg {
        color: #10b981;
        font-size: 0.72rem;
        font-weight: 600;
        white-space: nowrap;
        margin-right: 2px;
      }
      .error-banner {
        font-size: 0.76rem;
        color: var(--scs-danger);
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.35);
        border-radius: 7px;
        padding: 6px 8px;
      }
      .popover-panel {
        background: var(--scs-surface);
        border: 1px solid var(--scs-border);
        border-radius: 8px;
        padding: 8px 10px;
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .popover-title {
        font-size: 0.78rem;
        font-weight: 600;
      }
      .chip-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 5px;
      }
      .day-chip {
        background: transparent;
        color: var(--scs-text);
        border: 1px solid var(--scs-border);
        border-radius: 6px;
        padding: 3px 8px;
        font-size: 0.75rem;
        cursor: pointer;
      }
      .day-chip.active {
        background: rgba(245, 158, 11, 0.2);
        border-color: var(--scs-accent);
        color: var(--scs-accent);
        font-weight: 600;
      }
      .day-chip:disabled {
        opacity: 0.35;
        cursor: not-allowed;
      }
      .popover-actions {
        display: flex;
        justify-content: flex-end;
        gap: 6px;
      }
      .override-controls,
      .profile-manage-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
      }
      .unit-label {
        font-size: 0.75rem;
        color: var(--scs-muted);
      }
      .inspector {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 6px 10px;
      }
      .insp-fields {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
      }
      .insp-field {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.76rem;
        color: var(--scs-muted);
      }
      .insp-flags {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
      }
      .insp-check {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.76rem;
        cursor: pointer;
      }
      .insp-check input {
        accent-color: var(--scs-accent);
        width: 14px;
        height: 14px;
        cursor: pointer;
      }
      .insp-actions {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-left: auto;
      }
      .empty-card {
        padding: 18px;
        text-align: center;
        color: var(--scs-muted);
        font-size: 0.85rem;
      }
    `;
  }
}

class SmartClimateSchedulerCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._rooms = [];
  }

  setConfig(config) {
    this._config = {
      snap_minutes: 15,
      show_override_bar: true,
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._loadRooms();
  }

  async _loadRooms() {
    if (!this._hass) return;
    try {
      const res = await this._hass.callWS({ type: `${DOMAIN}/list_entries` });
      if (Array.isArray(res?.entries)) {
        this._rooms = res.entries;
      }
    } catch {
      // Fallback: discover via entity registry / states
      const seen = new Set();
      const list = [];
      for (const ent of Object.values(this._hass.entities || {})) {
        if (ent?.platform === DOMAIN && ent?.config_entry_id && !seen.has(ent.config_entry_id)) {
          seen.add(ent.config_entry_id);
          const st = ent.entity_id ? this._hass.states?.[ent.entity_id] : null;
          list.push({
            entry_id: ent.config_entry_id,
            config_entry: ent.config_entry_id,
            entity_id: ent.entity_id || "",
            name: st?.attributes?.friendly_name || ent.config_entry_id,
          });
        }
      }
      if (list.length === 0) {
        for (const [eid, st] of Object.entries(this._hass.states || {})) {
          if (eid.startsWith("sensor.") && st?.attributes?.active_slot !== undefined) {
            const ceId = this._hass.entities?.[eid]?.config_entry_id || eid;
            if (!seen.has(ceId)) {
              seen.add(ceId);
              list.push({
                entry_id: ceId,
                config_entry: ceId,
                entity_id: eid,
                name: st.attributes?.friendly_name || eid,
              });
            }
          }
        }
      }
      this._rooms = list;
    }
    this._render();
  }

  _emitChange(updated) {
    const nextConfig = { ...this._config, ...updated };
    Object.keys(nextConfig).forEach((k) => {
      if (nextConfig[k] === undefined) {
        delete nextConfig[k];
      }
    });
    this._config = nextConfig;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      })
    );
  }

  _render() {
    if (!this.shadowRoot) return;
    const t = getTexts(this._hass?.language || "de");
    let entryVal = this._config?.config_entry || this._config?.entry_id || "";
    if (!entryVal && this._config?.entity && this._rooms.length > 0) {
      const matched = this._rooms.find(
        (r) => r.entity_id === this._config.entity || r.climate_entity === this._config.entity
      );
      if (matched) entryVal = matched.entry_id;
    }
    const nameVal = this._config?.name || "";
    const snapVal = Number(this._config?.snap_minutes || 15);
    const showOv = this._config?.show_override_bar !== false;

    this.shadowRoot.innerHTML = `
      <style>
        .ed-root {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding: 8px 0;
          color: var(--primary-text-color, #f1f5f9);
          font-family: var(--ha-font-family-body, sans-serif);
        }
        label {
          display: flex;
          flex-direction: column;
          gap: 4px;
          font-size: 0.85rem;
          font-weight: 500;
        }
        label.inline {
          flex-direction: row;
          align-items: center;
          gap: 8px;
          cursor: pointer;
        }
        select, input[type="text"] {
          padding: 8px 10px;
          border-radius: 8px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.2));
          background: var(--secondary-background-color, rgba(255,255,255,0.05));
          color: var(--primary-text-color, #f1f5f9);
          font-size: 0.9rem;
        }
      </style>
      <div class="ed-root">
        <label>
          <span>${escapeHtml(t.editorEntity)}</span>
          ${
            this._rooms.length > 0
              ? `<select id="ed-config-entry">
                  <option value="">--</option>
                  ${this._rooms
                    .map(
                      (r) =>
                        `<option value="${escapeHtml(r.entry_id)}" ${r.entry_id === entryVal ? "selected" : ""}>${escapeHtml(r.name)}${r.climate_entity ? ` (${escapeHtml(r.climate_entity)})` : ""}</option>`
                    )
                    .join("")}
                </select>`
              : `<input id="ed-config-entry" type="text" value="${escapeHtml(entryVal)}" placeholder="config_entry_id" />`
          }
        </label>
        <label>
          <span>${escapeHtml(t.editorName)}</span>
          <input id="ed-name" type="text" value="${escapeHtml(nameVal)}" />
        </label>
        <label>
          <span>${escapeHtml(t.editorSnap)}</span>
          <select id="ed-snap">
            <option value="5" ${snapVal === 5 ? "selected" : ""}>5 ${escapeHtml(t.minutes)}</option>
            <option value="15" ${snapVal === 15 ? "selected" : ""}>15 ${escapeHtml(t.minutes)}</option>
            <option value="30" ${snapVal === 30 ? "selected" : ""}>30 ${escapeHtml(t.minutes)}</option>
          </select>
        </label>
        <label class="inline">
          <input id="ed-ov" type="checkbox" ${showOv ? "checked" : ""} />
          <span>${escapeHtml(t.editorShowOverride)}</span>
        </label>
      </div>
    `;

    this.shadowRoot.querySelector("#ed-config-entry")?.addEventListener("change", (ev) => {
      const val = ev.target.value.trim();
      this._emitChange({
        config_entry: val || undefined,
        entry_id: undefined,
        entity: undefined,
      });
    });
    this.shadowRoot.querySelector("#ed-name")?.addEventListener("change", (ev) => {
      const val = ev.target.value.trim();
      this._emitChange({ name: val || undefined });
    });
    this.shadowRoot.querySelector("#ed-snap")?.addEventListener("change", (ev) => {
      this._emitChange({ snap_minutes: parseInt(ev.target.value, 10) || 15 });
    });
    this.shadowRoot.querySelector("#ed-ov")?.addEventListener("change", (ev) => {
      this._emitChange({ show_override_bar: ev.target.checked });
    });
  }
}

if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, SmartClimateSchedulerCard);
}
if (!customElements.get(EDITOR_TAG)) {
  customElements.define(EDITOR_TAG, SmartClimateSchedulerCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Smart Climate Scheduler Card",
    description: "Interaktive 24h-Zeitleiste zur Bearbeitung von Heiz-Slots, Profilen & Overrides.",
    preview: true,
  });
}
