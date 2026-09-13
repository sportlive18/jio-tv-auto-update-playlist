/**
 * Gmax-JioTV — Main Homepage Logic
 * Fetches M3Us → deduplicates → builds server map → renders discovery UI
 */

"use strict";

/* ============================================================
   CONFIG
   ============================================================ */
const CONFIG = {
  // GitHub raw base (works from any host, including Cloudflare Pages)
  RAW_BASE: "https://raw.githubusercontent.com/purupc00-dev/Gmax-JioTV/main/",

  // Primary playlist (dictates metadata + order)
  PRIMARY_PLAYLIST: "Playlists/JioTV_S11.m3u",

  // Secondary playlists (attached as alternate servers)
  SECONDARY_PLAYLISTS: [
    "Playlists/JioTV_S1.m3u",
    "Playlists/JioTV_S2.m3u",
    "Playlists/JioTV_S3.m3u",
    "Playlists/JioTV_S4.m3u",
    "Playlists/JioTV_S5.m3u",
    "Playlists/JioTV_S6.m3u",
    "Playlists/JioTV_S7.m3u",
    "Playlists/JioTV_S8.m3u",
    "Playlists/JioTV_S9.m3u",
    "Playlists/JioTV_S10.m3u",
    "Playlists/JioTV_S12.m3u",
    "Playlists/JioTV_S13.m3u",
    "Playlists/Sport_S1.m3u",
    "Playlists/Sport_S2.m3u",
    "Playlists/Sport_S3.m3u",
    "Playlists/FreeDish.m3u",
    "Playlists/BiggBoss.m3u",
    "Playlists/LiveEvent.m3u",
    "Playlists/Pocket_TV.m3u",
    "Playlists/TnT_TV.m3u",
    "Playlists/digital.m3u",
  ],

  HIGHLIGHTS_URL: "highlights.json",          // or data/highlights.json
  NOTIFICATIONS_URL: "notifications.json",

  // Local storage keys
  SERVERS_MAP_KEY: "gmax_servers_map",
  FAVORITES_KEY: "gmax-jiotv-favorites",
  MOST_VIEWED_KEY: "gmax_most_viewed",
  NOTIF_READ_KEY: "gmax_notif_read",

  HERO_INTERVAL_MS: 5000,
  CHANNELS_PER_PAGE: 80,
};

/* ============================================================
   STATE
   ============================================================ */
let allChannels = [];          // deduplicated channel objects
let filteredChannels = [];
let activeCategory = "ALL";
let activeLanguage = "all";
let searchQuery = "";
let visibleCount = CONFIG.CHANNELS_PER_PAGE;
let heroIndex = 0;
let heroTimer = null;
let highlights = [];
let favorites = new Set(JSON.parse(localStorage.getItem(CONFIG.FAVORITES_KEY) || "[]"));
let mostViewed = JSON.parse(localStorage.getItem(CONFIG.MOST_VIEWED_KEY) || "{}"); // { id: count }

/* ============================================================
   DOM REFS
   ============================================================ */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const els = {
  searchInput: $("#search-input"),
  searchClear: $("#search-clear"),
  heroTrack: $("#hero-track"),
  heroDots: $("#hero-dots"),
  heroPrev: $("#hero-prev"),
  heroNext: $("#hero-next"),
  mostViewedSection: $("#most-viewed-section"),
  mostViewedTrack: $("#most-viewed-track"),
  mvPrev: $("#mv-prev"),
  mvNext: $("#mv-next"),
  categoryChips: $("#category-chips"),
  languageSelect: $("#language-select"),
  clearFilters: $("#clear-filters"),
  resultsCount: $("#results-count"),
  channelsGrid: $("#channels-grid"),
  emptyState: $("#empty-state"),
  loadingState: $("#loading-state"),
  emptyClear: $("#empty-clear"),
  notifBell: $("#notif-bell"),
  notifBadge: $("#notif-badge"),
  notifPanel: $("#notif-panel"),
  notifBody: $("#notif-body"),
  notifClose: $("#notif-close"),
  footerCount: $("#footer-channel-count"),
};

/* ============================================================
   HELPERS
   ============================================================ */
function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function normalizeName(name) {
  return String(name || "")
    .toLowerCase()
    .replace(/\s*\|\s*gmaxhub\s*$/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

function slugify(name) {
  return normalizeName(name)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "channel";
}

function getLogoFallback(name) {
  const initials = (name || "?")
    .replace(/\|.*$/, "")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0] || "")
    .join("")
    .toUpperCase();
  return initials || "?";
}

/* ============================================================
   M3U PARSER
   ============================================================ */
function parseM3U(text, sourceLabel = "unknown") {
  const lines = text.split(/\r?\n/);
  const channels = [];
  let current = null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    if (line.startsWith("#EXTINF:")) {
      // Parse attributes and display name
      const attrPart = line.substring(8);
      const commaIdx = attrPart.lastIndexOf(",");
      const attrsStr = commaIdx >= 0 ? attrPart.slice(0, commaIdx) : attrPart;
      const displayName = commaIdx >= 0 ? attrPart.slice(commaIdx + 1).trim() : "";

      const attrs = {};
      const attrRegex = /([\w-]+)="([^"]*)"/g;
      let m;
      while ((m = attrRegex.exec(attrsStr)) !== null) {
        attrs[m[1]] = m[2];
      }

      current = {
        tvgId: attrs["tvg-id"] || "",
        name: (attrs["tvg-name"] || displayName || "Unknown").replace(/\s*\|\s*GmaxHub\s*$/i, "").trim(),
        logo: attrs["tvg-logo"] || "",
        group: attrs["group-title"] || "Other",
        displayName: displayName || attrs["tvg-name"] || "Unknown",
        source: sourceLabel,
        // DRM / headers collected from following lines
        licenseKey: null,
        cookie: null,
        userAgent: null,
        referrer: null,
        origin: null,
        url: null,
        streamType: "mpd", // default
      };
    } else if (current) {
      if (line.startsWith("#KODIPROP:inputstream.adaptive.license_key=")) {
        current.licenseKey = line.split("=").slice(1).join("=").trim();
      } else if (line.startsWith("#EXTHTTP:")) {
        try {
          const json = JSON.parse(line.slice(9));
          if (json.Cookie) current.cookie = json.Cookie;
        } catch (_) {}
      } else if (line.startsWith("#EXTVLCOPT:http-cookie=")) {
        current.cookie = line.split("=").slice(1).join("=").trim();
      } else if (line.startsWith("#EXTVLCOPT:http-user-agent=")) {
        current.userAgent = line.split("=").slice(1).join("=").trim();
      } else if (line.startsWith("#EXTVLCOPT:http-referrer=")) {
        current.referrer = line.split("=").slice(1).join("=").trim();
      } else if (line.startsWith("#EXTVLCOPT:http-extra-headers=")) {
        const h = line.split("=").slice(1).join("=").trim();
        if (h.toLowerCase().startsWith("origin:")) {
          current.origin = h.slice(7).trim();
        }
      } else if (!line.startsWith("#")) {
        // Stream URL
        current.url = line;
        if (line.includes(".m3u8")) current.streamType = "hls";
        else if (line.includes(".mpd")) current.streamType = "mpd";
        channels.push(current);
        current = null;
      }
    }
  }
  return channels;
}

/* ============================================================
   FETCH + DEDUP ENGINE
   ============================================================ */
async function fetchText(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.text();
}

async function loadAllPlaylists() {
  const primaryUrl = CONFIG.RAW_BASE + CONFIG.PRIMARY_PLAYLIST;
  const primaryText = await fetchText(primaryUrl);
  const primaryChannels = parseM3U(primaryText, "S11");

  // key → channel entry. Primary (S11) stays first in display order.
  const map = new Map();
  const primaryOrder = []; // preserve S11 order for the grid

  for (const ch of primaryChannels) {
    const key = normalizeName(ch.name) || ch.tvgId || slugify(ch.name);
    const id = ch.tvgId || slugify(ch.name) || key;

    if (map.has(key)) continue; // skip exact dupes inside S11

    const entry = {
      id,
      name: ch.name,
      logo: ch.logo,
      group: ch.group || "Other",
      language: inferLanguage(ch.name, ch.group),
      isPrimary: true, // from JioTV S11
      servers: [
        {
          label: "Server 1 (S11)",
          source: "S11",
          url: ch.url,
          streamType: ch.streamType,
          licenseKey: ch.licenseKey,
          cookie: ch.cookie,
          userAgent: ch.userAgent,
          referrer: ch.referrer,
          origin: ch.origin,
        },
      ],
    };
    map.set(key, entry);
    primaryOrder.push(key);
  }

  // Secondary playlists:
  // - If name already exists in S11 → only attach as alternate server (for player switcher)
  // - If new → append AFTER all S11 channels (no source picker on main page)
  const secondaryPromises = CONFIG.SECONDARY_PLAYLISTS.map(async (path) => {
    try {
      const text = await fetchText(CONFIG.RAW_BASE + path);
      return { path, channels: parseM3U(text, path.split("/").pop().replace(".m3u", "")) };
    } catch (e) {
      console.warn("Failed to load", path, e.message);
      return { path, channels: [] };
    }
  });

  const secondaries = await Promise.all(secondaryPromises);
  const extraOrder = []; // new channels that appear only in secondary sources

  for (const { path, channels } of secondaries) {
    const sourceLabel = path.split("/").pop().replace(".m3u", "");
    for (const ch of channels) {
      const key = normalizeName(ch.name) || ch.tvgId;
      if (!key) continue;

      if (map.has(key)) {
        // Same channel as S11 → attach alternate server only (player will use this)
        const existing = map.get(key);
        const already = existing.servers.some((s) => s.url === ch.url);
        if (!already && ch.url) {
          existing.servers.push({
            label: `Server ${existing.servers.length + 1} (${sourceLabel})`,
            source: sourceLabel,
            url: ch.url,
            streamType: ch.streamType,
            licenseKey: ch.licenseKey,
            cookie: ch.cookie,
            userAgent: ch.userAgent,
            referrer: ch.referrer,
            origin: ch.origin,
          });
        }
      } else {
        // Brand-new channel → show BELOW S11 list
        const id = ch.tvgId || slugify(ch.name) || key;
        map.set(key, {
          id,
          name: ch.name,
          logo: ch.logo,
          group: ch.group || "Other",
          language: inferLanguage(ch.name, ch.group),
          isPrimary: false,
          servers: [
            {
              label: `Server 1 (${sourceLabel})`,
              source: sourceLabel,
              url: ch.url,
              streamType: ch.streamType,
              licenseKey: ch.licenseKey,
              cookie: ch.cookie,
              userAgent: ch.userAgent,
              referrer: ch.referrer,
              origin: ch.origin,
            },
          ],
        });
        extraOrder.push(key);
      }
    }
  }

  // Grid order: ALL S11 channels first, then other-source-only channels
  const result = [
    ...primaryOrder.map((k) => map.get(k)),
    ...extraOrder.map((k) => map.get(k)),
  ].filter(Boolean);

  // Persist full server map for player page (source switcher lives ONLY there)
  const serversMap = {};
  for (const ch of result) {
    serversMap[ch.id] = {
      id: ch.id,
      name: ch.name,
      logo: ch.logo,
      group: ch.group,
      servers: ch.servers,
    };
  }
  localStorage.setItem(CONFIG.SERVERS_MAP_KEY, JSON.stringify(serversMap));

  return result;
}

function inferLanguage(name, group) {
  const n = (name + " " + group).toLowerCase();
  if (/\b(hindi|star plus|colors|zee tv|sony sab|and tv)\b/.test(n)) return "Hindi";
  if (/\b(english|movies now|hbo|axn|star movies|sony pix)\b/.test(n)) return "English";
  if (/\b(tamil|sun tv|zee tamil|star vijay)\b/.test(n)) return "Tamil";
  if (/\b(telugu|gemini|zee telugu|star maa)\b/.test(n)) return "Telugu";
  if (/\b(malayalam|asianet|surya|zee keralam)\b/.test(n)) return "Malayalam";
  if (/\b(kannada|udaya|zee kannada|star suvarna)\b/.test(n)) return "Kannada";
  if (/\b(bengali|zee bangla|star jalsha)\b/.test(n)) return "Bengali";
  if (/\b(marathi|zee marathi|colors marathi|star pravah)\b/.test(n)) return "Marathi";
  if (/\b(punjabi|ptc|zee punjabi)\b/.test(n)) return "Punjabi";
  if (/\b(gujarati|colors gujarati|zee gujarati)\b/.test(n)) return "Gujarati";
  if (group && /sports|news|movies|kids|music|lifestyle|infotainment/i.test(group)) return "Multi";
  return "Other";
}

/* ============================================================
   CATEGORIES & LANGUAGES
   ============================================================ */
const MAIN_CATEGORIES = [
  "ALL",
  "Entertainment",
  "Movies",
  "Sports",
  "News",
  "Kids",
  "Music",
  "Lifestyle",
  "Infotainment",
  "English",
  "Regional",
];

function getUniqueLanguages(channels) {
  const set = new Set();
  channels.forEach((c) => set.add(c.language || "Other"));
  return ["all", ...Array.from(set).sort()];
}

function getCategoryCounts(channels) {
  const counts = { ALL: channels.length };
  MAIN_CATEGORIES.forEach((cat) => {
    if (cat === "ALL") return;
    counts[cat] = channels.filter((c) => matchCategory(c, cat)).length;
  });
  return counts;
}

function matchCategory(ch, cat) {
  if (cat === "ALL") return true;
  const g = (ch.group || "").toLowerCase();
  const n = (ch.name || "").toLowerCase();
  if (cat === "Regional") {
    return /tamil|telugu|malayalam|kannada|bengali|marathi|punjabi|gujarati|odia|assamese|bhojpuri/i.test(g + " " + n);
  }
  return g.includes(cat.toLowerCase()) || n.includes(cat.toLowerCase());
}

/* ============================================================
   FILTERS + RENDER
   ============================================================ */
function applyFilters() {
  const q = searchQuery.toLowerCase().trim();
  filteredChannels = allChannels.filter((ch) => {
    if (activeCategory !== "ALL" && !matchCategory(ch, activeCategory)) return false;
    if (activeLanguage !== "all" && ch.language !== activeLanguage) return false;
    if (q) {
      const hay = (ch.name + " " + ch.group + " " + (ch.language || "")).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  visibleCount = CONFIG.CHANNELS_PER_PAGE;
  renderChannels();
  updateResultsMeta();
  updateClearFiltersVisibility();
}

function updateResultsMeta() {
  const total = filteredChannels.length;
  const shown = Math.min(visibleCount, total);
  els.resultsCount.textContent =
    total === 0
      ? "No channels match"
      : shown < total
      ? `Showing ${shown} of ${total} channels`
      : `${total} channel${total === 1 ? "" : "s"}`;
  els.footerCount.textContent = `${allChannels.length} channels`;
}

function updateClearFiltersVisibility() {
  const hasFilter =
    activeCategory !== "ALL" || activeLanguage !== "all" || searchQuery.trim() !== "";
  els.clearFilters.classList.toggle("hidden", !hasFilter);
}

function renderCategoryChips() {
  const counts = getCategoryCounts(allChannels);
  els.categoryChips.innerHTML = "";

  MAIN_CATEGORIES.forEach((cat) => {
    if (cat !== "ALL" && (counts[cat] || 0) === 0) return;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip" + (activeCategory === cat ? " active" : "");
    btn.dataset.category = cat;
    btn.innerHTML =
      cat === "ALL"
        ? `All <span class="chip-count">${counts.ALL}</span>`
        : `${escapeHtml(cat)} <span class="chip-count">${counts[cat] || 0}</span>`;

    btn.addEventListener("click", () => {
      activeCategory = cat;
      $$(".chip").forEach((c) => c.classList.toggle("active", c.dataset.category === cat));
      applyFilters();
    });
    els.categoryChips.appendChild(btn);
  });
}

function renderLanguageSelect() {
  const langs = getUniqueLanguages(allChannels);
  els.languageSelect.innerHTML = "";
  langs.forEach((lang) => {
    const opt = document.createElement("option");
    opt.value = lang;
    opt.textContent = lang === "all" ? "All Languages" : lang;
    if (lang === activeLanguage) opt.selected = true;
    els.languageSelect.appendChild(opt);
  });
}

function createChannelCard(ch) {
  const isFav = favorites.has(String(ch.id));
  const card = document.createElement("article");
  card.className = "channel-card";
  card.setAttribute("role", "listitem");
  card.dataset.id = ch.id;

  const logoHtml = ch.logo
    ? `<img src="${escapeHtml(ch.logo)}" alt="" class="channel-logo" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
    : "";
  const fallback = `<div class="channel-fallback" style="${ch.logo ? "display:none" : ""}">${escapeHtml(getLogoFallback(ch.name))}</div>`;

  card.innerHTML = `
    <button type="button" class="fav-btn ${isFav ? "active" : ""}" data-id="${escapeHtml(ch.id)}" aria-label="Toggle favorite">
      ${isFav ? "♥" : "♡"}
    </button>
    <div class="channel-logo-wrap">
      ${logoHtml}
      ${fallback}
    </div>
    <div class="channel-info">
      <div class="channel-name">${escapeHtml(ch.name)}</div>
      <div class="channel-meta">
        <span class="channel-group">${escapeHtml(ch.group)}</span>
      </div>
    </div>
  `;

  // Click card → player
  card.addEventListener("click", (e) => {
    if (e.target.closest(".fav-btn")) return;
    trackView(ch.id);
    window.location.href = `./player.html?id=${encodeURIComponent(ch.id)}`;
  });

  // Favorite toggle
  card.querySelector(".fav-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    toggleFavorite(ch.id);
    const btn = e.currentTarget;
    const nowFav = favorites.has(String(ch.id));
    btn.classList.toggle("active", nowFav);
    btn.textContent = nowFav ? "♥" : "♡";
  });

  return card;
}

function renderChannels() {
  const slice = filteredChannels.slice(0, visibleCount);
  els.channelsGrid.innerHTML = "";
  els.loadingState.classList.add("hidden");

  if (slice.length === 0) {
    els.emptyState.classList.remove("hidden");
    els.channelsGrid.classList.add("hidden");
    return;
  }

  els.emptyState.classList.add("hidden");
  els.channelsGrid.classList.remove("hidden");

  const frag = document.createDocumentFragment();
  slice.forEach((ch) => frag.appendChild(createChannelCard(ch)));
  els.channelsGrid.appendChild(frag);

  // Infinite scroll sentinel
  if (visibleCount < filteredChannels.length) {
    const sentinel = document.createElement("div");
    sentinel.id = "scroll-sentinel";
    sentinel.style.height = "1px";
    els.channelsGrid.appendChild(sentinel);

    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          visibleCount += CONFIG.CHANNELS_PER_PAGE;
          obs.disconnect();
          renderChannels();
          updateResultsMeta();
        }
      },
      { rootMargin: "200px" }
    );
    obs.observe(sentinel);
  }
}

/* ============================================================
   FAVORITES + MOST VIEWED
   ============================================================ */
function toggleFavorite(id) {
  const key = String(id);
  if (favorites.has(key)) favorites.delete(key);
  else favorites.add(key);
  localStorage.setItem(CONFIG.FAVORITES_KEY, JSON.stringify([...favorites]));
}

function trackView(id) {
  const key = String(id);
  mostViewed[key] = (mostViewed[key] || 0) + 1;
  localStorage.setItem(CONFIG.MOST_VIEWED_KEY, JSON.stringify(mostViewed));
}

function renderMostViewed() {
  const sorted = Object.entries(mostViewed)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
    .map(([id]) => allChannels.find((c) => String(c.id) === id))
    .filter(Boolean);

  if (sorted.length === 0) {
    els.mostViewedSection.classList.add("hidden");
    return;
  }

  els.mostViewedSection.classList.remove("hidden");
  els.mostViewedTrack.innerHTML = "";

  sorted.forEach((ch) => {
    const item = document.createElement("div");
    item.className = "mv-item";
    item.innerHTML = `
      <div class="mv-logo-wrap">
        ${ch.logo ? `<img src="${escapeHtml(ch.logo)}" alt="" loading="lazy" onerror="this.style.display='none'">` : ""}
        <div class="mv-fallback">${escapeHtml(getLogoFallback(ch.name))}</div>
      </div>
      <div class="mv-name">${escapeHtml(ch.name)}</div>
    `;
    item.addEventListener("click", () => {
      trackView(ch.id);
      window.location.href = `./player.html?id=${encodeURIComponent(ch.id)}`;
    });
    els.mostViewedTrack.appendChild(item);
  });
}

/* ============================================================
   HERO BANNER
   ============================================================ */
async function loadHighlights() {
  const candidates = [
    "./" + CONFIG.HIGHLIGHTS_URL,
    "./data/" + CONFIG.HIGHLIGHTS_URL,
    CONFIG.RAW_BASE + CONFIG.HIGHLIGHTS_URL,
    CONFIG.RAW_BASE + "data/" + CONFIG.HIGHLIGHTS_URL,
  ];
  try {
    for (const url of candidates) {
      try {
        const res = await fetch(url, { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            highlights = data;
            return;
          }
        }
      } catch (_) {}
    }
    highlights = getDefaultHighlights();
  } catch {
    highlights = getDefaultHighlights();
  }
}

function getDefaultHighlights() {
  return [
    {
      title: "Star Sports 1 HD",
      description: "Live cricket, football and exclusive sports coverage in high definition.",
      image: "https://images.unsplash.com/photo-1540747913346-19e32dc3e20d?w=1200&q=80",
      tag: "🔴 LIVE",
      category: "SPORTS",
      channelName: "Star Sports 1 HD",
      channelId: null,
    },
    {
      title: "GmaxHub Premium",
      description: "Hundreds of channels. One place. Seamless ClearKey playback.",
      image: "https://images.unsplash.com/photo-1522869635100-9f4c5e86aa37?w=1200&q=80",
      tag: "NEW",
      category: "FEATURED",
      channelName: null,
      channelId: null,
    },
  ];
}

function renderHero() {
  if (!highlights.length) {
    $("#hero-section").classList.add("hidden");
    return;
  }

  els.heroTrack.innerHTML = "";
  els.heroDots.innerHTML = "";

  highlights.forEach((item, i) => {
    const slide = document.createElement("div");
    slide.className = "hero-slide" + (i === 0 ? " active" : "");
    slide.style.backgroundImage = `linear-gradient(90deg, rgba(10,13,24,0.92) 0%, rgba(10,13,24,0.4) 50%, rgba(10,13,24,0.7) 100%), url('${escapeHtml(item.image || "")}')`;
    slide.innerHTML = `
      <div class="hero-content">
        ${item.tag ? `<span class="hero-tag">${escapeHtml(item.tag)}</span>` : ""}
        <h2 class="hero-title">${escapeHtml(item.title || "")}</h2>
        <p class="hero-desc">${escapeHtml(item.description || "")}</p>
        <div class="hero-actions">
          ${
            item.channelId || item.channelName
              ? `<button type="button" class="btn-primary hero-play" data-id="${escapeHtml(item.channelId || "")}" data-name="${escapeHtml(item.channelName || "")}">▶ Watch Now</button>`
              : ""
          }
        </div>
      </div>
    `;
    els.heroTrack.appendChild(slide);

    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "hero-dot" + (i === 0 ? " active" : "");
    dot.setAttribute("aria-label", `Slide ${i + 1}`);
    dot.addEventListener("click", () => goToHero(i));
    els.heroDots.appendChild(dot);
  });

  // Play buttons
  els.heroTrack.querySelectorAll(".hero-play").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const name = btn.dataset.name;
      let target = null;
      if (id) target = allChannels.find((c) => String(c.id) === id);
      if (!target && name) {
        const n = normalizeName(name);
        target = allChannels.find((c) => normalizeName(c.name) === n);
      }
      if (target) {
        trackView(target.id);
        window.location.href = `./player.html?id=${encodeURIComponent(target.id)}`;
      }
    });
  });

  startHeroAutoplay();
}

function goToHero(index) {
  heroIndex = (index + highlights.length) % highlights.length;
  $$(".hero-slide").forEach((s, i) => s.classList.toggle("active", i === heroIndex));
  $$(".hero-dot").forEach((d, i) => d.classList.toggle("active", i === heroIndex));
  resetHeroAutoplay();
}

function startHeroAutoplay() {
  clearInterval(heroTimer);
  heroTimer = setInterval(() => goToHero(heroIndex + 1), CONFIG.HERO_INTERVAL_MS);
}

function resetHeroAutoplay() {
  startHeroAutoplay();
}

/* ============================================================
   NOTIFICATIONS
   ============================================================ */
async function loadNotifications() {
  const candidates = [
    "./" + CONFIG.NOTIFICATIONS_URL,
    "./data/" + CONFIG.NOTIFICATIONS_URL,
    CONFIG.RAW_BASE + CONFIG.NOTIFICATIONS_URL,
    CONFIG.RAW_BASE + "data/" + CONFIG.NOTIFICATIONS_URL,
  ];
  try {
    for (const url of candidates) {
      try {
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) continue;
        const data = await res.json();
        if (!data || !data.enabled) return;

        const readKey = localStorage.getItem(CONFIG.NOTIF_READ_KEY);
        const isNew = readKey !== data.time;

        els.notifBody.innerHTML = `
          <div class="notif-item">
            <strong>${escapeHtml(data.title || "Update")}</strong>
            <p>${escapeHtml(data.message || "")}</p>
            <span class="notif-time">${escapeHtml(data.time || "")}</span>
          </div>
        `;

        if (isNew) {
          els.notifBadge.classList.remove("hidden");
          els.notifBadge.textContent = "1";
        }
        return;
      } catch (_) {}
    }
  } catch (_) {}
}

/* ============================================================
   EVENT BINDINGS
   ============================================================ */
function bindEvents() {
  // Search
  let searchDebounce;
  els.searchInput.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      searchQuery = els.searchInput.value;
      els.searchClear.classList.toggle("hidden", !searchQuery);
      applyFilters();
    }, 180);
  });
  els.searchClear.addEventListener("click", () => {
    els.searchInput.value = "";
    searchQuery = "";
    els.searchClear.classList.add("hidden");
    applyFilters();
    els.searchInput.focus();
  });

  // Language
  els.languageSelect.addEventListener("change", () => {
    activeLanguage = els.languageSelect.value;
    applyFilters();
  });

  // Clear filters
  els.clearFilters.addEventListener("click", () => {
    activeCategory = "ALL";
    activeLanguage = "all";
    searchQuery = "";
    els.searchInput.value = "";
    els.searchClear.classList.add("hidden");
    els.languageSelect.value = "all";
    $$(".chip").forEach((c) => c.classList.toggle("active", c.dataset.category === "ALL"));
    applyFilters();
  });
  els.emptyClear.addEventListener("click", () => els.clearFilters.click());

  // Hero arrows
  els.heroPrev.addEventListener("click", () => goToHero(heroIndex - 1));
  els.heroNext.addEventListener("click", () => goToHero(heroIndex + 1));

  // Most viewed slider
  els.mvPrev.addEventListener("click", () => {
    els.mostViewedTrack.scrollBy({ left: -280, behavior: "smooth" });
  });
  els.mvNext.addEventListener("click", () => {
    els.mostViewedTrack.scrollBy({ left: 280, behavior: "smooth" });
  });

  // Notification
  els.notifBell.addEventListener("click", () => {
    els.notifPanel.classList.toggle("hidden");
    els.notifBadge.classList.add("hidden");
    // Mark as read
    const timeEl = els.notifBody.querySelector(".notif-time");
    if (timeEl) localStorage.setItem(CONFIG.NOTIF_READ_KEY, timeEl.textContent);
  });
  els.notifClose.addEventListener("click", () => els.notifPanel.classList.add("hidden"));

  // Close notif on outside click
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".notif-widget")) {
      els.notifPanel.classList.add("hidden");
    }
  });

  // Keyboard: / focuses search
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== els.searchInput) {
      e.preventDefault();
      els.searchInput.focus();
    }
  });
}

/* ============================================================
   INIT
   ============================================================ */
async function init() {
  bindEvents();
  loadNotifications();

  try {
    await loadHighlights();
    renderHero();

    allChannels = await loadAllPlaylists();
    console.log(`[Gmax] Loaded ${allChannels.length} unique channels`);

    renderCategoryChips();
    renderLanguageSelect();
    renderMostViewed();
    applyFilters();
  } catch (err) {
    console.error("Failed to load playlists", err);
    els.loadingState.innerHTML = `
      <div class="error-box">
        <p>Could not load playlists.</p>
        <p class="error-detail">${escapeHtml(err.message)}</p>
        <button type="button" class="btn-primary" onclick="location.reload()">Retry</button>
      </div>
    `;
  }
}

init();
