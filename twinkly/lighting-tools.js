const hueProductImageRevisions = new Map();

function hueProductImagePath(light) {
  const model = light.model;
  return typeof model === "string" && /^[A-Za-z0-9_-]{1,32}$/.test(model)
    ? "providers/hue/product-image/" + model.toUpperCase() : null;
}

function hueProductImage(light, fallback) {
  const path = hueProductImagePath(light);
  if (!path || !(light.has_product_image || light.has_catalog_image)) return fallback;
  const image = Object.assign(document.createElement("img"), {
    className: "hue-product-photo", alt: "", decoding: "async", draggable: false,
  });
  image.addEventListener("error", () => {
    fallback.style.rotate = image.style.rotate;
    image.replaceWith(fallback);
  }, {once: true});
  image.src = path + "?v=" + (hueProductImageRevisions.get(path) || 0);
  return image;
}

window.createLightingTools = ({mount, house, nav, api, node, field, language, roomLightControls}) => {
  const labels = {
    nl: ["Showbouwer", "Shownaam", "Scène", "Wachttijd (sec.)", "Stap toevoegen", "Omhoog", "Omlaag", "Verwijderen", "Opslaan", "Afspelen", "Stoppen", "Maak eerst een scène voor een gemengde groep op Home.", "Stap", "Show klaar", "Show gestopt", "Show onderbroken", "Geen bevestiging", "Spatial Light Studio", "Kies een foto", "Kies een lamp", "Plaats in het midden", "Verwijder plaatsing", "Klik op de foto om de gekozen lamp te plaatsen. Verplaats een markering met de pijltjestoetsen.", "Foto wissen", "Kies een geldige JPG, PNG of WebP van maximaal 15 MB.", "Opslaan op de server is mislukt.", "Shows en foto-indeling staan op je Home Assistant-server. Een show loopt door als je de pagina sluit.", "Groep", "Nieuwe show", "Bewerken", "Definieer minimaal één geldige stap.", "Onbekende lamp", "Locatie", "Foto van de ruimte", "Scène of groep ontbreekt", "Opdrachten gedeeltelijk uitgevoerd"],
    en: ["Show builder", "Show name", "Scene", "Hold (sec.)", "Add step", "Move up", "Move down", "Remove", "Save", "Play", "Stop", "First create a scene for a mixed group on Home.", "Step", "Show complete", "Show stopped", "Show interrupted", "Unconfirmed", "Spatial Light Studio", "Choose a photo", "Choose a light", "Place in the centre", "Remove placement", "Click the photo to place the selected light. Move a marker with the arrow keys.", "Clear photo", "Choose a valid JPG, PNG or WebP up to 15 MB.", "Could not save to the server.", "Shows and photo layouts are saved on your Home Assistant server. Playback continues when you close this page.", "Group", "New show", "Edit", "Add at least one valid step.", "Unknown light", "Position", "Photo of the space", "Scene or group missing", "Some commands did not complete"],
    de: ["Show-Editor", "Showname", "Szene", "Haltedauer (Sek.)", "Schritt hinzufügen", "Nach oben", "Nach unten", "Entfernen", "Speichern", "Abspielen", "Stoppen", "Erstelle zuerst auf der Startseite eine Szene für eine gemischte Gruppe.", "Schritt", "Show beendet", "Show gestoppt", "Show unterbrochen", "Unbestätigt", "Spatial Light Studio", "Foto auswählen", "Lampe auswählen", "In der Mitte platzieren", "Position entfernen", "Klicke auf das Foto, um die Lampe zu platzieren. Verschiebe Marker mit den Pfeiltasten.", "Foto löschen", "Wähle ein gültiges JPG, PNG oder WebP bis 15 MB.", "Speichern auf dem Server fehlgeschlagen.", "Shows und Fotolayout liegen auf deinem Home Assistant-Server. Die Wiedergabe läuft nach dem Schließen der Seite weiter.", "Gruppe", "Neue Show", "Bearbeiten", "Füge mindestens einen gültigen Schritt hinzu.", "Unbekannte Lampe", "Position", "Foto des Raums", "Szene oder Gruppe fehlt", "Einige Befehle wurden nicht ausgeführt"],
    es: ["Editor de espectáculos", "Nombre", "Escena", "Pausa (s)", "Añadir paso", "Subir", "Bajar", "Quitar", "Guardar", "Reproducir", "Detener", "Crea primero una escena para un grupo mixto en Inicio.", "Paso", "Espectáculo terminado", "Espectáculo detenido", "Espectáculo interrumpido", "Sin confirmar", "Spatial Light Studio", "Elegir foto", "Elegir luz", "Colocar en el centro", "Quitar posición", "Haz clic en la foto para colocar la luz. Usa las flechas para mover un marcador.", "Borrar foto", "Elige un JPG, PNG o WebP válido de hasta 15 MB.", "No se pudo guardar en el servidor.", "Los espectáculos y la distribución se guardan en tu servidor de Home Assistant. La reproducción continúa al cerrar esta página.", "Grupo", "Nuevo espectáculo", "Editar", "Añade al menos un paso válido.", "Luz desconocida", "Posición", "Foto del espacio", "Falta la escena o el grupo", "Algunos comandos no se completaron"],
  };
  const serverLabels = {
    nl: ["Projecten laden…", "Projecten konden niet worden geladen.", "Gegevens uit deze browser overzetten", "Gegevens overgezet.", "Er staat al een foto op de server. Je oude foto blijft in deze browser.", "Er is een conflict. Vernieuw de bewerking en probeer opnieuw.", "Show wordt gestopt…", "Foto vervangen? De huidige lampplaatsingen worden gewist."],
    en: ["Loading projects…", "Could not load projects.", "Import from this browser", "Projects imported.", "The server already has a photo. Your original photo remains in this browser.", "There is a conflict. Reload the edit and try again.", "Stopping show…", "Replace photo? Current light placements will be cleared."],
    de: ["Projekte werden geladen…", "Projekte konnten nicht geladen werden.", "Daten aus diesem Browser importieren", "Projekte importiert.", "Auf dem Server liegt bereits ein Foto. Das alte Foto bleibt in diesem Browser.", "Es gibt einen Konflikt. Lade die Bearbeitung neu und versuche es erneut.", "Show wird gestoppt…", "Foto ersetzen? Die aktuellen Lampenpositionen werden gelöscht."],
    es: ["Cargando proyectos…", "No se pudieron cargar los proyectos.", "Importar desde este navegador", "Proyectos importados.", "Ya hay una foto en el servidor. La foto anterior permanece en este navegador.", "Hay un conflicto. Vuelve a abrir la edición e inténtalo de nuevo.", "Deteniendo el espectáculo…", "¿Sustituir la foto? Se borrarán las posiciones de luces actuales."],
  };
  const houseLabels = {
    nl: ["Mijn Huis", "Lampen", "Grootte", "Nog geen lampen gevonden", "Kies een lamp en tik op de foto om hem te plaatsen. Versleep de lamp om hem te verplaatsen en sleep aan de ronde hoekgreep voor de grootte.", "Geplaatst"],
    en: ["My Home", "Lights", "Size", "No lights found", "Choose a light and tap the photo to place it. Drag the light to move it and drag its round corner handle to resize it.", "Placed"],
    de: ["Mein Zuhause", "Lampen", "Größe", "Keine Lampen gefunden", "Wähle eine Lampe und tippe auf das Foto. Ziehe die Lampe zum Verschieben und den runden Eckgriff zum Skalieren.", "Platziert"],
    es: ["Mi casa", "Luces", "Tamaño", "No hay luces", "Elige una luz y toca la foto para colocarla. Arrastra la luz para moverla y el tirador redondo para cambiar su tamaño.", "Colocada"],
  };
  const effectLabels = {
    nl: ["Kleurveeg", "Richting", "Links naar rechts", "Rechts naar links", "Boven naar beneden", "Beneden naar boven", "Tijd tussen lampen (ms)", "Volgorde tonen", "Lampen die meedoen", "RGB-lampen die als ingeschakeld bekend zijn, doen mee. Na de veeg blijft de gekozen kleur actief.", "Laatste uitgevoerde stap", "Opdrachttijd in de app", "Kleurveeg klaar", "Kleurveeg gestopt", "Kleurveeg mislukt", "Kleurveeg wordt voorbereid…", "Geaccepteerd", "Overgeslagen", "Mislukt"],
    en: ["Colour sweep", "Direction", "Left to right", "Right to left", "Top to bottom", "Bottom to top", "Time between lights (ms)", "Show order", "Participating lights", "Lights with RGB and a known on state take part. The selected colour stays active after the sweep.", "Last completed step", "Command time in the app", "Sweep complete", "Sweep stopped", "Sweep failed", "Preparing sweep…", "Accepted", "Skipped", "Failed"],
    de: ["Farbverlauf", "Richtung", "Links nach rechts", "Rechts nach links", "Oben nach unten", "Unten nach oben", "Zeit zwischen Lampen (ms)", "Reihenfolge anzeigen", "Teilnehmende Lampen", "RGB-Lampen mit bestätigtem Ein-Zustand nehmen teil. Die gewählte Farbe bleibt danach aktiv.", "Zuletzt ausgeführter Schritt", "Befehlsdauer in der App", "Farbverlauf abgeschlossen", "Farbverlauf gestoppt", "Farbverlauf fehlgeschlagen", "Farbverlauf wird vorbereitet…", "Angenommen", "Übersprungen", "Fehlgeschlagen"],
    es: ["Barrido de color", "Dirección", "Izquierda a derecha", "Derecha a izquierda", "Arriba abajo", "Abajo arriba", "Tiempo entre luces (ms)", "Mostrar orden", "Luces participantes", "Participan las luces RGB cuyo estado encendido es conocido. El color elegido permanece al terminar.", "Último paso ejecutado", "Tiempo de comando en la aplicación", "Barrido terminado", "Barrido detenido", "Barrido fallido", "Preparando barrido…", "Aceptado", "Omitido", "Fallido"],
  };
  const radialLabels = {
    nl: ["Van midden naar buiten", "Van buiten naar midden", "Deze kleurveeg gebruikt de afstand tot het midden van de foto."],
    en: ["Centre out", "Edges in", "This colour sweep uses the distance from the centre of the photo."],
    de: ["Von der Mitte nach außen", "Von außen zur Mitte", "Die Farbwelle nutzt den Abstand zur Mitte des Fotos."],
    es: ["Del centro hacia fuera", "De fuera hacia el centro", "El barrido usa la distancia hasta el centro de la foto."],
  };
  const radialModes = {outward: 0, inward: 1};
  const directions = {right: [0, 1], left: [0, -1], down: [1, 1], up: [1, -1]};
  const planLabels = {
    nl: ["3D-weergave", "Sluiten", "Sleep om te draaien. Gebruik de pijltjes of schuifknop om te draaien en te zoomen.", "Zoom", "Links draaien", "Rechts draaien", "Voeg muurmaten of een foto toe.", "Echte ledposities", "Ledmapping ontbreekt", "Ledmapping ophalen…", "Muur plaatsen", "Kamer en wandzijde", "Kamer", "Voor", "Rechts", "Achter", "Links", "Alle kamers", "Beginstand", "Vernieuwen", "Bij een bezette plek wisselen de twee muren van plaats.", "Plek opgeslagen", "Open 3D-weergave en kies voor elke muur de kamer en wandzijde."],
    en: ["3D view", "Close", "Drag to orbit. Use the arrow keys to turn and the slider to zoom.", "Zoom", "Turn left", "Turn right", "Add wall dimensions or a photo.", "Physical LED positions", "LED mapping unavailable", "Loading LED mapping…", "Place wall", "Room and wall side", "Room", "Front", "Right", "Back", "Left", "All rooms", "Reset view", "Refresh", "If a spot is occupied, the two walls swap positions.", "Position saved", "Open the 3D view and select a room and side for each wall."],
    de: ["3D-Ansicht", "Schließen", "Zum Drehen ziehen. Pfeiltasten drehen, der Schieberegler zoomt.", "Zoom", "Nach links drehen", "Nach rechts drehen", "Füge Wandmaße oder ein Foto hinzu.", "Physische LED-Positionen", "LED-Mapping fehlt", "LED-Mapping wird geladen…", "Wand platzieren", "Raum und Wandseite", "Raum", "Vorne", "Rechts", "Hinten", "Links", "Alle Räume", "Ansicht zurücksetzen", "Aktualisieren", "Ist ein Platz belegt, tauschen die beiden Wände ihre Position.", "Position gespeichert", "Öffne die 3D-Ansicht und wähle für jede Wand einen Raum und eine Seite."],
    es: ["Vista 3D", "Cerrar", "Arrastra para girar. Usa las flechas para girar y el control deslizante para ampliar.", "Zoom", "Girar a la izquierda", "Girar a la derecha", "Sube primero una foto de pared.", "Posiciones físicas de los LED", "Mapa LED no disponible", "Cargando mapa LED…", "Colocar pared", "Habitación y lado de la pared", "Habitación", "Delante", "Derecha", "Detrás", "Izquierda", "Todas las habitaciones", "Restablecer vista", "Actualizar", "Si el lugar está ocupado, las dos paredes intercambian posiciones.", "Posición guardada", "Abre la vista 3D y elige una habitación y un lado para cada pared."],
  };
  const wallLabels = {
    nl: ["Muur", "Muur 1", "Naam muur", "Muur toevoegen", "Naam wijzigen", "Muur verwijderen", "Deze muur met foto en lampplaatsingen verwijderen?"],
    en: ["Wall", "Wall 1", "Wall name", "Add wall", "Rename wall", "Delete wall", "Delete this wall, including its photo and light placements?"],
    de: ["Wand", "Wand 1", "Name der Wand", "Wand hinzufügen", "Wand umbenennen", "Wand löschen", "Diese Wand samt Foto und Lampenpositionen löschen?"],
    es: ["Pared", "Pared 1", "Nombre de la pared", "Añadir pared", "Cambiar nombre", "Eliminar pared", "¿Eliminar esta pared con su foto y posiciones de luces?"],
  };
  const dimensionLabels = {
    nl: ["Breedte (m)", "Hoogte (m)", "Muurmaten opslaan", "Lege muur"],
    en: ["Width (m)", "Height (m)", "Save wall dimensions", "Blank wall"],
    de: ["Breite (m)", "Höhe (m)", "Wandmaße speichern", "Leere Wand"],
    es: ["Ancho (m)", "Altura (m)", "Guardar medidas de la pared", "Pared sin foto"],
  };
  const placementLabels = {
    nl: ["Links/rechts (m)", "Voor/achter (m)", "Muurhoek (°)", "Wandzijde herstellen", "Draaihoek lamp (°)", "Kamernaam"],
    en: ["Left/right (m)", "Front/back (m)", "Wall angle (°)", "Reset to wall side", "Light angle (°)", "Room name"],
    de: ["Links/rechts (m)", "Vorne/hinten (m)", "Wandwinkel (°)", "Wandseite wiederherstellen", "Lampenwinkel (°)", "Raumname"],
    es: ["Izquierda/derecha (m)", "Delante/detrás (m)", "Ángulo de pared (°)", "Restablecer lado", "Ángulo de luz (°)", "Nombre de habitación"],
  };
  const placementLabel = index => (placementLabels[language()] || placementLabels.nl)[index];
  const wallGuide = {
    nl: ["Handleiding Mijn Huis", "Maak één foto per muur.", "Fotografeer de muur recht van voren, in goed licht. Zorg dat de hele muur en de plekken voor je lampen zichtbaar zijn.",
      "Voeg een muur toe, geef hem een naam en upload de bijbehorende foto.", "Kies een lamp uit de lijst en tik op de plek waar die hangt. Versleep de markering om de positie aan te passen en gebruik de hoekgreep of schuifregelaar voor de grootte.",
      "Kies onder Effect een kleurveeg of kleurverloop. Zet Volgorde tonen aan om het effect vooraf op je foto te bekijken.",
      "Elke muur bewaart zijn eigen foto en lampplaatsingen. Als je een foto vervangt, wist de app de plaatsingen op die muur."],
    en: ["My Home guide", "Take one photo per wall.", "Photograph the wall straight on in good light. Include the whole wall and the spots where your lights will go.",
      "Add and name a wall, then enter its dimensions or upload a photo.", "Choose a light from the list and tap where it hangs. Drag its marker to reposition it and use the corner handle or slider to resize it.",
      "Under Effect, choose a colour sweep or gradient. Turn on Show order to preview it on your photo.",
      "Each wall saves its own photo and light placements. Replacing a photo clears the placements on that wall."],
    de: ["Anleitung für Mein Zuhause", "Mache ein Foto pro Wand.", "Fotografiere die Wand frontal und bei gutem Licht. Die ganze Wand und alle vorgesehenen Lampenpositionen sollten sichtbar sein.",
      "Füge eine Wand hinzu, benenne sie und lade ihr Foto hoch.", "Wähle eine Lampe aus der Liste und tippe auf ihre Position. Ziehe die Markierung, um sie zu verschieben. Ändere die Größe mit dem Eckgriff oder Schieberegler.",
      "Wähle unter Effekt einen Farbverlauf oder eine Farbwelle. Aktiviere Reihenfolge anzeigen für die Vorschau auf deinem Foto.",
      "Jede Wand speichert ihr eigenes Foto und ihre Lampenpositionen. Beim Ersetzen eines Fotos werden die Positionen dieser Wand gelöscht."],
    es: ["Guía de Mi casa", "Haz una foto por pared.", "Fotografía la pared de frente y con buena luz. Incluye toda la pared y los lugares donde colocarás las luces.",
      "Añade una pared, ponle un nombre y sube su foto.", "Elige una luz y toca el lugar donde está instalada. Arrastra el marcador para moverlo y usa el tirador o el control deslizante para cambiar su tamaño.",
      "Elige un barrido o un degradado en Efecto. Activa Mostrar orden para ver una vista previa en la foto.",
      "Cada pared guarda su propia foto y sus posiciones de luces. Al sustituir una foto se borran las posiciones de esa pared."],
  };
  const timingLabels = {
    nl: ["Effect", "Kleurverloop", "Eindkleur", "Timingcorrectie (ms)", "Stuur de opdracht voor deze lamp eerder als hij trager reageert.", "Kleurverloop klaar", "Kleurverloop gestopt", "Kleurverloop mislukt", "Kleurverloop wordt voorbereid…", "Het verloop verdeelt de kleuren over de lampposities in de gekozen richting."],
    en: ["Effect", "Colour gradient", "End colour", "Timing correction (ms)", "Send the command earlier for this light if it responds more slowly.", "Gradient complete", "Gradient stopped", "Gradient failed", "Preparing gradient…", "The gradient distributes colours over the light positions in the selected direction."],
    de: ["Effekt", "Farbgradient", "Endfarbe", "Zeitkorrektur (ms)", "Sende den Befehl für diese Lampe früher, wenn sie langsamer reagiert.", "Gradient abgeschlossen", "Gradient gestoppt", "Gradient fehlgeschlagen", "Gradient wird vorbereitet…", "Der Gradient verteilt die Farben in der gewählten Richtung auf die Lampenpositionen."],
    es: ["Efecto", "Degradado", "Color final", "Corrección de tiempo (ms)", "Envía la orden antes para esta luz si tarda más en responder.", "Degradado terminado", "Degradado detenido", "Degradado fallido", "Preparando degradado…", "El degradado distribuye los colores por la posición de las luces en la dirección elegida."],
  };
  const sweep = {mode: "sweep", end: "#4b90ff", direction: "right", color: "#ffbd63", delay: 550, preview: false};
  const showKey = "christmas-mixed-shows-v1";
  const spatialKey = "christmas-spatial-layout-v1";
  const maxSteps = 20;
  const maxShows = 20;
  const maxWalls = 24;
  const planSlots = 8 * 4;
  const showSection = node("section", "", "lighting-tool");
  const spatialSection = node("section", "", "lighting-tool");
  const showStatus = node("p");
  const spatialStatus = node("p");
  const effectStatus = node("p");
  effectStatus.setAttribute("role", "status");
  const reports = [node("details", "", "house-effect-report"), node("details", "", "house-effect-report")];
  let refreshEffectButtons;
  showStatus.setAttribute("role", "status");
  spatialStatus.setAttribute("role", "status");
  showSection.append(showStatus);
  spatialSection.append(spatialStatus);
  const houseTitle = node("h2");
  houseTitle.id = "house-title";
  mount.append(showSection);
  const guide = node("details", "", "house-guide");
  guide.open = true;
  let guideLanguage;
  const wallPicker = node("div", "", "house-wall-picker");
  const wallStatus = node("p");
  wallStatus.setAttribute("role", "status");
  const plan = node("section", "", "house-3d");
  plan.hidden = true;
  const openPlan = action("", () => {
    plan.hidden = !plan.hidden;
    openPlan.setAttribute("aria-expanded", String(!plan.hidden));
    if (!plan.hidden) renderHouse3d();
  });
  openPlan.setAttribute("aria-expanded", "false");
  const floorPlan = node("section", "", "house-floor-plan");
  floorPlan.hidden = true;
  const openFloor = action("", () => {
    floorPlan.hidden = !floorPlan.hidden;
    openFloor.setAttribute("aria-expanded", String(!floorPlan.hidden));
    if (!floorPlan.hidden) renderFloorPlan();
  });
  openFloor.setAttribute("aria-expanded", "false");
  house.append(houseTitle, guide, openFloor, floorPlan, openPlan, plan, wallPicker, spatialSection);
  function renderWallGuide() {
    const current = language();
    if (guideLanguage === current) return;
    guideLanguage = current;
    const [title, first, photo, upload, place, effect, limit] = wallGuide[current] || wallGuide.nl;
    const steps = node("ol");
    const firstStep = node("li");
    firstStep.append(node("strong", first), document.createTextNode(" " + photo));
    steps.append(firstStep, node("li", upload), node("li", place), node("li", effect), node("li", v(22)));
    guide.replaceChildren(node("summary", title), steps, node("p", limit));
  }

  function read(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
    catch { return fallback; }
  }

  let legacyShows = read(showKey, []);
  if (!Array.isArray(legacyShows)) legacyShows = [];
  let legacyLayout = read(spatialKey, {});
  let shows = [];
  let layout = {revision: null, photoVersion: null, points: new Map()};
  let walls = [{id: "default", name: ""}];
  let wallId = "default";
  let requestedWall;
  let pickerSignature;
  const wallPath = (id, path = "lighting/projects") => id === "default" ? path : path + "?wall=" + encodeURIComponent(id);
  let playback = {state: "idle"};
  let inventory;
  let signature;
  let draft = {name: "", group: "", steps: []};
  let selected = "";
  let initialized = false;
  let busy = false;
  let reading = false;
  let generation = 0;
  let timer;
  let activePage;
  let players = [];
  let playersUnavailable = false;
  const showText = () => ({
    nl: ["Showbouwer", "Tijdlijn", "Music Assistant", "Speler", "Nummer, afspeellijst of link", "Automatisch", "Nummer", "Afspeellijst", "Album", "Radio", "Zonder muziek", "Kies een Music Assistant-speler uit Home Assistant. De muziek stopt wanneer de show stopt.", "Spelers ophalen mislukt", "Spelers vernieuwen", "Muziek kon niet starten", "Muziek kon niet stoppen", "Dupliceren", "Nieuwe show", "Opgeslagen shows"],
    en: ["Show builder", "Timeline", "Music Assistant", "Player", "Track, playlist or link", "Automatic", "Track", "Playlist", "Album", "Radio", "No music", "Choose a Music Assistant player from Home Assistant. Music stops when the show stops.", "Could not load players", "Refresh players", "Music could not start", "Music could not stop", "Duplicate", "New show", "Saved shows"],
    de: ["Show-Editor", "Zeitleiste", "Music Assistant", "Player", "Titel, Playlist oder Link", "Automatisch", "Titel", "Playlist", "Album", "Radio", "Ohne Musik", "Wähle einen Music Assistant-Player aus Home Assistant. Die Musik stoppt mit der Show.", "Player konnten nicht geladen werden", "Player aktualisieren", "Musik konnte nicht starten", "Musik konnte nicht gestoppt werden", "Duplizieren", "Neue Show", "Gespeicherte Shows"],
    es: ["Editor de espectáculos", "Cronología", "Music Assistant", "Reproductor", "Canción, lista o enlace", "Automático", "Canción", "Lista", "Álbum", "Radio", "Sin música", "Elige un reproductor de Music Assistant en Home Assistant. La música se detiene al terminar el espectáculo.", "No se cargaron los reproductores", "Actualizar reproductores", "No se pudo iniciar la música", "No se pudo detener la música", "Duplicar", "Nuevo espectáculo", "Espectáculos guardados"],
  }[language()]);
  async function refreshShowPlayers() {
    try {
      players = (await api("lighting/projects/music-players")).players;
      playersUnavailable = false;
    } catch {
      playersUnavailable = true;
    }
    if (activePage === "shows" && inventory && initialized) renderShows();
  }
  let gesture;
  let photoElement = node("img");
  const syncStatus = node("p");
  syncStatus.setAttribute("role", "status");
  mount.prepend(syncStatus);
  const t = index => (labels[language()] || labels.nl)[index];
  const g = index => (timingLabels[language()] || timingLabels.nl)[index];
  const e = index => (effectLabels[language()] || effectLabels.nl)[index];
  const radialText = index => (radialLabels[language()] || radialLabels.nl)[index];
  const v = index => (planLabels[language()] || planLabels.nl)[index];
  const ledMaps = new Map();
  const h = index => (houseLabels[language()] || houseLabels.nl)[index];
  const msg = index => (serverLabels[language()] || serverLabels.nl)[index];
  const isPlaying = () => ["playing", "stopping"].includes(playback.state);

  function renderWallPicker() {
    const current = language();
    const signature = JSON.stringify([current, walls, wallId, requestedWall]);
    if (pickerSignature === signature) return;
    pickerSignature = signature;
    const [label, first, nameLabel, add, rename, remove, confirmRemove] = wallLabels[current] || wallLabels.nl;
    const selector = dropdown(walls.map(wall => [wall.id, wall.name || first]), requestedWall ?? wallId);
    selector.setAttribute("aria-label", label);
    selector.onchange = () => {
      if (busy || gesture) {
        selector.value = requestedWall ?? wallId;
        return;
      }
      generation++;
      requestedWall = selector.value;
      wallStatus.textContent = "";
      spatialSection.hidden = true;
      renderWallPicker();
      wallPicker.querySelector("select").focus();
      refresh();
    };
    const name = node("input");
    Object.assign(name, {type: "text", maxLength: 60, required: true});
    const form = node("form", "", "lighting-controls");
    const addButton = node("button", add);
    addButton.type = "submit";
    addButton.disabled = Boolean(requestedWall) || walls.length >= maxWalls;
    form.onsubmit = event => {
      event.preventDefault();
      if (name.value.trim()) change({action: "add_wall", name: name.value}, wallStatus);
    };
    form.append(field(nameLabel, name), addButton, action(rename, () => {
      if (name.reportValidity() && name.value.trim()) {
        return change({action: "rename_wall", name: name.value, revision: layout.revision}, wallStatus);
      }
    }, Boolean(requestedWall)));
    if (wallId !== "default") form.append(action(remove, () => {
      if (window.confirm(confirmRemove)) return change({action: "delete_wall", revision: layout.revision}, wallStatus);
    }, Boolean(requestedWall)));
    wallPicker.replaceChildren(field(label, selector), form, wallStatus);
  }

  function receive(data, focusId) {
    const nextWall = data.wall_id || "default";
    const switched = wallId !== nextWall || Boolean(requestedWall);
    wallId = nextWall;
    requestedWall = undefined;
    walls = data.walls || walls;
    spatialSection.hidden = false;
    renderWallPicker();
    const showsChanged = !initialized || JSON.stringify(shows) !== JSON.stringify(data.shows);
    const layoutChanged = !initialized || switched || layout.revision !== data.layout.revision;
    const refreshPlan = initialized && layoutChanged && !plan.hidden && !savingPlan;
    const runningChanged = !initialized || isPlaying() !== ["playing", "stopping"].includes(data.playback.state)
      || playback.state !== data.playback.state;
    initialized = true;
    shows = data.shows;
    if (switched || layout.photoVersion !== data.layout.photo_version) {
      photoElement = node("img");
      layout.photoVersion = data.layout.photo_version;
      if (layout.photoVersion) photoElement.src = roomPhotoPath(wallId, layout.photoVersion);
    }
    layout.revision = data.layout.revision;
    layout.dimensions = data.layout.dimensions;
    layout.points = new Map(data.layout.points);
    const changed = JSON.stringify(playback) !== JSON.stringify(data.playback);
    playback = data.playback;
    if (changed) {
      updatePlaybackStatus();
      refreshEffectButtons?.();
    }
    if (inventory && (showsChanged || runningChanged)) renderShows();
    if (inventory && layoutChanged) renderSpatial(focusId);
    if (refreshPlan && activePage === "house") renderHouse3d();
  }

  const timingReportLabels = {
    nl: ["Verzendtijden per lamp of groep", "Gepland", "Verzonden", "Opdrachttijd", "Afwijking", "Deze tijden meten het verzenden vanuit de app. Kijk op de muur om te zien wanneer het licht verandert."],
    en: ["Dispatch times by light or group", "Planned", "Sent", "Command time", "Offset", "These timings measure dispatch from the app. Watch the wall to see when the light changes."],
    de: ["Sendezeiten pro Lampe oder Gruppe", "Geplant", "Gesendet", "Befehlsdauer", "Abweichung", "Diese Zeiten messen das Senden aus der App. Beobachte die Wand, um zu sehen, wann sich das Licht ändert."],
    es: ["Tiempos de envío por luz o grupo", "Previsto", "Enviado", "Duración", "Desviación", "Los tiempos miden el envío desde la app. Observa la pared para ver cuándo cambia la luz."],
  };

  function updatePlaybackStatus() {
    const state = playback.state;
    if (state === "idle") {
      for (const details of reports) details.hidden = true;
      return;
    }
    const spatial = playback.kind === "spatial";
    const gradient = playback.effect === "gradient";
    const radial = radialModes[playback.effect];
    const effectName = radial !== undefined ? radialText(radial) : gradient ? g(1) : e(0);
    const headline = state === "playing" ? (spatial && playback.step === 0 ? (gradient ? g(8) : e(15))
      : t(12) + " " + playback.step + " / " + playback.total)
      : state === "stopping" ? (spatial ? effectName + " · " + t(10) + "…" : msg(6))
      : spatial ? (gradient ? g({complete: 5, stopped: 6, failed: 7}[state]) : e({complete: 12, stopped: 13, failed: 14}[state]))
      : t({complete: 13, stopped: 14, failed: 15}[state]);
    const musicStatus = ({nl:["Muziektest speelt", "Muziektest klaar", "Muziektest gestopt", "Muziektest mislukt"], en:["Music test playing", "Music test complete", "Music test stopped", "Music test failed"], de:["Musiktest läuft", "Musiktest beendet", "Musiktest gestoppt", "Musiktest fehlgeschlagen"], es:["Prueba de música en curso", "Prueba de música completada", "Prueba de música detenida", "Error en la prueba de música"]})[language()];
    const status = [playback.kind === "music" && state !== "stopping" ? musicStatus[{playing:0, complete:1, stopped:2, failed:3}[state]] : headline, playback.music_error && showText()[playback.music_error === "start" ? 14 : 15], playback.uncertain && t(16), playback.partial && t(35)].filter(Boolean).join(" · ");
    showStatus.textContent = spatial && isPlaying() ? effectName + " · " + status : spatial ? "" : status;
    effectStatus.textContent = spatial ? (radial !== undefined && state !== "stopping" ? effectName + " · " + status : status)
      : isPlaying() ? t(0) + " · " + status : "";
    const names = new Map((inventory?.lights || []).map(light => [light.id, light.name]));
    for (const [id, group] of Object.entries(inventory?.spatial_groups || {})) names.set(id, group.name);
    for (const [index, details] of reports.entries()) {
      const last = playback.last;
      details.hidden = !last || spatial !== Boolean(index);
      if (details.hidden) continue;
      const label = result => ({accepted: e(16), skipped: e(17), failed: e(18), unconfirmed: t(16)})[result] || result;
      const list = node("ul");
      for (const [id, commands] of Object.entries(last.results)) {
        list.append(node("li", (names.get(id) || t(31)) + " · " + Object.values(commands).map(label).join(" / ")));
      }
      details.replaceChildren(node("summary", e(10) + " " + last.step + " · " + e(11) + " " + last.milliseconds + " ms"), list);
      if (spatial && playback.timing?.length) {
        const [title, planned, sent, duration, offset, help] = timingReportLabels[language()] || timingReportLabels.nl;
        const times = node("ol");
        for (const row of playback.timing) {
          const difference = row.sent_ms - row.planned_ms;
          times.append(node("li", [
            names.get(row.lamp) || t(31), planned + " " + row.planned_ms + " ms",
            sent + " " + row.sent_ms + " ms", duration + " " + row.command_ms + " ms",
            offset + " " + (difference > 0 ? "+" : "") + difference + " ms",
          ].join(" · ")));
        }
        details.append(node("h4", title), node("p", help), times);
      }
    }
  }

  async function refresh() {
    if (busy || reading || gesture || (mount.hidden && house.hidden)) return;
    reading = true;
    const request = generation;
    try {
      const data = await api(wallPath(requestedWall ?? wallId));
      if (request !== generation || gesture) return;
      if (!initialized || syncStatus.textContent === msg(1)) syncStatus.textContent = "";
      receive(data);
    } catch {
      if (request === generation) syncStatus.textContent = msg(1);
    } finally {
      reading = false;
    }
  }

  async function change(body, status, focusId) {
    if (busy || requestedWall) return;
    busy = true;
    generation++;
    try {
      const data = await api(wallPath(wallId), body);
      status.textContent = "";
      receive(data, focusId);
      return data;
    } catch (error) {
      status.textContent = error.message === "project_conflict" ? msg(5) : t(25);
    } finally {
      busy = false;
    }
  }

  function action(caption, handle, disabled = false) {
    const button = node("button", caption);
    button.type = "button";
    button.disabled = disabled;
    button.onclick = handle;
    return button;
  }

  function dropdown(pairs, selectedValue, placeholder) {
    const select = node("select");
    if (placeholder) select.add(new Option(placeholder, ""));
    for (const [id, name] of pairs) select.add(new Option(name, id));
    select.value = selectedValue;
    return select;
  }

  const scenes = group => Object.entries(inventory.scenes || {})
    .filter(([, scene]) => scene.group === group)
    .map(([id, scene]) => [id, scene.name]);

  function valid(show) {
    return show.steps.length > 0 && show.steps.every(step => {
      const group = step.group || show.group;
      return inventory.groups?.[group] && inventory.scenes?.[step.scene]?.group === group;
    });
  }

  function renderShows() {
    const labels = showText();
    const list = node("div", "", "lighting-show-library");
    list.append(node("h3", labels[18]));
    const openDraft = show => {
      draft = {
        ...show,
        steps: show.steps.map(step => ({...step, group: step.group || show.group})),
        music: show.music ? {...show.music} : null,
      };
      renderShows();
      showSection.querySelector("form input")?.focus();
    };
    for (const show of shows) {
      const card = node("article", "", "lighting-card");
      const playable = valid(show);
      const groupNames = [...new Set(show.steps.map(step => inventory.groups?.[step.group || show.group]?.name))];
      card.append(node("h4", show.name), node("p", playable ? groupNames.join(" · ") : t(34)),
        action(t(9), () => change({action: "play", id: show.id}, showStatus), isPlaying() || !playable),
        action(t(29), () => openDraft(show), isPlaying()),
        action(labels[16], () => openDraft({...show, id: undefined, revision: undefined}), isPlaying() || shows.length >= maxShows),
        action(t(7), async () => {
          if (!window.confirm(t(7) + " · " + show.name + "?")) return;
          if (await change({action: "delete", id: show.id, revision: show.revision}, showStatus)) {
            if (draft.id === show.id) draft = {name: "", group: "", steps: []};
            renderShows();
          }
        }, isPlaying()));
      if (show.music) card.append(node("p", show.music.media_id));
      list.append(card);
    }

    const groups = Object.entries(inventory.groups || {}).filter(([id]) => scenes(id).length)
      .map(([id, group]) => [id, group.name]);
    const form = node("form", "", "lighting-show-form");
    if (groups.length && !isPlaying()) {
      if (!groups.some(([id]) => id === draft.group)) draft.group = groups[0][0];
      const name = node("input");
      name.maxLength = 60;
      name.required = true;
      name.value = draft.name;
      name.oninput = () => { draft.name = name.value; };
      const group = dropdown(groups, draft.group);
      group.onchange = () => {
        draft.group = group.value;
        renderShows();
      };
      form.append(node("h3", draft.id ? draft.name : labels[17]), field(t(1), name), field(t(27), group));
      const music = node("fieldset", "", "lighting-show-music");
      music.append(node("legend", labels[2]), node("p", labels[11]));
      const playerChoices = players.map(item => [item.id, item.name]);
      if (draft.music?.player && !playerChoices.some(([id]) => id === draft.music.player)) {
        playerChoices.push([draft.music.player, draft.music.player]);
      }
      const player = dropdown(playerChoices, draft.music?.player || "", labels[10]);
      player.setAttribute("aria-label", labels[3]);
      player.onchange = () => {
        draft.music = player.value ? {...draft.music, player: player.value} : null;
        renderShows();
      };
      music.append(field(labels[3], player), action(labels[13], refreshShowPlayers));
      if (playersUnavailable) music.append(node("p", labels[12]));
      else if (!players.length) music.append(node("p", ({nl:"Geen spelers gevonden. Voeg de Music Assistant-integratie toe in Home Assistant.", en:"No players found. Add the Music Assistant integration in Home Assistant.", de:"Keine Player gefunden. Füge die Music Assistant-Integration in Home Assistant hinzu.", es:"No se encontraron reproductores. Añade la integración Music Assistant en Home Assistant."})[language()]));
      if (draft.music) {
        const media = Object.assign(node("input"), {required: true, maxLength: 500, value: draft.music.media_id || ""});
        media.oninput = () => {
          draft.music.media_id = media.value;
          preview.disabled = !media.value.trim();
        };
        const type = dropdown([["track", labels[6]], ["playlist", labels[7]], ["album", labels[8]], ["radio", labels[9]]],
          draft.music.media_type || "", labels[5]);
        type.onchange = () => { draft.music.media_type = type.value; };
        const preview = action(({nl:"Test muziek", en:"Test music", de:"Musik testen", es:"Probar música"})[language()], () => {
          change({action: "preview_music", music: draft.music}, showStatus);
        }, !media.value.trim());
        music.append(field(labels[4], media), field(labels[5], type), preview);
      }
      form.append(music);
      const duration = node("span");
      const updateDuration = () => {
        const total = draft.steps.reduce((sum, step) => sum + (step.seconds || 0), 0);
        duration.textContent = Math.floor(total / 60) + ":" + String(total % 60).padStart(2, "0");
      };
      updateDuration();
      const timeline = node("div", "", "lighting-heading");
      timeline.append(node("h3", labels[1]), duration);
      form.append(timeline);
      const available = scenes(draft.group);
      draft.steps.forEach((step, index) => {
        const row = node("div", "", "lighting-controls lighting-show-step");
        const target = dropdown(groups, step.group || draft.group, t(27));
        target.setAttribute("aria-label", t(27));
        target.onchange = () => {
          step.group = target.value;
          step.scene = scenes(target.value)[0]?.[0] || "";
          renderShows();
        };
        const scene = dropdown(scenes(step.group || draft.group), step.scene, t(2));
        scene.required = true;
        scene.onchange = () => { step.scene = scene.value; };
        const seconds = node("input");
        Object.assign(seconds, {type: "number", min: "1", max: "300", required: true, value: step.seconds});
        seconds.oninput = () => { step.seconds = seconds.valueAsNumber; updateDuration(); };
        const move = offset => {
          const next = index + offset;
          [draft.steps[index], draft.steps[next]] = [draft.steps[next], draft.steps[index]];
          renderShows();
        };
        row.append(node("strong", String(index + 1)), field(t(27), target), field(t(2), scene), field(t(3), seconds),
          action(t(5), () => move(-1), index === 0),
          action(t(6), () => move(1), index === draft.steps.length - 1),
          action(t(7), () => { draft.steps.splice(index, 1); renderShows(); }));
        form.append(row);
      });
      const controls = node("div", "", "lighting-controls");
      const submit = node("button", t(8));
      submit.type = "submit";
      controls.append(action(t(4), () => {
        draft.steps.push({group: draft.group, scene: available[0][0], seconds: 3});
        renderShows();
      }, !available.length || draft.steps.length >= maxSteps), submit);
      if (draft.id) controls.append(action(t(28), () => {
        draft = {name: "", group: "", steps: []};
        renderShows();
      }));
      form.append(controls);
      form.onsubmit = async event => {
        event.preventDefault();
        const name = draft.name.trim();
        if (!name || !valid(draft) || (!draft.id && shows.length >= maxShows) ||
            draft.steps.some(step => !Number.isInteger(step.seconds) || step.seconds < 1 || step.seconds > 300)) {
          showStatus.textContent = t(30);
          return;
        }
        const show = {...draft, name, music: draft.music ? {...draft.music, media_id: (draft.music.media_id || "").trim()} : null};
        submit.disabled = true;
        try {
          if (await change({...show, action: "save"}, showStatus)) {
            draft = {name: "", group: show.group, steps: []};
            renderShows();
          }
        } finally {
          submit.disabled = false;
        }
      };
    } else if (!isPlaying()) {
      form.append(node("p", t(11)));
    }
    const header = node("div", "", "lighting-heading");
    header.append(node("h2", labels[0]));
    if (isPlaying()) header.append(action(t(10), () => change({action: "stop"}, showStatus), playback.state === "stopping"));
    const editor = node("div", "", "lighting-show-editor");
    editor.append(form, list);
    showSection.replaceChildren(header, node("p", t(26)), showStatus, reports[0], editor);
    if (legacyShows.length || legacyLayout.photo) showSection.append(action(msg(2), () => migrate()));
  }

  async function importPhoto(file) {
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 15 * 1024 * 1024) {
      throw new Error("invalid_photo");
    }
    const source = URL.createObjectURL(file);
    try {
      const image = new Image();
      image.src = source;
      await image.decode();
      const canvas = node("canvas");
      const scale = Math.min(1, 1280 / Math.max(image.naturalWidth, image.naturalHeight));
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
      const context = canvas.getContext("2d");
      context.fillStyle = "#161b22";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      for (const quality of [0.82, 0.7, 0.55, 0.4]) {
        const encoded = canvas.toDataURL("image/jpeg", quality).split(",")[1];
        if (encoded?.length <= 600000) return encoded;
      }
      throw new Error("invalid_photo");
    } finally {
      URL.revokeObjectURL(source);
    }
  }

  async function migrate(status = showStatus) {
    const targetWall = wallId;
    const body = {action: "import", shows: legacyShows, points: legacyLayout.points || []};
    if (!layout.photoVersion && /^data:image\/jpeg;base64,/.test(legacyLayout.photo || "")) {
      try {
        body.photo = await importPhoto(await (await fetch(legacyLayout.photo)).blob());
      } catch {
        status.textContent = t(24);
        return;
      }
    }
    if (targetWall !== wallId || requestedWall) return;
    const data = await change(body, status);
    if (!data) return;
    if (!legacyLayout.photo || data.imported_photo) {
      legacyLayout = {};
      try { localStorage.removeItem(spatialKey); } catch {}
    }
    legacyShows = [];
    try { localStorage.removeItem(showKey); } catch {}
    status.textContent = legacyLayout.photo ? msg(4) : msg(3);
    renderShows();
    renderSpatial();
  }

  function updateLayout(points, options = {}, focusId) {
    return change({action: "layout", revision: layout.revision, points: [...points], ...options},
      spatialStatus, focusId);
  }

  const defaultSize = 12;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  function setPosition(id, x, y, size = defaultSize, focusId = id) {
    const point = [clamp(x, 0, 100), clamp(y, 0, 100), clamp(size, 4, 40)];
    const [, , , advance = 0, angle = 0, width] = wallPoints().get(id) || [];
    if (width !== undefined) point[0] = clamp(x, width / 2, 100 - width / 2);
    if (advance || angle || width !== undefined) point.push(advance);
    if (angle || width !== undefined) point.push(angle);
    if (width !== undefined) point.push(width);
    return saveWallPoint(id, point, focusId);
  }

  function wallGroupOwners() {
    const owners = new Map();
    for (const [id, group] of Object.entries(inventory.spatial_groups || {})) {
      for (const member of group.members) if (!owners.has(member)) owners.set(member, id);
    }
    return owners;
  }

  function wallPoints(source = layout.points) {
    const owners = wallGroupOwners();
    const points = new Map(source);
    for (const [id, point] of source) {
      const group = owners.get(id);
      if (!group) continue;
      if (!points.has(group)) points.set(group, point);
      points.delete(id);
    }
    return points;
  }

  function saveWallPoint(id, point, focusId) {
    const points = new Map(layout.points);
    const owners = wallGroupOwners();
    for (const key of points.keys()) if (owners.get(key) === id) points.delete(key);
    if (point) points.set(id, point);
    else points.delete(id);
    return updateLayout(points, {}, focusId);
  }

  function roomPhotoPath(id, version) {
    return wallPath(id, "lighting/projects/photo") + (id === "default" ? "?" : "&") + "v=" + encodeURIComponent(version);
  }

  function ledCoordinates(light) {
    const cached = ledMaps.get(light.id);
    if (cached && cached.until > Date.now()) return cached.result;
    const [, identifier] = JSON.parse(light.id);
    const grouped = Boolean(light.members);
    const query = encodeURIComponent(grouped ? identifier.slice("twinkly:".length) : identifier);
    const entry = {until: Infinity};
    entry.result = api((grouped ? "group-layout?id=" : "layout?id=") + query).then(data => {
      if (grouped) return (data.members || []).flatMap(member => member.points.map(point => point.slice(0, 2)));
      if (!data.layout || data.layout.synthesized) return [];
      const settings = data.settings || {};
      const angle = (settings.rotation || 0) * Math.PI / 180;
      const cos = Math.cos(angle), sin = Math.sin(angle);
      return data.layout.points.map(([, x, y]) => {
        x *= settings.mirror_x ? -1 : 1;
        y *= settings.mirror_y ? -1 : 1;
        return [x * cos - y * sin, x * sin + y * cos];
      });
    }).catch(() => []).then(points => {
      const clean = points.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
      entry.until = Date.now() + (clean.length ? 120000 : 15000);
      return clean;
    });
    ledMaps.set(light.id, entry);
    return entry.result;
  }

  function ledDrawing(light, showStatus) {
    const frame = node("span", "", "house-led-map");
    const drawing = node("canvas");
    drawing.width = drawing.height = 160;
    drawing.setAttribute("aria-hidden", "true");
    const label = node("small", v(9));
    frame.title = v(9);
    frame.append(drawing);
    if (showStatus) frame.append(label);
    ledCoordinates(light).then(points => {
      const ctx = drawing.getContext("2d");
      if (points.length) {
        let xmin = Infinity, ymin = Infinity, xmax = -Infinity, ymax = -Infinity;
        for (const [x, y] of points) {
          xmin = Math.min(xmin, x); ymin = Math.min(ymin, y);
          xmax = Math.max(xmax, x); ymax = Math.max(ymax, y);
        }
        const dx = xmax - xmin, dy = ymax - ymin;
        const scale = 144 / (Math.max(dx, dy) || 1);
        ctx.fillStyle = "#ffe6a5";
        for (const [x, y] of points) {
          ctx.fillRect(79 + (x - xmin - dx / 2) * scale, 79 + (y - ymin - dy / 2) * scale, 3, 3);
        }
      }
      frame.dataset.ledCount = String(points.length);
      frame.title = label.textContent = points.length ? points.length + " · " + v(7) : v(8);
    });
    return frame;
  }

  let showCeilings = false;
  let ceilingRoom = "";
  let ceilingLamp = "";
  let planResize;
  let planGeneration = 0;
  let planWall;
  let planRoom = "";
  let treeRoom;
  let treeEditorOpen = false;
  let savingPlan = false;
  const camera = {yaw: 28, pitch: -15, zoom: null};
  const planPath = "lighting/projects/overview";
  const roomLabel = (room, names) => names?.[room] || v(12) + " " + (room + 1);
  const wallPixelsPerMeter = 65;

  const treeLabels = {
    nl: ["3D-kerstboom", "Kamer voor de kerstboom", "Boom links/rechts (m)", "Boom voor/achter (m)", "Hoogte kerstboom (m)", "Draaihoek kerstboom (°)", "Kerstboom plaatsen", "Kerstboom opslaan", "Kerstboom verwijderen", "Kerstboom opgeslagen", "Kerstboom verwijderd"],
    en: ["3D Christmas tree", "Room for the tree", "Tree left/right (m)", "Tree front/back (m)", "Tree height (m)", "Tree angle (°)", "Place tree", "Save tree", "Remove tree", "Tree saved", "Tree removed"],
    de: ["3D-Weihnachtsbaum", "Raum für den Baum", "Baum links/rechts (m)", "Baum vorne/hinten (m)", "Baumhöhe (m)", "Baumwinkel (°)", "Baum platzieren", "Baum speichern", "Baum entfernen", "Baum gespeichert", "Baum entfernt"],
    es: ["Árbol de Navidad 3D", "Habitación para el árbol", "Árbol izquierda/derecha (m)", "Árbol delante/detrás (m)", "Altura del árbol (m)", "Ángulo del árbol (°)", "Colocar árbol", "Guardar árbol", "Quitar árbol", "Árbol guardado", "Árbol eliminado"],
  };
  const treeText = index => (treeLabels[language()] || treeLabels.nl)[index];
  const treeWidthRatio = 290 / 478;

  function roomFootprint(walls, room) {
    const widths = [[], []];
    for (const wall of walls) {
      if (Math.floor(wall.slot / 4) === room && wall.dimensions) {
        widths[wall.slot % 2].push(wall.dimensions.width_m);
      }
    }
    const width = Math.max(0, ...widths[0]);
    const depth = Math.max(0, ...widths[1]);
    return {width: width || depth || 4, depth: depth || width || 4};
  }

  function wallTransform(slot, placement, footprint) {
    if (!placement) {
      const depth = slot % 2 ? footprint.width : footprint.depth;
      return "rotateY(" + (slot % 4) * 90 + "deg) translateZ(" + depth * wallPixelsPerMeter / 2 + "px)";
    }
    return "translate3d(" + placement.x_m * wallPixelsPerMeter + "px,0," + placement.z_m * wallPixelsPerMeter +
      "px) rotateY(" + placement.angle + "deg)";
  }

  function showDimensions(dimensions) {
    const format = new Intl.NumberFormat(language(), {maximumFractionDigits: 2});
    return format.format(dimensions.width_m) + " × " + format.format(dimensions.height_m) + " m";
  }

  function homeRooms(snapshot) {
    const groups = Object.entries(inventory?.groups || {}).filter(([, group]) => group.kind === "room");
    const links = {...snapshot.room_groups};
    const occupied = new Set([...snapshot.walls.map(wall => Math.floor(wall.slot / 4)),
      ...Object.keys(snapshot.room_names || {}).map(Number), ...Object.keys(snapshot.trees || {}).map(Number)]);
    for (const [id, group] of groups) {
      if (Object.values(links).includes(id)) continue;
      const matching = [...occupied].find(room => !(room in links) && snapshot.room_names?.[room]?.toLowerCase() === group.name.toLowerCase());
      const free = Array.from({length: planSlots / 4}, (_, room) => room).find(room => !occupied.has(room) && !(room in links));
      const room = matching ?? free;
      if (room !== undefined) links[room] = id;
    }
    return {links, groups: new Map(groups)};
  }

  function planPlacement(snapshot, walls, onSaved, isFloor = false) {
    if (!snapshot.revision) return undefined;
    let selectedWall = isFloor ? floorWall : planWall;
    const wallNames = walls.map(wall => [wall.id, wall.name || (wallLabels[language()] || wallLabels.nl)[1]]);
    if (!walls.some(wall => wall.id === selectedWall)) selectedWall = walls.find(wall => wall.id === wallId)?.id || walls[0].id;
    const selectWall = dropdown(wallNames, selectedWall);
    const {links, groups} = homeRooms(snapshot);
    const names = {...snapshot.room_names};
    for (const [room, id] of Object.entries(links)) if (groups.has(id)) names[room] = groups.get(id).name;
    const slots = Array.from({length: planSlots}, (_, slot) => [String(slot),
      roomLabel(Math.floor(slot / 4), names) + " · " + v(13 + slot % 4)]);
    const currentWall = () => walls.find(wall => wall.id === selectedWall);
    const destination = dropdown(slots, String(currentWall().slot));
    const coordinate = (limit, step) => Object.assign(node("input"),
      {type: "number", min: -limit, max: limit, step, required: true});
    const x = coordinate(20, .01), z = coordinate(20, .01), angle = coordinate(180, 1);
    const roomName = Object.assign(node("input"), {type: "text", maxLength: 60});
    const destinationRoom = () => Math.floor(Number(destination.value) / 4);
    const link = dropdown([["", "—"], ...[...groups].map(([id, group]) => [id, group.name])], "");
    const savedRoomName = () => snapshot.room_names?.[destinationRoom()] || "";
    const fillRoomName = () => {
      link.value = groups.has(links[destinationRoom()]) ? links[destinationRoom()] : "";
      roomName.value = savedRoomName();
      roomName.placeholder = roomLabel(destinationRoom());
    };
    let custom;
    const transform = () => ({x_m: x.valueAsNumber, z_m: z.valueAsNumber, angle: angle.valueAsNumber});
    const inputs = [x, z, angle];
    const validCoordinates = () => inputs.every(input => input.validity.valid);
    const preview = () => {
      if (isFloor) return;
      for (const face of plan.querySelectorAll(".house-3d-wall")) {
        const original = walls.find(wall => wall.id === face.dataset.wall);
        if (!original) continue;
        const editing = original.id === selectedWall && original.slot === Number(destination.value) && validCoordinates();
        face.style.transform = wallTransform(original.slot, editing ? (custom ? transform() : null) : original.placement,
          roomFootprint(walls, Math.floor(original.slot / 4)));
      }
    };
    const fill = placement => {
      custom = Boolean(placement);
      const side = Number(destination.value) % 4;
      const {width, depth} = roomFootprint(walls, destinationRoom());
      x.value = placement?.x_m ?? [0, width / 2, 0, -width / 2][side];
      z.value = placement?.z_m ?? [depth / 2, 0, -depth / 2, 0][side];
      angle.value = placement?.angle ?? [0, 90, 180, -90][side];
      preview();
    };
    for (const input of inputs) input.oninput = () => { custom = true; preview(); };
    destination.onchange = () => {
      fill(Number(destination.value) === currentWall().slot ? currentWall().placement : null);
      fillRoomName();
    };
    const feedback = node("p");
    feedback.setAttribute("role", "status");
    const form = node("form", "", "house-3d-placement");
    const save = node("button", t(8));
    save.type = "submit";
    const reset = action(placementLabel(3), () => fill(null));
    form.onsubmit = async event => {
      event.preventDefault();
      if (savingPlan) return;
      savingPlan = true;
      const body = {wall: selectedWall, slot: Number(destination.value), revision: snapshot.revision};
      if (custom || currentWall().placement) body.placement = custom ? transform() : null;
      if (roomName.value.trim() !== savedRoomName()) body.room_name = roomName.value.trim();
      if (link.value || snapshot.room_groups?.[destinationRoom()]) body.room_group = link.value || null;
      const controls = [selectWall, destination, ...inputs, roomName, link, save, reset];
      controls.forEach(control => { control.disabled = true; });
      try {
        const updated = await api(planPath, body);
        onSaved(updated);
      } catch (error) {
        if (error.message === "project_conflict") {
          if (isFloor && !floorPlan.hidden) renderFloorPlan(undefined, msg(5));
          if (!isFloor && !plan.hidden) renderHouse3d(undefined, msg(5));
        } else {
          feedback.textContent = t(25);
        }
      } finally {
        savingPlan = false;
        controls.forEach(control => { control.disabled = false; });
      }
    };
    selectWall.onchange = () => {
      selectedWall = selectWall.value;
      if (isFloor) floorWall = selectedWall;
      else planWall = selectedWall;
      destination.value = String(currentWall().slot);
      fill(currentWall().placement);
      fillRoomName();
    };
    const row = node("div", "", "lighting-controls");
    row.append(field(v(10), selectWall), field(v(11), destination), field(placementLabel(5), roomName),
      field(placementLabel(0), x), field(placementLabel(1), z), field(placementLabel(2), angle), save, reset);
    if (groups.size) row.append(field(({nl:"Kamer op Home",en:"Room on Home",de:"Raum auf Home",es:"Habitación en Inicio"})[language()] || "Room on Home", link));
    fill(currentWall().placement);
    fillRoomName();
    form.append(row, node("p", v(20)), feedback);
    return form;
  }

  function renderTree(model, tree) {
    model.hidden = !tree;
    if (!tree) return;
    if (!model.firstChild) {
      for (const angle of [0, 60, 120]) {
        const image = node("img");
        Object.assign(image, {src: "product-photo/pre-lit-tree", alt: "", draggable: false});
        image.style.transform = "rotateY(" + angle + "deg)";
        model.append(image);
      }
    }
    const height = tree.height_m * wallPixelsPerMeter;
    model.style.width = height * treeWidthRatio + "px";
    model.style.height = height + "px";
    model.style.transform = "translate3d(calc(-50% + " + tree.x_m * wallPixelsPerMeter + "px),0," +
      tree.z_m * wallPixelsPerMeter + "px) rotateY(" + tree.angle + "deg)";
  }

  function treePlacement(snapshot, models) {
    const roomIds = [...models.keys()];
    if (!roomIds.includes(treeRoom)) treeRoom = roomIds[0];
    const trees = snapshot.trees || {};
    const room = dropdown(roomIds.map(id => [String(id), roomLabel(id, snapshot.room_names)]), String(treeRoom));
    const number = (min, max, step) => Object.assign(node("input"), {type: "number", min, max, step, required: true});
    const inputs = [number(-20, 20, .01), number(-20, 20, .01), number(.5, 5, .01), number(-180, 180, 1)];
    const fields = ["x_m", "z_m", "height_m", "angle"];
    const placement = () => Object.fromEntries(fields.map((key, index) => [key, inputs[index].valueAsNumber]));
    const panel = node("details", "", "house-tree-editor");
    panel.open = treeEditorOpen;
    panel.ontoggle = () => {
      if (!panel.isConnected) return;
      treeEditorOpen = panel.open;
      if (!panel.open) renderTree(models.get(treeRoom), trees[treeRoom]);
    };
    const form = node("form", "", "lighting-controls");
    const save = node("button");
    save.type = "submit";
    const remove = action(treeText(8), () => commit(null));
    const feedback = node("p");
    feedback.setAttribute("role", "status");
    const fill = () => {
      const tree = trees[treeRoom] || {x_m: 0, z_m: 0, height_m: 2, angle: 0};
      fields.forEach((key, index) => { inputs[index].value = tree[key]; });
      save.textContent = treeText(trees[treeRoom] ? 7 : 6);
      remove.hidden = !trees[treeRoom];
    };
    const preview = () => {
      if (inputs.every(input => input.validity.valid)) renderTree(models.get(treeRoom), placement());
    };
    room.onchange = () => {
      renderTree(models.get(treeRoom), trees[treeRoom]);
      treeRoom = Number(room.value);
      fill();
    };
    async function commit(tree) {
      if (savingPlan) return;
      savingPlan = true;
      const controls = [room, ...inputs, save, remove];
      controls.forEach(control => { control.disabled = true; });
      try {
        const response = await api(planPath + "/tree", {room: treeRoom, tree, revision: snapshot.revision});
        if (!plan.hidden) renderHouse3d(response, treeText(tree ? 9 : 10), ".house-tree-editor summary");
      } catch (error) {
        if (error.message === "project_conflict" && !plan.hidden) renderHouse3d(undefined, msg(5));
        else feedback.textContent = t(25);
      } finally {
        savingPlan = false;
        controls.forEach(control => { control.disabled = false; });
      }
    }
    form.onsubmit = event => { event.preventDefault(); commit(placement()); };
    for (const input of inputs) input.oninput = preview;
    fill();
    form.append(field(treeText(1), room), ...inputs.map((input, index) => field(treeText(index + 2), input)), save, remove);
    panel.append(node("summary", treeText(0)), form, feedback);
    return panel;
  }

  const floorWords = {
    nl: ["2D-plattegrond", "Sleep muren naar hun plek. Kies een kamer om de lampen te bedienen.", "Lampen in", "Geen lampen op de muren van deze kamer.", "Verplaats"],
    en: ["2D floor plan", "Drag walls into place. Select a room to control its lights.", "Lights in", "No lights on the walls of this room.", "Move"],
    de: ["2D-Grundriss", "Wände ziehen. Wähle einen Raum, um seine Lampen zu steuern.", "Lampen in", "Keine Lampen an den Wänden dieses Raums.", "Verschieben"],
    es: ["Plano 2D", "Arrastra las paredes. Elige una habitación para controlar sus luces.", "Luces en", "No hay luces en las paredes de esta habitación.", "Mover"],
  };
  const floorText = index => (floorWords[language()] || floorWords.nl)[index];
  let floorRoom;
  let floorWall;
  let floorGeneration = 0;

  function roomBoxes(ids, walls, saved = {}) {
    const footprints = ids.map(id => roomFootprint(walls, id));
    const spacing = Math.max(4, ...footprints.map(({width, depth}) => Math.max(width, depth))) + 1;
    const columns = Math.ceil(Math.sqrt(ids.length));
    return ids.map((id, index) => ({id, ...footprints[index],
      ...(saved[id] || {x_m:(index % columns) * spacing, z_m:Math.floor(index / columns) * spacing})}));
  }

  async function renderFloorPlan(snapshot, message = "") {
    const request = ++floorGeneration;
    const status = node("p", message);
    status.setAttribute("role", "status");
    try {
      snapshot ??= await api(planPath);
      if (request !== floorGeneration || floorPlan.hidden) return;
      const walls = snapshot.walls;
      floorPlan.replaceChildren(node("h3", floorText(0)), node("p", floorText(1)), status);
      const {links, groups} = homeRooms(snapshot);
      const ids = [...new Set([...walls.map(wall => Math.floor(wall.slot / 4)),
        ...Object.keys(links).filter(room => groups.has(links[room])).map(Number)])];
      if (!ids.length) return;
      if (!ids.includes(floorRoom)) floorRoom = ids[0];
      const roomName = id => groups.get(links[id])?.name || roomLabel(id, snapshot.room_names);
      const update = updated => {
        if (!floorPlan.hidden) renderFloorPlan(updated, v(21));
        if (!plan.hidden) renderHouse3d(updated);
      };
      if (walls.length && snapshot.revision) floorPlan.append(planPlacement(snapshot, walls, update, true));
      if (snapshot.revision && ids.length > 1) {
        const [heading, move] = ({
          nl:["Plattegrond van het huis", "Verplaats kamer"], en:["Whole-house plan", "Move room"],
          de:["Hausgrundriss", "Raum verschieben"], es:["Plano de la casa", "Mover habitación"],
        })[language()] || ["Whole-house plan", "Move room"];
        const map = node("div", "", "house-room-map");
        floorPlan.append(node("h4", heading), map);
        const view = node("div", "", "house-room-map-grid");
        map.append(view);
        const boxes = roomBoxes(ids, walls, snapshot.room_positions);
        const left = Math.min(...boxes.map(b => b.x_m - b.width / 2)) - 5;
        const top = Math.min(...boxes.map(b => b.z_m - b.depth / 2)) - 5;
        const pixels = 32;
        view.style.width = Math.ceil(pixels * (Math.max(...boxes.map(b => b.x_m + b.width / 2)) - left + 5)) + "px";
        view.style.height = Math.ceil(pixels * (Math.max(...boxes.map(b => b.z_m + b.depth / 2)) - top + 5)) + "px";
        for (const box of boxes) {
          const button = action(roomName(box.id), () => selectRoom(box.id));
          button.className = "house-room-map-tile";
          button.setAttribute("aria-label", move + " · " + roomName(box.id));
          const draw = (x, z) => Object.assign(button.style, {left:(x - left) * pixels + "px", top:(z - top) * pixels + "px"});
          Object.assign(button.style, {width:box.width * pixels + "px", height:box.depth * pixels + "px"});
          draw(box.x_m, box.z_m);
          view.append(button);
          const moveRoom = async (x, z) => {
            if (savingPlan) return;
            savingPlan = true;
            try {
              await api(planPath + "/room", {room:box.id, x_m:x, z_m:z, revision:snapshot.revision}).then(update);
            } catch (error) {
              if (error.message === "project_conflict") renderFloorPlan(undefined, msg(5));
              else { draw(box.x_m, box.z_m); status.textContent = t(25); }
            } finally { savingPlan = false; }
          };
          const adjusted = (dx, dz) => [box.x_m + dx, box.z_m + dz].map(value => clamp(Math.round(value * 4) / 4, -40, 40));
          button.onkeydown = event => {
            const offset = {ArrowLeft:[-.25,0],ArrowRight:[.25,0],ArrowUp:[0,-.25],ArrowDown:[0,.25]}[event.key];
            if (!offset) return;
            event.preventDefault();
            moveRoom(...adjusted(...offset));
          };
          button.onpointerdown = event => {
            if (!event.isPrimary || event.button !== 0 || gesture || savingPlan) return;
            gesture = button;
            let destination;
            button.setPointerCapture(event.pointerId);
            button.onpointermove = move => {
              if (gesture !== button || move.pointerId !== event.pointerId) return;
              const dx = move.clientX - event.clientX, dz = move.clientY - event.clientY;
              if (Math.hypot(dx, dz) < 4 && !destination) return;
              destination = adjusted(dx / pixels, dz / pixels);
              draw(...destination);
            };
            button.onpointerup = button.onpointercancel = button.onlostpointercapture = end => {
              if (gesture !== button || end.pointerId !== event.pointerId) return;
              gesture = undefined;
              if (destination && end.type === "pointerup") moveRoom(...destination);
              else draw(box.x_m, box.z_m);
            };
          };
        }
      }
      const areas = node("div", "", "house-floor-rooms");
      const lamps = node("div", "", "house-floor-lamps");
      floorPlan.append(areas, lamps);
      function selectRoom(id) {
        floorRoom = id;
        for (const button of areas.querySelectorAll("[data-room]")) {
          button.setAttribute("aria-pressed", String(Number(button.dataset.room) === id));
        }
        lamps.replaceChildren(node("h4", floorText(2) + " " + roomName(id)));
        const group = groups.get(links[id]);
        const ids = new Set(group?.members || []);
        if (!group) for (const points of [snapshot.ceiling_lights?.[id] || [],
          ...walls.filter(item => Math.floor(item.slot / 4) === id).map(wall => wall.points)]) {
          for (const [lightId] of points) {
            for (const member of inventory?.spatial_groups?.[lightId]?.members || [lightId]) ids.add(member);
          }
        }
        const lights = (inventory?.lights || []).filter(light => ids.has(light.id));
        if (lights.length) {
          const feedback = node("p");
          feedback.setAttribute("role", "status");
          for (const light of lights) {
            const card = node("article");
            card.append(node("h5", light.name));
            roomLightControls(card, light, feedback);
            lamps.append(card);
          }
          lamps.append(feedback);
        } else lamps.append(node("p", floorText(3)));
      }
      for (const id of ids) {
        const area = node("article");
        const label = action(roomName(id), () => selectRoom(id));
        label.dataset.room = id;
        const canvas = node("div", "", "house-floor-canvas");
        const assignments = node("div", "", "lighting-controls");
        area.append(label, canvas, assignments);
        areas.append(area);
        const footprint = roomFootprint(walls, id);
        const assigned = walls.filter(wall => Math.floor(wall.slot / 4) === id);
        const span = Math.max(footprint.width, footprint.depth, ...assigned.map(wall => {
          const position = wall.placement;
          return position ? 2 * Math.max(Math.abs(position.x_m), Math.abs(position.z_m)) + (wall.dimensions?.width_m || 4) : 0;
        }));
        const scale = 72 / span;
        const floor = node("span", "", "house-floor-outline");
        floor.style.width = footprint.width * scale + "%";
        floor.style.height = footprint.depth * scale + "%";
        canvas.append(floor);
        for (const wall of assigned) {
          const side = wall.slot % 4;
          const start = wall.placement || {x_m: [0, footprint.width / 2, 0, -footprint.width / 2][side],
            z_m: [footprint.depth / 2, 0, -footprint.depth / 2, 0][side], angle: [0, 90, 180, -90][side]};
          const button = action(wall.name || v(13 + side), () => selectRoom(id));
          button.className = "house-floor-wall";
          button.setAttribute("aria-label", floorText(4) + " " + button.textContent);
          canvas.append(button);
          const draw = ({x_m, z_m, angle}) => Object.assign(button.style, {
            left: 50 + x_m * scale + "%", top: 50 + z_m * scale + "%",
            width: (wall.dimensions?.width_m || 4) * scale + "%",
            transform: "translate(-50%, -50%) rotate(" + (-angle) + "deg)",
          });
          draw(start);
          const save = async (changes, targetRoom = id) => {
            if (savingPlan) return;
            roomChoice.disabled = true;
            savingPlan = true;
            try {
              const updated = await api(planPath, {wall: wall.id, slot: wall.slot, revision: snapshot.revision, ...changes});
              floorRoom = targetRoom;
              update(updated);
            } catch (error) {
              if (error.message === "project_conflict") renderFloorPlan(undefined, msg(5));
              else {
                draw(start);
                roomChoice.value = String(id);
                status.textContent = t(25);
              }
            } finally {
              savingPlan = false;
              roomChoice.disabled = false;
            }
          };
          const destinations = new Map();
          const used = new Set(walls.map(item => item.slot));
          const roomChoice = dropdown(ids.map(room => {
            if (room !== id) {
              const preferred = room * 4 + side;
              const slots = [preferred, ...Array.from({length: 4}, (_, side) => room * 4 + side)];
              const free = slots.find(slot => !used.has(slot));
              if (free !== undefined) destinations.set(room, free);
            }
            return [String(room), roomName(room)];
          }), String(id));
          for (const option of roomChoice.options) {
            option.disabled = Number(option.value) !== id && !destinations.has(Number(option.value));
          }
          roomChoice.onchange = () => {
            const room = Number(roomChoice.value);
            if (!destinations.has(room) || savingPlan) {
              roomChoice.value = String(id);
              return;
            }
            const group = links[room];
            save({slot: destinations.get(room), ...(groups.has(group) && {room_group: group})}, room);
          };
          const labelText = ({nl:"Kamer voor",en:"Room for",de:"Raum für",es:"Habitación para"})[language()] || "Room for";
          assignments.append(field(labelText + " " + button.textContent, roomChoice));
          const offset = (dx, dz) => ({...start,
            x_m: Math.round(clamp(start.x_m + dx, -20, 20) * 100) / 100,
            z_m: Math.round(clamp(start.z_m + dz, -20, 20) * 100) / 100});
          button.onpointerdown = event => {
            if (event.button !== 0 || !event.isPrimary || gesture || savingPlan) return;
            gesture = button;
            button.setPointerCapture(event.pointerId);
            const ratio = canvas.clientWidth * scale / 100;
            let position;
            button.onpointermove = move => {
              if (gesture !== button || move.pointerId !== event.pointerId) return;
              const dx = move.clientX - event.clientX, dz = move.clientY - event.clientY;
              if (!position && Math.hypot(dx, dz) < 3) return;
              position = offset(dx / ratio, dz / ratio);
              draw(position);
            };
            button.onpointerup = button.onpointercancel = button.onlostpointercapture = end => {
              if (gesture !== button || end.pointerId !== event.pointerId) return;
              gesture = undefined;
              if (position && end.type === "pointerup") save({placement: position});
              else draw(start);
            };
          };
          button.onkeydown = event => {
            const step = {ArrowLeft: [-.1, 0], ArrowRight: [.1, 0], ArrowUp: [0, -.1], ArrowDown: [0, .1]}[event.key];
            if (!step) return;
            event.preventDefault();
            save({placement: offset(...step)});
          };
        }
      }
      selectRoom(floorRoom);
    } catch {
      if (request === floorGeneration) floorPlan.replaceChildren(node("p", msg(1)));
    }
  }

  const planEditWords = {
    nl: ["Sleep een lamp over de muur. Gebruik het vierkantje om de grootte te wijzigen.", "Lamp opgeslagen"],
    en: ["Drag a light across its wall. Use the square handle to resize it.", "Light saved"],
    de: ["Ziehe eine Lampe über ihre Wand. Verwende den quadratischen Griff zum Skalieren.", "Lampe gespeichert"],
    es: ["Arrastra una luz por su pared. Usa el tirador cuadrado para cambiar el tamaño.", "Luz guardada"],
  };
  const planEdit = index => (planEditWords[language()] || planEditWords.nl)[index];

  function wallProjection(pins) {
    // Invert the perspective projection from the wall corners to recover wall coordinates.
    const [a, b, c, d] = pins.map(pin => pin.getBoundingClientRect());
    const dx = [b.x - d.x, c.x - d.x, a.x - b.x - c.x + d.x];
    const dy = [b.y - d.y, c.y - d.y, a.y - b.y - c.y + d.y];
    const determinant = dx[0] * dy[1] - dx[1] * dy[0];
    if (Math.abs(determinant) < 1) return null;
    const g = (dx[2] * dy[1] - dx[1] * dy[2]) / determinant;
    const h = (dx[0] * dy[2] - dx[2] * dy[0]) / determinant;
    const toWall = (x, y) => {
      const A = b.x - a.x + g * (b.x - x), B = c.x - a.x + h * (c.x - x);
      const C = b.y - a.y + g * (b.y - y), D = c.y - a.y + h * (c.y - y);
      const denominator = A * D - B * C;
      if (Math.abs(denominator) < 1) return null;
      return [100 * ((x - a.x) * D - B * (y - a.y)) / denominator,
        100 * (A * (y - a.y) - (x - a.x) * C) / denominator];
    };
    const toScreen = (x, y) => {
      const u = x / 100, v = y / 100;
      const divisor = 1 + g * u + h * v;
      return [((1 + g) * b.x * u + (1 + h) * c.x * v + a.x * (1 - u - v)) / divisor,
        ((1 + g) * b.y * u + (1 + h) * c.y * v + a.y * (1 - u - v)) / divisor];
    };
    return {toWall, toScreen};
  }

  function spatialPins(surface) {
    return [[0, 0], [100, 0], [0, 100], [100, 100]].map(([left, top]) => {
      const pin = node("span", "", "house-3d-pin");
      Object.assign(pin.style, {left: left + "%", top: top + "%"});
      surface.append(pin);
      return pin;
    });
  }

  function planLight(light, point, pins, save, layer, wallId) {
    const [x, y, size = defaultSize, advance = 0, angle = 0, customWidth] = point;
    const item = node("span", "", "house-3d-light");
    item.dataset.wall = wallId;
    item.classList.toggle("house-custom-width", customWidth !== undefined);
    const marker = node("button", "", "house-3d-lamp-button");
    marker.type = "button";
    marker.setAttribute("aria-label", light.name + " · " + t(32));
    marker.append(rotatedLampImage(light, angle));
    const handle = node("button", "", "house-3d-resize");
    handle.type = "button";
    handle.setAttribute("aria-label", h(2) + " · " + light.name);
    handle.title = h(2);
    item.append(marker, handle);
    let placement = [x, y, size];
    const position = () => {
      const projection = wallProjection(pins);
      item.hidden = !projection;
      if (!projection) return;
      const [left, top, width] = placement;
      const [cx, cy] = projection.toScreen(left, top);
      const extent = span => {
        const [ax, ay] = projection.toScreen(left - span / 2, top);
        const [bx, by] = projection.toScreen(left + span / 2, top);
        return Math.max(14, Math.hypot(bx - ax, by - ay));
      };
      const projectedWidth = extent(customWidth ?? width);
      const bounds = layer.getBoundingClientRect();
      Object.assign(item.style, {left: cx - bounds.left + "px", top: cy - bounds.top + "px",
        width: projectedWidth + "px", aspectRatio: customWidth === undefined ? "1" : String(projectedWidth / extent(width))});
    };
    const display = values => {
      placement = values;
      position();
    };
    layer.append(item);
    const commit = values => save(light.id, [...values, advance, angle, ...(customWidth === undefined ? [] : [customWidth])]);
    for (const control of [marker, handle]) {
      const resize = control === handle;
      control.onpointerdown = event => {
        if (event.button !== 0 || !event.isPrimary || gesture || busy || savingPlan) return;
        event.stopPropagation();
        const projection = wallProjection(pins);
        const origin = projection?.toWall(event.clientX, event.clientY);
        if (!origin) return;
        gesture = control;
        let values;
        control.setPointerCapture(event.pointerId);
        control.onpointermove = move => {
          if (gesture !== control || move.pointerId !== event.pointerId) return;
          const local = projection.toWall(move.clientX, move.clientY);
          if (!local) return;
          const [dx, dy] = local.map((value, index) => value - origin[index]);
          if (Math.hypot(move.clientX - event.clientX, move.clientY - event.clientY) < 3 && !values) return;
          values = resize
            ? [x, y, clamp(size + dx * 2, 4, 40)]
            : [clamp(x + dx, (customWidth ?? 0) / 2, 100 - (customWidth ?? 0) / 2), clamp(y + dy, 0, 100), size];
          display(values);
        };
        const finish = end => {
          if (gesture !== control || end.pointerId !== event.pointerId) return;
          gesture = undefined;
          if (end.type === "pointerup" && values) commit(values);
          else display([x, y, size]);
        };
        control.onpointerup = control.onpointercancel = control.onlostpointercapture = finish;
      };
      control.onkeydown = event => {
        const offset = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]}[event.key];
        if (!offset) return;
        event.stopPropagation();
        event.preventDefault();
        const [dx, dy] = offset;
        commit(resize ? [x, y, clamp(size + dx - dy, 4, 40)]
          : [clamp(x + dx, 0, 100), clamp(y + dy, 0, 100), size]);
      };
    }
    return position;
  }

  async function renderHouse3d(snapshot, message, focusSelector = ".house-3d-placement button") {
    if (gesture) return;
    const request = ++planGeneration;
    planResize?.disconnect();
    const close = action(v(1), () => {
      planResize?.disconnect();
      plan.hidden = true;
      openPlan.setAttribute("aria-expanded", "false");
      openPlan.focus();
    });
    const header = node("div", "", "lighting-controls");
    header.append(node("h3", v(0)), action(v(19), () => renderHouse3d()), close);
    const status = node("p");
    status.setAttribute("role", "status");
    plan.replaceChildren(header, status);
    try {
      snapshot ??= await api(planPath);
      if (request !== planGeneration || plan.hidden) return;
      const {links, groups: linkedGroups} = homeRooms(snapshot);
      const roomNames = {...snapshot.room_names};
      for (const [room, id] of Object.entries(links)) if (linkedGroups.has(id)) roomNames[room] = linkedGroups.get(id).name;
      const layoutWalls = snapshot.walls.map((wall, index) => ({...wall, slot: wall.slot ?? index}));
      if (!layoutWalls.length) {
        status.textContent = v(6);
        return;
      }
      const placement = planPlacement(snapshot, layoutWalls, updated => {
        if (!plan.hidden) renderHouse3d(updated, v(21));
        if (!floorPlan.hidden) renderFloorPlan(updated);
      });
      if (placement) plan.append(placement);
      const scene = node("div", "", "house-3d-scene");
      scene.tabIndex = 0;
      scene.setAttribute("aria-label", v(0));
      const world = node("div", "", "house-3d-world");
      const layer = node("div", "", "house-3d-lights");
      scene.append(world, layer);
      const lightPositions = [];
      const groups = inventory?.spatial_groups || {};
      const lights = new Map((inventory?.lights || []).map(light => [light.id, light]));
      for (const [id, group] of Object.entries(groups)) lights.set(id, {...group, id});
      const trees = snapshot.trees || {};
      const rooms = [...new Set([...layoutWalls.map(wall => Math.floor(wall.slot / 4)), ...Object.keys(trees).map(Number)])].sort();
      const treeModels = new Map();
      if (planRoom && !rooms.includes(Number(planRoom))) planRoom = "";
      const visibleRooms = planRoom ? rooms.filter(room => room === Number(planRoom)) : rooms;
      const roomCount = visibleRooms.length;
      const visibleWalls = layoutWalls.filter(wall => visibleRooms.includes(Math.floor(wall.slot / 4)));
      const footprints = new Map(visibleRooms.map(id => [id, roomFootprint(layoutWalls, id)]));
      const roomSpan = Math.max(260, ...[...footprints.values()].map(room => Math.max(room.width, room.depth) * wallPixelsPerMeter));
      const visibleTrees = visibleRooms.map(room => trees[room]).filter(Boolean);
      const heightSpan = Math.max(160, ...visibleWalls.map(wall => (wall.dimensions?.height_m || 0) * wallPixelsPerMeter),
        ...visibleTrees.map(tree => tree.height_m * wallPixelsPerMeter));
      const positionSpan = Math.max(roomSpan, ...visibleWalls.map(wall => wall.placement
        ? wallPixelsPerMeter * 2 * Math.hypot(wall.placement.x_m, wall.placement.z_m) + (wall.dimensions?.width_m ?? 4) * wallPixelsPerMeter
        : 0), ...visibleTrees.map(tree =>
        wallPixelsPerMeter * (2 * Math.hypot(tree.x_m, tree.z_m) + tree.height_m * treeWidthRatio)));
      const columns = Math.ceil(Math.sqrt(roomCount));
      const rows = Math.ceil(roomCount / columns);
      const shared = Object.keys(snapshot.room_positions || {}).length > 0;
      const mapIds = [...new Set([...layoutWalls.map(wall => Math.floor(wall.slot / 4)),
        ...Object.keys(links).filter(room => linkedGroups.has(links[room])).map(Number), ...rooms])];
      const boxes = roomBoxes(mapIds, layoutWalls, snapshot.room_positions).filter(box => visibleRooms.includes(box.id));
      const center = axis => (Math.max(...boxes.map(box => box[axis])) + Math.min(...boxes.map(box => box[axis]))) / 2;
      const centerX = shared ? center("x_m") : 0, centerZ = shared ? center("z_m") : 0;
      const spread = shared ? Math.max(...boxes.map(box => Math.max(Math.abs(box.x_m - centerX), Math.abs(box.z_m - centerZ)))) * wallPixelsPerMeter * 2 : 0;
      const fit = Math.min(1, 260 / positionSpan, 520 / (positionSpan + spread), 520 / (columns * positionSpan),
        520 / (rows * positionSpan), 290 / heightSpan);
      const faces = [];
      const ceilings = [];
      for (const [index, roomId] of visibleRooms.entries()) {
        const room = node("div", "", "house-3d-room");
        const row = Math.floor(index / columns);
        const roomsInRow = Math.min(columns, roomCount - row * columns);
        const box = boxes.find(box => box.id === roomId);
        const x = shared ? (box.x_m - centerX) * wallPixelsPerMeter :
          (index % columns - (roomsInRow - 1) / 2) * (positionSpan + 22);
        const z = shared ? (box.z_m - centerZ) * wallPixelsPerMeter :
          (row - (rows - 1) / 2) * (positionSpan + 22);
        room.style.transform = "translate3d(" + x + "px,0," + z + "px)";
        const footprint = footprints.get(roomId);
        const floor = node("div", "", "house-3d-floor");
        const floorWidth = footprint.width * wallPixelsPerMeter, floorDepth = footprint.depth * wallPixelsPerMeter;
        Object.assign(floor.style, {width: floorWidth + "px", height: floorDepth + "px",
          left: (260 - floorWidth) / 2 + "px", top: (160 - floorDepth / 2) + "px"});
        room.append(floor);
        const roomWalls = layoutWalls.filter(wall => Math.floor(wall.slot / 4) === roomId);
        const ceiling = node("div", "", "house-3d-floor house-3d-ceiling");
        ceiling.setAttribute("aria-hidden", "true");
        ceiling.hidden = !showCeilings;
        const ceilingHeight = Math.max(0, ...roomWalls.map(wall => (wall.dimensions?.height_m ?? 160 / wallPixelsPerMeter) * wallPixelsPerMeter));
        Object.assign(ceiling.style, {width: floor.style.width, height: floor.style.height, left: floor.style.left,
          top: (160 - ceilingHeight - floorDepth / 2) + "px"});
        room.append(ceiling);
        ceilings.push(ceiling);
        const ceilingPins = spatialPins(ceiling);
        for (const [id, point] of wallPoints(snapshot.ceiling_lights?.[roomId] || [])) {
          const light = lights.get(id);
          if (light) lightPositions.push(planLight(light, point, ceilingPins,
            (key, next) => saveCeiling(roomId, key, next), layer, "ceiling-" + roomId));
        }
        for (const wall of roomWalls) {
          const face = node("div", "", "house-3d-wall");
          face.dataset.wall = wall.id;
          face.style.transform = wallTransform(wall.slot, wall.placement, footprint);
          if (roomWalls.length === 4) faces.push([face, wall.placement?.angle ?? wall.slot % 4 * 90]);
          const name = wall.name || (wallLabels[language()] || wallLabels.nl)[1];
          if (wall.dimensions) {
            const width = wall.dimensions.width_m * wallPixelsPerMeter;
            const height = wall.dimensions.height_m * wallPixelsPerMeter;
            Object.assign(face.style, {width: width + "px", height: height + "px",
              left: (260 - width) / 2 + "px", top: (160 - height) + "px"});
          }
          if (wall.photo_version) {
            const image = node("img");
            image.alt = name;
            image.src = roomPhotoPath(wall.id, wall.photo_version);
            image.draggable = false;
            face.append(image);
          } else {
            face.classList.add("house-3d-wall-empty");
          }
          const caption = wall.dimensions ? name + " · " + showDimensions(wall.dimensions) : name;
          face.append(node("span", caption, "house-3d-name"));
          if (inventory) {
            const pins = spatialPins(face);
            const save = async (id, point) => {
              if (busy || savingPlan) return;
              busy = savingPlan = true;
              generation++;
              try {
                const current = wall.id === wallId;
                const revision = wall.revision ?? (current ? layout.revision : undefined);
                const points = new Map(wall.points);
                const owners = wallGroupOwners();
                for (const member of points.keys()) if (owners.get(member) === id) points.delete(member);
                points.set(id, point);
                const data = await api(wallPath(wall.id), {action: "layout", revision, points: [...points]});
                if (current && !requestedWall) receive(data);
                if (!plan.hidden) renderHouse3d(undefined, planEdit(1), null);
              } catch (error) {
                if (!plan.hidden) renderHouse3d(undefined, error.message === "project_conflict" ? msg(5) : t(25));
              } finally {
                busy = savingPlan = false;
              }
            };
            for (const [id, point] of wallPoints(wall.points)) {
              const light = lights.get(id);
              if (light) lightPositions.push(planLight(light, point, pins, save, layer, wall.id));
            }
          }
          room.append(face);
        }
        const tree = node("div", "", "house-3d-tree");
        tree.setAttribute("role", "img");
        tree.setAttribute("aria-label", treeText(0));
        tree.dataset.room = String(roomId);
        renderTree(tree, trees[roomId]);
        treeModels.set(roomId, tree);
        room.append(tree);
        world.append(room);
      }
      if (snapshot.revision) plan.append(treePlacement({...snapshot, room_names: roomNames}, treeModels));
      const zoom = node("input");
      const initialZoom = roomCount === 1 ? 76 : 54;
      Object.assign(zoom, {type: "range", min: 35, max: 125, value: camera.zoom ?? initialZoom});
      const positionLights = () => lightPositions.forEach(position => position());
      const rotate = () => {
        camera.pitch = clamp(camera.pitch, -75, 75);
        for (const [face, angle] of faces) {
          face.classList.toggle("house-3d-cutaway", Math.cos((camera.yaw + angle) * Math.PI / 180) > .15);
        }
        world.style.transform = "rotateX(" + camera.pitch + "deg) rotateY(" + camera.yaw + "deg) scale(" + (Number(zoom.value) / 100 * fit) + ")";
        positionLights();
      };
      zoom.oninput = () => { camera.zoom = Number(zoom.value); rotate(); };
      let drag;
      scene.onpointerdown = event => {
        if (event.button !== 0) return;
        drag = [event.clientX, event.clientY, camera.yaw, camera.pitch];
        scene.setPointerCapture(event.pointerId);
      };
      scene.onpointermove = event => {
        if (!drag) return;
        camera.yaw = drag[2] + (event.clientX - drag[0]) * .5;
        camera.pitch = drag[3] - (event.clientY - drag[1]) * .5;
        rotate();
      };
      scene.onlostpointercapture = () => { drag = undefined; };
      scene.onkeydown = event => {
        const offset = {ArrowLeft: [-12, 0], ArrowRight: [12, 0], ArrowUp: [0, -12], ArrowDown: [0, 12]}[event.key];
        if (!offset) return;
        event.preventDefault();
        camera.yaw += offset[0]; camera.pitch += offset[1]; rotate();
      };
      const controls = node("div", "", "lighting-controls");
      if (rooms.length > 1) {
        const roomFilter = dropdown([["", v(17)], ...rooms.map(room => [String(room), roomLabel(room, roomNames)])], planRoom);
        roomFilter.onchange = () => {
          planRoom = roomFilter.value;
          renderHouse3d(snapshot);
          plan.querySelector(".house-3d-room-filter")?.focus();
        };
        roomFilter.className = "house-3d-room-filter";
        controls.append(field(v(12), roomFilter));
      }
      async function saveCeiling(room, light, point) {
        if (busy || savingPlan) return;
        savingPlan = true;
        try {
          const updated = await api(planPath + "/ceiling", {room, light, point, revision:snapshot.revision});
          if (!plan.hidden) renderHouse3d(updated, planEdit(1), null);
          if (!floorPlan.hidden) renderFloorPlan(updated);
        } catch (error) {
          if (!plan.hidden) renderHouse3d(undefined, error.message === "project_conflict" ? msg(5) : t(25), null);
        } finally { savingPlan = false; }
      }
      const ceilingToggle = Object.assign(node("input"), {type:"checkbox", checked:showCeilings});
      ceilingToggle.onchange = () => {
        showCeilings = ceilingToggle.checked;
        for (const ceiling of ceilings) ceiling.hidden = !showCeilings;
        positionLights();
      };
      controls.append(field(({nl:"Plafond tonen",en:"Show ceiling",de:"Decke anzeigen",es:"Mostrar techo"})[language()] || "Show ceiling", ceilingToggle));
      controls.append(action(v(4), () => { camera.yaw -= 30; rotate(); }), action(v(5), () => { camera.yaw += 30; rotate(); }),
        field(v(3), zoom), action(v(18), () => {
          Object.assign(camera, {yaw: 28, pitch: -15, zoom: null});
          zoom.value = initialZoom;
          rotate();
        }));
      status.textContent = [message, v(2), planEdit(0), !visibleTrees.length && !layoutWalls.some(wall => wall.photo_version || wall.dimensions) && v(6)].filter(Boolean).join(" ");
      plan.append(controls, scene);
      const ceilingRooms = visibleRooms.filter(id => layoutWalls.some(wall => Math.floor(wall.slot / 4) === id));
      if (snapshot.revision && ceilingRooms.length && lights.size) {
        const words = ({
          nl:["Plafondlampen", "Kamer voor plafondlamp", "Plafondlamp", "Plaats op plafond", "Verwijder van plafond"],
          en:["Ceiling lights", "Room for ceiling light", "Ceiling light", "Place on ceiling", "Remove from ceiling"],
          de:["Deckenlampen", "Raum", "Lampe", "An Decke platzieren", "Von Decke entfernen"],
          es:["Luces de techo", "Habitación", "Luz", "Colocar en el techo", "Quitar del techo"],
        })[language()] || ["Ceiling lights", "Room", "Light", "Place on ceiling", "Remove from ceiling"];
        const room = dropdown(ceilingRooms.map(id => [String(id), roomLabel(id, roomNames)]), ceilingRoom);
        if (!room.value) room.selectedIndex = 0;
        const lamp = dropdown([...lights].map(([id, light]) => [id, light.name]), ceilingLamp);
        if (!lamp.value) lamp.selectedIndex = 0;
        const edit = node("div", "", "lighting-controls");
        const hasLamp = () => wallPoints(snapshot.ceiling_lights?.[room.value] || []).has(lamp.value);
        const place = action(words[3], () => {
          showCeilings = true;
          room.scrollIntoView({block:"nearest"});
          saveCeiling(Number(room.value), lamp.value, [50,50,defaultSize]);
        });
        const remove = action(words[4], () => saveCeiling(Number(room.value), lamp.value, null));
        const sync = () => {
          ceilingRoom = room.value;
          ceilingLamp = lamp.value;
          place.disabled = hasLamp();
          remove.disabled = !hasLamp();
        };
        room.onchange = lamp.onchange = sync;
        sync();
        edit.append(field(words[1], room), field(words[2], lamp), place, remove);
        plan.append(node("h4", words[0]), edit);
      }
      rotate();
      planResize = new ResizeObserver(positionLights);
      planResize.observe(scene);
      if (message && focusSelector) plan.querySelector(focusSelector)?.focus();
    } catch {
      if (request === planGeneration && !plan.hidden) status.textContent = msg(1);
    }
  }

  function lampImage(light, showStatus = false) {
    if (light.provider === "twinkly") return ledDrawing(light, showStatus);
    const archetype = typeof light.archetype === "string" ? light.archetype : "";
    let shape = "device";
    const model = light.provider === "hue" ? String(light.model || "").toUpperCase() : "";
    if (light.members) shape = "group";
    else if (model === "LCT024" || archetype === "hue_play") shape = "play";
    else if (model === "LCT026" || archetype === "hue_go") shape = "go";
    else if (model === "LST002") shape = "strip";
    else if (model === "LCG002") shape = "spot";
    else if (model === "LCT015") shape = "bulb";
    else if (/strip|tube/.test(archetype)) shape = "strip";
    else if (/spot/.test(archetype)) shape = "spot";
    else if (/bulb|candle/.test(archetype)) shape = "bulb";
    else if (/ceiling|panel|pendant/.test(archetype)) shape = "panel";
    const illustration = node("span", "", "house-lamp-art house-art-" + shape);
    illustration.setAttribute("aria-hidden", "true");
    illustration.append(node("span"));
    return light.provider === "hue" ? hueProductImage(light, illustration) : illustration;
  }

  function rotatedLampImage(light, angle) {
    const image = lampImage(light);
    if (angle) image.style.rotate = angle + "deg";
    return image;
  }

  function lampMarker(photo, light, point) {
    const [x, y, size = defaultSize, advance = 0, angle = 0, width] = point;
    const item = node("div", "", "house-marker");
    item.dataset.lamp = light.id;
    const marker = action("", () => {
      selected = light.id;
      renderSpatial(light.id);
    });
    marker.className = "house-marker-lamp";
    const artwork = rotatedLampImage(light, angle);
    const artworkFrame = node("span", "", "house-marker-artwork");
    artworkFrame.append(artwork);
    marker.append(artworkFrame);
    marker.setAttribute("aria-label", light.name + " · " + t(32) + " " + Math.round(x) + "%, " + Math.round(y) + "%");
    marker.setAttribute("aria-pressed", String(light.id === selected));
    item.classList.toggle("is-selected", light.id === selected);
    item.classList.toggle("handle-top", y >= 50);

    const captions = ({
      nl:["Draai lamp", "Volle muurbreedte"],
      en:["Rotate light", "Full wall width"],
      de:["Lampe drehen", "Ganze Wandbreite"],
      es:["Girar luz", "Ancho completo de la pared"],
    })[language()] || ["Rotate light", "Full wall width"];
    const tool = (symbol, label, run = () => {}) => {
      const button = action(symbol, run);
      button.setAttribute("aria-label", label);
      button.title = label;
      return button;
    };
    const saveGeometry = (left, top, scale, rotation, span) => {
      const next = [left, top, scale, advance, rotation];
      if (span !== undefined) next.push(span);
      return saveWallPoint(light.id, next, light.id);
    };
    const rotate = tool("↻", captions[0]);
    const full = tool("⇔", captions[1], () => saveGeometry(50, y, size, angle, 100));
    const remove = tool("×", t(21), () => saveWallPoint(light.id, null));
    const tools = node("div", "", "house-marker-tools");
    tools.hidden = light.id !== selected;
    tools.append(rotate, full, remove);
    const normalize = value => ((Math.round(value) + 540) % 360) - 180;
    function display(left, top, scale, rotation = angle, span = width) {
      item.style.left = left + "%";
      item.style.top = top + "%";
      item.style.width = (span ?? scale) + "%";
      item.style.aspectRatio = String((span ?? scale) / scale);
      item.classList.toggle("house-custom-width", span !== undefined);
      const ratio = (span ?? scale) / scale;
      const radians = rotation * Math.PI / 180;
      const fit = 1 / (Math.abs(Math.cos(radians)) + Math.abs(Math.sin(radians)));
      artworkFrame.style.setProperty("--art-width", 100 / ratio + "%");
      artworkFrame.style.setProperty("--art-stretch", ratio);
      artwork.style.rotate = rotation + "deg";
      artwork.style.scale = String(fit);
    }
    display(x, y, size);

    const resize = (horizontal, vertical, dx, dy, wallRatio) => {
      const span = width ?? size;
      const height = size * wallRatio;
      const fixedX = x - horizontal * span / 2, fixedY = y - vertical * height / 2;
      const maxWidth = horizontal > 0 ? 100 - fixedX : fixedX;
      const maxHeight = vertical > 0 ? 100 - fixedY : fixedY;
      if (horizontal && vertical) {
        const relative = (horizontal * dx * span + vertical * dy / wallRatio * size) /
          (span * span + size * size);
        const minimum = Math.max(4 / size, 4 / span);
        const maximum = Math.min(40 / size, 100 / span, maxWidth / span, maxHeight / height);
        const factor = clamp(1 + relative, minimum, Math.max(minimum, maximum));
        const next = size * factor, nextWidth = span * factor;
        return [fixedX + horizontal * nextWidth / 2, fixedY + vertical * next * wallRatio / 2,
          next, angle, width === undefined ? undefined : nextWidth];
      }
      if (horizontal) {
        const next = clamp(span + horizontal * dx, 4, Math.max(4, maxWidth));
        return [fixedX + horizontal * next / 2, y, size, angle, next];
      }
      const next = clamp(size + vertical * dy / wallRatio, 4, Math.max(4, Math.min(40, maxHeight / wallRatio)));
      return [x, fixedY + vertical * next * wallRatio / 2, next, angle, span];
    };
    function wire(control, mode, horizontal = 0, vertical = 0) {
      let moved = false;
      control.onpointerdown = event => {
        if (!event.isPrimary || event.button !== 0 || gesture || busy) return;
        const rect = photo.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        moved = false;
        const startX = event.clientX, startY = event.clientY;
        let values = [x, y, size, angle, width];
        const cx = rect.left + rect.width * x / 100, cy = rect.top + rect.height * y / 100;
        const bearing = (px, py) => Math.atan2(py - cy, px - cx) * 180 / Math.PI;
        selected = light.id;
        gesture = control;
        control.setPointerCapture(event.pointerId);
        control.onpointermove = move => {
          if (gesture !== control || move.pointerId !== event.pointerId) return;
          const deltaX = move.clientX - startX, deltaY = move.clientY - startY;
          moved ||= Math.hypot(deltaX, deltaY) > 3;
          if (!moved) return;
          if (mode === "rotate") {
            values[3] = normalize(angle + bearing(move.clientX, move.clientY) - bearing(startX, startY));
          } else if (mode === "size") {
            values = resize(horizontal, vertical, 100 * deltaX / rect.width, 100 * deltaY / rect.height, rect.width / rect.height);
          } else {
            values[0] = clamp(x + 100 * deltaX / rect.width, (width ?? 0) / 2, 100 - (width ?? 0) / 2);
            values[1] = clamp(y + 100 * deltaY / rect.height, 0, 100);
          }
          display(...values);
        };
        const finish = async end => {
          if (gesture !== control || end.pointerId !== event.pointerId) return;
          gesture = undefined;
          if (end.type === "pointerup" && moved) {
            if (!await saveGeometry(...values)) renderSpatial(light.id);
          } else if (end.type !== "pointerup") {
            renderSpatial(light.id);
          }
        };
        control.onpointerup = finish;
        control.onpointercancel = finish;
        control.onlostpointercapture = finish;
      };
      control.addEventListener("click", event => {
        if (moved && event.detail) event.stopImmediatePropagation();
      }, true);
    }
    wire(marker, "move");
    wire(rotate, "rotate");
    const arrows = callback => event => {
      const delta = {ArrowLeft:-1, ArrowDown:-1, ArrowRight:1, ArrowUp:1}[event.key];
      if (!delta) return;
      event.preventDefault();
      callback(delta);
    };
    rotate.onkeydown = arrows(delta => saveGeometry(x, y, size, normalize(angle - delta * 5), width));
    marker.onkeydown = event => {
      const nudge = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]}[event.key];
      if (!nudge) return;
      event.preventDefault();
      selected = light.id;
      setPosition(light.id, x + nudge[0], y + nudge[1], size);
    };
    const edges = [
      ["nw",-1,-1], ["n",0,-1], ["ne",1,-1], ["e",1,0],
      ["se",1,1], ["s",0,1], ["sw",-1,1], ["w",-1,0],
    ];
    const handles = edges.map(([side, horizontal, vertical]) => {
      const label = h(2) + " · " + light.name + " (" + side.toUpperCase() + ")";
      const grip = tool("", label);
      grip.className = "house-edge-grip";
      grip.dataset.edge = side;
      grip.hidden = light.id !== selected;
      wire(grip, "size", horizontal, vertical);
      grip.onkeydown = arrows(delta => {
        const rect = photo.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        saveGeometry(...resize(horizontal, vertical, delta * horizontal, delta * vertical, rect.width / rect.height));
      });
      return grip;
    });
    item.append(marker, ...handles, tools);
    return {item, marker};
  }

  const rgbFromHex = hex => hex.slice(1).match(/../g).map(value => parseInt(value, 16));

  function effectControls(stage) {
    const section = node("section", "", "house-effects");
    const controls = node("div", "", "lighting-controls");
    const mode = dropdown([["sweep", e(0)], ["gradient", g(1)],
      ...Object.entries(radialModes).map(([key, index]) => [key, radialText(index)])], sweep.mode);
    mode.setAttribute("aria-label", g(0));
    const direction = dropdown(Object.keys(directions).map((key, index) => [key, e(index + 2)]), sweep.direction);
    const speed = node("input");
    Object.assign(speed, {type: "number", min: 250, max: 2000, step: 50, required: true, value: sweep.delay});
    speed.onchange = () => { sweep.delay = Number(speed.value); drawOrder(); };
    const color = node("input");
    Object.assign(color, {type: "color", value: sweep.color, title: e(0)});
    color.oninput = () => { sweep.color = color.value; drawOrder(); };
    const end = node("input");
    Object.assign(end, {type: "color", value: sweep.end});
    end.oninput = () => { sweep.end = end.value; drawOrder(); };
    const endField = field(g(2), end);
    const speedField = field(e(6), speed);
    const gradientHelp = node("p", g(9));
    const radialHelp = node("p", radialText(2));
    const directionField = field(e(1), direction);
    const preview = node("input");
    Object.assign(preview, {type: "checkbox", checked: sweep.preview});
    const summary = node("p");
    const play = action(t(9), () => {
      const gradient = sweep.mode === "gradient";
      if (!gradient && !speed.reportValidity()) return;
      const rgb = rgbFromHex(sweep.color);
      const endRgb = rgbFromHex(sweep.end);
      if (!rgb.some(Boolean) || (gradient && !endRgb.some(Boolean))) {
        effectStatus.textContent = gradient ? g(7) : e(14);
        return;
      }
      const command = {action: "spatial", revision: layout.revision, direction: sweep.direction,
        color: rgb, delay: gradient ? 550 : Number(speed.value)};
      if (gradient) command.end_color = endRgb;
      if (Object.hasOwn(radialModes, sweep.mode)) command.effect = sweep.mode;
      return change(command, effectStatus);
    });
    const stop = action(t(10), () => change({action: "stop"}, effectStatus));
    function drawOrder() {
      const available = new Set((inventory.lights || []).filter(light => light.status !== "unavailable"
        && light.capabilities?.rgb && light.state?.on === true).map(light => light.id));
      const [axis, sign] = directions[sweep.direction];
      const points = wallPoints();
      const groups = inventory.spatial_groups || {};
      const claimed = new Set();
      const radial = Object.hasOwn(radialModes, sweep.mode);
      const position = point => radial
        ? (sweep.mode === "outward" ? 1 : -1) * ((point[0] - 50) ** 2 + (point[1] - 50) ** 2)
        : sign * point[axis];
      const ordered = [...points].sort((a, b) => position(a[1]) - position(b[1])).filter(([id]) => {
        const eligible = (groups[id]?.members || [id]).filter(key => available.has(key) && !claimed.has(key));
        eligible.forEach(key => claimed.add(key));
        return eligible.length > 0;
      });
      const gradient = sweep.mode === "gradient";
      endField.hidden = gradientHelp.hidden = !gradient;
      speedField.hidden = gradient;
      directionField.hidden = radial;
      radialHelp.hidden = !radial;
      const first = ordered[0]?.[1][axis];
      const span = ordered.at(-1)?.[1][axis] - first;
      const startRgb = rgbFromHex(sweep.color), endRgb = rgbFromHex(sweep.end);
      const dispatch = radial ? ordered.map(([id, point], index) => ({id, point,
        due: index * Number(speed.value) - (point[3] || 0)})).sort((a, b) => a.due - b.due)
        : ordered.map(([id, point]) => ({id, point}));
      const numbers = new Map(dispatch.map(({id, point}, index) => {
        const ratio = span ? (point[axis] - first) / span : 0;
        const previewColor = startRgb.map((channel, i) => Math.round(channel + (endRgb[i] - channel) * ratio));
        return [id, {number: index + 1, color: "rgb(" + previewColor.join(",") + ")"}];
      }));
      for (const marker of stage.querySelectorAll(".house-marker")) {
        const entry = numbers.get(marker.dataset.lamp);
        if (sweep.preview && entry) marker.dataset.order = entry.number;
        else delete marker.dataset.order;
        if ((gradient || radial) && sweep.preview && entry) marker.style.setProperty("--gradient-preview", radial ? sweep.color : entry.color);
        else marker.style.removeProperty("--gradient-preview");
      }
      summary.textContent = e(8) + " · " + ordered.length + " / " + points.size;
      play.disabled = isPlaying() || !ordered.length;
      stop.hidden = !isPlaying();
      stop.disabled = playback.state === "stopping";
    }
    refreshEffectButtons = drawOrder;
    mode.onchange = () => { sweep.mode = mode.value; drawOrder(); };
    direction.onchange = () => { sweep.direction = direction.value; drawOrder(); };
    preview.onchange = () => { sweep.preview = preview.checked; drawOrder(); };
    const colorLabel = {nl: "Kleur", en: "Colour", de: "Farbe", es: "Color"}[language()] || "Colour";
    controls.append(field(g(0), mode), directionField, field(colorLabel, color), endField, speedField,
      field(e(7), preview), play, stop);
    section.append(node("h3", g(0)), node("p", e(9)), gradientHelp, radialHelp, controls, summary, effectStatus, reports[1]);
    drawOrder();
    updatePlaybackStatus();
    return section;
  }

  function dimensionsForm() {
    const [widthLabel, heightLabel, saveLabel] = dimensionLabels[language()] || dimensionLabels.nl;
    const input = value => Object.assign(node("input"),
      {type: "number", min: 0.25, max: 20, step: 0.01, value: value ?? "", required: true});
    const width = input(layout.dimensions?.width_m);
    const height = input(layout.dimensions?.height_m);
    const form = node("form", "", "lighting-controls house-dimensions");
    const save = node("button", saveLabel);
    save.type = "submit";
    form.append(field(widthLabel, width), field(heightLabel, height), save);
    form.onsubmit = async event => {
      event.preventDefault();
      save.disabled = true;
      try {
        await change({action: "wall_dimensions", revision: layout.revision,
          width_m: width.valueAsNumber, height_m: height.valueAsNumber}, spatialStatus, "dimensions");
      } finally {
        save.disabled = false;
      }
    };
    return form;
  }

  function renderSpatial(focusId) {
    const owners = wallGroupOwners();
    const placements = wallPoints();
    const lights = new Map(Object.entries(inventory.spatial_groups || {}).map(([id, group]) => [id, {...group, id}]));
    for (const light of inventory.lights || []) if (!owners.has(light.id)) lights.set(light.id, light);
    for (const id of placements.keys()) {
      if (!lights.has(id)) lights.set(id, {id, name: t(31) + " · " + id});
    }
    const upload = node("input");
    upload.type = "file";
    upload.accept = "image/jpeg,image/png,image/webp";
    upload.onchange = async () => {
      const file = upload.files[0];
      if (!file) return;
      if (layout.photoVersion && !window.confirm(msg(7))) {
        upload.value = "";
        return;
      }
      const revision = layout.revision;
      const targetWall = wallId;
      upload.disabled = true;
      try {
        const photo = await importPhoto(file);
        if (targetWall === wallId && !requestedWall) await updateLayout(layout.photoVersion ? new Map() : placements, {photo, revision});
      } catch {
        spatialStatus.textContent = t(24);
      } finally {
        upload.disabled = false;
        upload.value = "";
      }
    };
    const toolbar = node("div", "", "lighting-controls");
    toolbar.append(field(t(18), upload));
    if (legacyLayout.photo) toolbar.append(action(msg(2), () => migrate(spatialStatus)));
    const dimensions = dimensionsForm();
    if (!layout.photoVersion && !layout.dimensions) {
      refreshEffectButtons = undefined;
      spatialSection.replaceChildren(spatialStatus, dimensions, toolbar);
      return;
    }
    const photo = layout.photoVersion ? photoElement : node("div", "", "house-blank-wall");
    const stage = node("div", "", "lighting-spatial-stage");
    if (layout.photoVersion) {
      photo.className = "house-room-photo";
      photo.alt = t(33);
    } else {
      const blankLabel = (dimensionLabels[language()] || dimensionLabels.nl)[3];
      photo.setAttribute("role", "img");
      photo.setAttribute("aria-label", blankLabel + " · " + showDimensions(layout.dimensions));
      stage.style.width = Math.min(720, 480 * layout.dimensions.width_m / layout.dimensions.height_m) + "px";
      photo.style.aspectRatio = layout.dimensions.width_m + " / " + layout.dimensions.height_m;
    }
    stage.append(photo);
    const wallCoordinates = event => {
      const rect = photo.getBoundingClientRect();
      if (!rect.width || !rect.height) return null;
      const x = 100 * (event.clientX - rect.left) / rect.width;
      const y = 100 * (event.clientY - rect.top) / rect.height;
      return x >= 0 && x <= 100 && y >= 0 && y <= 100 ? [x,y] : null;
    };
    const place = (id, at) => setPosition(id, ...at, placements.get(id)?.[2]);
    photo.onclick = event => {
      const at = wallCoordinates(event);
      if (at && selected && lights.has(selected)) place(selected, at);
    };
    const cards = node("div", "", "house-lamp-list");
    let focus;
    for (const light of lights.values()) {
      const point = placements.get(light.id);
      const choose = action("", () => {
        selected = light.id;
        renderSpatial("list");
      });
      choose.className = "house-lamp-choice";
      let dragged = false;
      choose.addEventListener("click", event => {
        if (dragged && event.detail) event.stopImmediatePropagation();
      }, true);
      choose.onpointerdown = event => {
        if (!event.isPrimary || event.button !== 0 || gesture || busy) return;
        dragged = false;
        gesture = choose;
        choose.setPointerCapture(event.pointerId);
        choose.onpointermove = move => {
          if (gesture !== choose || move.pointerId !== event.pointerId) return;
          dragged ||= Math.hypot(move.clientX - event.clientX, move.clientY - event.clientY) > 5;
          stage.classList.toggle("house-drop-target", dragged && Boolean(wallCoordinates(move)));
        };
        choose.onpointerup = choose.onpointercancel = choose.onlostpointercapture = end => {
          if (gesture !== choose || end.pointerId !== event.pointerId) return;
          gesture = undefined;
          stage.classList.remove("house-drop-target");
          const at = dragged && end.type === "pointerup" && wallCoordinates(end);
          if (at) {
            selected = light.id;
            place(light.id, at);
          }
        };
      };
      choose.setAttribute("aria-pressed", String(light.id === selected));
      const icon = lampImage(light, true);
      choose.append(icon, node("span", light.name));
      const mappingStatus = icon.querySelector("small");
      if (mappingStatus) choose.append(mappingStatus);
      const model = [light.product_name, light.product_code || light.model].filter(value => value && value !== light.name);
      if (model.length) choose.append(node("small", model.join(" · ")));
      if (point) choose.append(node("small", h(5)));
      cards.append(choose);
      if (focusId === "list" && light.id === selected) focus = choose;
      if (!point) continue;
      const {item, marker} = lampMarker(photo, light, point);
      stage.append(item);
      if (light.id === focusId) focus = marker;
    }
    if (!lights.size) cards.append(node("p", h(3)));
    const panel = node("aside", "", "house-lamp-panel");
    panel.append(node("h3", h(1)), cards);
    const selectedLight = lights.get(selected);
    if (layout.photoVersion) toolbar.append(action(t(23), () => {
      if (window.confirm(t(23) + "?")) return updateLayout(new Map(), {photo: null});
    }));
    if (selectedLight && !placements.has(selected)) {
      panel.append(action(t(20), () => setPosition(selected, 50, 50)));
    }
    const editor = node("div", "", "house-editor");
    const canvas = node("div", "", "house-canvas");
    canvas.append(stage);
    editor.append(canvas, panel);
    spatialSection.replaceChildren(dimensions, toolbar, spatialStatus, node("p", ({
      nl:"Sleep een lamp uit de lijst naar de muur. Sleep de geplaatste lamp om haar te verplaatsen en gebruik de gele grepen aan de randen en hoeken om haar te schalen.",
      en:"Drag a light from the list onto the wall. Drag a placed light to move it, or use the yellow edge and corner handles to resize it.",
      de:"Ziehe eine Lampe aus der Liste auf die Wand. Ziehe sie an ihre Position und ändere ihre Größe am runden Griff.",
      es:"Arrastra una luz de la lista a la pared. Arrástrala para moverla o usa el tirador redondo para cambiar su tamaño.",
    })[language()] || h(4)), editor, effectControls(stage));
    if (focusId === "dimensions") focus = dimensions.querySelector("button");
    focus?.focus();
  }

  return (page, data) => {
    const visible = page === "shows" || page === "house";
    const opening = visible && page !== activePage;
    activePage = page;
    mount.hidden = page !== "shows";
    document.getElementById("nav-shows").textContent = showText()[0];
    house.hidden = page !== "house";
    nav.textContent = houseTitle.textContent = h(0);
    if (page === "house") {
      renderWallGuide();
      openPlan.textContent = v(0);
      openFloor.textContent = floorText(0);
      if (initialized) renderWallPicker();
    }
    nav.setAttribute("aria-current", page === "house" ? "page" : "false");
    if (!visible) {
      clearInterval(timer);
      timer = undefined;
      return;
    }
    if (opening) {
      if (page === "shows") refreshShowPlayers();
      (page === "house" ? house : mount).append(syncStatus);
      if (!initialized) syncStatus.textContent = msg(0);
      refresh();
      timer ??= setInterval(refresh, 1500);
    }
    if (!data || gesture) return;
    inventory = data;
    const nextSignature = JSON.stringify([language(), data.groups, data.scenes, data.spatial_groups,
      (data.lights || []).map(light => [light.id, light.name, light.product_code, light.model, light.product_name, light.archetype,
        light.has_product_image, light.has_catalog_image, hueProductImageRevisions.get(hueProductImagePath(light))])]);
    if (initialized && signature !== nextSignature) {
      signature = nextSignature;
      renderShows();
      renderSpatial();
      if (page === "house" && !plan.hidden && !savingPlan) renderHouse3d();
      if (page === "house" && !floorPlan.hidden && !savingPlan) renderFloorPlan();
      updatePlaybackStatus();
    }
    if (page === "house") refreshEffectButtons?.();
  };
};
