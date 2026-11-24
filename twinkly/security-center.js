(() => {
  "use strict";
  const root = document.getElementById("security-modules");
  const language = document.getElementById("language");
  const words = {
    nl: ["Broncode en release", "Docker en bibliotheken", "Lokale beveiligingscontroles", "Controles verversen", "Bezig met controleren…",
      "Gegevens ophalen mislukt.", "Broncode", "GitHub-tests en beveiligingsrapporten", "Geïnstalleerde versie", "Python en architectuur",
      "Draait als root", "Draait als niet-root", "Pakketten volgens lockfile", "Afwijkingen", "Geen versie gevonden", "Lockfile onleesbaar",
      "De app test de eigen toegangsregels met gesimuleerde aanvragen.", "Gecontroleerd om", "Geslaagd", "Afwijking", "Niet ingesteld", "Onbeschikbaar",
      "Ingress-regels actief", "Toegang via Ingress toegestaan", "Rechtstreekse toegang geblokkeerd", "POST vereist JSON",
      "Healthcheck lokaal toegestaan", "Healthcheck via Ingress geblokkeerd", "Toegangsrechten van de sleutelopslag"],
    en: ["Source and release", "Docker and libraries", "Local security checks", "Refresh checks", "Checking…",
      "Could not load the results.", "Source code", "GitHub tests and security reports", "Installed version", "Python and architecture",
      "Running as root", "Running as non-root", "Packages in the lockfile", "Mismatches", "Version missing", "Lockfile unavailable",
      "The app checks its access rules with simulated requests.", "Checked at", "Passed", "Mismatch", "Not configured", "Unavailable",
      "Ingress rules installed", "Ingress accepted", "Direct access blocked", "POST requires JSON",
      "Local health check allowed", "Health check blocked through ingress", "Credential file permissions"],
    de: ["Quellcode und Release", "Docker und Bibliotheken", "Lokale Sicherheitsprüfungen", "Prüfungen aktualisieren", "Prüfung läuft…",
      "Ergebnisse konnten nicht geladen werden.", "Quellcode", "GitHub-Tests und Sicherheitsberichte", "Installierte Version", "Python und Architektur",
      "Läuft als Root", "Läuft ohne Root", "Pakete aus der Lockdatei", "Abweichungen", "Version fehlt", "Lockdatei nicht verfügbar",
      "Die App prüft ihre Zugriffsregeln mit simulierten Anfragen.", "Geprüft um", "Bestanden", "Abweichung", "Nicht eingerichtet", "Nicht verfügbar",
      "Ingress-Regeln aktiv", "Ingress erlaubt", "Direkter Zugriff blockiert", "POST erfordert JSON",
      "Lokaler Healthcheck erlaubt", "Healthcheck über Ingress blockiert", "Berechtigungen der Schlüsseldatei"],
    es: ["Código y versión", "Docker y bibliotecas", "Comprobaciones locales", "Actualizar comprobaciones", "Comprobando…",
      "No se pudieron cargar los resultados.", "Código fuente", "Pruebas e informes en GitHub", "Versión instalada", "Python y arquitectura",
      "Ejecutándose como root", "Ejecutándose sin root", "Paquetes del archivo de bloqueo", "Diferencias", "Falta la versión", "Archivo de bloqueo no disponible",
      "La aplicación comprueba sus reglas de acceso con peticiones simuladas.", "Comprobado a las", "Correcto", "Diferencia", "Sin configurar", "No disponible",
      "Reglas de Ingress activas", "Ingress permitido", "Acceso directo bloqueado", "POST requiere JSON",
      "Comprobación local permitida", "Comprobación vía Ingress bloqueada", "Permisos del archivo de credenciales"],
  };
  const updateWords = {
    nl: ["Controleren op updates", "Versies opzoeken…", "Update beschikbaar", "Actueel", "Geïnstalleerde versie is nieuwer", "Nieuwere Python-versie vereist", "Onbekend", "Niet geïnstalleerd", "Nieuwste versie", "Laatste updatecheck", "Updatecheck mislukt.", "Bibliotheekupdates", "Pakketten kunnen niet worden gecontroleerd."],
    en: ["Check for updates", "Looking up versions…", "Update available", "Up to date", "Installed version is newer", "Newer Python required", "Unknown", "Not installed", "Latest version", "Last update check", "Update check failed.", "Library updates", "Packages could not be checked."],
    de: ["Nach Updates suchen", "Versionen werden gesucht…", "Update verfügbar", "Aktuell", "Installierte Version ist neuer", "Neuere Python-Version erforderlich", "Unbekannt", "Nicht installiert", "Neueste Version", "Letzte Updateprüfung", "Updateprüfung fehlgeschlagen.", "Bibliotheksupdates", "Pakete konnten nicht geprüft werden."],
    es: ["Buscar actualizaciones", "Buscando versiones…", "Actualización disponible", "Al día", "La versión instalada es más reciente", "Requiere una versión de Python más reciente", "Desconocido", "No instalado", "Última versión", "Última búsqueda", "Falló la búsqueda de actualizaciones.", "Actualizaciones de bibliotecas", "No se pudieron comprobar los paquetes."],
  };
  const scanWords = {
    nl: ["Containerscans", "Rapporten ophalen", "Rapporten ophalen…", "Geïnstalleerde versie",
      "Bekijk bevindingen en SBOM in GitHub", "Geen bewaard rapport gevonden", "GitHub onbereikbaar",
      "Gecontroleerd", "Er wordt gezocht naar rapporten voor jouw geïnstalleerde versie."],
    en: ["Container scans", "Find reports", "Looking up reports…", "Installed version",
      "View findings and SBOM on GitHub", "No retained report found", "GitHub unavailable",
      "Checked", "Looks up reports for your installed version."],
    de: ["Container-Scans", "Berichte suchen", "Berichte werden gesucht…", "Installierte Version",
      "Befunde und SBOM auf GitHub öffnen", "Kein gespeicherter Bericht gefunden", "GitHub nicht erreichbar",
      "Geprüft", "Sucht Berichte für die installierte Version."],
    es: ["Escaneos del contenedor", "Buscar informes", "Buscando informes…", "Versión instalada",
      "Ver hallazgos y SBOM en GitHub", "No se encontró un informe guardado", "GitHub no disponible",
      "Comprobado", "Busca informes para la versión instalada."],
  };
  const updateResults = {update: 2, current: 3, ahead: 4, incompatible_python: 5, unavailable: 6, not_installed: 7};
  const ids = ["middleware_installed", "ingress_access", "direct_access", "json_only",
    "health_loopback", "health_ingress_denied", "credentials_permissions"];
  const results = {pass: 18, fail: 19, not_configured: 20, unavailable: 21};
  const repository = "https://github.com/ferrynl/ha-apps";
  let active = false;
  let loading = false;
  let failed = false;
  let report;
  let updateReport;
  let updating = false;
  let updateFailed = false;
  let dependenciesOpen = false;
  let scanReport;
  let checkingScans = false;
  let scanFailed = false;

  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text) element.textContent = text;
    if (className) element.className = className;
    return element;
  }

  function link(text, path) {
    const element = node("a", text);
    element.href = repository + path;
    element.target = "_blank";
    element.rel = "noopener noreferrer";
    return element;
  }

  function scanCard() {
    const t = scanWords[language.value] || scanWords.nl;
    const card = node("article", "", "lighting-card");
    const button = node("button", checkingScans ? t[2] : t[1]);
    button.type = "button";
    button.id = "security-scan-check";
    button.disabled = checkingScans;
    button.onclick = checkScans;
    const status = node("p", checkingScans ? t[2] : scanFailed ? t[6] : "");
    status.setAttribute("role", "status");
    card.append(node("h3", t[0]), node("p", t[8]), button, status);
    if (scanReport) {
      if (scanReport.version) card.append(node("p", t[3] + " · " + scanReport.version));
      const list = node("ul");
      for (const row of scanReport.reports) {
        const item = node("li", row.architecture + " · ");
        if (row.result === "available" && Number.isSafeInteger(row.run_id)) {
          item.append(link(t[4], "/actions/runs/" + row.run_id));
          if (row.created_at) item.append(" · " + new Date(row.created_at).toLocaleDateString(language.value || "nl"));
        } else {
          item.append(t[row.result === "not_found" ? 5 : 6]);
        }
        list.append(item);
      }
      card.append(list, node("p", t[7] + " · " +
        new Date(scanReport.checked_at).toLocaleString(language.value || "nl")));
    }
    return card;
  }

  async function checkScans() {
    if (checkingScans) return;
    checkingScans = true;
    scanFailed = false;
    show();
    try {
      const response = await fetch("security-center/reports", {method: "POST",
        headers: {"Content-Type": "application/json"}, body: "{}"});
      if (!response.ok) throw new Error("Scan report lookup unavailable");
      scanReport = await response.json();
    } catch {
      scanFailed = true;
    } finally {
      checkingScans = false;
      show();
      if (active) root.querySelector("#security-scan-check").focus();
    }
  }

  function show() {
    const t = words[language.value] || words.nl;
    const u = updateWords[language.value] || updateWords.nl;
    const updateText = row => (row.latest ? u[8] + " · " + row.latest + " · " : "") + u[updateResults[row.result] ?? 6];
    const refresh = node("button", t[3]);
    refresh.type = "button";
    refresh.disabled = loading;
    refresh.onclick = () => load(true);
    const updateButton = node("button", updating ? u[1] : u[0]);
    updateButton.type = "button";
    updateButton.id = "security-update-check";
    updateButton.disabled = updating;
    updateButton.onclick = checkUpdates;
    const notification = node("p", loading ? t[4] : failed ? t[5] : "");
    notification.setAttribute("role", "status");
    const cards = node("div", "", "lighting-grid");
    const source = node("article", "", "lighting-card");
    source.append(node("h3", t[0]), link(t[6], "/tree/main/twinkly"),
      link(t[7], "/actions/workflows/twinkly-stable.yml"), updateButton);
    const updateNotification = node("p", updating ? u[1] : updateFailed ? u[10] : "");
    updateNotification.setAttribute("role", "status");
    source.append(updateNotification);
    if (updateReport) {
      const checked = new Date(updateReport.checked_at).toLocaleString(language.value || "nl");
      source.append(node("p", updateText(updateReport.app)), node("p", u[9] + " · " + checked));
    }
    const runtime = node("article", "", "lighting-card");
    runtime.append(node("h3", t[1]));
    const checks = node("article", "", "lighting-card");
    checks.append(node("h3", t[2]), node("p", t[16]));
    if (report) {
      source.append(node("p", t[8] + " · " + (report.version || t[14])));
      runtime.append(node("p", t[9] + " · " + report.runtime.python + " · " + report.runtime.architecture),
        node("p", t[report.runtime.root ? 10 : 11]));
      if (report.dependencies) {
        const total = report.dependencies.length;
        const mismatches = report.dependencies.filter(pkg => pkg.expected !== pkg.installed).length;
        const detail = node("details");
        detail.open = dependenciesOpen;
        detail.ontoggle = () => { dependenciesOpen = detail.open; };
        const list = node("ul");
        const latest = new Map((updateReport?.packages || []).map(pkg => [pkg.name, pkg]));
        for (const pkg of report.dependencies) {
          const summary = pkg.expected === pkg.installed ? pkg.installed
            : (pkg.installed || t[14]) + " → " + pkg.expected;
          const updateRow = latest.get(pkg.name);
          list.append(node("li", pkg.name + " · " + summary + (updateRow ? " · " + updateText(updateRow) : "")));
        }
        detail.append(node("summary", t[12] + " · " + (total - mismatches) + " / " + total), list);
        runtime.append(node("p", t[13] + " · " + mismatches), detail);
      } else runtime.append(node("p", t[15]));
      if (updateReport) {
        const available = updateReport.packages.filter(row => row.result === "update").length;
        const unknown = updateReport.packages.filter(row => row.result === "unavailable").length;
        runtime.append(node("p", updateReport.packages_checked ? u[11] + " · " + available + " · " + u[6] + " · " + unknown : u[12]));
      }
      const items = node("ul");
      for (const check of report.checks) {
        const index = ids.indexOf(check.id);
        if (index !== -1) items.append(node("li", t[22 + index] + " · " + t[results[check.result] ?? 21]));
      }
      const time = new Date(report.checked_at).toLocaleTimeString(language.value || "nl");
      checks.append(items, node("p", t[17] + " " + time));
    }
    cards.append(source, runtime, checks, scanCard());
    root.replaceChildren(refresh, notification, cards);
  }

  async function load(restoreFocus = false) {
    if (loading) return;
    const priorScanReport = scanReport;
    loading = true;
    failed = false;
    show();
    try {
      const response = await fetch("security-center/status", {cache: "no-store"});
      if (!response.ok) throw new Error("Security status unavailable");
      report = await response.json();
      if (report.updates && !updating) updateReport = report.updates;
      if (!checkingScans && scanReport === priorScanReport) scanReport = report.scan_reports;
    } catch {
      failed = true;
    } finally {
      loading = false;
      show();
      if (restoreFocus && active) root.querySelector("button").focus();
    }
  }

  async function checkUpdates() {
    if (updating) return;
    updating = true;
    updateFailed = false;
    show();
    try {
      const response = await fetch("security-center/updates", {method: "POST",
        headers: {"Content-Type": "application/json"}, body: "{}"});
      if (!response.ok) throw new Error("Update check unavailable");
      updateReport = await response.json();
    } catch {
      updateFailed = true;
    } finally {
      updating = false;
      show();
      if (active) root.querySelector("#security-update-check").focus();
    }
  }

  function pageChanged() {
    const visible = /^#(?:security-center|netwerk)$/.test(location.hash);
    if (visible && !active) load();
    active = visible;
  }

  window.addEventListener("hashchange", pageChanged);
  language.addEventListener("change", () => { if (active) show(); });
  pageChanged();
})();
