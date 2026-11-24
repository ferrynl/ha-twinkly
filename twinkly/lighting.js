(() => {
  const words = {
    nl: ["Home", "Alle lampen", "Vernieuwen", "Verbonden", "Niet bereikbaar", "Status onbekend", "Govee · onbevestigd", "Aan", "Uit", "Helderheid", "Kleur", "Nog geen lampen", "Verbindingen", "Apparaten zoeken", "Koppelen", "Opnieuw koppelen", "Apparaat-ID", "LAN-adres", "Certificaat ophalen", "SHA256-vingerafdruk", "Vergelijk deze vingerafdruk via een onafhankelijke, vertrouwde bron. Ga alleen door als je het certificaat vertrouwt.", "Druk vlak voor het koppelen op de fysieke knop van de Hue Bridge.", "Schakel LAN-bediening in via de Govee-app.", "Gemengde groepen", "Groepsnaam", "Opslaan", "Bewerken", "Verwijderen", "Annuleren", "Gelukt", "Onbevestigd", "Overgeslagen", "Mislukt", "Verbinding beheren", "Kies lampen", "Geen apparaten gevonden", "Gegevens laden…", "Onbekende lamp", "Gekoppeld"],
    en: ["Home", "All lights", "Refresh", "Connected", "Unavailable", "Status unknown", "Govee · unconfirmed", "On", "Off", "Brightness", "Color", "No lights yet", "Connections", "Find devices", "Pair", "Reconnect", "Device ID", "LAN address", "Inspect certificate", "SHA256 fingerprint", "Compare this fingerprint through an independent, trusted source. Continue only if you trust the certificate.", "Press the physical Hue Bridge button just before pairing.", "Enable LAN control in the Govee app.", "Mixed groups", "Group name", "Save", "Edit", "Delete", "Cancel", "Accepted", "Unconfirmed", "Skipped", "Failed", "Manage connection", "Choose lights", "No devices found", "Loading…", "Unavailable light", "Paired"],
    de: ["Start", "Alle Lampen", "Aktualisieren", "Verbunden", "Nicht erreichbar", "Status unbekannt", "Govee · unbestätigt", "Ein", "Aus", "Helligkeit", "Farbe", "Noch keine Lampen", "Verbindungen", "Geräte suchen", "Koppeln", "Erneut koppeln", "Geräte-ID", "LAN-Adresse", "Zertifikat abrufen", "SHA256-Fingerabdruck", "Vergleiche diesen Fingerabdruck mit einer unabhängigen, vertrauenswürdigen Quelle. Fahre nur fort, wenn du dem Zertifikat vertraust.", "Drücke kurz vor dem Koppeln die Taste an der Hue Bridge.", "Aktiviere die LAN-Steuerung in der Govee-App.", "Gemischte Gruppen", "Gruppenname", "Speichern", "Bearbeiten", "Löschen", "Abbrechen", "Angenommen", "Unbestätigt", "Übersprungen", "Fehlgeschlagen", "Verbindung verwalten", "Lampen auswählen", "Keine Geräte gefunden", "Wird geladen…", "Nicht erreichbare Lampe", "Gekoppelt"],
    es: ["Inicio", "Todas las luces", "Actualizar", "Conectado", "No disponible", "Estado desconocido", "Govee · sin confirmar", "Encender", "Apagar", "Brillo", "Color", "Aún no hay luces", "Conexiones", "Buscar dispositivos", "Vincular", "Volver a vincular", "ID del dispositivo", "Dirección LAN", "Consultar certificado", "Huella SHA256", "Compara esta huella con una fuente fiable e independiente. Continúa solo si confías en el certificado.", "Pulsa el botón físico del puente Hue justo antes de vincularlo.", "Activa el control LAN en la aplicación Govee.", "Grupos mixtos", "Nombre del grupo", "Guardar", "Editar", "Eliminar", "Cancelar", "Aceptado", "Sin confirmar", "Omitido", "Error", "Gestionar conexión", "Elegir luces", "No se encontraron dispositivos", "Cargando…", "Luz no disponible", "Vinculado"],
  };
  const collectionWords = {
    nl: ["Hue-kamers en zones", "Kamer", "Zone", "Hue-scènes", "Geen kamers of zones gevonden.", "Stop de Hue-test of gemengde muziek op deze bridge en probeer opnieuw."],
    en: ["Hue rooms and zones", "Room", "Zone", "Hue scenes", "No rooms or zones found.", "Stop the Hue test or mixed music on this bridge and try again."],
    de: ["Hue-Räume und -Zonen", "Raum", "Zone", "Hue-Szenen", "Keine Räume oder Zonen gefunden.", "Beende den Hue-Test oder die gemischte Musik auf dieser Bridge und versuche es erneut."],
    es: ["Habitaciones y zonas Hue", "Habitación", "Zona", "Escenas Hue", "No se encontraron habitaciones ni zonas.", "Detén la prueba Hue o la música mixta en este puente e inténtalo de nuevo."],
  };
  const previewWords = {
    nl: ["Afbeelding kiezen", "Afbeelding verwijderen", "Masterfader muziek"],
    en: ["Choose image", "Remove image", "Music master fader"],
    de: ["Bild auswählen", "Bild entfernen", "Musik-Masterfader"],
    es: ["Elegir imagen", "Eliminar imagen", "Control maestro de música"],
  };
  const previewText = () => previewWords[el("language").value] || previewWords.nl;
  const temperatureLabels = {
    nl: "Wittemperatuur", en: "White temperature", de: "Weißtemperatur", es: "Temperatura del blanco",
  };
  const sceneWords = {
    nl: ["Scènes", "Scènenaam", "Groep", "Afspelen", "Groep ontbreekt", "Maak een gemengde groep om een scène op te slaan."],
    en: ["Scenes", "Scene name", "Group", "Apply", "Group missing", "Create a mixed group to save a scene."],
    de: ["Szenen", "Szenenname", "Gruppe", "Anwenden", "Gruppe fehlt", "Erstelle eine gemischte Gruppe, um eine Szene zu speichern."],
    es: ["Escenas", "Nombre de escena", "Grupo", "Aplicar", "Falta el grupo", "Crea un grupo mixto para guardar una escena."],
  };
  const musicWords = {
    nl: ["Muziek starten", "Muziek stoppen", "Wacht op LedFX", "LedFX actief", "Deelnemend", "Overgeslagen"],
    en: ["Start music", "Stop music", "Waiting for LedFX", "LedFX active", "Participating", "Skipped"],
    de: ["Musik starten", "Musik stoppen", "Warte auf LedFX", "LedFX aktiv", "Teilnehmend", "Übersprungen"],
    es: ["Iniciar música", "Detener música", "Esperando a LedFX", "LedFX activo", "Participan", "Omitidas"],
  };
  const timingWords = {
    nl: ["Frameleeftijd", "Opdrachtduur", "Mislukt", "Gemeten in de app, zonder reactietijd van de lamp."],
    en: ["Frame age", "Command duration", "Failed", "Measured in the app, excluding the light’s reaction time."],
    de: ["Frame-Alter", "Befehlsdauer", "Fehlgeschlagen", "In der App gemessen, ohne Reaktionszeit der Lampe."],
    es: ["Antigüedad del fotograma", "Duración del comando", "Fallidos", "Medido en la aplicación, sin el tiempo de reacción de la luz."],
  };
  const hueTestWords = {
    nl: ["Kies een Hue-lamp", "Identificeren", "Aan/uit-test", "Dimtest", "RGB-test", "Regenboog", "Warm/koel wit", "Hue-test stoppen", "Hue-test loopt", "Vorige stand hersteld", "Hue-test mislukt. Controleer de lamp en stop eventuele effecten.", "Vorige stand kon niet worden hersteld.", "Tests gelden voor de hele Hue-lamp. LED-volgorde en richtingstests staan bij Twinkly.", "De bridge heeft het herstel van de vorige stand nog niet bevestigd."],
    en: ["Choose a Hue light", "Identify", "Power test", "Dimmer test", "RGB test", "Rainbow", "Warm/cool white", "Stop Hue test", "Hue test running", "Previous state restored", "Hue test failed. Check the light and stop any effects.", "Could not restore the previous state.", "Tests apply to the whole Hue light. LED order and direction tests are under Twinkly.", "The bridge did not confirm that the previous state was restored."],
    de: ["Hue-Lampe auswählen", "Identifizieren", "Ein-/Aus-Test", "Dimmtest", "RGB-Test", "Regenbogen", "Warm-/Kaltweiß", "Hue-Test stoppen", "Hue-Test läuft", "Vorheriger Zustand wiederhergestellt", "Hue-Test fehlgeschlagen. Prüfe die Lampe und beende aktive Effekte.", "Der vorherige Zustand konnte nicht wiederhergestellt werden.", "Tests gelten für die ganze Hue-Lampe. LED-Reihenfolge und Richtungstests findest du bei Twinkly.", "Die Bridge hat den vorherigen Zustand noch nicht bestätigt."],
    es: ["Elige una luz Hue", "Identificar", "Prueba de encendido", "Prueba de brillo", "Prueba RGB", "Arcoíris", "Blanco cálido/frío", "Detener prueba Hue", "Prueba Hue en curso", "Estado anterior restaurado", "La prueba Hue falló. Comprueba la luz y detén cualquier efecto.", "No se pudo restaurar el estado anterior.", "Las pruebas se aplican a toda la luz Hue. Las pruebas de orden LED y dirección están en Twinkly.", "El puente no ha confirmado que se haya restaurado el estado anterior."],
  };
  const goveeTestWords = {
    nl: ["Kies een Govee-lamp", "Identificeren", "Aan/uit-test", "Dimtest", "RGB-test", "Regenboog", "", "Govee-test stoppen", "Govee-test loopt", "Vorige stand hersteld", "Govee-test mislukt. Controleer LAN-bediening en de lampstatus.", "Vorige stand kon niet worden hersteld.", "Tests gelden voor de hele Govee-lamp. Beschikbaarheid hangt af van de LAN-status.", "De lamp heeft het herstel niet bevestigd."],
    en: ["Choose a Govee light", "Identify", "Power test", "Dimmer test", "RGB test", "Rainbow", "", "Stop Govee test", "Govee test running", "Previous state restored", "Govee test failed. Check LAN control and the light status.", "Could not restore the previous state.", "Tests apply to the whole Govee light. Availability depends on LAN status.", "The light did not confirm restoration."],
    de: ["Govee-Lampe auswählen", "Identifizieren", "Ein-/Aus-Test", "Dimmtest", "RGB-Test", "Regenbogen", "", "Govee-Test stoppen", "Govee-Test läuft", "Vorheriger Zustand wiederhergestellt", "Govee-Test fehlgeschlagen. Prüfe LAN-Steuerung und Lampenstatus.", "Der vorherige Zustand konnte nicht wiederhergestellt werden.", "Tests gelten für die ganze Govee-Lampe. Die Verfügbarkeit hängt vom LAN-Status ab.", "Die Lampe hat die Wiederherstellung nicht bestätigt."],
    es: ["Elige una luz Govee", "Identificar", "Prueba de encendido", "Prueba de brillo", "Prueba RGB", "Arcoíris", "", "Detener prueba Govee", "Prueba Govee en curso", "Estado anterior restaurado", "La prueba Govee falló. Comprueba el control LAN y el estado.", "No se pudo restaurar el estado anterior.", "Las pruebas se aplican a toda la luz Govee. La disponibilidad depende del estado LAN.", "La luz no confirmó la restauración."],
  };
  const brands = {twinkly: "Twinkly", hue: "Philips Hue", govee: "Govee"};
  const homeWords = {
    nl: ["Lichtmengtafel", "Alles", "Lampen", "Kamers", "Groepen", "Scènes", "Lamp toevoegen", "Kamer toevoegen", "Groep toevoegen", "Scène toevoegen", "Kies een doel", "Naam", "Actie", "Sluiten", "Aan/uit", "Lamp indelen", "Kies een lamp", "Kies een kamer of groep", "Geen kamers", "Geen groepen", "Geen scènes", "Twinkly-scènes", "Apparaten vernieuwen", "Actieve scène"],
    en: ["Light mixer", "All", "Lights", "Rooms", "Groups", "Scenes", "Add light", "Add room", "Add group", "Add scene", "Select a target", "Name", "Action", "Close", "Power", "Assign light", "Select a light", "Select a room or group", "No rooms", "No groups", "No scenes", "Twinkly scenes", "Refresh lights", "Active scene"],
    de: ["Lichtmischpult", "Alle", "Lampen", "Räume", "Gruppen", "Szenen", "Lampe hinzufügen", "Raum hinzufügen", "Gruppe hinzufügen", "Szene hinzufügen", "Ziel wählen", "Name", "Aktion", "Schließen", "Ein/Aus", "Lampe zuordnen", "Lampe wählen", "Raum oder Gruppe wählen", "Keine Räume", "Keine Gruppen", "Keine Szenen", "Twinkly-Szenen", "Lampen aktualisieren", "Aktive Szene"],
    es: ["Mesa de luces", "Todo", "Luces", "Habitaciones", "Grupos", "Escenas", "Añadir luz", "Añadir habitación", "Añadir grupo", "Añadir escena", "Elige un destino", "Nombre", "Acción", "Cerrar", "Encendido", "Asignar luz", "Elige una luz", "Elige una habitación o un grupo", "Sin habitaciones", "Sin grupos", "Sin escenas", "Escenas de Twinkly", "Actualizar luces", "Escena activa"],
  };
  const wordmarks = {twinkly: "twinkly-nav-logo.svg", hue: "hue-app-icon.webp", govee: "govee-logo.png"};
  const el = id => document.getElementById(id);
  const panel = el("lighting-panel");
  const settings = el("lighting-settings");
  const studio = el("twinkly-lighting");
  const hueCollections = el("hue-collections");
  const feedback = el("lighting-feedback");
  const t = i => (words[el("language").value] || words.nl)[i];
  const h = i => (homeWords[el("language").value] || homeWords.nl)[i];
  let homeBrand = "all";
  let homeView = "lights";
  let homeSelection = "all";
  let activeScene;
  const mixerValues = new Map();
  let mixerWrites = 0;
  let homeDialog;
  let data;
  let pending;
  let context = "";
  let groupBusy = false;
  let collections = [];
  let collectionsStatus = "loading";
  let collectionsRead = 0;
  const sceneImageRevisions = new Map();
  const entertainment = node("section", "", "lighting-section");
  entertainment.hidden = true;
  hueCollections.after(entertainment);
  const entertainmentPath = "providers/hue/entertainment";
  const hueMusicWords = {
    nl: {streaming: "Muziekstream actief", missing_area: "Maak in de Hue-app een Entertainmentruimte met de ingeschakelde kleurenlampen van deze groep.", no_lights: "Zet de Hue-kleurenlampen van deze groep aan.", stop: "Stop muziek op Home."},
    en: {streaming: "Music streaming", missing_area: "Create an Entertainment area in the Hue app with this group’s powered-on color lights.", no_lights: "Turn on this group’s Hue color lights.", stop: "Stop music on Home."},
    de: {streaming: "Musikstream aktiv", missing_area: "Erstelle in der Hue-App einen Entertainment-Bereich mit den eingeschalteten Farblampen dieser Gruppe.", no_lights: "Schalte die Hue-Farblampen dieser Gruppe ein.", stop: "Stoppe die Musik auf der Startseite."},
    es: {streaming: "Música en directo", missing_area: "Crea un área de entretenimiento en la app Hue con las luces de color encendidas de este grupo.", no_lights: "Enciende las luces Hue de color de este grupo.", stop: "Detén la música en Inicio."},
  };
  const entertainmentWords = {
    nl: ["Maak een Entertainment-zone in de Philips Hue-app en kies die hieronder.", "Entertainment-zone", "Regenboog", "Zonsondergang", "Start effect", "Stop effect", "Effect actief", "Geen Entertainment-zones gevonden.", "Koppel de Bridge opnieuw via Instellingen om effecten te streamen.", "De Bridge is niet bereikbaar.", "Stop de actieve stream, Hue-test of gemengde muziek en probeer opnieuw.", "De verbinding met de Hue-stream is verbroken.", "De Bridge heeft het stoppen niet bevestigd.", "Effect starten mislukt. Controleer de Bridge en vernieuw de zones."],
    en: ["Create an entertainment area in the Philips Hue app, then select it below.", "Entertainment area", "Rainbow", "Sunset", "Start effect", "Stop effect", "Effect running", "No entertainment areas found.", "Reconnect the Bridge in Settings to stream effects.", "The Bridge is unavailable.", "Stop the active stream, Hue test or mixed music and try again.", "The Hue stream disconnected.", "The Bridge did not confirm that streaming stopped.", "Could not start the effect. Check the Bridge and refresh the areas."],
    de: ["Erstelle in der Philips Hue App einen Entertainment-Bereich und wähle ihn hier aus.", "Entertainment-Bereich", "Regenbogen", "Sonnenuntergang", "Effekt starten", "Effekt stoppen", "Effekt läuft", "Keine Entertainment-Bereiche gefunden.", "Verbinde die Bridge in den Einstellungen erneut, um Effekte zu streamen.", "Die Bridge ist nicht erreichbar.", "Beende den aktiven Stream, Hue-Test oder die gemischte Musik und versuche es erneut.", "Die Verbindung zum Hue-Stream wurde unterbrochen.", "Die Bridge hat das Beenden nicht bestätigt.", "Der Effekt konnte nicht gestartet werden. Prüfe die Bridge und aktualisiere die Bereiche."],
    es: ["Crea un área de entretenimiento en la aplicación Philips Hue y selecciónala aquí.", "Área de entretenimiento", "Arcoíris", "Atardecer", "Iniciar efecto", "Detener efecto", "Efecto activo", "No se encontraron áreas de entretenimiento.", "Vuelve a vincular el puente en Ajustes para transmitir efectos.", "El puente no está disponible.", "Detén la transmisión activa, la prueba Hue o la música mixta y vuelve a intentarlo.", "Se perdió la conexión con la transmisión Hue.", "El puente no confirmó que la transmisión se detuviera.", "No se pudo iniciar el efecto. Comprueba el puente y actualiza las áreas."],
  };
  let entertainmentRead = 0;
  let entertainmentSelection;
  let entertainmentControls;

  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text) item.textContent = text;
    if (className) item.className = className;
    return item;
  }

  function button(text, handler) {
    const item = node("button", text);
    item.type = "button";
    item.addEventListener("click", () => task(item, handler));
    return item;
  }

  async function task(item, callback) {
    item.disabled = true;
    item.dataset.running = "";
    try {
      await callback(item);
    } catch (error) {
      const message = item.closest("dialog[open]")?.querySelector("[role=status]") || feedback;
      message.textContent = error.message === "hue_bridge_busy"
        ? (collectionWords[el("language").value] || collectionWords.nl)[5]
        : t(error.message === "pairing_permission" ? 21 : 32);
    } finally {
      item.disabled = false;
      delete item.dataset.running;
    }
  }

  async function api(path, body) {
    const response = await fetch(path, body === undefined ? {cache: "no-store"} : {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    return result;
  }

  function status(light) {
    if (light.provider === "govee") return t(6) + (light.status === "unknown" ? " · " + t(5) : "");
    return t({online: 3, unavailable: 4, unknown: 5}[light.status] ?? 5);
  }

  function stateColor(color) {
    return color?.length === 3 ? "#" + color.map(channel => channel.toString(16).padStart(2, "0")).join("") : null;
  }

  function field(caption, input) {
    const label = node("label", caption);
    label.append(input);
    return label;
  }

  function mixerState(lights, target, state) {
    const remembered = mixerValues.get(JSON.stringify(target)) || {};
    const result = {...state};
    for (const [action, key, capability] of [["color", "color", "rgb"], ["brightness", "brightness", "brightness"]]) {
      const samples = lights.filter(light => light.status !== "unavailable" && light.capabilities[capability])
        .map(light => light.state?.[key] ?? null);
      const first = samples[0];
      const actual = first != null && samples.every(value =>
        action === "color" ? stateColor(value) === stateColor(first) : value === first) ? first : null;
      const last = remembered[action];
      result[key] = last && (actual == null || last.until > Date.now()) ? last.value : actual;
    }
    return result;
  }

  function controls(card, lights, target, state = {}, mixer = false, controlFeedback = feedback, brightnessOnly = false) {
    const available = lights.filter(light => light.status !== "unavailable");
    const capable = key => available.some(light => light.capabilities[key]);
    const row = node("div", "", "lighting-controls");
    if (mixer) state = mixerState(lights, target, state);
    const mixerKey = JSON.stringify(target);
    function remember(action, value) {
      const previous = mixerValues.get(mixerKey);
      mixerValues.set(mixerKey, {...previous, [action]: {value, until: Date.now() + 4000}});
    }
    const send = async (action, value) => {
      if (target.twinklyGroup) {
        const mode = action === "power" ? (value ? "on" : "off") : action;
        const result = await request("control", {
          group: target.twinklyGroup, action: mode, value: action === "color" ? stateColor(value) : value,
        });
        controlFeedback.textContent = controlResult(result);
        const accepted = lights.length > (result.offline?.length || 0) + result.failed.length;
        if (mixer && accepted) remember(action, value);
        if (!mixer || action === "power") await refresh(false);
        return accepted;
      }
      const result = await api("lighting/control", {...target, action, value});
      const outcomes = ["accepted", "unconfirmed", "skipped", "failed"];
      controlFeedback.textContent = outcomes.map((outcome, i) => {
        const count = Object.values(result.results).filter(value => value === outcome).length;
        return count ? t(29 + i) + " · " + count : "";
      }).filter(Boolean).join(" / ");
      const accepted = Object.values(result.results).some(outcome => ["accepted", "unconfirmed"].includes(outcome));
      if (mixer) {
        if (accepted) remember(action, value);
        activeScene = undefined;
        panel.querySelector(".mixer-active")?.replaceChildren();
        panel.querySelectorAll(".mixer-pad [aria-pressed]").forEach(pad => pad.setAttribute("aria-pressed", "false"));
      }
      if (!mixer || !["color", "brightness"].includes(action)) await refresh(false);
      return accepted;
    };

    function bindMixerValue(input, action, read, preview = false) {
      let timer;
      let queued;
      let running = false;
      let lastSent;
      async function flush() {
        clearTimeout(timer);
        if (running || queued === undefined) return;
        running = true;
        mixerWrites++;
        try {
          while (queued !== undefined) {
            const value = queued;
            queued = undefined;
            const signature = JSON.stringify(value);
            if (signature === lastSent) continue;
            try {
              lastSent = await send(action, value) ? signature : undefined;
            } catch {
              lastSent = undefined;
              feedback.textContent = t(32);
            }
          }
        } finally {
          mixerWrites--;
          running = false;
        }
      }
      if (preview) input.addEventListener("input", () => {
        queued = read();
        clearTimeout(timer);
        timer = setTimeout(flush, 140);
      });
      input.addEventListener("change", () => {
        queued = read();
        flush();
      });
    }

    if (!brightnessOnly && capable("power")) {
      for (const [value, index] of [[true, 7], [false, 8]]) {
        const toggle = button(t(index), () => send("power", value));
        if (typeof state.on === "boolean") toggle.setAttribute("aria-pressed", String(state.on === value));
        row.append(toggle);
      }
    }
    if (capable("brightness")) {
      const input = node("input");
      input.type = "range";
      input.min = 1;
      input.max = 100;
      input.value = state.brightness ?? 50;
      const read = () => Number(input.value);
      if (mixer) bindMixerValue(input, "brightness", read);
      else input.addEventListener("change", () => task(input, () => send("brightness", read())));
      if (mixer) {
        input.setAttribute("aria-label", brightnessOnly ? brands[target.provider] + " · " + t(9) : t(9));
        const label = field(t(9), input);
        const value = node("output", state.brightness == null ? "–" : input.value + "%");
        input.addEventListener("input", () => { value.textContent = input.value + "%"; });
        label.classList.add("mixer-fader");
        label.append(value);
        row.append(label);
      } else {
        row.append(field(t(9) + (state.brightness == null ? "" : " · " + Math.round(state.brightness) + "%"), input));
      }
    }
    if (!brightnessOnly && capable("rgb")) {
      const input = node("input");
      input.type = "color";
      input.value = stateColor(state.color) || "#ffffff";
      const read = () => input.value.slice(1).match(/../g).map(channel => parseInt(channel, 16));
      if (mixer) bindMixerValue(input, "color", read, true);
      else input.addEventListener("change", () => task(input, () => send("color", read())));
      const label = field(t(10), input);
      if (mixer) label.classList.add("mixer-color");
      row.append(label);
    }
    if (target.id && capable("temperature") && lights[0].provider === "hue") {
      const {min, max} = lights[0].temperature_mirek;
      const caption = temperatureLabels[el("language").value] || temperatureLabels.nl;
      const input = node("input");
      input.type = "range";
      input.dir = "rtl";
      input.setAttribute("aria-label", caption);
      input.min = min;
      input.max = max;
      input.value = state.mirek ?? Math.round((min + max) / 2);
      const label = field(caption, input);
      const reading = node("span");
      label.append(reading);
      const update = () => {
        const kelvin = Math.round(1000000 / Number(input.value));
        reading.textContent = kelvin + " K";
        input.setAttribute("aria-valuetext", reading.textContent);
      };
      if (state.mirek != null) update();
      input.addEventListener("input", update);
      input.addEventListener("change", () => task(input, () => send("temperature", Number(input.value))));
      row.append(label);
    }
    if (target.id && capable("temperature") && lights[0].provider === "govee") {
      const caption = temperatureLabels[el("language").value] || temperatureLabels.nl;
      const input = node("input");
      input.type = "range";
      input.min = 2000;
      input.max = 9000;
      input.step = 1;
      input.setAttribute("aria-label", caption);
      input.value = state.color_temperature_kelvin;
      const reading = node("span");
      const label = field(caption, input);
      label.append(reading);
      const update = () => {
        reading.textContent = input.value + " K";
        input.setAttribute("aria-valuetext", reading.textContent);
      };
      update();
      input.addEventListener("input", update);
      input.addEventListener("change", () => task(input, () => send("temperature", Number(input.value))));
      row.append(label);
    }
    card.append(row);
  }

  function lightCard(light) {
    const card = node("article", "", "lighting-card");
    card.dataset.provider = light.provider;
    const head = node("div", "", "lighting-card-head");
    const mark = node("span", "", "lighting-brand-mark");
    const logo = node("img", "", "brand-wordmark brand-wordmark-" + light.provider);
    logo.src = wordmarks[light.provider];
    logo.alt = "";
    const path = light.provider === "hue" && hueProductImagePath(light);
    mark.append(path ? hueProductImage(light, logo) : logo);
    const color = stateColor(light.state?.color);
    if (color && light.state.on !== false) mark.style.setProperty("--lamp-color", color);
    mark.setAttribute("aria-hidden", "true");
    const title = node("div");
    title.append(node("p", brands[light.provider], "lighting-brand"), node("h3", light.name));
    head.append(mark, title);
    card.append(head, node("p", status(light), "lighting-state"));
    controls(card, [light], {id: light.id}, light.state);
    if (light.provider === "hue") appendHueLampCollections(card, light);
    return card;
  }

  const restorationWords = {
    nl: ["Muziek gestopt", "Twinkly-muziekmodus losgelaten", "Hue Entertainment vrijgegeven", "Hue bevestigt het vrijgeven van de ruimte niet"],
    en: ["Music stopped", "Twinkly music mode released", "Hue Entertainment released", "Hue did not confirm release of the area"],
    de: ["Musik gestoppt", "Twinkly-Musikmodus beendet", "Hue Entertainment freigegeben", "Hue hat die Freigabe des Bereichs nicht bestätigt"],
    es: ["Música detenida", "Modo música de Twinkly liberado", "Hue Entertainment liberado", "Hue no confirmó que la zona quedara libre"],
  };

  function musicStopMessage(report, members) {
    const [stopped, twinkly, hue, hueUnknown] = restorationWords[el("language").value] || restorationWords.nl;
    const details = [stopped];
    if (report?.twinkly_released) details.push(twinkly + " · " + report.twinkly_released);
    if (report?.hue) details.push(report.hue === "released" ? hue : hueUnknown);
    const names = new Map(members.map(light => [light.id, light.name]));
    for (const [action, label] of [["color", t(10)], ["brightness", t(9)]]) {
      for (const [key, outcome] of Object.entries(report?.[action] || {})) {
        const result = {accepted: 29, unconfirmed: 30, skipped: 31, failed: 32}[outcome] ?? 32;
        details.push((names.get(key) || t(37)) + " · " + label + ": " + t(result));
      }
    }
    return details.join(" / ");
  }

  const ledfxInputWords = {
    nl: ["Geen recente LedFX-frames", "LedFX-frames ontvangen, wacht op lichtsignaal"],
    en: ["No recent LedFX frames", "LedFX frames received, waiting for a light signal"],
    de: ["Keine aktuellen LedFX-Frames", "LedFX-Frames empfangen, warte auf Lichtsignal"],
    es: ["Sin fotogramas recientes de LedFX", "Fotogramas de LedFX recibidos, esperando señal de luz"],
  };

  function groupCard(id, members, target) {
    const [startMusic, stopMusic, waitingMusic, activeMusic, participating, skippedMusic] =
      musicWords[el("language").value] || musicWords.nl;
    const card = node("article", "", "mixer-group");
    controls(card, members, target, {}, true);
    if (homeBrand === "all" && data.groups?.[id]) {
      const music = data.music?.group === id;
      if (music) {
        const input = ledfxInputWords[el("language").value] || ledfxInputWords.nl;
        const audio = data.music.audio_received;
        card.append(node("p", audio === false ? input[0] : data.music.live ? activeMusic :
          audio === true ? input[1] : waitingMusic));
        const master = node("input");
        master.type = "range";
        master.min = 1;
        master.max = 100;
        master.value = data.music.level ?? 100;
        const reading = node("output");
        const caption = previewText()[2];
        master.setAttribute("aria-label", caption);
        const label = field(caption, master);
        label.append(reading);
        const readLevel = () => {
          reading.value = master.value + "%";
          master.setAttribute("aria-valuetext", reading.value);
        };
        readLevel();
        master.addEventListener("input", readLevel);
        master.addEventListener("change", () => task(master, async () => {
          const result = await api("lighting/music", {group: id, level: Number(master.value)});
          if (data.music.group === id) data.music.level = result.level;
          const failed = Object.values(result.results).filter(status => status === "failed").length;
          feedback.textContent = failed ? t(32) + " · " + failed : "";
        }));
        card.append(label);
        const timings = Object.entries(data.music.timings || {});
        if (timings.length) {
          const [frame, command, failed, hint] = timingWords[el("language").value] || timingWords.nl;
          const measurements = node("ul", "", "lighting-timings");
          for (const [provider, result] of timings) {
            const failures = result.failed ? " · " + failed + ": " + result.failed : "";
            measurements.append(node("li", brands[provider] + " · " + frame + ": " + result.frame_age_ms +
              " ms · " + command + ": " + result.command_ms + " ms" + failures));
          }
          card.append(measurements, node("small", hint));
        }
      }
      const hueMusic = data.music?.hue;
      if (hueMusic?.group === id) {
        const language = el("language").value;
        const words = hueMusicWords[language] || hueMusicWords.nl;
        const labels = entertainmentWords[language] || entertainmentWords.nl;
        const errors = {pair_again: 8, busy: 10, stream_lost: 11, connection_failed: 9};
        const status = words[hueMusic.state] || labels[errors[hueMusic.state] ?? 13];
        const area = hueMusic.area ? " · " + hueMusic.area : "";
        const skipped = hueMusic.skipped ? " · " + skippedMusic + " " + hueMusic.skipped : "";
        card.append(node("p", "Hue Entertainment · " + status + area + skipped));
      }
      card.append(button(music ? stopMusic : startMusic, async () => {
        const result = await api("lighting/music", music ? {stop: true} : {group: id});
        feedback.textContent = music ? musicStopMessage(result.restoration, members) :
          participating + " · " + result.eligible.length + " / " + skippedMusic + " · " + result.skipped.length;
        await refresh();
      }));
    }
    return card;
  }

  function editGroup(kind, id, opener) {
    const group = data.groups?.[id];
    const lights = new Map(data.lights.map(light => [light.id, light]));
    const form = node("form", "", "lighting-group-form");
    const name = node("input");
    name.required = true;
    name.maxLength = 60;
    name.value = group?.name || "";
    name.autofocus = true;
    form.append(field(kind === "room" ? h(11) : t(24), name));
    const choices = node("fieldset");
    choices.append(node("legend", t(34)));
    for (const key of new Set([...lights.keys(), ...(group?.members || [])])) {
      const light = lights.get(key);
      const choice = node("input");
      choice.type = "checkbox";
      choice.name = "members";
      choice.value = key;
      choice.checked = group?.members.includes(key) || false;
      choices.append(field(light ? light.name + " · " + brands[light.provider] : t(37), choice));
    }
    const save = node("button", t(25));
    form.append(choices, save);
    const dialog = openDialog(group ? t(26) + " · " + group.name : h(kind === "room" ? 7 : 8), form, opener);
    form.addEventListener("submit", event => {
      event.preventDefault();
      const members = new FormData(form).getAll("members");
      if (!members.length) {
        dialog.querySelector("[role=status]").textContent = t(34);
        return;
      }
      task(save, async () => {
        groupBusy = true;
        try {
          const result = await api("lighting/groups", {id, name: name.value, members, ...(kind === "room" && {kind})});
          homeSelection = result.id;
          await refresh().finally(() => dialog.close());
        } finally {
          groupBusy = false;
        }
      });
    });
    if (group) {
      form.append(button(t(27), async () => {
          if (!window.confirm(t(27) + " · " + group.name + "?")) return;
          await api("lighting/groups", {id, delete: true});
          await refresh().finally(() => dialog.close());
        }));
    }

  }

  function sceneList(lights) {
    const [title, nameLabel, groupLabel, applyLabel, missingGroup, needsGroup] =
      sceneWords[el("language").value] || sceneWords.nl;
    const section = node("section", "", "mixer-deck mixer-scenes");
    const header = node("header");
    header.append(node("h3", title));
    section.append(header);
    if (!data.scenes || !data.groups) {
      section.append(node("p", t(32)));
      return section;
    }
    if (Object.keys(data.groups).length) {
      header.append(mixerButton(h(9), "add-scene", item => editScene(undefined, item)));
    } else {
      section.append(node("p", needsGroup));
    }
    const grid = node("div", "", "mixer-pads");
    const keys = new Set(lights.map(light => light.id));
    for (const [id, scene] of Object.entries(data.scenes)) {
      const group = data.groups[scene.group];
      if (homeBrand !== "all" && !group?.members.some(key => keys.has(key))) continue;
      const card = node("article", "", "mixer-pad");
      const options = [group?.name || missingGroup, t(scene.on ? 7 : 8)];
      if (scene.brightness != null) options.push(scene.brightness + "%");
      if (scene.color) options.push(stateColor(scene.color));
      const apply = mixerButton(scene.name, "scene-" + id, async () => {
        const names = new Map(data.lights.map(light => [light.id, light.name]));
        const filter = homeBrand === "all" ? {} : {provider: homeBrand};
        const {results} = await api("lighting/scenes/" + encodeURIComponent(id) + "/apply", filter);
        if (Object.values(results).some(actions => Object.values(actions).some(result => ["accepted", "unconfirmed"].includes(result)))) {
          activeScene = id;
          for (const key of mixerValues.keys()) {
            const target = JSON.parse(key);
            if (target.group === scene.group || target.provider || group.members.includes(target.id)) mixerValues.delete(key);
          }
          grid.querySelectorAll("[aria-pressed]").forEach(pad => pad.setAttribute("aria-pressed", String(pad === apply)));
          const reading = panel.querySelector(".mixer-active");
          if (reading) reading.textContent = h(23) + " · " + scene.name;
        }
        const outcomes = {accepted: 29, unconfirmed: 30, skipped: 31, failed: 32};
        const actions = {power: t(scene.on ? 7 : 8), brightness: t(9), color: t(10)};
        feedback.textContent = Object.entries(results).map(([key, commands]) => {
          const resultsText = Object.entries(commands).map(([action, outcome]) =>
            actions[action] + " " + t(outcomes[outcome])).join(", ");
          return (names.get(key) || t(37)) + " · " + resultsText;
        }).join(" / ");
        await refresh(false);
      }, activeScene === id);
      apply.disabled = !group;
      apply.title = applyLabel + " · " + options.join(" · ");
      if (scene.color) card.style.setProperty("--pad-accent", stateColor(scene.color));
      const edit = mixerButton(t(26), "scene-edit-" + id, item => editScene(id, item));
      edit.setAttribute("aria-label", t(26) + " · " + scene.name);
      card.append(apply, edit);
      grid.append(card);
    }
    section.append(grid);
    if (lights.some(light => light.provider === "twinkly")) {
      const legacy = node("div", "", "mixer-pads mixer-pads-legacy");
      legacy.append(node("h4", h(21)));
      const pads = el("scene-pads");
      for (const [index, original] of [...pads.querySelectorAll(".scene-pad > button:first-child")].entries()) {
        legacy.append(mixerButton(original.textContent, "twinkly-scene-" + index, () => original.click()));
      }
      section.append(legacy);
    }
    return section;
  }

  function editScene(id, opener) {
    const [, nameLabel, groupLabel, , missingGroup] = sceneWords[el("language").value] || sceneWords.nl;
    const groups = Object.entries(data.groups);
    const scene = data.scenes[id];
    const form = node("form", "", "lighting-form lighting-scene-form");
    const name = node("input");
    name.required = true;
    name.maxLength = 60;
    name.value = scene?.name || "";
    name.autofocus = true;
    const group = node("select");
    group.required = true;
    const placeholder = node("option", missingGroup);
    placeholder.value = "";
    placeholder.disabled = true;
    group.append(placeholder);
    for (const [id, row] of groups) {
      const option = node("option", row.name);
      option.value = id;
      group.append(option);
    }
    group.value = scene ? (data.groups[scene.group] ? scene.group : "") : groups[0]?.[0] || "";
    const power = node("select");
    for (const [value, label] of [["on", t(7)], ["off", t(8)]]) {
      const option = node("option", label);
      option.value = value;
      power.append(option);
    }
    power.value = scene?.on === false ? "off" : "on";
    const level = node("input");
    level.type = "number";
    level.min = 1;
    level.max = 100;
    level.placeholder = "1–100%";
    level.value = scene?.brightness ?? "";
    const color = node("input");
    color.type = "color";
    color.value = stateColor(scene?.color) || "#ffbf69";
    color.setAttribute("aria-label", t(10));
    const useColor = node("input");
    useColor.type = "checkbox";
    useColor.checked = Boolean(scene?.color);
    const update = () => {
      const on = power.value === "on";
      level.disabled = useColor.disabled = !on;
      color.disabled = !on || !useColor.checked;
    };
    update();
    power.addEventListener("change", update);
    useColor.addEventListener("change", update);
    const save = node("button", t(25));
    form.append(field(nameLabel, name), field(groupLabel, group), field(t(7) + " / " + t(8), power),
      field(t(9), level), field(t(10), useColor), color, save);
    const dialog = openDialog(scene ? t(26) + " · " + scene.name : h(9), form, opener);
    form.addEventListener("submit", event => {
      event.preventDefault();
      task(save, async () => {
        const on = power.value === "on";
        const payload = {id, name: name.value, group: group.value, on};
        if (on && level.value) payload.brightness = Number(level.value);
        if (on && useColor.checked) payload.color = color.value.slice(1).match(/../g).map(channel => parseInt(channel, 16));
        await api("lighting/scenes", payload);
        await refresh().finally(() => dialog.close());
      });
    });
    if (scene) {
      form.append(button(t(27), async () => {
          if (!window.confirm(t(27) + " · " + scene.name + "?")) return;
          await api("lighting/scenes", {id, delete: true});
          if (activeScene === id) activeScene = undefined;
          await refresh().finally(() => dialog.close());
        }));
    }
  }

  function connectionCard(brand, onConnected) {
    const card = node("article", "", "lighting-card");
    card.dataset.provider = brand;
    card.append(node("h3", brands[brand]));
    const connections = data.connections[brand];
    const rows = node("div", "", "lighting-connections");
    if (connections === null) rows.append(node("p", t(32)));
    const setup = node("details");
    setup.append(node("summary", t(33)));
    const id = node("input");
    id.maxLength = 128;
    id.required = true;
    const address = node("input");
    address.required = true;
    const pin = node("input");
    pin.maxLength = 64;
    pin.autocomplete = "off";
    pin.required = brand === "hue";
    const found = node("div", "", "lighting-controls");
    const form = node("form", "", "lighting-form");
    const submit = node("button", t(14));
    function select(identifier, ip, reconnect = false) {
      id.value = identifier;
      address.value = ip;
      pin.value = "";
      submit.textContent = t(reconnect ? 15 : 14);
      setup.open = true;
    }
    for (const row of connections || []) {
      const connection = node("div", "", "lighting-connection");
      connection.append(node("span", row.id + " · " + row.address + " · " + status({...row, provider: brand})),
        button(t(15), () => { select(row.id, row.address, true); address.focus(); }));
      rows.append(connection);
    }
    setup.append(node("p", t(brand === "hue" ? 21 : 22)), button(t(13), async () => {
      const result = await api("providers/" + brand + "/discover", {});
      found.replaceChildren();
      for (const device of result.devices) {
        const ip = device.ip || device.addresses?.[0];
        if (!ip) continue;
        found.append(button((device.name || device.sku || device.bridge_id) + " · " + ip,
          () => select(device.bridge_id || device.device, ip)));
      }
      if (!found.childElementCount) found.append(node("p", t(35)));
    }), found);
    form.append(field(t(16), id), field(t(17), address));
    address.addEventListener("input", () => { pin.value = ""; });
    if (brand === "hue") {
      form.append(field(t(19), pin), button(t(18), async () => {
        const ip = address.value;
        const result = await api("providers/hue/certificate", {address: ip});
        if (address.value === ip && form.isConnected && window.confirm(t(20) + "\n\n" + result.certificate_sha256)) {
          pin.value = result.certificate_sha256;
        }
      }));
    }
    form.append(submit);
    form.addEventListener("submit", event => {
      event.preventDefault();
      task(submit, async () => {
        await api("providers/" + brand + "/connect",
          {id: id.value, address: address.value, certificate_sha256: pin.value});
        pin.value = "";
        (card.closest("dialog[open]")?.querySelector("[role=status]") || feedback).textContent = t(38);
        await refresh();
        onConnected?.();
      });
    });
    setup.append(form);
    card.append(rows, setup);
    return card;
  }

  function lampTestPanel(brand, after) {
    const section = node("section", "", "lighting-surface gap provider-test-" + brand);
    after.after(section);
    let choice = "";
    let testStatus;
    let timer;
    let busy = false;

    async function update() {
      clearTimeout(timer);
      try {
        testStatus = await api("lighting/" + brand + "-test");
      } catch {
        testStatus = {result: "failed"};
      }
      if (context === "tests") renderTests();
    }

    function renderTests() {
      clearTimeout(timer);
      const labels = brand === "hue" ? (hueTestWords[el("language").value] || hueTestWords.nl) :
        (goveeTestWords[el("language").value] || goveeTestWords.nl);
      const lights = (data?.lights || []).filter(light => light.provider === brand);
      section.replaceChildren(node("h3", brands[brand]), node("p", labels[12]));
      const select = node("select");
      select.append(new Option(labels[0], ""));
      for (const light of lights) {
        const option = new Option(light.name + " · " + status(light), light.id);
        option.disabled = light.status === "unavailable";
        select.append(option);
      }
      select.value = lights.some(light => light.id === choice && light.status !== "unavailable") ? choice : "";
      const selected = lights.find(light => light.id === select.value);
      select.onchange = () => {
        choice = select.value;
        renderTests();
        section.querySelector("select").focus();
      };
      section.append(field(labels[0], select));
      const actions = node("div", "", "lighting-controls");
      const run = async test => {
        busy = true;
        clearTimeout(timer);
        try {
          testStatus = await api("lighting/" + brand + "-test", {test, id: selected?.id});
        } catch {
          testStatus = {result: "failed"};
        } finally {
          busy = false;
          if (context === "tests") renderTests();
        }
      };
      const running = testStatus?.result === "running";
      const tests = [["identify", "power"], ["power", "power"], ["brightness", "brightness"],
        ["rgb", "rgb"], ["rainbow", "rgb"], ["temperature", "temperature"]];
      for (const [index, [test, capability]] of tests.entries()) {
        if (brand === "govee" && test === "temperature") continue;
        const action = button(labels[index + 1], () => run(test));
        action.disabled = busy || running || !selected?.capabilities[capability] ||
          (brand === "govee" && capability === "rgb" && Boolean(selected?.state.color_temperature_kelvin));
        actions.append(action);
      }
      const stop = button(labels[7], () => run("stop"));
      stop.disabled = busy || !running;
      actions.append(stop);
      const result = {running: 8, restored: 9, failed: 10, restore_failed: 11, restore_unverified: 13}[testStatus?.result];
      section.append(actions);
      if (result != null) {
        const message = node("p", labels[result]);
        message.setAttribute("role", "status");
        section.append(message);
      }
      if (running && !busy) timer = setTimeout(update, 1000);
    }
    return {section, update, render: renderTests};
  }

  const hueTestPanel = lampTestPanel("hue", el("tests-content"));
  const goveeTestPanel = lampTestPanel("govee", hueTestPanel.section);

  function hueSceneCard(bridge, scene, activate) {
    const [chooseImage, removeImage] = previewText();
    const card = node("div", "", "hue-scene-card");
    const path = "providers/hue/scene-image/" + encodeURIComponent(bridge) + "/" + encodeURIComponent(scene.id);
    const play = button(scene.name, activate);
    const cover = node("span", "", "hue-scene-cover");
    cover.setAttribute("aria-hidden", "true");
    const colors = (scene.palette || []).map(stateColor).filter(Boolean);
    if (colors.length === 1) colors.push(colors[0]);
    if (colors.length) {
      cover.style.backgroundImage = "linear-gradient(165deg, #fff2, transparent 48%, #0008), " +
        "linear-gradient(125deg, " + colors.join(", ") + ")";
    }
    if (scene.has_image) {
      const image = node("img");
      image.alt = "";
      image.loading = "lazy";
      image.addEventListener("error", () => image.remove(), {once: true});
      image.src = path + "?v=" + (sceneImageRevisions.get(path) || 0);
      cover.append(image);
    }
    play.prepend(cover);
    const upload = node("input");
    upload.type = "file";
    upload.accept = "image/jpeg,image/png,image/webp";
    upload.className = "hue-scene-file";
    upload.setAttribute("aria-label", chooseImage + " · " + scene.name);
    const update = async image => {
      await api(path, {image});
      sceneImageRevisions.set(path, Date.now());
      await loadCollections();
    };
    const choose = node("label", "", "hue-scene-upload");
    choose.append(node("span", chooseImage), upload);
    upload.addEventListener("change", () => {
      if (upload.files.length) task(upload, async () => {
        try {
          await update(await encodeImage(upload.files[0]));
        } finally {
          upload.value = "";
        }
      });
    });
    card.append(play, choose);
    if (scene.has_image) {
      const remove = button(removeImage, () => update(null));
      remove.setAttribute("aria-label", removeImage + " · " + scene.name);
      card.append(remove);
    }
    return card;
  }

  function hueLampCollections(light) {
    if (!light.id.startsWith("[")) return [undefined, []];
    const [, bridgeId, resourceId] = JSON.parse(light.id);
    const bridge = collections.find(bridge => bridge.id === bridgeId);
    return [bridge, (bridge?.collections || []).filter(entry => entry.members?.includes(resourceId))];
  }

  function appendHueLampCollections(card, light) {
    const [bridge, entries] = hueLampCollections(light);
    const labels = collectionWords[el("language").value] || collectionWords.nl;
    for (const entry of entries) {
      if (entry.kind !== "zone" && !entry.scenes.length) continue;
      const section = node("details", "", "hue-lamp-collection");
      section.append(node("summary", (entry.kind === "zone" ? labels[2] : labels[3]) + " · " + entry.name));
      const send = async (id, action, value) => {
        await api("providers/hue/collections/control", {bridge:bridge.id,id,action,value});
        feedback.textContent = t(29);
      };
      if (entry.kind === "zone" && entry.grouped_light) {
        const row = node("div", "", "lighting-controls");
        row.append(button(t(7), () => send(entry.grouped_light, "power", true)),
          button(t(8), () => send(entry.grouped_light, "power", false)));
        section.append(row);
      }
      for (const scene of entry.scenes) {
        section.append(button(scene.name, () => send(scene.id, "recall")));
      }
      card.append(section);
    }
  }

  function hueRoomCards(lights) {
    const rooms = new Map();
    const homeRooms = Object.entries(data.groups || {}).filter(([, group]) => group.kind === "room");
    const fallback = ({nl:"Zonder kamer",en:"Unassigned",de:"Ohne Raum",es:"Sin habitación"})[el("language").value] || "Unassigned";
    for (const light of lights) {
      const home = homeRooms.find(([, room]) => room.members.includes(light.id));
      const key = home?.[0] ?? "";
      if (!rooms.has(key)) rooms.set(key, {name:home?.[1].name || fallback, lights:[]});
      rooms.get(key).lights.push(light);
    }
    return [...rooms.values()].map(room => {
      const section = node("section", "", "hue-room-section");
      const cards = node("div", "", "lighting-grid hue-compact-grid");
      cards.append(...room.lights.map(lightCard));
      section.append(node("h3", room.name), cards);
      return section;
    });
  }

  function renderCollections() {
    hueCollections.hidden = context !== "hue";
    if (hueCollections.hidden) return;
    const labels = collectionWords[el("language").value] || collectionWords.nl;
    const title = node("h2", labels[0]);
    title.id = "hue-collections-title";
    const heading = node("div", "", "lighting-heading");
    heading.append(title, button(t(2), loadCollections));
    hueCollections.replaceChildren(heading);
    if (collectionsStatus !== "ready") {
      hueCollections.append(node("p", t(collectionsStatus === "loading" ? 36 : 32)));
      return;
    }
    if (!collections.length) hueCollections.append(node("p", labels[4]));
    const hasInlineCollections = (data?.lights || []).some(light => light.provider === "hue" && hueLampCollections(light)[1].length);
    const overview = hasInlineCollections ? node("details") : hueCollections;
    if (hasInlineCollections) {
      overview.append(node("summary", labels[0]));
      hueCollections.append(overview);
    }
    for (const bridge of collections) {
      const grid = node("div", "", "lighting-grid hue-collection-grid");
      overview.append(node("h3", "Hue Bridge · " + bridge.address), grid);
      if (bridge.status !== "online" || !bridge.collections.length) {
        grid.append(node("p", bridge.status === "online" ? labels[4] : t(4)));
        continue;
      }
      const send = async (id, action, value) => {
        await api("providers/hue/collections/control", {bridge: bridge.id, id, action, value});
        if (context === "hue") {
          feedback.textContent = t(29);
          await Promise.all([loadCollections(), refresh(false).catch(() => {})]);
        }
      };
      for (const collection of bridge.collections) {
        const card = node("article", "", "lighting-card hue-collection");
        card.append(node("p", collection.kind === "room" ? labels[1] : labels[2]),
          node("h4", collection.name));
        const controls = node("div", "", "lighting-controls");
        if (collection.grouped_light && typeof collection.on === "boolean") {
          for (const [value, index] of [[true, 7], [false, 8]]) {
            const toggle = button(t(index), () => send(collection.grouped_light, "power", value));
            toggle.setAttribute("aria-pressed", String(collection.on === value));
            controls.append(toggle);
          }
        }
        if (collection.grouped_light && Number.isFinite(collection.brightness)) {
          const level = node("input");
          level.type = "range";
          level.min = 1;
          level.max = 100;
          level.value = collection.brightness;
          level.addEventListener("change", () => task(level,
            () => send(collection.grouped_light, "brightness", Number(level.value))));
          controls.append(field(t(9), level));
        }
        if (controls.childElementCount) card.append(controls);
        if (collection.scenes.length) {
          const scenes = node("div", "", "hue-scenes");
          for (const scene of collection.scenes) {
            scenes.append(hueSceneCard(bridge.id, scene, () => send(scene.id, "recall")));
          }
          card.append(node("h5", labels[3]), scenes);
        }
        grid.append(card);
      }
    }
  }

  async function loadCollections() {
    const request = ++collectionsRead;
    try {
      const result = await api("providers/hue/collections");
      if (request !== collectionsRead) return;
      collections = result.bridges;
      collectionsStatus = "ready";
      if (context === "hue" && data) render();
    } catch {
      if (request !== collectionsRead) return;
      collectionsStatus = "failed";
    }
    renderCollections();
  }

  const renderTools = window.createLightingTools({
    mount: el("lighting-tools"), house: el("house-page"), nav: el("nav-house"), api, node, field,
    language: () => el("language").value,
    roomLightControls: (card, light, status) => controls(card, [light], {id: light.id}, light.state, false, status),
  });

  function openDialog(title, content, opener) {
    const dialog = node("dialog", "", "mixer-dialog");
    const heading = node("h2", title);
    heading.id = "mixer-dialog-title";
    dialog.setAttribute("aria-labelledby", heading.id);
    const message = node("p", "", "mixer-dialog-message");
    message.setAttribute("role", "status");
    const close = button(h(13), () => dialog.close());
    const header = node("header");
    header.append(heading, close);
    dialog.append(header, message, content);
    document.querySelector("main").append(dialog);
    homeDialog = dialog;
    dialog.addEventListener("close", () => {
      dialog.remove();
      if (homeDialog === dialog) homeDialog = undefined;
      if (context === "home") {
        const fallback = [...panel.querySelectorAll("[data-mixer-key]")]
          .find(item => item.dataset.mixerKey === opener?.dataset.mixerKey);
        (opener?.isConnected ? opener : fallback || panel.querySelector("button"))?.focus();
      }
    }, {once: true});
    dialog.showModal();
    return dialog;
  }

  function addLight(opener) {
    const content = node("div", "", "mixer-add-light");
    const brand = node("select");
    for (const [key, name] of Object.entries(brands)) brand.add(new Option(name, key));
    brand.value = homeBrand === "all" ? "twinkly" : homeBrand;
    brand.setAttribute("aria-label", h(6));
    const setup = node("div");
    const assignment = node("form", "", "lighting-form");
    const light = node("select");
    const collection = node("select");
    const assign = node("button", h(15));
    function updateAssignment() {
      const before = light.value;
      light.replaceChildren(new Option(h(16), ""));
      for (const entry of data.lights.filter(item => item.provider === brand.value)) {
        light.add(new Option(entry.name, entry.id));
      }
      if ([...light.options].some(option => option.value === before)) light.value = before;
      collection.replaceChildren(new Option(h(17), ""));
      for (const [kind, label] of [["rooms", h(3)], ["groups", h(4)]]) {
        const options = node("optgroup");
        options.label = label;
        for (const [id, entry] of Object.entries(data.groups || {})) {
          if ((entry.kind === "room") === (kind === "rooms")) options.append(new Option(entry.name, id));
        }
        if (options.children.length) collection.append(options);
      }
      assignment.hidden = light.options.length < 2 || collection.options.length < 2;
    }
    function showSetup() {
      setup.replaceChildren();
      if (brand.value === "twinkly") {
        const ip = node("input");
        ip.placeholder = "192.168.1.50";
        ip.inputMode = "decimal";
        const connect = async address => {
          const result = await register(address);
          dialog.querySelector("[role=status]").textContent = result;
          await refresh();
          updateAssignment();
        };
        setup.append(field(t(17), ip), button(t(14), () => {
          if (ip.reportValidity()) return connect(ip.value.trim());
        }), button(t(13), () => connect("")));
        ip.required = true;
      } else {
        const card = connectionCard(brand.value, updateAssignment);
        card.querySelector("details").open = true;
        setup.append(card);
      }
      updateAssignment();
    }
    light.required = collection.required = true;
    assignment.append(field(h(16), light), field(h(17), collection), assign);
    content.append(brand, setup, assignment);
    const dialog = openDialog(h(6), content, opener);
    brand.addEventListener("change", showSetup);
    assignment.addEventListener("submit", event => {
      event.preventDefault();
      task(assign, async () => {
        await api("lighting/groups", {id: collection.value, member: light.value});
        await refresh().finally(() => dialog.close());
      });
    });
    showSetup();
  }

  function mixerButton(label, key, handler, pressed) {
    const item = button(label, handler);
    item.dataset.mixerKey = key;
    if (pressed !== undefined) item.setAttribute("aria-pressed", String(pressed));
    return item;
  }

  function demoShow(opener) {
    const labels = ({
      nl: ["Demo lichtshow", "Start", "Stop", "Kies een kamer op Home met kleurlampen.", "Klaar", "De kamer heeft de kleurwissel niet bevestigd."],
      en: ["Demo light show", "Start", "Stop", "Choose a room on Home with colour lights.", "Finished", "The room did not confirm the colour change."],
      de: ["Demo-Lichtshow", "Start", "Stopp", "Wähle auf Home einen Raum mit Farblampen.", "Fertig", "Der Raum hat den Farbwechsel nicht bestätigt."],
      es: ["Demostración de luces", "Iniciar", "Detener", "Elige una habitación de Inicio con luces de color.", "Finalizado", "La habitación no confirmó el cambio de color."],
    })[el("language").value] || ["Demo light show", "Start", "Stop", "Choose a room on Home with colour lights.", "Finished", "The room did not confirm the colour change."];
    function roomLights(room) {
      const members = new Set(room.members);
      const lights = new Map(data.lights.map(light => [light.id, light]));
      const grouped = new Set(), claimed = new Set(), targets = [];
      for (const [id, group] of Object.entries(data.spatial_groups || {})) {
        if (group.provider !== "twinkly") continue;
        const [, key] = JSON.parse(id);
        if (typeof key !== "string" || !key.startsWith("twinkly:")) continue;
        group.members.forEach(member => grouped.add(member));
        if (!group.members.length || !group.members.every(member => members.has(member) && !claimed.has(member))) continue;
        group.members.forEach(member => claimed.add(member));
        targets.push({id, name:group.name, members:group.members, target:{twinklyGroup:key.slice(8)},
          rgb:group.members.some(member => lights.get(member)?.capabilities?.rgb)});
      }
      for (const id of members) {
        const light = lights.get(id);
        if (!grouped.has(id) && light?.capabilities?.power && light.status !== "unavailable") {
          targets.push({id, name:light.name, members:[id], target:{id}, rgb:light.capabilities.rgb});
        }
      }
      return {targets, grouped:[...members].some(id => grouped.has(id))};
    }
    const rooms = Object.entries(data?.groups || {}).filter(([, group]) =>
      group.kind === "room" && roomLights(group).targets.some(light => light.rgb));
    const room = node("select");
    for (const [id, group] of rooms) room.add(new Option(group.name, id));
    const content = node("div");
    const preview = node("div", "✦", "mixer-demo-preview");
    preview.setAttribute("aria-hidden", "true");
    const controls = node("div", "", "lighting-controls");
    const palette = [[225,38,69], [24,170,91], [255,173,68], [100,68,238], [255,214,148]];
    let running = false, timer, run = 0;
    const stop = (message = "") => {
      running = false;
      run++;
      clearTimeout(timer);
      preview.classList.remove("is-playing");
      room.disabled = false;
      start.disabled = !rooms.length;
      end.disabled = true;
      status.textContent = message;
    };
    const start = button(labels[1], () => {
      if (running || !room.value) return;
      running = true;
      room.disabled = start.disabled = true;
      end.disabled = false;
      status.textContent = "";
      const group = room.value;
      const currentRun = ++run;
      preview.classList.add("is-playing");
      const send = async (target, action, value) => {
        if (target.twinklyGroup) {
          const mode = action === "power" ? (value ? "on" : "off") : action;
          const result = await request("control", {group:target.twinklyGroup, action:mode,
            value:action === "color" ? stateColor(value) : value});
          return !result.failed?.length && !result.offline?.length;
        }
        const result = await api("lighting/control", {...target, action, value});
        return Object.values(result.results || {}).some(value => value === "accepted" || value === "unconfirmed");
      };
      const perform = async () => {
        const overview = await api("lighting/projects/overview").catch(() => ({walls:[]}));
        if (currentRun !== run) return;
        const {targets, grouped} = roomLights(data.groups[group]);
        const colors = targets.filter(light => light.rgb);
        const linkedRoom = Object.keys(overview.room_groups || {}).find(id => overview.room_groups[id] === group);
        const position = new Map();
        for (const wall of overview.walls || []) {
          if (linkedRoom !== undefined && Math.floor(wall.slot / 4) !== Number(linkedRoom)) continue;
          const side = wall.slot % 4;
          for (const [id, point] of wall.points || []) {
            const distance = (point[0] / 100 - .5) * (wall.dimensions?.width_m || 4);
            const placement = wall.placement;
            const x = placement ? placement.x_m + distance * Math.cos(placement.angle * Math.PI / 180) :
              [distance, 3, -distance, -3][side];
            for (const lamp of [id, ...(data.spatial_groups?.[id]?.members || [])]) if (!position.has(lamp)) position.set(lamp, x);
          }
        }
        const location = light => position.get(light.id) ?? Math.min(...light.members.map(id => position.get(id) ?? Infinity));
        colors.sort((left, right) => location(left) - location(right));
        const blackout = grouped
          ? (await Promise.allSettled(targets.map(light => send(light.target, "power", false))))
            .some(result => result.status === "fulfilled" && result.value)
          : await send({group}, "power", false);
        if (!colors.length || !blackout) {
          if (currentRun === run) stop(labels[5]);
          return;
        }
        const sequence = [...colors, ...colors.slice().reverse()];
        const step = async index => {
          if (currentRun !== run) return;
          try {
            if (index > 0) await send(sequence[index - 1].target, "power", false);
            if (currentRun !== run) return;
            if (index === sequence.length) return stop(labels[4]);
            const light = sequence[index], target = light.target;
            const color = palette[index % palette.length];
            if (!await send(target, "color", color)) throw new Error();
            if (currentRun !== run) return;
            if (!await send(target, "power", true)) throw new Error();
            if (currentRun !== run) return;
            preview.style.setProperty("--demo-color", "rgb(" + color.join(",") + ")");
            status.textContent = light.name;
            timer = setTimeout(() => step(index + 1), index < colors.length ? 1200 : 750);
          } catch {
            if (currentRun === run) stop(labels[5]);
          }
        };
        if (currentRun === run) timer = setTimeout(() => step(0), 650);
      };
      perform().catch(() => { if (currentRun === run) stop(labels[5]); });
    });
    const end = button(labels[2], () => stop());
    const status = node("p", rooms.length ? "" : labels[3]);
    status.setAttribute("role", "status");
    start.disabled = room.disabled = !rooms.length;
    end.disabled = true;
    controls.append(field(h(3), room), start, end);
    content.append(preview, controls, status);
    const dialog = openDialog(labels[0], content, opener);
    dialog.addEventListener("close", () => stop(), {once:true});
  }

  function renderMixer() {
    const mixer = node("section", "", "home-mixer");
    const header = node("header", "", "mixer-header");
    const brandBar = node("div", "", "mixer-switches");
    brandBar.setAttribute("role", "group");
    brandBar.setAttribute("aria-label", h(0));
    for (const [brand, label] of Object.entries({all: h(1), ...brands})) {
      brandBar.append(mixerButton(label, "brand-" + brand, () => {
        homeBrand = brand;
        activeScene = undefined;
        render();
      }, homeBrand === brand));
    }
    const tools = node("div", "", "mixer-switches");
    const add = mixerButton(h(6), "add-light", addLight);
    add.className = "mixer-add";
    add.disabled = !data;
    const demoLabel = ({nl:"Demo lichtshow", en:"Demo light show", de:"Demo-Lichtshow", es:"Demostración de luces"})[el("language").value] || "Demo light show";
    tools.append(mixerButton(t(2), "refresh", () => refresh()), add, mixerButton(demoLabel, "demo-show", demoShow));
    header.append(brandBar, tools);
    mixer.append(header);
    if (!data) {
      mixer.append(node("p", pending ? t(36) : t(32), "mixer-empty"));
      return mixer;
    }

    const channels = node("div", "", "mixer-decks");
    const targets = node("section", "", "mixer-deck");
    const categories = node("div", "", "mixer-switches mixer-categories");
    categories.setAttribute("role", "group");
    categories.setAttribute("aria-label", h(10));
    for (const [view, label] of [["lights", h(2)], ["rooms", h(3)], ["groups", h(4)]]) {
      categories.append(mixerButton(label, "view-" + view, () => {
        homeView = view;
        homeSelection = view === "lights" ? "all" : undefined;
        render();
      }, homeView === view));
    }
    targets.append(categories);
    const visibleLights = data.lights.filter(light => homeBrand === "all" || light.provider === homeBrand);
    const byKey = new Map(visibleLights.map(light => [light.id, light]));
    const rows = node("div", "", "mixer-targets");
    const entries = [];
    if (homeView === "lights") {
      if (visibleLights.length) entries.push({id: "all", name: homeBrand === "all" ? t(1) : brands[homeBrand],
        lights: visibleLights, target: {provider: homeBrand}});
      for (const light of visibleLights) {
        entries.push({id: light.id, name: light.name, detail: brands[light.provider] + " · " + status(light),
          lights: [light], target: {id: light.id}, state: light.state});
      }
    } else {
      for (const [id, entry] of Object.entries(data.groups || {})) {
        if ((entry.kind === "room") !== (homeView === "rooms")) continue;
        const lights = entry.members.map(key => byKey.get(key)).filter(Boolean);
        if (!lights.length && homeBrand !== "all") continue;
        entries.push({id, name: entry.name, lights, group: entry, editable: true,
          target: homeBrand === "all" ? {group: id} : {group: id, provider: homeBrand}});
      }
      if (homeView === "groups" && ["all", "twinkly"].includes(homeBrand)) {
        for (const [id, entry] of Object.entries(visibleGroups() || {})) {
          const lights = entry.members.map(key => byKey.get(JSON.stringify(["twinkly", key]))).filter(Boolean);
          entries.push({id: "twinkly-" + id, name: entry.name, detail: brands.twinkly, lights,
            target: {twinklyGroup: id}});
        }
      }
    }
    const selected = entries.find(entry => entry.id === homeSelection) || entries[0];
    for (const entry of entries) {
      const row = node("div", "", "mixer-target");
      const pick = mixerButton(entry.name, "target-" + entry.id, () => {
        homeSelection = entry.id;
        render();
      }, entry === selected);
      if (entry.detail) pick.append(node("small", entry.detail));
      row.append(pick);
      if (entry.editable) {
        const edit = mixerButton(t(26), "edit-" + entry.id, item => editGroup(homeView === "rooms" ? "room" : "group", entry.id, item));
        edit.setAttribute("aria-label", t(26) + " · " + entry.name);
        row.append(edit);
      }
      rows.append(row);
    }
    if (!entries.length) rows.append(node("p", homeView === "lights" ? t(11) : h(homeView === "rooms" ? 18 : 19)));
    targets.append(rows);
    if (homeView !== "lights" && data.groups && visibleLights.length) {
      const room = homeView === "rooms";
      targets.append(mixerButton(h(room ? 7 : 8), "add-collection", item => editGroup(room ? "room" : "group", undefined, item)));
    }

    const center = node("section", "", "mixer-deck mixer-center");
    const screen = node("div", "", "mixer-screen");
    screen.append(node("h3", selected?.name || h(10)));
    if (selected) {
      const counts = Object.keys(brands).map(brand => {
        const count = selected.lights.filter(light => light.provider === brand).length;
        return count ? brands[brand] + " " + count : "";
      }).filter(Boolean);
      const selectedScene = data.scenes?.[activeScene];
      screen.append(node("p", counts.join("  /  ") || t(11)));
      screen.append(node("p", selectedScene ? h(23) + " · " + selectedScene.name : "", "mixer-active"));
    }
    center.append(screen);
    if (selected?.group) center.append(groupCard(selected.id, selected.lights, selected.target));
    else if (selected?.lights.length) controls(center, selected.lights, selected.target, selected.state, true);

    if (selected && !selected.target.id && !selected.target.twinklyGroup && homeBrand === "all") {
      const faders = node("div", "", "mixer-brand-faders");
      for (const [provider, name] of Object.entries(brands)) {
        const lights = selected.lights.filter(light => light.provider === provider && light.capabilities.brightness);
        const channel = node("section");
        channel.append(node("h4", name));
        if (lights.some(light => light.status !== "unavailable")) {
          controls(channel, lights, {...selected.target, provider}, {}, true, feedback, true);
        } else channel.append(node("small", lights.length ? t(4) : "–"));
        faders.append(channel);
      }
      center.append(faders);
    }
    channels.append(targets, center, sceneList(visibleLights));
    mixer.append(channels);
    return mixer;
  }

  function render() {
    renderTools(context, data);
    panel.hidden = !["home", "hue", "govee"].includes(context);
    if (context === "tests") {
      hueTestPanel.render();
      goveeTestPanel.render();
      return;
    }
    const mount = context === "control" ? studio : context === "settings" ? settings : panel;
    if (!["home", "hue", "govee", "control", "settings", "tests"].includes(context)) return;
    if (context === "home") {
      const focusKey = mount.contains(document.activeElement) && document.activeElement.dataset.mixerKey;
      mount.replaceChildren(renderMixer());
      if (focusKey && !homeDialog?.open) [...mount.querySelectorAll("[data-mixer-key]")]
        .find(item => item.dataset.mixerKey === focusKey)?.focus();
      return;
    }
    mount.replaceChildren();
    const title = context === "settings" ? t(12) : brands[context] || brands.twinkly;
    const heading = node("div", "", "lighting-heading");
    heading.append(node("h2", title), button(t(2), () => refresh()));
    mount.append(heading);
    if (!data) {
      mount.append(node("p", pending ? t(36) : t(32)));
      return;
    }
    const grid = node("div", "", "lighting-grid");
    if (context === "settings") {
      grid.append(connectionCard("hue"), connectionCard("govee"));
    } else {
      const provider = context === "control" ? "twinkly" : context;
      const lights = data.lights.filter(light => light.provider === provider);
      if (provider === "hue") {
        grid.classList.add("hue-room-grid");
        grid.append(...hueRoomCards(lights));
      } else grid.append(...lights.map(lightCard));
      if (!grid.childElementCount) grid.append(node("p", t(11)));
      if (provider === "hue" || provider === "govee") {
        const link = node("a", t(33));
        link.href = "#instellingen";
        heading.append(link);
      }
    }
    mount.append(grid);
  }

  async function refresh(force = true) {
    if (force && pending) await pending.catch(() => {});
    const previous = data;
    pending ||= api("lighting").then(value => { data = value; }).finally(() => { pending = null; });
    try {
      await pending;
    } finally {
      renderTools(context, data);
      const settingsInUse = context === "settings" && settings.querySelector("details[open]");
      const groupInUse = context === "home" && (groupBusy || homeDialog?.open || mixerWrites ||
        panel.contains(document.activeElement) && document.activeElement.matches("input[type=color], input[type=range]"));
      if (force || (!settingsInUse && !groupInUse && JSON.stringify(previous) !== JSON.stringify(data))) {
        render();
      }
    }
  }

  async function loadEntertainment() {
    const revision = ++entertainmentRead;
    entertainmentControls = null;
    const labels = entertainmentWords[el("language").value] || entertainmentWords.nl;
    const reload = node("button", t(2));
    reload.type = "button";
    reload.addEventListener("click", loadEntertainment);
    entertainment.replaceChildren(node("h2", "Hue Entertainment"), node("p", labels[0]), reload);
    const loading = node("p", t(36));
    const check = {
      nl: ["Praktijktest op je Hue Bridge", "Zet de lampen van de Entertainmentruimte aan en start Regenboog. Verlaag de helderheid en stop het effect. Controleer in de Hue-app of de ruimte weer vrij is. Herhaal met LedFX-muziek op Home, met alle lampen van die Entertainmentruimte in dezelfde groep."],
      en: ["Test on your Hue Bridge", "Turn on the lights in the Entertainment area and start Rainbow. Lower brightness and stop the effect. Check the Hue app to see if the area is free again. Repeat with LedFX music on Home, with all lights from the Entertainment area in the same group."],
      de: ["Test auf deiner Hue Bridge", "Schalte die Lampen des Entertainment-Bereichs ein und starte Regenbogen. Dimme das Licht und stoppe den Effekt. Prüfe in der Hue-App, ob der Bereich wieder frei ist. Wiederhole den Test auf der Startseite mit LedFX und allen Lampen des Bereichs in einer Gruppe."],
      es: ["Prueba en tu puente Hue", "Enciende las luces de la zona de entretenimiento e inicia Arcoíris. Baja el brillo y detén el efecto. Comprueba en la app Hue si la zona vuelve a estar libre. Repite con LedFX en Inicio y con todas las luces de la zona en el mismo grupo."],
    };
    const [checkTitle, steps] = check[el("language").value] || check.nl;
    const guide = node("details");
    guide.append(node("summary", checkTitle), node("p", steps));
    entertainment.append(guide, loading);
    try {
      const result = await api(entertainmentPath);
      if (revision !== entertainmentRead || context !== "hue") return;
      loading.remove();
      const area = node("select");
      const choices = [];
      for (const bridge of result.bridges) {
        if (!bridge.has_client_key || bridge.unavailable) {
          entertainment.append(node("p", bridge.address + " · " + labels[bridge.unavailable ? 9 : 8]));
          continue;
        }
        for (const choice of bridge.areas) {
          const option = node("option", choice.name + " · " + bridge.address);
          option.value = choices.length;
          choices.push({bridge: bridge.bridge, area: choice.id, name: choice.name});
          area.append(option);
        }
      }
      if (!choices.length) entertainment.append(node("p", labels[7]));
      const effect = node("select");
      for (const [value, caption] of [["rainbow", labels[2]], ["sunset", labels[3]]]) {
        const option = node("option", caption);
        option.value = value;
        effect.append(option);
      }
      effect.setAttribute("aria-label", "Hue Entertainment");
      const brightness = node("input");
      Object.assign(brightness, {type: "number", min: 1, max: 100, value: entertainmentSelection?.brightness ?? 40, required: true});
      const savedArea = choices.findIndex(choice => choice.bridge === entertainmentSelection?.bridge &&
        choice.area === entertainmentSelection?.area);
      if (savedArea >= 0) area.value = String(savedArea);
      effect.value = entertainmentSelection?.effect ?? "rainbow";
      const rememberSelection = () => {
        if (!choices.length || !brightness.validity.valid) return;
        entertainmentSelection = {...choices[Number(area.value)], effect: effect.value, brightness: brightness.valueAsNumber};
      };
      area.onchange = effect.onchange = brightness.onchange = rememberSelection;
      const start = node("button", labels[4]);
      const stop = node("button", labels[5]);
      start.type = stop.type = "button";
      const status = node("p");
      status.setAttribute("role", "status");
      const row = node("div", "", "lighting-controls");
      if (choices.length) row.append(field(labels[1], area), effect, field(t(9) + " (%)", brightness), start);
      row.append(stop);
      entertainment.append(row, status);

      let active;
      let busy = false;
      let error;
      let released;
      let requestRevision = 0;
      const confirmed = {
        nl: "Hue Bridge bevestigt dat de ruimte vrij is", en: "Hue Bridge confirms the area is free",
        de: "Hue Bridge bestätigt die Freigabe", es: "El puente Hue confirma que la zona está libre",
      };
      const errors = {pair_again: 8, busy: 10, stream_lost: 11, stop_failed: 12};
      function update(state) {
        active = state.active;
        error = state.error;
        released = state.released;
        paint();
      }
      function paint() {
        start.disabled = busy || Boolean(active);
        stop.disabled = busy;
        stop.hidden = !active || active.effect === "music";
        reload.disabled = busy;
        const running = choices.find(choice => choice.bridge === active?.bridge && choice.area === active?.area);
        status.textContent = error ? labels[errors[error] ?? 13] :
          active ? labels[6] + (running ? " · " + running.name : "") :
          released ? (confirmed[el("language").value] || confirmed.nl) : "";
        if (active?.effect === "music") {
          const words = hueMusicWords[el("language").value] || hueMusicWords.nl;
          status.textContent = words.streaming + (running ? " · " + running.name : "") + " · " + words.stop;
        }
      }
      async function control(action) {
        busy = true;
        requestRevision++;
        paint();
        try {
          const body = action === "stop" ? {action} : {
            action, bridge: choices[Number(area.value)].bridge, area: choices[Number(area.value)].area,
            effect: effect.value, brightness: brightness.valueAsNumber,
          };
          update(await api(entertainmentPath + "/control", body));
        } catch (failure) {
          error = failure.message;
        } finally {
          busy = false;
          paint();
        }
      }
      start.addEventListener("click", () => {
        if (brightness.reportValidity()) control("start");
      });
      stop.addEventListener("click", () => control("stop"));
      entertainmentControls = async () => {
        if (busy) return;
        const request = requestRevision;
        const state = await api(entertainmentPath + "/status");
        if (revision === entertainmentRead && request === requestRevision && !busy &&
            (state.error !== error || state.released !== released ||
              JSON.stringify(state.active) !== JSON.stringify(active))) update(state);
      };
      update(result);
    } catch {
      if (revision === entertainmentRead) loading.textContent = labels[9];
    }
  }

  setInterval(() => {
    if (context === "hue" && !document.hidden) entertainmentControls?.().catch(() => {});
  }, 3000);

  window.addEventListener("lighting-page", event => {
    const previous = context;
    context = event.detail;
    if (previous !== context) {
      feedback.textContent = "";
      if (homeDialog?.open) homeDialog.close();
    }
    if (previous !== context && context === "tests") {
      hueTestPanel.update();
      goveeTestPanel.update();
    }
    el("nav-home").textContent = t(0);
    render();
    entertainment.hidden = context !== "hue";
    if (previous !== context && context === "hue") {
      loadEntertainment();
      collectionsStatus = "loading";
      loadCollections();
    }
    renderCollections();
    if (previous !== context && ["home", "house", "shows", "hue", "govee", "control", "settings", "tests"].includes(context)) {
      refresh(false).catch(() => { feedback.textContent = t(32); });
    }
  });

  window.addEventListener("twinkly-studio-update", () => {
    if (context === "home" && !homeDialog?.open && !mixerWrites && !panel.contains(document.activeElement)) render();
  });

  // The existing studio's first synchronous page event may have fired before this script loaded.
  if (el("nav-home")) showPage();
  setInterval(() => {
    if (document.hidden || pending || groupBusy || homeDialog?.open || mixerWrites || !["home", "house", "hue", "govee", "control"].includes(context)) return;
    const mount = context === "control" ? studio : panel;
    if (!mount.contains(document.activeElement) && !mount.querySelector(".lighting-group-form input:checked") &&
        !mount.querySelector("button[data-running]")) refresh(false).catch(() => {});
  }, 15000);
})();
