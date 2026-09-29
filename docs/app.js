(() => {
  "use strict";

  const REPOSITORY = "mrryzensor/DxDesk";
  const RELEASES_API = `https://api.github.com/repos/${REPOSITORY}/releases?per_page=100`;
  const RELEASES_PAGE = `https://github.com/${REPOSITORY}/releases`;
  const CACHE_KEY = "dxdesk-release-assets-v1";
  const CACHE_TTL = 10 * 60 * 1000;

  const platforms = {
    windows: { label: "Windows", assets: ["DxDesk-Windows-Setup.exe", "DxDesk-Windows-x64.exe"] },
    macos: { label: "macOS", assets: ["DxDesk-macOS-AppleSilicon.dmg", "DxDesk-macOS-Intel.dmg"] },
    linux: { label: "Linux", assets: ["DxDesk-Linux-x64.AppImage", "DxDesk-Linux-x64.deb"] },
    android: { label: "Android", assets: ["DxDesk-Android-Universal.apk", "DxDesk-Android-arm64.apk"] },
  };

  function detectPlatform() {
    const ua = navigator.userAgent || "";
    const platform = [navigator.userAgentData?.platform, navigator.platform, ua].filter(Boolean).join(" ");
    if (/android/i.test(platform)) return { key: "android", label: "Android" };
    if (/iphone|ipad|ipod/i.test(platform) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1)) return { key: "ios", label: "iOS" };
    if (/windows/i.test(platform)) return { key: "windows", label: "Windows" };
    if (/macintosh|mac os|macos/i.test(platform)) return { key: "macos", label: "macOS" };
    if (/linux|x11/i.test(platform)) return { key: "linux", label: "Linux" };
    return { key: "unknown", label: "tu dispositivo" };
  }

  function getCachedReleases() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(CACHE_KEY));
      if (saved && Date.now() - saved.savedAt < CACHE_TTL && Array.isArray(saved.releases)) return saved.releases;
    } catch (_) {
      // Ignore stale or unavailable browser storage and fetch fresh data.
    }
    return null;
  }

  function saveCachedReleases(releases) {
    try {
      sessionStorage.setItem(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), releases }));
    } catch (_) {
      // The page still works when browser storage is disabled or full.
    }
  }

  async function fetchReleases() {
    const cached = getCachedReleases();
    if (cached) return cached;

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 9000);
    let response;
    try {
      response = await fetch(RELEASES_API, {
        headers: { Accept: "application/vnd.github+json" },
        signal: controller.signal,
        cache: "no-store",
      });
    } finally {
      window.clearTimeout(timeout);
    }
    if (!response.ok) throw new Error(`GitHub Releases respondió ${response.status}`);
    const releases = await response.json();
    if (!Array.isArray(releases)) throw new Error("La respuesta de GitHub no contiene releases");
    saveCachedReleases(releases);
    return releases;
  }

  function getLatestAssets(releases) {
    const latest = new Map();
    const published = releases
      .filter((release) => !release.draft && !release.prerelease)
      .sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0));

    for (const release of published) {
      for (const asset of release.assets || []) {
        if (!latest.has(asset.name) && asset.browser_download_url) latest.set(asset.name, { ...asset, release });
      }
    }
    return latest;
  }

  function versionFor(release) {
    if (!release) return "Ver en GitHub";
    const label = `${release.name || ""} ${release.tag_name || ""}`;
    const match = label.match(/\bv?(\d+\.\d+(?:\.\d+)?)(?:[-+\s)]|$)/i);
    return match ? `v${match[1]}` : release.tag_name || "Versión reciente";
  }

  function formatDate(value) {
    if (!value) return "";
    return new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short", year: "numeric" }).format(new Date(value));
  }

  function bindAssets(assets) {
    document.querySelectorAll("[data-asset]").forEach((link) => {
      const record = assets.get(link.dataset.asset);
      if (!record) {
        link.href = RELEASES_PAGE;
        link.classList.add("is-unavailable");
        link.title = "Este paquete no aparece en las releases actuales. Ver todas las versiones.";
        return;
      }
      link.href = record.browser_download_url;
      link.classList.remove("is-unavailable");
      link.title = `${link.dataset.asset} · ${versionFor(record.release)}`;
    });

    document.querySelectorAll(".platform-card").forEach((card) => {
      const cardAssets = platforms[card.dataset.platform].assets;
      const record = cardAssets.map((name) => assets.get(name)).filter(Boolean)
        .sort((a, b) => new Date(b.release.published_at || 0) - new Date(a.release.published_at || 0))[0];
      card.querySelector(".release-version").textContent = record ? versionFor(record.release) : "Ver en GitHub";
    });

    const newest = [...assets.values()].sort((a, b) => new Date(b.release.published_at || 0) - new Date(a.release.published_at || 0))[0];
    const status = document.getElementById("release-status");
    status.classList.toggle("ready", Boolean(newest));
    status.classList.remove("error");
    document.getElementById("release-status-title").textContent = newest ? "Descargas actualizadas" : "Revisa las versiones en GitHub";
    document.getElementById("release-status-detail").textContent = newest
      ? `${versionFor(newest.release)} · ${formatDate(newest.release.published_at)}`
      : "No hay paquetes publicados todavía";

    return assets;
  }

  function prioritizePlatform(detected) {
    const cards = [...document.querySelectorAll(".platform-card")];
    const supported = Boolean(platforms[detected.key]);
    const grid = document.getElementById("platform-grid");
    if (supported) {
      cards.sort((a, b) => Number(b.dataset.platform === detected.key) - Number(a.dataset.platform === detected.key));
      cards.forEach((card) => {
        grid.append(card);
        const selected = card.dataset.platform === detected.key;
        card.classList.toggle("is-detected", selected);
        card.querySelector(".recommended-tag").hidden = !selected;
      });
      const info = platforms[detected.key];
      const banner = document.getElementById("platform-banner");
      banner.hidden = false;
      document.getElementById("platform-banner-title").textContent = `${info.label} detectado · tu opción está primero`;
      document.getElementById("detected-note").innerHTML = `<span class="detected-check" aria-hidden="true">✓</span><span>Detectamos ${info.label}. Preparamos la versión más reciente para ti.</span>`;
    } else {
      const banner = document.getElementById("platform-banner");
      banner.hidden = false;
      const message = detected.key === "ios"
        ? "iOS detectado · todavía no hay un paquete DxDesk para iPhone o iPad"
        : "No reconocimos el sistema · elige una de las plataformas disponibles";
      document.getElementById("platform-banner-title").textContent = message;
      document.getElementById("platform-banner").querySelector("small").textContent = "Puedes consultar las descargas disponibles para otros dispositivos.";
      document.getElementById("detected-note").innerHTML = `<span class="detected-check" aria-hidden="true">i</span><span>${message}</span>`;
    }

    const heroLink = document.getElementById("hero-download");
    const heroLabel = document.getElementById("hero-download-label");
    const heroCard = cards.find((card) => card.dataset.platform === detected.key);
    const primary = heroCard?.querySelector(".asset-link-primary");
    if (detected.key === "macos") {
      heroLink.href = "#platform-grid";
      heroLabel.textContent = "Elegir versión para macOS";
    } else if (primary) {
      heroLink.href = primary.href;
      heroLink.dataset.asset = primary.dataset.asset;
      heroLabel.textContent = `Descargar para ${platforms[detected.key].label}`;
    } else {
      heroLink.href = "#descargas";
      heroLabel.textContent = detected.key === "ios" ? "Ver plataformas disponibles" : "Descargar DxDesk";
    }
  }

  function startRevealAnimations() {
    document.documentElement.classList.add("js");
    const elements = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) {
      elements.forEach((element) => element.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver((entries, currentObserver) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          currentObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.13, rootMargin: "0px 0px -25px 0px" });
    elements.forEach((element) => observer.observe(element));
  }

  function setupMobileMenu() {
    const toggle = document.querySelector(".menu-toggle");
    const menu = document.getElementById("mobile-menu");
    const close = () => {
      toggle.setAttribute("aria-expanded", "false");
      menu.hidden = true;
      document.body.classList.remove("menu-open");
    };
    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(open));
      menu.hidden = !open;
      document.body.classList.toggle("menu-open", open);
    });
    menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", close));
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
  }

  function setupPlatformBannerLink() {
    const link = document.querySelector("#platform-banner a");
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const heading = document.getElementById("descargas-titulo");
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      heading.scrollIntoView({ block: "start", behavior: reducedMotion ? "auto" : "smooth" });
    });
  }

  async function init() {
    const detected = detectPlatform();
    prioritizePlatform(detected);
    startRevealAnimations();
    setupMobileMenu();
    setupPlatformBannerLink();
    document.getElementById("year").textContent = String(new Date().getFullYear());

    try {
      bindAssets(getLatestAssets(await fetchReleases()));
      const heroLink = document.getElementById("hero-download");
      if (heroLink.dataset.asset) {
        const latestHeroAsset = document.querySelector(`[data-asset="${CSS.escape(heroLink.dataset.asset)}"]`);
        if (latestHeroAsset) heroLink.href = latestHeroAsset.href;
      }
    } catch (error) {
      const status = document.getElementById("release-status");
      status.classList.add("error");
      document.getElementById("release-status-title").textContent = "No se pudieron cargar las descargas";
      document.getElementById("release-status-detail").textContent = "Abre GitHub para ver las versiones disponibles";
      document.querySelectorAll("[data-asset]").forEach((link) => { link.href = RELEASES_PAGE; });
      const heroLink = document.getElementById("hero-download");
      heroLink.href = detected.key === "macos" ? "#platform-grid" : RELEASES_PAGE;
      console.info("DxDesk: se mostrarán las releases de GitHub como alternativa.", error);
    }
  }

  init();
})();
