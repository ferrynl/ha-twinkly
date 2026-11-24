(() => {
  "use strict";
  const root = document.getElementById("govee-cloud");
  const language = document.getElementById("language");
  const base = "providers/govee/cloud";
  const words = {
    nl: ["Govee-cloud", "Govee-cloud is nog niet ingesteld.", "Synchroniseren", "Gegevens ophalen…", "Geen lampen gevonden in dit Govee-account.", "Lamp", "Scène", "Scène toepassen", "Segmenten", "Segmentkleur", "Segmenthelderheid", "Toepassen", "Govee heeft de opdracht geaccepteerd.", "Dit model geeft geen ondersteunde scènes of segmentbediening door.", "Govee is niet bereikbaar of de opdracht is geweigerd.", "Govee weigert de API-sleutel. Controleer de appconfiguratie.", "Te veel verzoeken. Probeer het over een moment opnieuw.", "Stop eerst de actieve test of muziekbediening voor deze lamp.", "Kies {min} tot {max} segmenten.", "De dynamische scènes konden niet worden opgehaald.", "API-sleutel aanvragen"],
    en: ["Govee Cloud", "Govee Cloud is not configured yet.", "Sync", "Loading…", "No lights found in this Govee account.", "Light", "Scene", "Apply scene", "Segments", "Segment colour", "Segment brightness", "Apply", "Govee accepted the command.", "This model reports no supported scenes or segment controls.", "Govee is unavailable or rejected the command.", "Govee rejected the API key. Check the app configuration.", "Too many requests. Try again in a moment.", "Stop the running test or music control for this light first.", "Select {min} to {max} segments.", "Could not fetch dynamic scenes.", "Request an API key"],
    de: ["Govee-Cloud", "Govee-Cloud ist noch nicht eingerichtet.", "Synchronisieren", "Daten werden geladen…", "In diesem Govee-Konto wurden keine Lampen gefunden.", "Lampe", "Szene", "Szene anwenden", "Segmente", "Segmentfarbe", "Segmenthelligkeit", "Anwenden", "Govee hat den Befehl angenommen.", "Dieses Modell meldet keine unterstützten Szenen oder Segmentsteuerung.", "Govee ist nicht erreichbar oder hat den Befehl abgelehnt.", "Govee hat den API-Schlüssel abgelehnt. Prüfe die App-Konfiguration.", "Zu viele Anfragen. Versuche es gleich erneut.", "Beende zuerst den aktiven Test oder die Musiksteuerung dieser Lampe.", "Wähle {min} bis {max} Segmente.", "Dynamische Szenen konnten nicht abgerufen werden.", "API-Schlüssel anfordern"],
    es: ["Nube de Govee", "La nube de Govee aún no está configurada.", "Sincronizar", "Cargando…", "No se encontraron luces en esta cuenta de Govee.", "Luz", "Escena", "Aplicar escena", "Segmentos", "Color de segmento", "Brillo de segmento", "Aplicar", "Govee ha aceptado el comando.", "Este modelo no indica escenas ni controles de segmentos compatibles.", "Govee no está disponible o ha rechazado el comando.", "Govee ha rechazado la clave API. Comprueba la configuración.", "Demasiadas solicitudes. Inténtalo de nuevo en un momento.", "Detén primero la prueba o el control musical de esta luz.", "Selecciona de {min} a {max} segmentos.", "No se pudieron obtener las escenas dinámicas.", "Solicitar clave API"],
  };
  const guides = {
    nl: {
      title: "Govee API-sleutel instellen",
      steps: [
        "Open Home Assistant → Instellingen → Apps → Christmas Control Center Beta → Configuratie.",
        "Zet Ongebruikte optionele configuratieopties weergeven aan. Vul je sleutel in bij govee_api_key en klik op Opslaan.",
        "Ga naar Info en herstart de bèta-app. Open daarna in Christmas Control Center Govee → Govee-cloud → Synchroniseren.",
      ],
      fallback: "Zie je het veld niet? Kies bij Opties ⋮ → Bewerken in YAML. Voeg deze regel op hetzelfde niveau als fps toe en vervang YOUR_API_KEY door je eigen sleutel. Sla op en herstart de app.",
      captions: ["Voorbeeld van de configuratie in Home Assistant", "Voorbeeld van Bewerken in YAML", "De knop Synchroniseren in Christmas Control Center"],
      alt: ["Het tabblad Configuratie met de schakelaar voor optionele opties en het veld govee_api_key gemarkeerd.", "De YAML-editor met govee_api_key onder de bestaande opties.", "Govee-cloud met de knop Synchroniseren."],
    },
    en: {
      title: "Set up your Govee API key",
      steps: [
        "Open Home Assistant → Settings → Apps → Christmas Control Center Beta → Configuration.",
        "Turn on Show unused optional configuration options. Enter your key in govee_api_key and click Save.",
        "Go to Info and restart the beta app. Then open Govee → Govee Cloud → Sync in Christmas Control Center.",
      ],
      fallback: "If the field is missing, choose Options ⋮ → Edit in YAML. Add this line at the same level as fps and replace YOUR_API_KEY with your key. Save and restart the app.",
      captions: ["Home Assistant configuration example", "YAML editor example", "The Sync button in Christmas Control Center"],
      alt: ["Configuration tab highlighting the optional options switch and the govee_api_key field.", "YAML editor showing govee_api_key below the existing options.", "Govee Cloud showing the Sync button."],
    },
    de: {
      title: "Govee-API-Schlüssel einrichten",
      steps: [
        "Öffne Home Assistant → Einstellungen → Apps → Christmas Control Center Beta → Konfiguration.",
        "Aktiviere die Anzeige ungenutzter optionaler Konfigurationsoptionen. Trage deinen Schlüssel bei govee_api_key ein und speichere.",
        "Starte die Beta-App unter Info neu. Öffne danach in Christmas Control Center Govee → Govee-Cloud → Synchronisieren.",
      ],
      fallback: "Fehlt das Feld, wähle unter Optionen ⋮ → In YAML bearbeiten. Füge diese Zeile auf derselben Ebene wie fps hinzu und ersetze YOUR_API_KEY durch deinen Schlüssel. Speichere und starte die App neu.",
      captions: ["Beispiel für die Home-Assistant-Konfiguration", "Beispiel des YAML-Editors", "Die Schaltfläche Synchronisieren in Christmas Control Center"],
      alt: ["Konfiguration mit markiertem Schalter für optionale Optionen und dem Feld govee_api_key.", "YAML-Editor mit govee_api_key unter den vorhandenen Optionen.", "Govee-Cloud mit der Schaltfläche zum Laden der Cloud-Lampen."],
    },
    es: {
      title: "Configurar la clave API de Govee",
      steps: [
        "Abre Home Assistant → Ajustes → Aplicaciones → Christmas Control Center Beta → Configuración.",
        "Activa la opción para mostrar las opciones de configuración opcionales sin usar. Introduce la clave en govee_api_key y guarda.",
        "Reinicia la aplicación beta desde Información. Después, abre Govee → Nube de Govee → Sincronizar en Christmas Control Center.",
      ],
      fallback: "Si falta el campo, selecciona Opciones ⋮ → Editar en YAML. Añade esta línea al mismo nivel que fps y sustituye YOUR_API_KEY por tu clave. Guarda y reinicia la aplicación.",
      captions: ["Ejemplo de configuración en Home Assistant", "Ejemplo del editor YAML", "El botón para cargar luces de la nube en Christmas Control Center"],
      alt: ["Pestaña de configuración con el interruptor de opciones opcionales y el campo govee_api_key destacados.", "Editor YAML con govee_api_key debajo de las opciones existentes.", "Nube de Govee con el botón para cargar las luces."],
    },
  };
  const practice = {
    nl: ["Praktijktest", "Kijk op de lamp of de gekozen scène of alleen de geselecteerde segmenten zijn gewijzigd.", "Lamp reageerde zoals bedoeld", "Lamp reageerde anders of bleef gelijk", "Waarneming voor deze opdracht"],
    en: ["Hardware check", "Look at the light and check whether the selected scene or only the selected segments changed.", "Light responded as expected", "Light responded differently or did not change", "Observation for this command"],
    de: ["Praxistest", "Prüfe an der Lampe, ob sich die gewählte Szene oder nur die ausgewählten Segmente geändert haben.", "Lampe reagierte wie erwartet", "Lampe reagierte anders oder blieb unverändert", "Beobachtung für diesen Befehl"],
    es: ["Prueba en la luz", "Comprueba si cambió la escena elegida o si solo cambiaron los segmentos seleccionados.", "La luz respondió como se esperaba", "La luz respondió de otro modo o no cambió", "Observación para este comando"],
  };
  const errors = {key_rejected: 15, rate_limited: 16, device_busy: 17};
  let visible = false;
  let revision = 0;

  const t = index => (words[language.value] || words.nl)[index];
  function element(tag, text) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    return node;
  }
  function field(name, control) {
    const label = element("label", name);
    label.append(control);
    return label;
  }
  function button(name, handler) {
    const control = element("button", name);
    control.type = "button";
    control.onclick = handler;
    return control;
  }
  async function api(path, body) {
    const response = await fetch(base + path, body === undefined ? {cache: "no-store"} :
      {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    return result;
  }
  function select(rows) {
    const control = element("select");
    for (const [value, text] of rows) control.add(new Option(text, value));
    return control;
  }

  function controls(container, device, details) {
    const status = element("p");
    status.setAttribute("role", "status");
    const [title, help, expected, different, observation] = practice[language.value] || practice.nl;
    const check = element("fieldset");
    check.hidden = true;
    const reading = element("p");
    reading.setAttribute("aria-live", "polite");
    const choices = [[expected, "expected"], [different, "different"]].map(([caption, value]) => {
      const option = Object.assign(element("input"), {type: "radio", name: "govee-cloud-observation", value});
      option.onchange = () => { reading.textContent = observation + " · " + caption; };
      return field(caption, option);
    });
    check.append(element("legend", title), element("p", help), ...choices, reading);
    let busy = false;
    const buttons = [];
    const command = async body => {
      if (busy) return;
      busy = true;
      for (const control of buttons) control.disabled = true;
      status.textContent = t(3);
      check.hidden = true;
      reading.textContent = "";
      for (const option of check.querySelectorAll("input")) option.checked = false;
      try {
        await api("/apply", {device, ...body});
        status.textContent = t(12);
        check.hidden = false;
      } catch (error) {
        status.textContent = t(errors[error.message] ?? 14);
      } finally {
        busy = false;
        for (const control of buttons) control.disabled = false;
      }
    };
    if (details.scenes.length) {
      const scene = select(details.scenes.map(row => [row.id, row.name]));
      const apply = button(t(7), () => command({action: "scene", scene: scene.value}));
      buttons.push(apply);
      const row = element("div");
      row.className = "lighting-controls";
      row.append(field(t(6), scene), apply);
      container.append(row);
    }
    if (details.scene_error) container.append(element("p", t(19) + " " + t(errors[details.scene_error] ?? 14)));
    for (const [action, spec] of Object.entries(details.segments)) {
      const group = element("fieldset");
      const legend = t(action === "color" ? 9 : 10);
      group.append(element("legend", legend));
      const indices = element("div");
      indices.className = "govee-segments";
      for (const index of spec.indices) {
        const check = element("input");
        Object.assign(check, {type: "checkbox", value: index});
        indices.append(field(t(8) + " " + (index + 1), check));
      }
      const hint = t(18).replace("{min}", spec.minimum).replace("{max}", spec.limit);
      const value = element("input");
      if (action === "color") Object.assign(value, {type: "color", value: "#ff7e33"});
      else Object.assign(value, {type: "number", min: spec.low, max: spec.high, step: spec.step, value: spec.high, required: true});
      const apply = button(t(11), () => {
        const segments = Array.from(indices.querySelectorAll("input:checked"), input => Number(input.value));
        if (segments.length < spec.minimum || segments.length > spec.limit) {
          status.textContent = hint;
          return;
        }
        if (!value.reportValidity()) return;
        command({action, segments, value: action === "color"
          ? value.value.slice(1).match(/../g).map(channel => parseInt(channel, 16)) : value.valueAsNumber});
      });
      buttons.push(apply);
      const row = element("div");
      row.className = "lighting-controls";
      row.append(field(legend, value), apply);
      group.append(element("p", hint), indices, row);
      container.append(group);
    }
    if (!details.scenes.length && !Object.keys(details.segments).length && !details.scene_error) {
      container.append(element("p", t(13)));
    }
    container.append(status, check);
  }

  function setupGuide(open) {
    const guide = guides[language.value] || guides.nl;
    const details = element("details");
    details.className = "govee-setup-guide";
    details.open = open;
    const list = element("ol");
    for (const step of guide.steps) list.append(element("li", step));
    const figures = element("div");
    figures.className = "govee-setup-figures";
    ["config", "yaml", "cloud"].forEach((name, index) => {
      const figure = element("figure");
      const screenshot = element("img");
      Object.assign(screenshot, {src: "govee-guide-" + name + ".webp", alt: guide.alt[index], loading: "lazy"});
      const fullSize = element("a");
      Object.assign(fullSize, {href: screenshot.getAttribute("src"), target: "_blank", rel: "noopener noreferrer"});
      fullSize.append(screenshot);
      figure.append(fullSize, element("figcaption", guide.captions[index]));
      figures.append(figure);
    });
    const yaml = element("pre");
    yaml.append(element("code", 'govee_api_key: "YOUR_API_KEY"'));
    details.append(element("summary", guide.title), list, element("p", guide.fallback), yaml, figures);
    return details;
  }

  async function show() {
    const token = ++revision;
    const content = element("div");
    content.className = "govee-cloud-content";
    const status = element("p", t(3));
    status.setAttribute("role", "status");
    root.replaceChildren(element("h2", t(0)), status, content);
    try {
      const meta = await api("");
      if (token !== revision || !visible) return;
      status.textContent = "";
      if (!meta.configured) {
        status.textContent = t(1);
        const help = element("a", t(20));
        help.href = "https://developer.govee.com/reference/apply-you-govee-api-key";
        help.target = "_blank";
        help.rel = "noopener noreferrer";
        content.append(setupGuide(true), help);
        return;
      }
      const devices = element("div");
      async function display(rows) {
          if (!rows.length) {
            devices.replaceChildren();
            status.textContent = t(4);
            return;
          }
          const device = select(rows.map(row => [row.id, row.name + " · " + row.sku]));
          const detail = element("div");
          let selection = 0;
          async function choose() {
            const request = ++selection;
            const id = device.value;
            status.textContent = t(3);
            detail.replaceChildren();
            try {
              const result = await api("/details", {device: id});
              if (request !== selection || token !== revision || !visible) return;
              status.textContent = "";
              controls(detail, id, result);
            } catch (error) {
              if (request === selection) status.textContent = t(errors[error.message] ?? 14);
            }
          }
          device.onchange = choose;
          devices.replaceChildren(field(t(5), device), detail);
          await choose();
      }
      const load = button(t(2), async () => {
        load.disabled = true;
        status.textContent = t(3);
        try {
          const result = await api("/devices", {});
          if (token === revision && visible) await display(result.devices);
        } catch (error) {
          status.textContent = t(errors[error.message] ?? 14);
        } finally {
          load.disabled = false;
        }
      });
      content.append(load, devices, setupGuide(false));
      if (meta.devices?.length) await display(meta.devices);
      else status.textContent = ({
        nl:"Synchroniseer om je Govee-cloudlampen toe te voegen.",
        en:"Sync to add your Govee cloud lights.",
        de:"Synchronisiere, um deine Govee-Cloud-Lampen hinzuzufügen.",
        es:"Sincroniza para añadir tus luces de Govee.",
      })[language.value] || "Sync to add your Govee cloud lights.";
    } catch {
      status.textContent = t(14);
    }
  }

  function page(name) {
    const next = name === "govee";
    root.hidden = !next;
    if (next && !visible) {
      visible = true;
      show();
    }
    if (!next && visible) {
      visible = false;
      revision++;
    }
  }
  window.addEventListener("lighting-page", event => page(event.detail));
  language.addEventListener("change", () => { if (visible) show(); });
  if (location.hash === "#govee") page("govee");
})();
