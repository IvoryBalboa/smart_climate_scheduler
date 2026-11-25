/**
 * Smart Climate Scheduler Card (v3.2.0)
 * Embedded interactive 24h timeline & multi-room overview Lovelace cards for Home Assistant.
 * Self-contained ES module with Shadow DOM & zero external dependencies.
 */

const CARD_TAG = "smart-climate-scheduler-card";
const EDITOR_TAG = "smart-climate-scheduler-card-editor";
const OVERVIEW_CARD_TAG = "smart-climate-scheduler-overview-card";
const OVERVIEW_EDITOR_TAG = "smart-climate-scheduler-overview-card-editor";
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
    editorShowThermal: "Vorheiz- & Auskühl-Vorschau auf Zeitleiste",
    preheatPreview: "Vorheiz-Vorschau",
    cooldownPreview: "Auskühl-Vorschau",
    nextAction: "Nächste Aktion",
    overviewDefaultTitle: "Heizungs-Übersicht",
    overviewAllRoomsHint: "Keine Auswahl = alle Räume automatisch anzeigen",
    overviewEditorTitle: "Überschrift (optional)",
    overviewEditorRooms: "Räume auswählen (leer = alle Räume)",
    overviewEditorMiniTimeline: "Kompakte 24h-Mini-Zeitleiste anzeigen",
    overviewEditorShowBulk: "Filter- & Sammelaktionen-Leiste anzeigen",
    overviewEditorDefaultFilter: "Standard-Filter",
    overviewEditorDefaultSort: "Standard-Sortierung",
    filterAll: "Alle",
    filterAutoOn: "Automatik An",
    filterHeating: "Heizt / Thermik",
    filterOverride: "Override",
    filterEmpty: "Keine Räume entsprechen dem aktuellen Filter.",
    resetFilter: "Filter zurücksetzen",
    sortName: "Name (A–Z)",
    sortPhase: "Aktive Phase zuerst",
    sortDelta: "Größte Abweichung",
    bulkAutoOn: "Alle An",
    bulkAutoOff: "Alle Aus",
    bulkOverride: "Sammel-Override",
    bulkStopOverrides: "Overrides aus",
    bulkProfile: "Profil (alle)",
    bulkApply: "Auf Räume anwenden",
    heatingActive: "Heizt",
    roomsCount: "Räume",
    noRoomsConfigured: "Keine Smart Climate Scheduler Räume gefunden.",
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
    editorShowThermal: "Show preheat & cooldown preview on timeline",
    preheatPreview: "Preheat preview",
    cooldownPreview: "Cooldown preview",
    nextAction: "Next action",
    overviewDefaultTitle: "Climate Overview",
    overviewAllRoomsHint: "None selected = show all rooms automatically",
    overviewEditorTitle: "Card title (optional)",
    overviewEditorRooms: "Select rooms (empty = all rooms)",
    overviewEditorMiniTimeline: "Show compact 24h mini timeline",
    overviewEditorShowBulk: "Show filter & bulk actions bar",
    overviewEditorDefaultFilter: "Default filter",
    overviewEditorDefaultSort: "Default sort",
    filterAll: "All",
    filterAutoOn: "Auto On",
    filterHeating: "Heating / Thermal",
    filterOverride: "Override",
    filterEmpty: "No rooms match the selected filter.",
    resetFilter: "Reset filter",
    sortName: "Name (A–Z)",
    sortPhase: "Active phase first",
    sortDelta: "Largest delta",
    bulkAutoOn: "All On",
    bulkAutoOff: "All Off",
    bulkOverride: "Bulk override",
    bulkStopOverrides: "Stop overrides",
    bulkProfile: "Profile (all)",
    bulkApply: "Apply to rooms",
    heatingActive: "Heating",
    roomsCount: "rooms",
    noRoomsConfigured: "No Smart Climate Scheduler rooms found.",
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
    editorShowThermal: "Afficher l'aperçu préchauffage / refroidissement",
    preheatPreview: "Aperçu préchauffage",
    cooldownPreview: "Aperçu refroidissement",
    nextAction: "Prochaine action",
    overviewDefaultTitle: "Aperçu chauffage",
    overviewAllRoomsHint: "Aucune sélection = toutes les pièces",
    overviewEditorTitle: "Titre (optionnel)",
    overviewEditorRooms: "Pièces (vide = toutes)",
    overviewEditorMiniTimeline: "Afficher la mini-chronologie 24h",
    overviewEditorShowBulk: "Afficher filtres et actions groupées",
    overviewEditorDefaultFilter: "Filtre par défaut",
    overviewEditorDefaultSort: "Tri par défaut",
    filterAll: "Toutes",
    filterAutoOn: "Auto activé",
    filterHeating: "Chauffe / Thermique",
    filterOverride: "Dérogation",
    filterEmpty: "Aucune pièce ne correspond au filtre.",
    resetFilter: "Réinitialiser",
    sortName: "Nom (A–Z)",
    sortPhase: "Phase active en premier",
    sortDelta: "Plus grand écart",
    bulkAutoOn: "Tout activer",
    bulkAutoOff: "Tout couper",
    bulkOverride: "Dérogation groupée",
    bulkStopOverrides: "Arrêter dérogations",
    bulkProfile: "Profil (toutes)",
    bulkApply: "Appliquer aux pièces",
    heatingActive: "Chauffe",
    roomsCount: "pièces",
    noRoomsConfigured: "Aucune pièce Smart Climate Scheduler trouvée.",
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
    editorShowThermal: "Mostrar vista previa de precalentamiento/enfriamiento",
    preheatPreview: "Vista previa precalentamiento",
    cooldownPreview: "Vista previa enfriamiento",
    nextAction: "Próxima acción",
    overviewDefaultTitle: "Resumen de clima",
    overviewAllRoomsHint: "Sin selección = mostrar todas las habitaciones",
    overviewEditorTitle: "Título (opcional)",
    overviewEditorRooms: "Habitaciones (vacío = todas)",
    overviewEditorMiniTimeline: "Mostrar mini línea temporal 24h",
    overviewEditorShowBulk: "Mostrar barra de filtros y acciones",
    overviewEditorDefaultFilter: "Filtro predeterminado",
    overviewEditorDefaultSort: "Orden predeterminado",
    filterAll: "Todas",
    filterAutoOn: "Auto activo",
    filterHeating: "Calentando / Térmica",
    filterOverride: "Anulación",
    filterEmpty: "Ninguna habitación coincide con el filtro.",
    resetFilter: "Restablecer",
    sortName: "Nombre (A–Z)",
    sortPhase: "Fase activa primero",
    sortDelta: "Mayor diferencia",
    bulkAutoOn: "Activar todo",
    bulkAutoOff: "Apagar todo",
    bulkOverride: "Anulación grupal",
    bulkStopOverrides: "Detener anulaciones",
    bulkProfile: "Perfil (todas)",
    bulkApply: "Aplicar a salas",
    heatingActive: "Calentando",
    roomsCount: "salas",
    noRoomsConfigured: "No se encontraron habitaciones.",
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
    editorShowThermal: "Mostra anteprima preriscaldamento/raffreddamento",
    preheatPreview: "Anteprima preriscaldamento",
    cooldownPreview: "Anteprima raffreddamento",
    nextAction: "Prossima azione",
    overviewDefaultTitle: "Panoramica clima",
    overviewAllRoomsHint: "Nessuna selezione = mostra tutte le stanze",
    overviewEditorTitle: "Titolo (opzionale)",
    overviewEditorRooms: "Stanze (vuoto = tutte)",
    overviewEditorMiniTimeline: "Mostra mini timeline 24h",
    overviewEditorShowBulk: "Mostra filtri e azioni di gruppo",
    overviewEditorDefaultFilter: "Filtro predefinito",
    overviewEditorDefaultSort: "Ordinamento predefinito",
    filterAll: "Tutte",
    filterAutoOn: "Auto attivo",
    filterHeating: "Riscaldamento / Termica",
    filterOverride: "Override",
    filterEmpty: "Nessuna stanza corrisponde al filtro.",
    resetFilter: "Reimposta",
    sortName: "Nome (A–Z)",
    sortPhase: "Fase attiva prima",
    sortDelta: "Differenza maggiore",
    bulkAutoOn: "Attiva tutte",
    bulkAutoOff: "Disattiva tutte",
    bulkOverride: "Override di gruppo",
    bulkStopOverrides: "Ferma override",
    bulkProfile: "Profilo (tutte)",
    bulkApply: "Applica alle stanze",
    heatingActive: "Riscalda",
    roomsCount: "stanze",
    noRoomsConfigured: "Nessuna stanza trovata.",
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
    editorShowThermal: "Toon voorverwarm- & afkoelvoorbeeld",
    preheatPreview: "Voorverwarmvoorbeeld",
    cooldownPreview: "Afkoelvoorbeeld",
    nextAction: "Volgende actie",
    overviewDefaultTitle: "Klimaatoverzicht",
    overviewAllRoomsHint: "Geen selectie = toon alle kamers",
    overviewEditorTitle: "Titel (optioneel)",
    overviewEditorRooms: "Kamers selecteren (leeg = alle)",
    overviewEditorMiniTimeline: "Toon compacte 24u-tijdlijn",
    overviewEditorShowBulk: "Toon filters & groepsacties",
    overviewEditorDefaultFilter: "Standaardfilter",
    overviewEditorDefaultSort: "Standaardsortering",
    filterAll: "Alle",
    filterAutoOn: "Auto Aan",
    filterHeating: "Verwarmt / Thermisch",
    filterOverride: "Override",
    filterEmpty: "Geen kamers komen overeen met het filter.",
    resetFilter: "Reset filter",
    sortName: "Naam (A–Z)",
    sortPhase: "Actieve fase eerst",
    sortDelta: "Grootste afwijking",
    bulkAutoOn: "Alles Aan",
    bulkAutoOff: "Alles Uit",
    bulkOverride: "Groeps-override",
    bulkStopOverrides: "Overrides uit",
    bulkProfile: "Profiel (alle)",
    bulkApply: "Toepassen op kamers",
    heatingActive: "Verwarmt",
    roomsCount: "kamers",
    noRoomsConfigured: "Geen kamers gevonden.",
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
    editorShowThermal: "Pokaż podgląd nagrzewania i ochładzania",
    preheatPreview: "Podgląd nagrzewania",
    cooldownPreview: "Podgląd ochładzania",
    nextAction: "Następna akcja",
    overviewDefaultTitle: "Przegląd klimatu",
    overviewAllRoomsHint: "Brak wyboru = pokaż wszystkie pokoje",
    overviewEditorTitle: "Tytuł (opcjonalnie)",
    overviewEditorRooms: "Pokoje (puste = wszystkie)",
    overviewEditorMiniTimeline: "Pokaż mini oś czasu 24h",
    overviewEditorShowBulk: "Pokaż pasek filtrów i akcji zbiorczych",
    overviewEditorDefaultFilter: "Domyślny filtr",
    overviewEditorDefaultSort: "Domyślne sortowanie",
    filterAll: "Wszystkie",
    filterAutoOn: "Auto Wł.",
    filterHeating: "Grzanie / Termika",
    filterOverride: "Override",
    filterEmpty: "Brak pokoi pasujących do filtra.",
    resetFilter: "Resetuj filtr",
    sortName: "Nazwa (A–Z)",
    sortPhase: "Aktywna faza najpierw",
    sortDelta: "Największa różnica",
    bulkAutoOn: "Wszystkie Wł.",
    bulkAutoOff: "Wszystkie Wył.",
    bulkOverride: "Zbiorczy override",
    bulkStopOverrides: "Zatrzymaj override",
    bulkProfile: "Profil (wszystkie)",
    bulkApply: "Zastosuj do pokoi",
    heatingActive: "Grzeje",
    roomsCount: "pokoi",
    noRoomsConfigured: "Nie znaleziono pokoi.",
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

function getLocalDateKey(offsetDays = 0) {
  const dt = new Date();
  dt.setDate(dt.getDate() + offsetDays);
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const d = String(dt.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function computeThermalPreviewSegments(data, isToday) {
  if (!isToday || !data) return [];
  const todayStr = getLocalDateKey(0);
  const tomorrowStr = getLocalDateKey(1);
  const nextSlot = data.next_slot;
  if (!nextSlot || !nextSlot.from) return [];

  const nextDate = nextSlot.date || todayStr;
  if (nextDate !== todayStr && nextDate !== tomorrowStr) return [];

  const nextFromMin = parseMinutes(nextSlot.from);
  const segments = [];

  const addPhase = (kind, phase, targetPreset) => {
    if (!phase || !(Number(phase.duration_minutes) > 0) || !phase.start_time) return;
    const dur = Number(phase.duration_minutes);
    const sMin = parseMinutes(phase.start_time);
    let drawStart = null;
    let drawEnd = null;
    if (nextDate === todayStr) {
      drawEnd = nextFromMin === 0 ? 1440 : nextFromMin;
      drawStart = Math.max(0, Math.min(drawEnd, sMin));
    } else if (nextDate === tomorrowStr && dur > nextFromMin) {
      drawStart = sMin;
      drawEnd = 1440;
    }
    if (drawStart !== null && drawEnd !== null && drawEnd > drawStart) {
      segments.push({
        kind,
        startMin: drawStart,
        endMin: drawEnd,
        durationMinutes: dur,
        active: Boolean(kind === "preheat" ? phase.is_preheating : phase.is_cooling_down),
        targetPreset: targetPreset || "comfort",
      });
    }
  };

  if (data.preheat && Number(data.preheat.duration_minutes) > 0) {
    addPhase("preheat", data.preheat, nextSlot.preset);
  }
  if (data.cooldown && Number(data.cooldown.duration_minutes) > 0) {
    addPhase("cooldown", data.cooldown, data.cooldown.target_preset || nextSlot.preset);
  }
  return segments;
}

const ICONS = {
  gear: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>',
  copy: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>',
  bolt: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>',
  plus: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>',
  chevron: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>',
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
      show_thermal_preview: true,
    };
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this._config = {
      snap_minutes: 15,
      show_override_bar: true,
      show_thermal_preview: true,
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
    if (!this._hass || !this._data?.entry_id) return;
    const { automationOn } = this._getLiveStatus();
    try {
      const res = await this._hass.callWS({
        type: `${DOMAIN}/set_automation`,
        entry_id: this._data.entry_id,
        enabled: !automationOn,
      });
      if (res && res.entry_id) {
        this._data = res;
      }
      this._error = null;
    } catch (err) {
      this._error = err?.message || "Toggle automation failed";
    }
    this._render();
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

    const showThermal = this._config?.show_thermal_preview !== false;
    const thermalPreviewHtml = showThermal
      ? computeThermalPreviewSegments(d, isToday)
          .map((seg) => {
            const leftPct = (seg.startMin / 1440) * 100;
            const widthPct = Math.max(0.8, ((seg.endMin - seg.startMin) / 1440) * 100);
            const col = getPresetColor(seg.targetPreset);
            const pLabel = this._getPresetLabel(seg.targetPreset);
            const kindLabel = seg.kind === "preheat" ? t.preheatPreview : t.cooldownPreview;
            const timeStr = `${formatMinutes(seg.startMin, false)}–${formatMinutes(seg.endMin, false)}`;
            const marker = seg.kind === "preheat" ? "▲" : "▼";
            return `
              <div
                class="thermal-preview ${seg.kind} ${seg.active ? "active" : ""}"
                style="left:${leftPct}%;width:${widthPct}%;--tp-color:${col.bg};--tp-border:${col.border};"
                title="${escapeHtml(`${kindLabel}: ${timeStr} (${seg.durationMinutes} ${t.minutes} → ${pLabel})`)}"
              >
                ${widthPct >= 2.2 ? `<span class="thermal-preview-badge">${marker}</span>` : ""}
              </div>
            `;
          })
          .join("")
      : "";

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
                ${thermalPreviewHtml}
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
      .thermal-preview {
        position: absolute;
        top: 3px;
        bottom: 3px;
        border-radius: 5px;
        border: 1.5px dashed var(--tp-border, #fbbf24);
        background: repeating-linear-gradient(
          -45deg,
          color-mix(in srgb, var(--tp-color, #f59e0b) 32%, transparent),
          color-mix(in srgb, var(--tp-color, #f59e0b) 32%, transparent) 4px,
          transparent 4px,
          transparent 8px
        );
        box-sizing: border-box;
        display: flex;
        align-items: flex-start;
        justify-content: flex-start;
        padding: 1px 3px;
        pointer-events: none;
        z-index: 6;
        opacity: 0.88;
      }
      .thermal-preview.active {
        opacity: 1;
        box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.45);
      }
      .thermal-preview-badge {
        font-size: 0.56rem;
        line-height: 1;
        color: #ffffff;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8);
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
      show_thermal_preview: true,
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
    const showThermal = this._config?.show_thermal_preview !== false;

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
          <input id="ed-thermal" type="checkbox" ${showThermal ? "checked" : ""} />
          <span>${escapeHtml(t.editorShowThermal)}</span>
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
    this.shadowRoot.querySelector("#ed-thermal")?.addEventListener("change", (ev) => {
      this._emitChange({ show_thermal_preview: ev.target.checked });
    });
    this.shadowRoot.querySelector("#ed-ov")?.addEventListener("change", (ev) => {
      this._emitChange({ show_override_bar: ev.target.checked });
    });
  }
}

class SmartClimateSchedulerOverviewCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._roomsData = [];
    this._loading = false;
    this._error = null;
    this._expandedRoomId = null;
    this._overridePresets = {};
    this._overrideDurations = {};
    this._lastStateSig = null;
    this._fetchPending = false;
    this._refreshTimer = null;
    this._filterMode = "all";
    this._sortMode = "name";
    this._bulkOverrideOpen = false;
    this._bulkOverridePreset = "eco";
    this._bulkOverrideDuration = 60;
    this._bulkPending = false;
  }

  static getConfigElement() {
    return document.createElement(OVERVIEW_EDITOR_TAG);
  }

  static getStubConfig() {
    return {
      title: "",
      rooms: [],
      show_mini_timeline: true,
      show_thermal_preview: true,
      show_override_bar: true,
      show_bulk_actions: true,
      default_filter: "all",
      default_sort: "phase",
    };
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this._config = {
      title: "",
      rooms: [],
      show_mini_timeline: true,
      show_thermal_preview: true,
      show_override_bar: true,
      show_bulk_actions: true,
      default_filter: "all",
      default_sort: "name",
      ...config,
    };
    this._filterMode = this._config.default_filter || "all";
    this._sortMode = this._config.default_sort || "name";
    this._lastStateSig = null;
    if (this._hass) {
      this._fetchAllRooms(true);
    } else {
      this._render();
    }
  }

  getCardSize() {
    return Math.max(2, Math.min(9, 2 + (this._roomsData.length || 2)));
  }

  set hass(hass) {
    const prevHass = this._hass;
    this._hass = hass;
    if (!hass) return;

    if (this._roomsData.length === 0 && !this._fetchPending) {
      this._fetchAllRooms(true);
      return;
    }

    if (this._roomsData.length > 0) {
      const sig = this._roomsData
        .map((d) => {
          const ids = [
            d.schedule_entity_id,
            d.climate_entity,
            d.automation_switch_entity_id,
            d.profile_select_entity_id,
          ].filter(Boolean);
          return ids
            .map((id) => {
              const st = hass.states?.[id];
              if (!st) return `${id}:missing`;
              const attrs = st.attributes || {};
              return `${id}:${st.state}:${attrs.current_temperature}:${attrs.temperature}:${attrs.hvac_action}:${attrs.profile}`;
            })
            .join(",");
        })
        .join("|");

      if (sig !== this._lastStateSig) {
        this._lastStateSig = sig;
        if (prevHass) {
          this._scheduleRefresh();
        } else {
          this._render();
        }
      }
    }
  }

  _scheduleRefresh() {
    if (this._refreshTimer) clearTimeout(this._refreshTimer);
    this._refreshTimer = setTimeout(() => {
      this._refreshTimer = null;
      this._fetchAllRooms(false);
    }, 300);
  }

  async _fetchAllRooms(showLoading = false) {
    if (!this._hass || this._fetchPending) return;
    this._fetchPending = true;
    if (showLoading && this._roomsData.length === 0) {
      this._loading = true;
      this._render();
    }
    try {
      const listRes = await this._hass.callWS({ type: `${DOMAIN}/list_entries` });
      const allEntries = Array.isArray(listRes?.entries) ? listRes.entries : [];
      const configuredIds = Array.isArray(this._config?.rooms)
        ? this._config.rooms.filter(Boolean)
        : [];
      const targetEntries = configuredIds.length > 0
        ? configuredIds
            .map((id) => allEntries.find((e) => e.entry_id === id))
            .filter(Boolean)
        : allEntries;

      const results = await Promise.all(
        targetEntries.map((entry) =>
          this._hass
            .callWS({ type: `${DOMAIN}/get_schedule`, config_entry: entry.entry_id })
            .catch(() => null)
        )
      );
      this._roomsData = results.filter(Boolean);
      this._error = null;
    } catch (err) {
      this._error = err?.message || String(err || "Error loading rooms");
    } finally {
      this._loading = false;
      this._fetchPending = false;
      this._render();
    }
  }

  _getLang() {
    return this._roomsData[0]?.language || this._hass?.language || "de";
  }

  _t() {
    return getTexts(this._getLang());
  }

  _getRoomLive(d) {
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
    const hvacAction = clSt?.attributes?.hvac_action ?? d.hvac_action ?? null;
    const isHeating = hvacAction === "heating";
    const activeOverrides = Object.entries(d.overrides || {});
    const tempDelta =
      curTemp !== null && curTemp !== undefined && tgtTemp !== null && tgtTemp !== undefined
        ? Number(tgtTemp) - Number(curTemp)
        : -999;

    return {
      automationOn,
      curTemp,
      tgtTemp,
      tempDelta,
      activePreset,
      preheating,
      coolingDown,
      hvacAction,
      isHeating,
      activeOverrides,
    };
  }

  _matchesFilter(room, live, filterMode) {
    if (filterMode === "auto_on") return live.automationOn;
    if (filterMode === "heating") return live.isHeating || live.preheating || live.coolingDown;
    if (filterMode === "override") return live.activeOverrides.length > 0;
    return true;
  }

  _getFilteredSortedRooms() {
    const filterMode = this._filterMode || "all";
    const sortMode = this._sortMode || "name";
    const enriched = this._roomsData.map((room) => ({
      room,
      live: this._getRoomLive(room),
    }));

    const filtered = enriched.filter(({ room, live }) => this._matchesFilter(room, live, filterMode));
    const phaseWeight = (live) => {
      if (live.activeOverrides.length > 0) return 5;
      if (live.preheating) return 4;
      if (live.isHeating) return 3;
      if (live.coolingDown) return 2;
      if (live.automationOn) return 1;
      return 0;
    };

    filtered.sort((a, b) => {
      if (sortMode === "phase") {
        const diff = phaseWeight(b.live) - phaseWeight(a.live);
        if (diff !== 0) return diff;
      } else if (sortMode === "temp_delta") {
        const diff = b.live.tempDelta - a.live.tempDelta;
        if (Math.abs(diff) > 0.05) return diff;
      }
      const nameA = String(a.room.room_name || a.room.entry_id || "").toLowerCase();
      const nameB = String(b.room.room_name || b.room.entry_id || "").toLowerCase();
      return nameA.localeCompare(nameB);
    });

    return filtered;
  }

  _getPresetLabel(d, preset) {
    const labels = d?.preset_labels || {};
    if (labels[preset]) return labels[preset];
    const lower = String(preset || "").toLowerCase();
    return labels[lower] || preset || "Eco";
  }

  async _toggleAuto(entryId) {
    const room = this._roomsData.find((r) => r.entry_id === entryId);
    if (!this._hass || !room?.entry_id) return;
    const { automationOn } = this._getRoomLive(room);
    try {
      const updated = await this._hass.callWS({
        type: `${DOMAIN}/set_automation`,
        entry_id: room.entry_id,
        enabled: !automationOn,
      });
      if (updated && updated.entry_id) {
        this._roomsData = this._roomsData.map((r) => (r.entry_id === entryId ? updated : r));
      }
      this._error = null;
    } catch (err) {
      this._error = err?.message || "Toggle automation failed";
    }
    this._render();
    setTimeout(() => this._fetchAllRooms(false), 250);
  }

  async _bulkSetAutomation(turnOn) {
    if (!this._hass || this._bulkPending) return;
    const entryIds = this._getFilteredSortedRooms()
      .map((x) => x.room?.entry_id)
      .filter(Boolean);
    if (entryIds.length === 0) return;

    this._bulkPending = true;
    this._error = null;
    this._render();
    try {
      const res = await this._hass.callWS({
        type: `${DOMAIN}/set_automation`,
        entry_ids: entryIds,
        enabled: Boolean(turnOn),
      });
      if (Array.isArray(res?.rooms)) {
        const updatedMap = new Map(res.rooms.filter(Boolean).map((r) => [r.entry_id, r]));
        this._roomsData = this._roomsData.map((r) => updatedMap.get(r.entry_id) || r);
      }
      setTimeout(() => this._fetchAllRooms(false), 250);
    } catch (err) {
      this._error = err?.message || "Bulk action failed";
    } finally {
      this._bulkPending = false;
      this._render();
    }
  }

  async _bulkStartOverride() {
    if (!this._hass || this._bulkPending) return;
    const visible = this._getFilteredSortedRooms().map((x) => x.room);
    if (visible.length === 0) return;

    const preset = this._bulkOverridePreset || "eco";
    const minutes = Number(this._bulkOverrideDuration || 60);
    this._bulkPending = true;
    this._error = null;
    this._render();
    try {
      await Promise.all(
        visible.map((r) =>
          this._hass.callService(DOMAIN, "set_override", {
            entry_id: r.entry_id,
            preset,
            duration: { minutes },
          })
        )
      );
      this._bulkOverrideOpen = false;
      setTimeout(() => this._fetchAllRooms(false), 300);
    } catch (err) {
      this._error = err?.message || "Bulk override failed";
    } finally {
      this._bulkPending = false;
      this._render();
    }
  }

  async _bulkStopOverrides() {
    if (!this._hass || this._bulkPending) return;
    const visibleWithOverrides = this._getFilteredSortedRooms().filter(({ live }) => live.activeOverrides.length > 0);
    if (visibleWithOverrides.length === 0) return;

    this._bulkPending = true;
    this._error = null;
    this._render();
    try {
      await Promise.all(
        visibleWithOverrides.map(({ room }) =>
          this._hass.callService(DOMAIN, "remove_override", { entry_id: room.entry_id })
        )
      );
      setTimeout(() => this._fetchAllRooms(false), 300);
    } catch (err) {
      this._error = err?.message || "Stop overrides failed";
    } finally {
      this._bulkPending = false;
      this._render();
    }
  }

  async _bulkSwitchProfile(profileName) {
    if (!this._hass || !profileName || this._bulkPending) return;
    const visibleTargets = this._getFilteredSortedRooms()
      .map((x) => x.room)
      .filter((r) => r.profiles && Object.prototype.hasOwnProperty.call(r.profiles, profileName));
    if (visibleTargets.length === 0) return;

    this._bulkPending = true;
    this._error = null;
    this._render();
    try {
      const updatedRooms = await Promise.all(
        visibleTargets.map((r) =>
          this._hass.callWS({
            type: `${DOMAIN}/manage_profile`,
            entry_id: r.entry_id,
            action: "switch",
            profile: profileName,
          })
        )
      );
      const updatedMap = new Map(updatedRooms.filter(Boolean).map((r) => [r.entry_id, r]));
      this._roomsData = this._roomsData.map((r) => updatedMap.get(r.entry_id) || r);
    } catch (err) {
      this._error = err?.message || "Bulk profile switch failed";
    } finally {
      this._bulkPending = false;
      this._render();
    }
  }

  async _switchProfile(entryId, profileName) {
    if (!this._hass) return;
    try {
      const updated = await this._hass.callWS({
        type: `${DOMAIN}/manage_profile`,
        entry_id: entryId,
        action: "switch",
        profile: profileName,
      });
      this._roomsData = this._roomsData.map((r) => (r.entry_id === entryId ? updated : r));
      this._render();
    } catch (err) {
      this._error = err?.message || "Profile switch failed";
      this._render();
    }
  }

  async _startOverride(entryId) {
    if (!this._hass) return;
    const preset = this._overridePresets[entryId] || "boost";
    const minutes = Number(this._overrideDurations[entryId] || 60);
    try {
      await this._hass.callService(DOMAIN, "set_override", {
        entry_id: entryId,
        preset,
        duration: { minutes },
      });
      setTimeout(() => this._fetchAllRooms(false), 250);
    } catch (err) {
      this._error = err?.message || "Override failed";
      this._render();
    }
  }

  async _cancelOverride(entryId, overrideId) {
    if (!this._hass) return;
    try {
      const data = { entry_id: entryId };
      if (overrideId) data.override_id = overrideId;
      await this._hass.callService(DOMAIN, "remove_override", data);
      setTimeout(() => this._fetchAllRooms(false), 250);
    } catch (err) {
      this._error = err?.message || "Remove override failed";
      this._render();
    }
  }

  _renderMiniTimeline(d, t) {
    const todayKey = getTodayKey();
    const activeProfile = d.active_profile || "Standard";
    const daySlots = d.profiles?.[activeProfile]?.[todayKey] || [];
    const baseColor = getPresetColor(d.default_preset || "eco");
    const nowDt = new Date();
    const nowPct = ((nowDt.getHours() * 60 + nowDt.getMinutes()) / 1440) * 100;

    const slotsHtml = daySlots
      .map((slot) => {
        const sMin = parseMinutes(slot.from);
        const eMin = slot.to?.startsWith("23:59") ? 1440 : parseMinutes(slot.to);
        const leftPct = (sMin / 1440) * 100;
        const widthPct = Math.max(1, ((eMin - sMin) / 1440) * 100);
        const col = getPresetColor(slot.preset);
        return `<div class="ov-mini-slot" style="left:${leftPct}%;width:${widthPct}%;background:${col.bg};"></div>`;
      })
      .join("");

    const thermalHtml = this._config?.show_thermal_preview !== false
      ? computeThermalPreviewSegments(d, true)
          .map((seg) => {
            const leftPct = (seg.startMin / 1440) * 100;
            const widthPct = Math.max(0.8, ((seg.endMin - seg.startMin) / 1440) * 100);
            const col = getPresetColor(seg.targetPreset);
            return `<div class="ov-mini-thermal" style="left:${leftPct}%;width:${widthPct}%;--tp-color:${col.bg};--tp-border:${col.border};"></div>`;
          })
          .join("")
      : "";

    return `
      <div class="ov-mini-track" title="${escapeHtml(activeProfile)}">
        <div class="ov-mini-base" style="background:${baseColor.bg}24;"></div>
        ${slotsHtml}
        ${thermalHtml}
        <div class="ov-mini-now" style="left:${nowPct}%;"></div>
      </div>
    `;
  }

  _render() {
    if (!this.shadowRoot) return;
    const t = this._t();

    if (this._loading && this._roomsData.length === 0) {
      this.shadowRoot.innerHTML = `
        <style>${this._getStyles()}</style>
        <ha-card><div class="ov-empty">${escapeHtml(t.loading)}</div></ha-card>
      `;
      return;
    }

    if (this._roomsData.length === 0) {
      this.shadowRoot.innerHTML = `
        <style>${this._getStyles()}</style>
        <ha-card><div class="ov-empty">${escapeHtml(this._error || t.noRoomsConfigured)}</div></ha-card>
      `;
      return;
    }

    const titleText = String(this._config?.title || "").trim();
    const showMini = this._config?.show_mini_timeline !== false;
    const showOv = this._config?.show_override_bar !== false;
    const showBulk = this._config?.show_bulk_actions !== false;
    const filterMode = this._filterMode || "all";
    const sortMode = this._sortMode || "name";

    const allEnriched = this._roomsData.map((room) => ({ room, live: this._getRoomLive(room) }));
    const visibleEntries = this._getFilteredSortedRooms();

    const countAll = allEnriched.length;
    const countAutoOn = allEnriched.filter((x) => x.live.automationOn).length;
    const countHeating = allEnriched.filter((x) => x.live.isHeating || x.live.preheating || x.live.coolingDown).length;
    const countOverride = allEnriched.filter((x) => x.live.activeOverrides.length > 0).length;
    const visibleWithOverrides = visibleEntries.filter((x) => x.live.activeOverrides.length > 0).length;

    const allProfileNames = Array.from(
      new Set(visibleEntries.flatMap(({ room }) => Object.keys(room.profiles || {})))
    );
    const bulkPresets = Array.from(
      new Set([...(this._roomsData[0]?.supported_presets || DEFAULT_PRESETS), ...DEFAULT_PRESETS])
    ).filter((p) => p !== "none");

    const filterChips = [
      { key: "all", label: `${t.filterAll} (${countAll})` },
      { key: "auto_on", label: `${t.filterAutoOn} (${countAutoOn})` },
      { key: "heating", label: `${t.filterHeating} (${countHeating})` },
      { key: "override", label: `${t.filterOverride} (${countOverride})` },
    ];

    const roomsHtml = visibleEntries
      .map(({ room: d, live }) => {
        const expanded = this._expandedRoomId === d.entry_id;
        const presetCol = getPresetColor(live.activePreset);
        const presetLabel = this._getPresetLabel(d, live.activePreset);
        const profileNames = Object.keys(d.profiles || { Standard: {} });
        const activeProfile = d.active_profile || "Standard";
        const presets = Array.from(new Set([...(d.supported_presets || DEFAULT_PRESETS), ...DEFAULT_PRESETS])).filter(
          (p) => p !== "none"
        );
        const selOvPreset = this._overridePresets[d.entry_id] || "boost";
        const selOvDur = Number(this._overrideDurations[d.entry_id] || 60);

        let phaseBadge = "";
        if (live.activeOverrides.length > 0) {
          phaseBadge = `<span class="ov-phase ov-phase-warn">${escapeHtml(t.overrideActive)}</span>`;
        } else if (live.preheating) {
          phaseBadge = `<span class="ov-phase ov-phase-heat">${escapeHtml(t.preheating)}</span>`;
        } else if (live.coolingDown) {
          phaseBadge = `<span class="ov-phase ov-phase-cool">${escapeHtml(t.coolingDown)}</span>`;
        } else if (live.isHeating) {
          phaseBadge = `<span class="ov-phase ov-phase-heat">${escapeHtml(t.heatingActive)}</span>`;
        }

        const tempStr = [
          live.curTemp !== null && live.curTemp !== undefined ? `${Number(live.curTemp).toFixed(1)}°` : null,
          live.tgtTemp !== null && live.tgtTemp !== undefined ? `→ ${Number(live.tgtTemp).toFixed(1)}°` : null,
        ]
          .filter(Boolean)
          .join(" ");

        const nextAct = d.next_action;
        const nextActionLine = nextAct?.action && nextAct?.time
          ? `${t.nextAction}: ${nextAct.action} (${nextAct.time})`
          : "";

        return `
          <div class="ov-room ${expanded ? "expanded" : ""}" data-room-id="${escapeHtml(d.entry_id)}">
            <div class="ov-row" data-toggle-expand="${escapeHtml(d.entry_id)}">
              <div class="ov-row-main">
                <div class="ov-row-top">
                  <span class="ov-room-name">${escapeHtml(d.room_name || d.entry_id)}</span>
                  <span class="ov-preset-dot" style="background:${presetCol.bg};border-color:${presetCol.border};color:${presetCol.text};">${escapeHtml(presetLabel)}</span>
                  ${phaseBadge}
                  <span class="ov-temps tabular">${escapeHtml(tempStr)}</span>
                </div>
                ${showMini ? this._renderMiniTimeline(d, t) : ""}
              </div>
              <div class="ov-row-actions">
                <label class="auto-switch" title="${escapeHtml(t.automatic)}" data-stop-expand="1">
                  <input class="ov-auto-input" data-auto-entry="${escapeHtml(d.entry_id)}" type="checkbox" ${live.automationOn ? "checked" : ""} />
                  <span class="switch-track"><span class="switch-thumb"></span></span>
                </label>
                <span class="ov-chevron ${expanded ? "open" : ""}">${ICONS.chevron}</span>
              </div>
            </div>

            ${
              expanded
                ? `<div class="ov-drawer">
                    ${nextActionLine ? `<div class="ov-next-action tabular">${escapeHtml(nextActionLine)}</div>` : ""}
                    <div class="ov-drawer-controls">
                      <label class="ov-ctrl-group">
                        <span>${escapeHtml(t.profile)}</span>
                        <select class="ctrl-select ov-prof-select" data-prof-entry="${escapeHtml(d.entry_id)}">
                          ${profileNames
                            .map(
                              (pn) =>
                                `<option value="${escapeHtml(pn)}" ${pn === activeProfile ? "selected" : ""}>${escapeHtml(pn)}</option>`
                            )
                            .join("")}
                        </select>
                      </label>

                      ${
                        showOv
                          ? live.activeOverrides.length > 0
                            ? `<button type="button" class="btn-outline danger" data-ov-cancel="${escapeHtml(d.entry_id)}" data-ov-id="${escapeHtml(live.activeOverrides[0][0])}">${escapeHtml(t.cancelOverride)}</button>`
                            : `<div class="ov-quick-ov">
                                <select class="ctrl-select ov-ov-preset" data-ov-preset-entry="${escapeHtml(d.entry_id)}">
                                  ${presets
                                    .map(
                                      (p) =>
                                        `<option value="${escapeHtml(p)}" ${p === selOvPreset ? "selected" : ""}>${escapeHtml(this._getPresetLabel(d, p))}</option>`
                                    )
                                    .join("")}
                                </select>
                                <div class="chip-row">
                                  ${[30, 60, 120, 240]
                                    .map(
                                      (mins) =>
                                        `<button type="button" class="day-chip ${selOvDur === mins ? "active" : ""}" data-ov-dur-entry="${escapeHtml(d.entry_id)}" data-ov-dur-min="${mins}">${mins >= 60 ? `${mins / 60}h` : `${mins}m`}</button>`
                                    )
                                    .join("")}
                                </div>
                                <button type="button" class="btn-primary" data-ov-start="${escapeHtml(d.entry_id)}">${escapeHtml(t.startOverride)}</button>
                              </div>`
                          : ""
                      }
                    </div>
                  </div>`
                : ""
            }
          </div>
        `;
      })
      .join("");

    const toolbarHtml = showBulk
      ? `
        <div class="ov-toolbar">
          <div class="ov-filter-row">
            <div class="ov-filter-chips">
              ${filterChips
                .map(
                  (fc) =>
                    `<button type="button" class="day-chip ov-filter-chip ${filterMode === fc.key ? "active" : ""}" data-filter-key="${fc.key}">${escapeHtml(fc.label)}</button>`
                )
                .join("")}
            </div>
            <select id="ov-sort-select" class="ctrl-select ov-sort-select" title="${escapeHtml(t.overviewEditorDefaultSort)}">
              <option value="name" ${sortMode === "name" ? "selected" : ""}>${escapeHtml(t.sortName)}</option>
              <option value="phase" ${sortMode === "phase" ? "selected" : ""}>${escapeHtml(t.sortPhase)}</option>
              <option value="temp_delta" ${sortMode === "temp_delta" ? "selected" : ""}>${escapeHtml(t.sortDelta)}</option>
            </select>
          </div>
          <div class="ov-bulk-row">
            <button type="button" class="btn-outline ov-bulk-btn" id="ov-bulk-on" ${this._bulkPending || visibleEntries.length === 0 ? "disabled" : ""}>${escapeHtml(t.bulkAutoOn)}</button>
            <button type="button" class="btn-outline ov-bulk-btn" id="ov-bulk-off" ${this._bulkPending || visibleEntries.length === 0 ? "disabled" : ""}>${escapeHtml(t.bulkAutoOff)}</button>
            ${
              showOv
                ? `<button type="button" class="btn-outline ov-bulk-btn ${this._bulkOverrideOpen ? "active" : ""}" id="ov-bulk-ov-toggle" ${this._bulkPending || visibleEntries.length === 0 ? "disabled" : ""}>${escapeHtml(t.bulkOverride)}</button>`
                : ""
            }
            ${
              showOv && visibleWithOverrides > 0
                ? `<button type="button" class="btn-outline danger ov-bulk-btn" id="ov-bulk-ov-stop" ${this._bulkPending ? "disabled" : ""}>${escapeHtml(t.bulkStopOverrides)} (${visibleWithOverrides})</button>`
                : ""
            }
            ${
              allProfileNames.length > 1
                ? `<select id="ov-bulk-profile" class="ctrl-select ov-bulk-prof" ${this._bulkPending || visibleEntries.length === 0 ? "disabled" : ""}>
                    <option value="">${escapeHtml(t.bulkProfile)}</option>
                    ${allProfileNames.map((pn) => `<option value="${escapeHtml(pn)}">${escapeHtml(pn)}</option>`).join("")}
                  </select>`
                : ""
            }
          </div>
          ${
            showOv && this._bulkOverrideOpen
              ? `<div class="ov-bulk-popover">
                  <select id="ov-bulk-ov-preset" class="ctrl-select">
                    ${bulkPresets
                      .map(
                        (p) =>
                          `<option value="${escapeHtml(p)}" ${p === this._bulkOverridePreset ? "selected" : ""}>${escapeHtml(this._getPresetLabel(this._roomsData[0], p))}</option>`
                      )
                      .join("")}
                  </select>
                  <div class="chip-row">
                    ${[30, 60, 120, 240]
                      .map(
                        (mins) =>
                          `<button type="button" class="day-chip ${Number(this._bulkOverrideDuration) === mins ? "active" : ""}" data-bulk-dur="${mins}">${mins >= 60 ? `${mins / 60}h` : `${mins}m`}</button>`
                      )
                      .join("")}
                  </div>
                  <button type="button" class="btn-primary" id="ov-bulk-ov-apply" ${this._bulkPending ? "disabled" : ""}>${escapeHtml(t.bulkApply)} (${visibleEntries.length})</button>
                </div>`
              : ""
          }
        </div>
      `
      : "";

    this.shadowRoot.innerHTML = `
      <style>${this._getStyles()}</style>
      <ha-card>
        <div class="ov-root">
          ${titleText ? `<div class="ov-header"><span>${escapeHtml(titleText)}</span><span class="ov-header-count tabular">${visibleEntries.length}/${countAll} ${escapeHtml(t.roomsCount)}</span></div>` : ""}
          ${toolbarHtml}
          ${this._error ? `<div class="ov-error">${escapeHtml(this._error)}</div>` : ""}
          <div class="ov-list">
            ${
              visibleEntries.length > 0
                ? roomsHtml
                : `<div class="ov-filter-empty">
                    <span>${escapeHtml(t.filterEmpty)}</span>
                    <button type="button" class="btn-outline" id="ov-reset-filter">${escapeHtml(t.resetFilter)}</button>
                  </div>`
            }
          </div>
        </div>
      </ha-card>
    `;

    this._bindEvents();
  }

  _bindEvents() {
    const root = this.shadowRoot;
    if (!root) return;

    root.querySelectorAll("[data-filter-key]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._filterMode = btn.dataset.filterKey || "all";
        this._render();
      });
    });

    root.querySelector("#ov-sort-select")?.addEventListener("change", (ev) => {
      this._sortMode = ev.target.value || "name";
      this._render();
    });

    root.querySelector("#ov-reset-filter")?.addEventListener("click", () => {
      this._filterMode = "all";
      this._render();
    });

    root.querySelector("#ov-bulk-on")?.addEventListener("click", () => this._bulkSetAutomation(true));
    root.querySelector("#ov-bulk-off")?.addEventListener("click", () => this._bulkSetAutomation(false));
    root.querySelector("#ov-bulk-ov-toggle")?.addEventListener("click", () => {
      this._bulkOverrideOpen = !this._bulkOverrideOpen;
      this._render();
    });
    root.querySelector("#ov-bulk-ov-stop")?.addEventListener("click", () => this._bulkStopOverrides());
    root.querySelector("#ov-bulk-ov-preset")?.addEventListener("change", (ev) => {
      this._bulkOverridePreset = ev.target.value;
    });
    root.querySelectorAll("[data-bulk-dur]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._bulkOverrideDuration = parseInt(btn.dataset.bulkDur, 10) || 60;
        this._render();
      });
    });
    root.querySelector("#ov-bulk-ov-apply")?.addEventListener("click", () => this._bulkStartOverride());
    root.querySelector("#ov-bulk-profile")?.addEventListener("change", (ev) => {
      const val = ev.target.value;
      if (val) {
        this._bulkSwitchProfile(val);
      }
    });

    root.querySelectorAll("[data-toggle-expand]").forEach((row) => {
      row.addEventListener("click", (ev) => {
        if (ev.target.closest("[data-stop-expand]")) return;
        const entryId = row.dataset.toggleExpand;
        this._expandedRoomId = this._expandedRoomId === entryId ? null : entryId;
        this._render();
      });
    });

    root.querySelectorAll(".ov-auto-input").forEach((inp) => {
      inp.addEventListener("change", () => this._toggleAuto(inp.dataset.autoEntry));
    });

    root.querySelectorAll(".ov-prof-select").forEach((sel) => {
      sel.addEventListener("change", (ev) => this._switchProfile(sel.dataset.profEntry, ev.target.value));
    });

    root.querySelectorAll(".ov-ov-preset").forEach((sel) => {
      sel.addEventListener("change", (ev) => {
        this._overridePresets[sel.dataset.ovPresetEntry] = ev.target.value;
      });
    });

    root.querySelectorAll("[data-ov-dur-entry]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._overrideDurations[btn.dataset.ovDurEntry] = parseInt(btn.dataset.ovDurMin, 10) || 60;
        this._render();
      });
    });

    root.querySelectorAll("[data-ov-start]").forEach((btn) => {
      btn.addEventListener("click", () => this._startOverride(btn.dataset.ovStart));
    });

    root.querySelectorAll("[data-ov-cancel]").forEach((btn) => {
      btn.addEventListener("click", () => this._cancelOverride(btn.dataset.ovCancel, btn.dataset.ovId));
    });
  }

  _getStyles() {
    return `
      :host {
        display: block;
        --scs-accent: #f59e0b;
        --scs-accent-hover: #d97706;
        --scs-surface: var(--secondary-background-color, rgba(255, 255, 255, 0.04));
        --scs-border: var(--divider-color, rgba(255, 255, 255, 0.1));
        --scs-text: var(--primary-text-color, #f1f5f9);
        --scs-muted: var(--secondary-text-color, #94a3b8);
        --scs-danger: #ef4444;
      }
      .ov-root {
        padding: 10px 12px;
        color: var(--scs-text);
        font-family: var(--ha-font-family-body, system-ui, -apple-system, sans-serif);
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .tabular {
        font-variant-numeric: tabular-nums;
      }
      .ov-header {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 8px;
        font-size: 0.96rem;
        font-weight: 600;
      }
      .ov-header-count {
        font-size: 0.74rem;
        font-weight: 500;
        color: var(--scs-muted);
      }
      .ov-toolbar {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 7px 8px;
        border-radius: 9px;
        border: 1px solid var(--scs-border);
        background: var(--scs-surface);
      }
      .ov-filter-row,
      .ov-bulk-row,
      .ov-bulk-popover {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 5px;
      }
      .ov-filter-chips {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 4px;
        flex: 1;
      }
      .ov-sort-select,
      .ov-bulk-prof {
        min-height: 24px;
        font-size: 0.72rem;
        padding: 2px 6px;
      }
      .ov-bulk-btn {
        min-height: 24px;
        font-size: 0.72rem;
        padding: 2px 8px;
        background: transparent;
        color: var(--scs-text);
        border: 1px solid var(--scs-border);
      }
      .ov-bulk-btn.active {
        border-color: var(--scs-accent);
        color: var(--scs-accent);
        background: rgba(245, 158, 11, 0.14);
      }
      .ov-bulk-btn:disabled,
      .btn-primary:disabled {
        opacity: 0.45;
        cursor: not-allowed;
      }
      .ov-bulk-popover {
        padding-top: 4px;
        border-top: 1px dashed var(--scs-border);
      }
      .ov-filter-empty {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        padding: 10px 12px;
        border-radius: 9px;
        border: 1px dashed var(--scs-border);
        color: var(--scs-muted);
        font-size: 0.78rem;
      }
      .ov-error {
        font-size: 0.76rem;
        color: var(--scs-danger);
      }
      .ov-empty {
        padding: 16px;
        text-align: center;
        color: var(--scs-muted);
        font-size: 0.85rem;
      }
      .ov-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .ov-room {
        border: 1px solid var(--scs-border);
        background: var(--scs-surface);
        border-radius: 9px;
        overflow: hidden;
      }
      .ov-room.expanded {
        border-color: rgba(245, 158, 11, 0.55);
      }
      .ov-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 7px 9px;
        cursor: pointer;
      }
      .ov-row-main {
        min-width: 0;
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .ov-row-top {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 5px 7px;
      }
      .ov-room-name {
        font-size: 0.88rem;
        font-weight: 600;
        white-space: nowrap;
      }
      .ov-preset-dot {
        font-size: 0.68rem;
        font-weight: 600;
        border: 1px solid transparent;
        border-radius: 5px;
        padding: 1px 6px;
        line-height: 1.3;
      }
      .ov-phase {
        font-size: 0.68rem;
        font-weight: 600;
        border-radius: 5px;
        padding: 1px 5px;
      }
      .ov-phase-heat {
        background: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
      }
      .ov-phase-cool {
        background: rgba(56, 189, 248, 0.18);
        color: #38bdf8;
      }
      .ov-phase-warn {
        background: rgba(234, 88, 12, 0.22);
        color: #fb923c;
      }
      .ov-temps {
        font-size: 0.78rem;
        color: var(--scs-muted);
        margin-left: auto;
      }
      .ov-row-actions {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-shrink: 0;
      }
      .ov-chevron {
        color: var(--scs-muted);
        display: inline-flex;
        transition: transform 150ms ease;
      }
      .ov-chevron.open {
        transform: rotate(180deg);
        color: var(--scs-accent);
      }
      .ov-mini-track {
        position: relative;
        height: 7px;
        border-radius: 999px;
        overflow: hidden;
        background: rgba(148, 163, 184, 0.16);
      }
      .ov-mini-base {
        position: absolute;
        inset: 0;
      }
      .ov-mini-slot {
        position: absolute;
        top: 0;
        bottom: 0;
        opacity: 0.88;
      }
      .ov-mini-thermal {
        position: absolute;
        top: 0;
        bottom: 0;
        background: repeating-linear-gradient(
          -45deg,
          color-mix(in srgb, var(--tp-color, #f59e0b) 75%, transparent),
          color-mix(in srgb, var(--tp-color, #f59e0b) 75%, transparent) 2px,
          transparent 2px,
          transparent 4px
        );
        border-left: 1px solid var(--tp-border, #fbbf24);
      }
      .ov-mini-now {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 2px;
        background: #ffffff;
        box-shadow: 0 0 3px rgba(0, 0, 0, 0.7);
      }
      .ov-drawer {
        border-top: 1px solid var(--scs-border);
        padding: 7px 9px;
        display: flex;
        flex-direction: column;
        gap: 7px;
        background: rgba(0, 0, 0, 0.12);
      }
      .ov-next-action {
        font-size: 0.74rem;
        color: var(--scs-muted);
      }
      .ov-drawer-controls {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
      }
      .ov-ctrl-group {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.74rem;
        color: var(--scs-muted);
      }
      .ov-quick-ov {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        margin-left: auto;
      }
      .auto-switch {
        display: inline-flex;
        align-items: center;
        cursor: pointer;
        user-select: none;
      }
      .auto-switch input {
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
      }
      .switch-track {
        width: 34px;
        height: 18px;
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
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #ffffff;
        transition: transform 150ms ease;
      }
      .auto-switch input:checked + .switch-track .switch-thumb {
        transform: translateX(16px);
      }
      .ctrl-select {
        background: var(--scs-surface);
        color: var(--scs-text);
        border: 1px solid var(--scs-border);
        border-radius: 7px;
        padding: 3px 8px;
        font-size: 0.76rem;
        min-height: 28px;
      }
      .chip-row {
        display: flex;
        align-items: center;
        gap: 4px;
      }
      .day-chip {
        background: transparent;
        color: var(--scs-text);
        border: 1px solid var(--scs-border);
        border-radius: 6px;
        padding: 2px 7px;
        font-size: 0.72rem;
        cursor: pointer;
      }
      .day-chip.active {
        background: rgba(245, 158, 11, 0.2);
        border-color: var(--scs-accent);
        color: var(--scs-accent);
        font-weight: 600;
      }
      .btn-primary,
      .btn-outline {
        border-radius: 7px;
        padding: 3px 9px;
        font-size: 0.76rem;
        font-weight: 600;
        cursor: pointer;
        min-height: 28px;
      }
      .btn-primary {
        background: var(--scs-accent);
        color: #111827;
        border: 1px solid var(--scs-accent);
      }
      .btn-outline.danger {
        background: transparent;
        color: var(--scs-danger);
        border: 1px solid rgba(239, 68, 68, 0.45);
      }
    `;
  }
}

class SmartClimateSchedulerOverviewCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._rooms = [];
  }

  setConfig(config) {
    this._config = {
      title: "",
      rooms: [],
      show_mini_timeline: true,
      show_thermal_preview: true,
      show_override_bar: true,
      show_bulk_actions: true,
      default_filter: "all",
      default_sort: "name",
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
      this._rooms = [];
    }
    this._render();
  }

  _emitChange(updated) {
    const nextConfig = { ...this._config, ...updated };
    Object.keys(nextConfig).forEach((k) => {
      if (nextConfig[k] === undefined) delete nextConfig[k];
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
    const selectedRooms = new Set(Array.isArray(this._config?.rooms) ? this._config.rooms : []);
    const titleVal = this._config?.title || "";
    const showMini = this._config?.show_mini_timeline !== false;
    const showThermal = this._config?.show_thermal_preview !== false;
    const showOv = this._config?.show_override_bar !== false;
    const showBulk = this._config?.show_bulk_actions !== false;
    const defaultFilter = this._config?.default_filter || "all";
    const defaultSort = this._config?.default_sort || "name";

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
        .field-title {
          font-size: 0.85rem;
          font-weight: 500;
          margin-bottom: 4px;
        }
        input[type="text"], select {
          width: 100%;
          box-sizing: border-box;
          padding: 8px 10px;
          border-radius: 8px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.2));
          background: var(--secondary-background-color, rgba(255,255,255,0.05));
          color: var(--primary-text-color, #f1f5f9);
          font-size: 0.9rem;
        }
        .two-col {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
        }
        .room-checks {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding: 8px 10px;
          border-radius: 8px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.14));
        }
        label.inline {
          display: flex;
          flex-direction: row;
          align-items: center;
          gap: 8px;
          font-size: 0.85rem;
          cursor: pointer;
        }
        .hint {
          font-size: 0.76rem;
          color: var(--secondary-text-color, #94a3b8);
        }
      </style>
      <div class="ed-root">
        <div>
          <div class="field-title">${escapeHtml(t.overviewEditorTitle)}</div>
          <input id="oved-title" type="text" value="${escapeHtml(titleVal)}" placeholder="${escapeHtml(t.overviewDefaultTitle)}" />
        </div>
        <div>
          <div class="field-title">${escapeHtml(t.overviewEditorRooms)}</div>
          <div class="room-checks">
            ${
              this._rooms.length > 0
                ? this._rooms
                    .map(
                      (r) => `
                        <label class="inline">
                          <input type="checkbox" class="oved-room" value="${escapeHtml(r.entry_id)}" ${selectedRooms.has(r.entry_id) ? "checked" : ""} />
                          <span>${escapeHtml(r.name)}</span>
                        </label>
                      `
                    )
                    .join("")
                : `<div class="hint">${escapeHtml(t.overviewAllRoomsHint)}</div>`
            }
          </div>
        </div>
        <div class="two-col">
          <div>
            <div class="field-title">${escapeHtml(t.overviewEditorDefaultFilter)}</div>
            <select id="oved-filter">
              <option value="all" ${defaultFilter === "all" ? "selected" : ""}>${escapeHtml(t.filterAll)}</option>
              <option value="auto_on" ${defaultFilter === "auto_on" ? "selected" : ""}>${escapeHtml(t.filterAutoOn)}</option>
              <option value="heating" ${defaultFilter === "heating" ? "selected" : ""}>${escapeHtml(t.filterHeating)}</option>
              <option value="override" ${defaultFilter === "override" ? "selected" : ""}>${escapeHtml(t.filterOverride)}</option>
            </select>
          </div>
          <div>
            <div class="field-title">${escapeHtml(t.overviewEditorDefaultSort)}</div>
            <select id="oved-sort">
              <option value="name" ${defaultSort === "name" ? "selected" : ""}>${escapeHtml(t.sortName)}</option>
              <option value="phase" ${defaultSort === "phase" ? "selected" : ""}>${escapeHtml(t.sortPhase)}</option>
              <option value="temp_delta" ${defaultSort === "temp_delta" ? "selected" : ""}>${escapeHtml(t.sortDelta)}</option>
            </select>
          </div>
        </div>
        <label class="inline">
          <input id="oved-bulk" type="checkbox" ${showBulk ? "checked" : ""} />
          <span>${escapeHtml(t.overviewEditorShowBulk)}</span>
        </label>
        <label class="inline">
          <input id="oved-mini" type="checkbox" ${showMini ? "checked" : ""} />
          <span>${escapeHtml(t.overviewEditorMiniTimeline)}</span>
        </label>
        <label class="inline">
          <input id="oved-thermal" type="checkbox" ${showThermal ? "checked" : ""} />
          <span>${escapeHtml(t.editorShowThermal)}</span>
        </label>
        <label class="inline">
          <input id="oved-ov" type="checkbox" ${showOv ? "checked" : ""} />
          <span>${escapeHtml(t.editorShowOverride)}</span>
        </label>
      </div>
    `;

    this.shadowRoot.querySelector("#oved-title")?.addEventListener("change", (ev) => {
      const val = ev.target.value.trim();
      this._emitChange({ title: val });
    });
    this.shadowRoot.querySelectorAll(".oved-room").forEach((cb) => {
      cb.addEventListener("change", () => {
        const chosen = Array.from(this.shadowRoot.querySelectorAll(".oved-room"))
          .filter((el) => el.checked)
          .map((el) => el.value);
        this._emitChange({ rooms: chosen });
      });
    });
    this.shadowRoot.querySelector("#oved-filter")?.addEventListener("change", (ev) => {
      this._emitChange({ default_filter: ev.target.value || "all" });
    });
    this.shadowRoot.querySelector("#oved-sort")?.addEventListener("change", (ev) => {
      this._emitChange({ default_sort: ev.target.value || "name" });
    });
    this.shadowRoot.querySelector("#oved-bulk")?.addEventListener("change", (ev) => {
      this._emitChange({ show_bulk_actions: ev.target.checked });
    });
    this.shadowRoot.querySelector("#oved-mini")?.addEventListener("change", (ev) => {
      this._emitChange({ show_mini_timeline: ev.target.checked });
    });
    this.shadowRoot.querySelector("#oved-thermal")?.addEventListener("change", (ev) => {
      this._emitChange({ show_thermal_preview: ev.target.checked });
    });
    this.shadowRoot.querySelector("#oved-ov")?.addEventListener("change", (ev) => {
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
if (!customElements.get(OVERVIEW_CARD_TAG)) {
  customElements.define(OVERVIEW_CARD_TAG, SmartClimateSchedulerOverviewCard);
}
if (!customElements.get(OVERVIEW_EDITOR_TAG)) {
  customElements.define(OVERVIEW_EDITOR_TAG, SmartClimateSchedulerOverviewCardEditor);
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
if (!window.customCards.some((c) => c.type === OVERVIEW_CARD_TAG)) {
  window.customCards.push({
    type: OVERVIEW_CARD_TAG,
    name: "Smart Climate Scheduler Overview Card",
    description: "Kompakte Multi-Raum-Übersicht mit Mini-Zeitleiste, Automatik-Schalter & aufklappbarer Steuerung.",
    preview: true,
  });
}
