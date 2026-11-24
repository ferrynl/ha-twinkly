(() => {
  if (!document.getElementById("project-page")) {
    const roadmap = new URLSearchParams(location.search).get("view") === "roadmap";
    const release = /^#release-[\w.-]+$/.test(location.hash) ? location.hash : "#changelog";
    location.replace("./" + (roadmap ? "#roadmap" : release));
    return;
  }

  const translations = {
    nl: {
      changelog: "Changelog", roadmap: "Roadmap", version: "Versie",
      search: "Zoek op versie of wijziging", empty: "Geen versies gevonden.",
      failed: "Deze informatie kon niet worden geladen. Probeer de pagina opnieuw te openen.",
      changelogIntro: "Bekijk wat er is toegevoegd, verbeterd of opgelost in elke versie.",
      roadmapIntro: "Bekijk wat we voor 2.x en 3.0 willen verbeteren.",
    },
    en: {
      changelog: "Changelog", roadmap: "Roadmap", version: "Version",
      search: "Search by version or change", empty: "No versions found.",
      failed: "This information could not be loaded. Try reopening the page.",
      changelogIntro: "See the features, improvements and fixes in each version.",
      roadmapIntro: "See what we plan to improve in 2.x and 3.0.",
    },
    de: {
      changelog: "Änderungsprotokoll", roadmap: "Roadmap", version: "Version",
      search: "Nach Version oder Änderung suchen", empty: "Keine Versionen gefunden.",
      failed: "Diese Informationen konnten nicht geladen werden. Öffne die Seite erneut.",
      changelogIntro: "Hier findest du die Neuerungen, Verbesserungen und Korrekturen jeder Version.",
      roadmapIntro: "Hier siehst du, was wir in 2.x und 3.0 verbessern wollen.",
    },
    es: {
      changelog: "Registro de cambios", roadmap: "Hoja de ruta", version: "Versión",
      search: "Buscar por versión o cambio", empty: "No se encontraron versiones.",
      failed: "No se pudo cargar esta información. Vuelve a abrir la página.",
      changelogIntro: "Consulta las novedades, mejoras y correcciones de cada versión.",
      roadmapIntro: "Consulta las mejoras previstas para 2.x y 3.0.",
    },
  };

  const versionHeading = /^#{1,2} (\d+\.\d+\.\d+(?:-[\w.-]+)?)\s*$/;
  const footerVersion = document.querySelector("[data-project-version]");
  const content = document.getElementById("project-entries");
  const languageControl = document.getElementById("language");
  let currentVersion = "";
  let currentView;
  let renderId = 0;

  function language() {
    const selected = languageControl?.value || localStorage.getItem("twinkly-language");
    return Object.hasOwn(translations, selected) ? selected : "nl";
  }

  function translateLabels() {
    const labels = translations[language()];
    document.querySelectorAll("[data-project-label]").forEach(element => {
      element.textContent = labels[element.dataset.projectLabel];
    });
    footerVersion.textContent = currentVersion ? labels.version + " " + currentVersion : labels.changelog;
  }

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function appendInline(node, text) {
    for (const segment of text.split(/(\*\*[^*]+\*\*|`[^`]+`)/)) {
      if (segment.startsWith("**") && segment.endsWith("**")) {
        node.append(element("strong", segment.slice(2, -2)));
      } else if (segment.startsWith("`") && segment.endsWith("`")) {
        node.append(element("code", segment.slice(1, -1)));
      } else {
        node.append(segment);
      }
    }
  }

  async function readMarkdown(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error("Cannot load " + path);
    return (await response.text()).split(/\r?\n/);
  }

  function parseReleases(lines) {
    const releases = [];
    for (const line of lines) {
      const heading = versionHeading.exec(line);
      if (heading) {
        releases.push({version: heading[1], lines: []});
      } else if (line.trim() && !line.startsWith("#")) {
        releases.at(-1)?.lines.push(line.trim());
      }
    }
    if (!releases.length) throw new Error("Changelog has no releases");
    return releases;
  }

  async function showVersion() {
    const releases = parseReleases(await readMarkdown("CHANGELOG.md"));
    currentVersion = releases[0].version;
    footerVersion.href = "#release-" + currentVersion;
    translateLabels();
    return releases;
  }

  function releaseCard(release, index) {
    const card = element("details", "", "release-entry");
    card.id = "release-" + release.version;
    card.open = index === 0;
    card.append(element("summary", release.version));
    let list;
    for (const line of release.lines) {
      if (line.startsWith("- ")) {
        if (!list) {
          list = element("ul");
          card.append(list);
        }
        const item = element("li");
        appendInline(item, line.slice(2));
        list.append(item);
      } else {
        list = null;
        const paragraph = element("p");
        appendInline(paragraph, line);
        card.append(paragraph);
      }
    }
    return card;
  }

  function showChangelog(releases, status) {
    const cards = releases.map(releaseCard);
    content.append(...cards);
    const search = document.getElementById("project-query");
    document.getElementById("project-search").hidden = false;
    search.value = "";
    search.oninput = () => {
      const query = search.value.trim().toLowerCase();
      let matches = 0;
      cards.forEach((card, index) => {
        card.hidden = !card.textContent.toLowerCase().includes(query);
        card.open = !card.hidden && (query !== "" || index === 0);
        if (!card.hidden) matches += 1;
      });
      status.textContent = matches ? "" : translations[language()].empty;
    };
    function revealRelease() {
      const selected = cards.find(card => "#" + card.id === location.hash);
      if (selected) {
        search.value = "";
        search.dispatchEvent(new Event("input"));
        selected.open = true;
        selected.scrollIntoView();
      }
    }
    revealRelease();
  }

  function showRoadmap(lines) {
    content.lang = "nl";
    let grid;
    let list;
    for (const line of lines) {
      if (line.startsWith("# ")) {
        const section = element("section", "", "roadmap-version");
        grid = element("div", "", "roadmap-grid");
        list = null;
        section.append(element("h2", line.slice(2)), grid);
        content.append(section);
      } else if (line.startsWith("## ") && grid) {
        const card = element("section", "", "roadmap-item");
        list = element("ul");
        card.append(element("h3", line.slice(3)), list);
        grid.append(card);
      } else if (line.startsWith("- ") && list) {
        const item = element("li");
        appendInline(item, line.slice(2));
        list.append(item);
      }
    }
    if (!content.childElementCount) throw new Error("Roadmap has no sections");
  }

  const releases = showVersion();
  releases.catch(() => {});
  let roadmapLines;
  const status = document.getElementById("project-status");
  const title = document.getElementById("project-title");
  const searchLabel = document.getElementById("project-search");

  async function showProject(event) {
    translateLabels();
    if (event.detail !== "project") {
      currentView = undefined;
      renderId += 1;
      document.title = "Christmas Control Center";
      return;
    }
    const view = location.hash === "#roadmap" ? "roadmap" : "changelog";
    const labels = translations[language()];
    document.title = labels[view] + " · Christmas Control Center";
    title.textContent = labels[view];
    document.getElementById("project-intro").textContent = labels[view + "Intro"];
    document.querySelectorAll("[data-project-view]").forEach(link => {
      if (link.dataset.projectView === view) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    const viewKey = location.hash + "/" + language();
    if (currentView === viewKey) return;
    currentView = viewKey;
    const id = ++renderId;
    content.replaceChildren();
    content.removeAttribute("lang");
    searchLabel.hidden = true;
    status.textContent = "";
    try {
      if (view === "roadmap") {
        roadmapLines ||= readMarkdown("ROADMAP.md").catch(error => {
          roadmapLines = undefined;
          throw error;
        });
        const lines = await roadmapLines;
        if (id === renderId) showRoadmap(lines);
      } else {
        const entries = await releases;
        if (id === renderId) showChangelog(entries, status);
      }
    } catch {
      if (id === renderId) status.textContent = labels.failed;
    }
  }

  window.addEventListener("lighting-page", showProject);
  showPage();
})();
