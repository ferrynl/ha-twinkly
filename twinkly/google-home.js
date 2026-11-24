(() => {
  const page = document.querySelector("#google-page");
  const node = (tag, content) => {
    const element = document.createElement(tag);
    element.textContent = content ?? "";
    return element;
  };
  const option = (value, caption) => new Option(caption, value);
  let revision = 0;

  async function render() {
    const token = ++revision;
    page.replaceChildren(node("h2", "Google Home"), node("p", "Shows en kamers ophalen…"));
    try {
      const get = async path => {
        const response = await fetch(path);
        if (!response.ok) throw new Error();
        return response.json();
      };
      const [inventory, projects] = await Promise.all([get("lighting"), get("lighting/projects")]);
      if (token !== revision) return;
      const rooms = Object.values(inventory.groups || {}).filter(room => room.kind === "room");
      const shows = (Array.isArray(projects.shows) ? projects.shows : Object.values(projects.shows || {}));
      const type = node("select"), target = node("select");
      type.setAttribute("aria-label", "Type");
      target.setAttribute("aria-label", "Kamer of show");
      type.append(option("room", "Kerstdemo per kamer"), option("show", "Eigen opgeslagen show"));
      const label = (caption, input) => {
        const field = node("label", caption + " ");
        field.append(input);
        return field;
      };
      const targetLabel = label("Kamer of show", target);
      const script = node("pre");
      const copy = node("button", "Kopieer Home Assistant-script");
      copy.type = "button";
      const status = node("p");
      status.setAttribute("role", "status");
      const refreshScript = () => {
        status.textContent = "";
        copy.disabled = !target.value;
        const show = type.value === "show";
        const entry = show ? shows.find(item => item.id === target.value) : rooms.find(item => item.name === target.value);
        const name = entry?.name;
        script.textContent = name ? [
          "alias: " + JSON.stringify(show ? name : "Kerstdemo"),
          "mode: single",
          "sequence:",
          "  - event: christmas_control_center_demo",
          "    event_data:",
          "      " + (show ? "show_id" : "room") + ": " + JSON.stringify(target.value),
        ].join("\n") : (show ? "Sla eerst een show op in Showbouwer." : "Maak eerst een kamer aan op Home.");
      };
      type.onchange = () => {
        target.replaceChildren(...(type.value === "show"
          ? shows.map(show => option(show.id, show.name))
          : rooms.map(room => option(room.name, room.name))));
        refreshScript();
      };
      target.onchange = refreshScript;
      copy.onclick = async () => {
        try {
          await navigator.clipboard.writeText(script.textContent);
          status.textContent = "Script gekopieerd.";
        } catch {
          const range = document.createRange();
          range.selectNodeContents(script);
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          status.textContent = "Script geselecteerd. Gebruik Ctrl+C om te kopiëren.";
        }
      };
      const controls = node("div");
      controls.className = "lighting-controls";
      controls.append(label("Type", type), targetLabel);
      const steps = node("ol");
      for (const text of [
        "Kies hierboven de kerstdemo of je eigen show. Kopieer het script.",
        "Open in Home Assistant Instellingen → Automatiseringen en scènes → Scripts. Maak een script, open het ⋮-menu, kies Bewerken in YAML, plak het script en sla het op. Voer het één keer uit om de verlichting te testen.",
        "Stel het script beschikbaar aan Google Assistant via je Home Assistant-koppeling. Het verschijnt als scène in Google Home.",
        "Open in Google Home Automatiseringen en maak een routine. Kies een gesproken starter, bijvoorbeeld ‘start de kerstdemo’. Voeg de scène toe als actie en sla de routine op.",
      ]) steps.append(node("li", text));
      const reload = node("button", "Lijst vernieuwen");
      reload.type = "button";
      reload.onclick = render;
      page.replaceChildren(node("h2", "Google Home"), controls, reload, script, copy, status, node("h3", "Installatie"), steps);
      script.style.whiteSpace = "pre-wrap";
      script.style.overflowWrap = "anywhere";
      const sources = node("p");
      for (const [name, url] of [
        ["Home Assistant · Google Assistant", "https://www.home-assistant.io/integrations/google_assistant/"],
        ["Google Home · Routines", "https://support.google.com/googlenest/answer/7029585?hl=nl"],
      ]) {
        const link = node("a", name);
        Object.assign(link, {href:url, target:"_blank", rel:"noopener noreferrer"});
        sources.append(link, node("br"));
      }
      page.append(sources);
      type.onchange();
      for (const [file, caption] of [
        ["google-home-demo.jpg", "Voorbeeld: kerstdemo per kamer"],
        ["google-home-show.jpg", "Voorbeeld: een eigen show koppelen"],
      ]) {
        const figure = node("figure"), image = node("img");
        image.src = file;
        image.alt = caption;
        image.loading = "lazy";
        image.style.maxWidth = "100%";
        figure.append(image, node("figcaption", caption));
        page.append(figure);
      }
    } catch {
      if (token !== revision) return;
      const retry = node("button", "Opnieuw proberen");
      retry.type = "button";
      retry.onclick = render;
      page.replaceChildren(node("h2", "Google Home"), node("p", "De shows of kamers konden niet worden opgehaald."), retry);
    }
  }

  window.addEventListener("lighting-page", event => {
    if (event.detail === "google") render();
    else revision++;
  });
  if (location.hash === "#google-home") render();
})();
