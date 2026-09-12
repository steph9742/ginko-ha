// custom_components/ginko/lovelace/ginko-card.js
// Ginko Besançon — Lovelace custom card

const VERSION = "1.2.0";

// ── SVG icons ────────────────────────────────────────────────────────────────

// Bus vu de face : carrosserie, pare-brise scindé, phares, passages de roues
const ICON_BUS  = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17.5V5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v12a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5Z"/><path d="M4 11.5h16"/><path d="M12 3v8.5"/><circle cx="7.6" cy="15.2" r=".9" fill="currentColor" stroke="none"/><circle cx="16.4" cy="15.2" r=".9" fill="currentColor" stroke="none"/><path d="M6.2 19v1.2a.9.9 0 0 1-.9.9h-.4a.9.9 0 0 1-.9-.9V19"/><path d="M20 19v1.2a.9.9 0 0 1-.9.9h-.4a.9.9 0 0 1-.9-.9V19"/></svg>`;
// Tram vu de face : pantographe, caisse, phares, bogies sur rail
const ICON_TRAM = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 1.5L12 3.8l3.5-2.3"/><path d="M12 3.8V5"/><rect x="5" y="5" width="14" height="12.5" rx="2.4"/><path d="M5 11h14"/><circle cx="8.3" cy="14.4" r=".9" fill="currentColor" stroke="none"/><circle cx="15.7" cy="14.4" r=".9" fill="currentColor" stroke="none"/><path d="M9.5 17.5L8 21M14.5 17.5L16 21"/><path d="M5.5 21h13"/></svg>`;
const ICON_PERSON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="7" r="4"/><path d="M4 21v-1a8 8 0 0116 0v1"/></svg>`;
const ICON_ARROW = `<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 6h8M7 3l3 3-3 3"/></svg>`;
const ICON_WARN = `<svg viewBox="0 0 16 16" fill="none"><path d="M8 2L14.5 14H1.5L8 2Z" stroke="currentColor" stroke-width="1.2"/><path d="M8 7v3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><circle cx="8" cy="12" r=".6" fill="currentColor"/></svg>`;
// Pictogramme fauteuil roulant (accessibilité PMR) — personne assise + roue
const ICON_ACCESS = `<svg class="gk-icon-access" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><title>Accessible PMR</title><circle cx="13" cy="4.3" r="1.8"/><path d="M12.7 6.8v5.7h4.3l2.6 5.7"/><path d="M12.7 9.6h3.6"/><path d="M9.9 11.5a5.3 5.3 0 1 0 6.9 7"/></svg>`;

function _modeIcon(modeTransport) {
  return modeTransport === 1 ? ICON_TRAM : ICON_BUS;
}

function _iconWifi(color) {
  return `<svg class="gk-icon-wifi" style="color:${color}" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.7"><title>Temps réel</title><path d="M1.5 6a9 9 0 0113 0" opacity=".3"/><path d="M3.5 8.2a6 6 0 019 0" opacity=".6"/><path d="M5.8 10.4a3 3 0 014.4 0"/><circle cx="8" cy="13" r="1" fill="currentColor" stroke="none"/></svg>`;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function _esc(str) {
  if (str == null) return "";
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

/**
 * Sanitise du HTML semi-fiable (corps de message API Ginko).
 * Supprime les scripts, les gestionnaires d'événements inline et les
 * URLs javascript: — conserve la mise en forme (gras, liens, paragraphes).
 */
function _sanitizeHtml(raw) {
  if (!raw) return "";
  return String(raw)
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script\s*>/gi, "")
    .replace(/\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, "")
    .replace(/href\s*=\s*(?:"javascript:[^"]*"|'javascript:[^']*')/gi, 'href="#"')
    .replace(/src\s*=\s*(?:"javascript:[^"]*"|'javascript:[^']*')/gi, "");
}

function _capitalize(str) {
  if (!str) return str;
  // Capitalise uniquement après espace, tiret ou début — pas après les caractères accentués
  return String(str).replace(/(^|[ \t\-])([^\s\-])/g, (_, sep, char) => sep + char.toUpperCase());
}

function _hexToRgb(hex) {
  if (!hex) return "128,128,128";
  const h = String(hex).replace("#","");
  if (h.length < 6) return "128,128,128";
  return `${parseInt(h.slice(0,2),16)},${parseInt(h.slice(2,4),16)},${parseInt(h.slice(4,6),16)}`;
}

function _color(hex) {
  if (!hex) return "#888888";
  const h = String(hex).trim();
  return h.startsWith("#") ? h : "#" + h;
}

function _timeSince(isoDate) {
  if (!isoDate) return "";
  const diff = Math.round((Date.now() - new Date(isoDate).getTime()) / 1000);
  if (diff < 5)  return "à l'instant";
  if (diff < 60) return `il y a ${diff}s`;
  return `il y a ${Math.round(diff / 60)} min`;
}

// Distance Haversine en mètres
function _haversine(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat/2)**2
    + Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * Math.sin(dLng/2)**2;
  return Math.round(R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
}

// ── Styles ───────────────────────────────────────────────────────────────────
// Utilise exclusivement les variables CSS de HA → fonctionne en mode clair ET sombre

const STYLES = `
  :host {
    --gk-bg:     var(--ha-card-background, var(--card-background-color));
    --gk-row-bg: var(--secondary-background-color, rgba(128,128,128,0.06));
    --gk-border: var(--divider-color, rgba(0,0,0,0.12));
    --gk-r-lg:   var(--ha-card-border-radius, 14px);
    --gk-r-md:   10px;
    --gk-r-sm:   6px;
    --gk-txt:    var(--primary-text-color);
    --gk-txt-2:  var(--secondary-text-color);
    --gk-txt-3:  var(--disabled-text-color);
    --gk-warn:   var(--warning-color, #f59e0b);
    --gk-blue:   var(--info-color, #3b82f6);
    --gk-amber:  var(--warning-color, #f59e0b);
    font-size: 14px;
    display: block;
  }
  /* Teintes dérivées du texte : contraste correct en thème clair (où
     disabled-text-color ≈ #bdbdbd est illisible) comme en thème sombre. */
  @supports (color: color-mix(in srgb, red 50%, blue)) {
    :host {
      --gk-txt-3:  color-mix(in srgb, var(--primary-text-color) 55%, transparent);
      --gk-row-bg: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
    }
  }
  * { box-sizing: border-box; }
  .gk-card {
    background: var(--gk-bg);
    border: 0.5px solid var(--gk-border);
    border-radius: var(--gk-r-lg);
    overflow: hidden;
    font-family: var(--paper-font-body1_-_font-family, system-ui, sans-serif);
    box-shadow: var(--ha-card-box-shadow, none);
  }
  /* Header */
  .gk-header { padding:10px 12px; display:flex; align-items:center; gap:8px; border-bottom:0.5px solid var(--gk-border); }
  .gk-header svg { width:18px; height:18px; color:var(--gk-txt-3); flex-shrink:0; }
  .gk-header-title { font-size:13px; font-weight:600; color:var(--gk-txt); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gk-header-upd { font-size:10px; color:var(--gk-txt-3); white-space:nowrap; }
  /* Next banner */
  .gk-next { margin:10px 10px 6px; border-radius:var(--gk-r-md); overflow:hidden; }
  .gk-next-body { padding:10px 12px 10px; display:flex; align-items:flex-start; justify-content:space-between; gap:8px; }
  .gk-next-left { display:flex; align-items:center; gap:6px; flex-wrap:wrap; flex:1; min-width:0; }
  .gk-next-dest { font-size:12px; color:var(--gk-txt-2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gk-next-time { display:flex; align-items:baseline; gap:2px; flex-shrink:0; }
  .gk-next-val { font-size:24px; font-weight:700; color:var(--gk-txt); line-height:1; }
  .gk-next-val--sm { font-size:17px; font-weight:700; color:var(--gk-txt); line-height:1; }
  .gk-next-unit { font-size:11px; color:var(--gk-txt-3); align-self:flex-end; padding-bottom:2px; }
  /* Badge — liseré adaptatif : les couleurs officielles de ligne peuvent être
     sombres (bleu marine…) et se fondre dans une carte sombre, ou claires et
     se fondre dans une carte claire. Un anneau à 20% de la couleur du texte
     du thème garantit le contour dans les deux modes. */
  .gk-badge { font-size:11px; font-weight:700; padding:2px 7px; border-radius:var(--gk-r-sm); line-height:1.4; white-space:nowrap; flex-shrink:0; box-shadow:0 0 0 1px color-mix(in srgb, var(--gk-txt) 20%, transparent); }
  /* Icons */
  .gk-icon-wifi { width:13px; height:13px; flex-shrink:0; }
  .gk-icon-access { width:12px; height:12px; color:var(--gk-blue); flex-shrink:0; }
  .gk-approx { font-size:11px; font-weight:700; color:var(--gk-amber); line-height:1; flex-shrink:0; }
  /* Lines section */
  .gk-lines { padding:0 10px 10px; display:flex; flex-direction:column; gap:6px; }
  .gk-ligne { border-radius:var(--gk-r-md); overflow:hidden; border:0.5px solid var(--gk-border); }
  .gk-ligne-hd { padding:7px 10px; display:flex; align-items:center; gap:8px; background:var(--gk-row-bg); }
  .gk-ligne-dests { font-size:11px; color:var(--gk-txt-3); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  /* Direction */
  .gk-dir { padding:0; }
  .gk-dir+.gk-dir { border-top:0.5px solid var(--gk-border); }
  /* Pills */
  .gk-pills { display:flex; gap:5px; flex-wrap:wrap; }
  .gk-pills-follow { padding:2px 10px 8px; }
  .gk-pill { display:inline-flex; align-items:center; gap:4px; padding:5px 9px; border-radius:99px; border:0.5px solid; }
  .gk-pill-time { display:flex; align-items:baseline; gap:2px; }
  .gk-pill-val { font-weight:600; color:var(--gk-txt); font-size:13px; font-variant-numeric:tabular-nums; }
  .gk-pill-unit { font-size:10px; color:var(--gk-txt-3); }
  .gk-pill-hhmm { font-weight:500; color:var(--gk-txt-2); font-size:12px; font-variant-numeric:tabular-nums; }
  .gk-pill-disruption { font-size:11px; font-weight:600; color:#b45309; font-style:italic; }
  .gk-dir-prec { font-size:9px; color:var(--gk-txt-3); font-weight:400; text-transform:none; letter-spacing:0; }
  /* Alert — bandeau perturbations en haut de carte */
  .gk-alert { margin:0 10px 6px; padding:8px 10px; font-size:12px; background:rgba(245,158,11,0.10); border:0.5px solid rgba(245,158,11,0.40); border-left:3px solid #d97706; color:var(--gk-txt); display:flex; flex-direction:column; gap:5px; border-radius:var(--gk-r-md); }
  .gk-alert-row { display:flex; gap:6px; align-items:flex-start; line-height:1.35; min-width:0; }
  .gk-alert-row svg { width:13px; height:13px; flex-shrink:0; margin-top:1px; color:#d97706; }
  .gk-alert-badge { font-size:10px; font-weight:700; color:var(--gk-txt); background:rgba(245,158,11,0.22); padding:1px 6px; border-radius:99px; white-space:nowrap; flex-shrink:0; }
  .gk-alert-txt { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; }
  .gk-alert-more { font-size:10px; color:var(--gk-txt-3); font-style:italic; padding-left:19px; }
  /* Misc */
  .gk-empty   { padding:20px 14px; font-size:13px; color:var(--gk-txt-3); text-align:center; }
  .gk-unavail { padding:14px; font-size:13px; color:var(--gk-txt-3); }
  .gk-fin { font-size:11px; color:var(--gk-txt-3); font-style:italic; }
  /* Proximity */
  .gk-prox-stops { padding:10px 10px 10px; display:flex; flex-direction:column; gap:6px; }
  .gk-stop { border-radius:var(--gk-r-md); overflow:hidden; border:0.5px solid var(--gk-border); }
  .gk-stop-hd { padding:7px 10px; display:flex; align-items:center; gap:6px; background:var(--gk-row-bg); border-bottom:0.5px solid var(--gk-border); }
  .gk-stop-name { font-size:12px; font-weight:600; color:var(--gk-txt); flex:1; }
  .gk-stop-dist { font-size:10px; color:var(--gk-txt-3); white-space:nowrap; }
  .gk-stop-pmr { display:inline-flex; align-items:center; }
  .gk-stop-pmr svg { width:13px; height:13px; color:var(--gk-blue); }
  .gk-stop-row { display:flex; align-items:center; gap:8px; padding:6px 10px; border-top:0.5px solid var(--gk-border); }
  .gk-stop-dest { flex:1; font-size:12px; color:var(--gk-txt-2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gk-stop-time { font-size:13px; font-weight:600; color:var(--gk-txt); white-space:nowrap; font-variant-numeric:tabular-nums; }
  /* Position suivi (option A) */
  .gk-next-pos { display:flex; align-items:center; gap:5px; padding:3px 10px 6px; font-size:10px; color:var(--gk-txt-3); }
  .gk-next-pos-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }
  .gk-pill-pos { width:5px; height:5px; border-radius:50%; flex-shrink:0; }
`;

// ── Card class ────────────────────────────────────────────────────────────────

class GinkoCard extends HTMLElement {
  static getConfigElement() { return document.createElement("ginko-card-editor"); }
  static getStubConfig() {
    return { entity: "", mode: "lieu", max_passages: 3, show_traffic: "if_disrupted" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._refreshTimer = null;
  }

  setConfig(config) {
    this._config = {
      entity:          config.entity ?? "",
      messages_entity: config.messages_entity ?? "",
      person_entity:   config.person_entity ?? "",
      // suivi_entity (string) gardé pour compat ; suivi_entities (array) prioritaire
      suivi_entities:  Array.isArray(config.suivi_entities)
                         ? config.suivi_entities
                         : (config.suivi_entity ? [config.suivi_entity] : []),
      mode:            config.mode ?? "lieu",
      max_passages:    Math.min(5, Math.max(1, config.max_passages ?? 3)),
      max_stops:       Math.min(10, Math.max(1, config.max_stops ?? 5)),
      show_traffic:    config.show_traffic ?? "if_disrupted",
      lignes_filtre:   Array.isArray(config.lignes_filtre) ? config.lignes_filtre : [],
    };
    if (this._hass) this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }

  connectedCallback()    { this._refreshTimer = setInterval(() => this._render(), 15000); }
  disconnectedCallback() { clearInterval(this._refreshTimer); }
  getCardSize()          { return 3; }

  _render() {
    if (!this._config || !this._hass) return;
    let html;
    if (this._config.mode === "proximity") {
      html = this._config.person_entity
        ? this._renderPersonProximity()
        : this._renderProximity();
    } else {
      html = this._renderLieu();
    }
    const isDark = this._hass?.themes?.darkMode ?? false;
    const darkBg = isDark ? `<style>.gk-card{background:#0f1729!important}</style>` : "";
    this.shadowRoot.innerHTML = `<style>${STYLES}</style>${darkBg}${html}`;
  }

  // ── Header ────────────────────────────────────────────────────────────────

  _header(title, updated, icon = ICON_BUS) {
    return `<div class="gk-header">
      ${icon}
      <span class="gk-header-title">${_esc(title)}</span>
      <span class="gk-header-upd">màj ${_timeSince(updated)}</span>
    </div>`;
  }

  // ── Position suivi ───────────────────────────────────────────────────────

  _posMap() {
    const entities = this._config.suivi_entities ?? [];
    if (!entities.length) return new Map();
    const map = new Map();
    for (const eid of entities) {
      const e = this._hass?.states[eid];
      for (const bus of e?.attributes?.buses ?? []) {
        if (bus.id == null) continue;
        const key = String(bus.id);
        const prev = map.get(key);
        if (!prev || (bus.dans_sec ?? Infinity) < (prev.dans_sec ?? Infinity)) {
          map.set(key, bus);
        }
      }
    }
    return map;
  }

  // ── Mode lieu ─────────────────────────────────────────────────────────────

  _renderLieu() {
    if (!this._config.entity) {
      return `<div class="gk-card"><div class="gk-empty">Sélectionnez une entité Ginko dans la configuration de la carte.</div></div>`;
    }
    const entity = this._hass.states[this._config.entity];
    if (!entity) return `<div class="gk-card"><div class="gk-unavail">Entité introuvable : ${_esc(this._config.entity)}</div></div>`;

    const attrs    = entity.attributes ?? {};
    const raw      = Array.isArray(attrs.passages) ? attrs.passages : [];
    const filtre   = this._config.lignes_filtre ?? [];
    const all      = filtre.length
      ? raw.filter(p => filtre.includes(String(p.numLignePublic ?? p.idLigne ?? "")))
      : raw;
    const rawTitle = attrs.nom_arret ?? attrs.friendly_name ?? entity.entity_id;
    const title    = _capitalize(rawTitle);

    return `<div class="gk-card">
      ${this._header(title, entity.last_updated)}
      ${this._passagesInner(all)}
    </div>`;
  }

  _passagesInner(all) {
    const lineNums  = [...new Set(all.map(p => String(p.numLignePublic ?? p.idLigne ?? "")))].filter(Boolean);
    const alerts    = this._alerts(lineNums);
    const disrupted = alerts.length > 0;
    const banner    = this._shouldShowTraffic(disrupted) && disrupted ? this._alertBanner(alerts) : "";

    if (all.length === 0) {
      return `${banner}<div class="gk-empty">Aucun passage disponible.</div>`;
    }

    const nextP = all.reduce((a, b) =>
      (a.tempsEnSeconde ?? 999999) <= (b.tempsEnSeconde ?? 999999) ? a : b
    );

    const byLigne = new Map();
    for (const p of all) {
      const k = p.idLigne ?? p.numLignePublic ?? "?";
      if (!byLigne.has(k)) byLigne.set(k, []);
      byLigne.get(k).push(p);
    }

    const posMap     = this._posMap();
    const ligneCards = [...byLigne.values()].map(lp => this._renderLigneCard(lp, nextP, posMap)).join("");
    return `${banner}<div class="gk-lines">${ligneCards}</div>`;
  }

  _renderNextBanner(p, posMap = new Map()) {
    const bg  = _color(p.couleurFond);
    const fg  = _color(p.couleurTexte);
    const rgb = _hexToRgb(bg);
    const gpsIcon    = p.fiable === false ? `<span class="gk-approx" title="Horaire théorique">~</span>` : _iconWifi(bg);
    const accessIcon = p.accessibiliteVehicule == 1 ? ICON_ACCESS : "";

    const bus = posMap.get(String(p.numVehicule ?? ""));
    let posHtml = "";
    if (bus) {
      const dot = bus.statut === "a_quai" ? "#22c55e" : "#3b82f6";
      const label = bus.statut === "a_quai"
        ? `À quai : ${_esc(bus.prochain_arret ?? "")}`
        : bus.statut === "depart"
          ? `Au départ de ${_esc(bus.prochain_arret ?? "")}`
          : `${_esc(bus.arret_precedent ?? "")} → ${_esc(bus.prochain_arret ?? "")}`;
      posHtml = `<div class="gk-next-pos"><span class="gk-next-pos-dot" style="background:${dot}"></span>${label}</div>`;
    }
    const prec       = p.precisionDestination ? ` <span style="font-size:10px;opacity:.7">(${_esc(p.precisionDestination)})</span>` : "";
    let timeHtml;
    if (p.typeDeTemps === 0) {
      const mins = String(p.temps ?? "").replace(" min","").trim();
      timeHtml = `<span class="gk-next-val">${_esc(mins)}</span><span class="gk-next-unit">min</span>`;
    } else if (p.typeDeTemps === 2) {
      timeHtml = `<span class="gk-next-val--sm" style="color:#b45309;font-style:italic">${_esc(p.temps ?? "—")}</span>`;
    } else {
      timeHtml = `<span class="gk-next-val--sm">${_esc(p.temps ?? "—")}</span>`;
    }
    return `<div class="gk-next" style="background:rgba(${rgb},0.12);border:1px solid rgba(${rgb},0.6)">
      <div class="gk-next-body">
        <div class="gk-next-left">
          <span class="gk-badge" style="background:${bg};color:${fg}">${_esc(p.numLignePublic ?? p.idLigne ?? "?")}</span>
          <span class="gk-next-dest">→ ${_esc(p.destination ?? "—")}${prec}</span>
          ${gpsIcon}${accessIcon}
        </div>
        <div class="gk-next-time">${timeHtml}</div>
      </div>
      ${posHtml}
    </div>`;
  }

  _renderLigneCard(lignePassages, nextP, posMap = new Map()) {
    const first = lignePassages[0];
    const bg  = _color(first.couleurFond);
    const fg  = _color(first.couleurTexte);
    const rgb = _hexToRgb(bg);

    const byDest = new Map();
    for (const p of lignePassages) {
      const d = p.destination ?? "?";
      if (!byDest.has(d)) byDest.set(d, []);
      byDest.get(d).push(p);
    }

    const destsLabel = _esc([...byDest.keys()].join(" · "));

    const dirs = [...byDest.entries()].map(([dest, dps], i) => {
      const borderStyle = i > 0 ? `border-color:rgba(${rgb},0.15)` : "";
      // Bannière = premier passage de cette direction
      const banner = this._renderNextBanner(dps[0], posMap);
      // Pills = passages suivants (on ne répète pas le premier)
      const follow = dps.slice(1, this._config.max_passages);
      const pillsHtml = follow.length
        ? `<div class="gk-pills gk-pills-follow">${follow.map(p => this._renderPill(p, nextP, posMap)).join("")}</div>`
        : "";
      return `<div class="gk-dir" style="${borderStyle}">${banner}${pillsHtml}</div>`;
    }).join("");

    const modeIco = `<span style="width:13px;height:13px;display:inline-flex;opacity:.5;flex-shrink:0">${_modeIcon(first.modeTransport)}</span>`;
    return `<div class="gk-ligne" style="border:0.5px solid rgba(${rgb},0.30)">
      <div class="gk-ligne-hd" style="background:rgba(${rgb},0.10)">
        <span class="gk-badge" style="background:${bg};color:${fg}">${_esc(first.numLignePublic ?? first.idLigne ?? "?")}</span>
        ${modeIco}
        <span class="gk-ligne-dests">${destsLabel}</span>
      </div>
      ${dirs}
    </div>`;
  }

  _renderPill(p, nextP, posMap = new Map()) {
    const bg  = _color(p.couleurFond);
    const rgb = _hexToRgb(bg);
    const isNext = p.tempsEnSeconde === nextP.tempsEnSeconde
      && p.idLigne === nextP.idLigne
      && p.destination === nextP.destination;
    const bgA     = isNext ? "0.18" : "0.10";
    const borderA = isNext ? "0.50" : "0.32";
    const gpsIcon    = p.fiable === false ? `<span class="gk-approx" title="Horaire théorique">~</span>` : _iconWifi(bg);
    const accessIcon = p.accessibiliteVehicule == 1 ? ICON_ACCESS : "";

    const bus = posMap.get(String(p.numVehicule ?? ""));
    let posDot = "";
    if (bus) {
      const aQuai    = bus.statut === "a_quai";
      const dotColor = aQuai ? "#22c55e" : "#3b82f6";
      const dotTitle = aQuai ? "Bus à quai" : "Bus localisé, en circulation";
      posDot = `<span class="gk-pill-pos" style="background:${dotColor}" title="${dotTitle}"></span>`;
    }

    let timeHtml;
    if (p.typeDeTemps === 0) {
      const mins = String(p.temps ?? "").replace(" min","").trim();
      timeHtml = `<span class="gk-pill-val">${_esc(mins)}</span><span class="gk-pill-unit">min</span>`;
    } else if (p.typeDeTemps === 2) {
      // Texte de remplacement : Déviation, Travaux, Bus complet…
      timeHtml = `<span class="gk-pill-disruption">${_esc(p.temps ?? "—")}</span>`;
    } else {
      timeHtml = `<span class="gk-pill-hhmm">${_esc(p.temps ?? "—")}</span>`;
    }
    return `<span class="gk-pill" style="background:rgba(${rgb},${bgA});border-color:rgba(${rgb},${borderA})">
      ${gpsIcon}
      <span class="gk-pill-time">${timeHtml}</span>
      ${accessIcon}${posDot}
    </span>`;
  }

  // ── Mode proximity (entité sensor) ────────────────────────────────────────

  _renderProximity() {
    const entity = this._hass.states[this._config.entity];
    if (!entity) return `<div class="gk-card"><div class="gk-unavail">Entité introuvable : ${_esc(this._config.entity)}</div></div>`;

    const attrs  = entity.attributes ?? {};
    const arrets   = (Array.isArray(attrs.arrets) ? attrs.arrets : []).slice(0, this._config.max_stops);
    const lineNums  = [...new Set(arrets.flatMap(a =>
      (Array.isArray(a.passages) ? a.passages : []).map(p => String(p.numLignePublic ?? p.idLigne ?? ""))
    ))].filter(Boolean);
    const alerts    = this._alerts(lineNums);
    const disrupted = alerts.length > 0;

    const stops = arrets.length
      ? arrets.map(a => this._renderStop(a)).join("")
      : `<div class="gk-empty">Aucun arrêt à proximité.</div>`;

    return `<div class="gk-card">
      ${this._header("Arrêts à proximité", entity.last_updated)}
      ${this._shouldShowTraffic(disrupted) && disrupted ? this._alertBanner(alerts) : ""}
      <div class="gk-prox-stops">${stops}</div>
    </div>`;
  }

  // ── Mode proximity (entité personne) ─────────────────────────────────────

  _renderPersonProximity() {
    const personEntity = this._hass.states[this._config.person_entity];
    if (!personEntity) {
      return `<div class="gk-card"><div class="gk-unavail">Entité introuvable : ${_esc(this._config.person_entity)}</div></div>`;
    }

    const lat = personEntity.attributes.latitude;
    const lng = personEntity.attributes.longitude;
    if (!lat || !lng) {
      const name = personEntity.attributes.friendly_name ?? this._config.person_entity;
      return `<div class="gk-card">
        ${this._header(_esc(name), personEntity.last_updated, ICON_PERSON)}
        <div class="gk-empty">Position GPS non disponible pour cette personne.</div>
      </div>`;
    }

    // Scanner tous les capteurs Ginko lieu dans les états HA
    const ginkoSensors = Object.entries(this._hass.states)
      .filter(([id, s]) => {
        if (!id.startsWith("sensor.ginko_")) return false;
        if (["sensor.ginko_etat_lignes","sensor.ginko_messages"].includes(id)) return false;
        const passages = s.attributes?.passages;
        return Array.isArray(passages) && passages.length > 0 && passages[0].latitude != null;
      })
      .map(([id, s]) => {
        const p0   = s.attributes.passages[0];
        const dist = _haversine(lat, lng, p0.latitude, p0.longitude);
        return { id, state: s, dist };
      })
      .sort((a, b) => a.dist - b.dist)
      .slice(0, this._config.max_stops);

    const personName = _capitalize(personEntity.attributes.friendly_name ?? this._config.person_entity);
    const lineNums   = [...new Set(ginkoSensors.flatMap(({ state }) =>
      (Array.isArray(state.attributes.passages) ? state.attributes.passages : [])
        .map(p => String(p.numLignePublic ?? p.idLigne ?? ""))
    ))].filter(Boolean);
    const alerts     = this._alerts(lineNums);
    const disrupted  = alerts.length > 0;

    if (ginkoSensors.length === 0) {
      return `<div class="gk-card">
        ${this._header(personName, personEntity.last_updated, ICON_PERSON)}
        <div class="gk-empty">Aucun capteur Ginko configuré ou aucun arrêt à proximité.</div>
      </div>`;
    }

    const stops = ginkoSensors.map(({ state, dist }) => {
      const passages = (Array.isArray(state.attributes.passages) ? state.attributes.passages : [])
        .slice(0, this._config.max_passages);
      const nom = _capitalize(state.attributes.nom_arret ?? state.attributes.friendly_name ?? "Arrêt");
      return this._renderStop({ nom, distance: dist, passages });
    }).join("");

    return `<div class="gk-card">
      ${this._header(personName, personEntity.last_updated, ICON_PERSON)}
      ${this._shouldShowTraffic(disrupted) && disrupted ? this._alertBanner(alerts) : ""}
      <div class="gk-prox-stops">${stops}</div>
    </div>`;
  }

  // ── Stop block (partagé proximity + person) ───────────────────────────────

  _renderStop(arret) {
    const allPassages = Array.isArray(arret.passages) ? arret.passages : [];
    const dist = arret.distance != null
      ? `<span class="gk-stop-dist">${Math.round(arret.distance)} m</span>` : "";
    // accessibiliteArret = accessibilité du quai physique (1 = accessible)
    const isPmr = allPassages.some(p => p.accessibiliteArret == 1)
      ? `<span class="gk-stop-pmr" title="Arrêt accessible PMR">${ICON_ACCESS}</span>` : "";

    // Grouper par ligne puis par destination — max_passages par sens
    const byLigne = new Map();
    for (const p of allPassages) {
      const k = p.idLigne ?? p.numLignePublic ?? "?";
      if (!byLigne.has(k)) byLigne.set(k, []);
      byLigne.get(k).push(p);
    }

    let rows = "";
    for (const lignePassages of byLigne.values()) {
      const byDest = new Map();
      for (const p of lignePassages) {
        const d = p.destination ?? "?";
        if (!byDest.has(d)) byDest.set(d, []);
        byDest.get(d).push(p);
      }
      for (const dPassages of byDest.values()) {
        const shown = dPassages.slice(0, this._config.max_passages);
        if (!shown.length) continue;
        const first = shown[0];
        const bg  = _color(first.couleurFond);
        const fg  = _color(first.couleurTexte);
        const gps = first.fiable === false
          ? `<span class="gk-approx">~</span>` : _iconWifi(bg);
        const times = shown.map(p => {
          if (p.typeDeTemps === 0) return `${String(p.temps ?? "").replace(" min","").trim()} min`;
          if (p.typeDeTemps === 2) return `<span class="gk-pill-disruption">${_esc(p.temps ?? "—")}</span>`;
          return _esc(p.temps ?? "—");
        }).join(" · ");
        rows += `<div class="gk-stop-row">
          <span class="gk-badge" style="background:${bg};color:${fg}">${_esc(first.numLignePublic ?? first.idLigne ?? "?")}</span>
          <span class="gk-stop-dest">${_esc(first.destination ?? "—")}</span>
          ${gps}
          <span class="gk-stop-time">${times}</span>
        </div>`;
      }
    }

    return `<div class="gk-stop">
      <div class="gk-stop-hd">
        <span class="gk-stop-name">${_esc(_capitalize(arret.nom ?? "Arrêt"))}</span>
        ${isPmr}
        ${dist}
      </div>
      ${rows || `<div class="gk-empty" style="padding:10px">Aucun passage.</div>`}
    </div>`;
  }

  // ── Shared ────────────────────────────────────────────────────────────────

  _alertBanner(alerts) {
    const rows = alerts.slice(0, 3).map(m => {
      let titre = m.titre ? _esc(m.titre) : "";
      if (!titre) {
        // Fallback : dépouiller le HTML du champ texte
        const raw = String(m.texte ?? m.message ?? "");
        titre = _esc(raw.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 120));
      }
      const badge = Array.isArray(m.lignes) && m.lignes.length
        ? `<span class="gk-alert-badge">${m.lignes.map(l => _esc(String(l))).join(" · ")}</span>`
        : "";
      return `<div class="gk-alert-row">${ICON_WARN}${badge}<span class="gk-alert-txt">${titre}</span></div>`;
    }).join("");
    const rest = alerts.length - 3;
    const more = rest > 0
      ? `<div class="gk-alert-more">+${rest} autre${rest > 1 ? "s" : ""} message${rest > 1 ? "s" : ""}</div>`
      : "";
    return `<div class="gk-alert">${rows}${more}</div>`;
  }

  _alerts(lineFilter = null) {
    const e = this._config.messages_entity ? this._hass.states[this._config.messages_entity] : null;
    const msgs = e?.attributes?.messages ?? [];
    if (!lineFilter || lineFilter.length === 0) return msgs;
    return msgs.filter(m => {
      const mLines = Array.isArray(m.lignes) ? m.lignes.map(String) : [];
      return mLines.some(l => lineFilter.includes(l));
    });
  }

  _shouldShowTraffic(disrupted) {
    const m = this._config.show_traffic;
    return m === "always" || (m === "if_disrupted" && disrupted);
  }

}

// ── Recherche card ────────────────────────────────────────────────────────────

const ICON_SEARCH = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></svg>`;
const ICON_CLEAR  = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>`;

const RECHERCHE_STYLES = `
  .gk-search-hd { padding:8px 10px; display:flex; align-items:center; gap:8px; border-bottom:0.5px solid var(--gk-border); }
  .gk-search-hd > svg { width:18px; height:18px; color:var(--gk-txt-3); flex-shrink:0; }
  .gk-search-in { flex:1; min-width:0; border:none; outline:none; background:transparent; color:var(--gk-txt); font:inherit; font-size:14px; padding:4px 0; }
  .gk-search-in::placeholder { color:var(--gk-txt-3); }
  .gk-search-clear { display:none; width:22px; height:22px; border:none; background:var(--gk-row-bg); border-radius:50%; color:var(--gk-txt-2); cursor:pointer; padding:4px; flex-shrink:0; }
  .gk-search-clear svg { width:100%; height:100%; display:block; }
  .gk-search-clear.on { display:block; }
  .gk-sugg { display:none; max-height:220px; overflow-y:auto; border-bottom:0.5px solid var(--gk-border); }
  .gk-sugg.on { display:block; }
  .gk-sugg-row { display:flex; align-items:center; gap:8px; padding:8px 12px; font-size:13px; color:var(--gk-txt); cursor:pointer; border-bottom:0.5px solid var(--gk-border); }
  .gk-sugg-row:last-child { border-bottom:none; }
  .gk-sugg-row:hover, .gk-sugg-row.hl { background:var(--gk-row-bg); }
  .gk-sugg-row svg { width:14px; height:14px; color:var(--gk-txt-3); flex-shrink:0; }
  .gk-sugg-name { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gk-sugg-meta { font-size:10px; color:var(--gk-txt-3); white-space:nowrap; }
  .gk-rs-title { padding:8px 12px 2px; display:flex; align-items:baseline; gap:8px; }
  .gk-rs-name { font-size:13px; font-weight:600; color:var(--gk-txt); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gk-rs-err { padding:12px 14px; font-size:12px; color:#dc2626; }
`;

class GinkoRechercheCard extends GinkoCard {
  static getConfigElement() { return document.createElement("ginko-recherche-card-editor"); }
  static getStubConfig() {
    return { nb_passages: 3, refresh: 30, show_traffic: "if_disrupted" };
  }

  constructor() {
    super();
    this._arret = "";
    this._data = null;
    this._loadedAt = null;
    this._error = "";
    this._loading = false;
    this._sugg = [];
    this._hl = -1;
    this._debounce = null;
    this._shellBuilt = false;
    this._restored = false;
  }

  setConfig(config) {
    this._config = {
      messages_entity: config.messages_entity ?? "",
      suivi_entities:  Array.isArray(config.suivi_entities) ? config.suivi_entities : [],
      nb_passages:     Math.min(5, Math.max(1, Number(config.nb_passages ?? 3))),
      refresh:         Math.min(300, Math.max(10, Number(config.refresh ?? 30))),
      show_traffic:    config.show_traffic ?? "if_disrupted",
      arret:           config.arret ?? "",
      placeholder:     config.placeholder ?? "Rechercher un arrêt…",
      remember:        config.remember ?? true,
      lignes_filtre:   [],
      max_passages:    5,
    };
    this._shellBuilt = false;
    this._restartTimer();
    if (this._hass) this._render();
  }

  connectedCallback()    { this._restartTimer(); }
  disconnectedCallback() { clearInterval(this._refreshTimer); this._refreshTimer = null; }
  getCardSize()          { return 4; }

  _restartTimer() {
    clearInterval(this._refreshTimer);
    const ms = (this._config?.refresh ?? 30) * 1000;
    this._refreshTimer = setInterval(() => {
      if (this._arret) this._loadHoraires();
      else this._renderResults();
    }, ms);
  }

  _storageKey() { return "ginko-recherche-last"; }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this._shellBuilt) this._buildShell();
    if (!this._restored) {
      this._restored = true;
      let initial = this._config.arret;
      if (!initial && this._config.remember) {
        try { initial = localStorage.getItem(this._storageKey()) || ""; } catch (e) { initial = ""; }
      }
      if (initial) this._select(initial, false);
    }
    this._renderResults();
  }

  _buildShell() {
    const isDark = this._hass?.themes?.darkMode ?? false;
    const darkBg = isDark ? `<style>.gk-card{background:#0f1729!important}</style>` : "";
    this.shadowRoot.innerHTML = `<style>${STYLES}${RECHERCHE_STYLES}</style>${darkBg}
    <div class="gk-card">
      <div class="gk-search-hd">
        ${ICON_SEARCH}
        <input class="gk-search-in" type="text" autocomplete="off" spellcheck="false"
               placeholder="${_esc(this._config.placeholder)}" value="${_esc(this._arret)}">
        <button class="gk-search-clear${this._arret ? " on" : ""}" title="Effacer">${ICON_CLEAR}</button>
      </div>
      <div class="gk-sugg"></div>
      <div class="gk-results"></div>
    </div>`;
    this._shellBuilt = true;

    const input = this.shadowRoot.querySelector(".gk-search-in");
    const clear = this.shadowRoot.querySelector(".gk-search-clear");
    const sugg  = this.shadowRoot.querySelector(".gk-sugg");

    input.addEventListener("input", () => {
      clear.classList.toggle("on", input.value.length > 0);
      clearTimeout(this._debounce);
      const q = input.value.trim();
      if (q.length < 2) { this._sugg = []; this._renderSugg(); return; }
      this._debounce = setTimeout(() => this._search(q), 300);
    });
    input.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { e.preventDefault(); this._hl = Math.min(this._sugg.length - 1, this._hl + 1); this._renderSugg(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); this._hl = Math.max(-1, this._hl - 1); this._renderSugg(); }
      else if (e.key === "Enter") {
        e.preventDefault();
        const pick = this._sugg[this._hl >= 0 ? this._hl : 0];
        if (pick) this._select(pick.nom);
        else if (input.value.trim()) this._select(input.value.trim());
      }
      else if (e.key === "Escape") { this._sugg = []; this._renderSugg(); }
    });
    input.addEventListener("focus", () => { if (this._sugg.length) sugg.classList.add("on"); });
    clear.addEventListener("click", () => {
      input.value = ""; clear.classList.remove("on");
      this._sugg = []; this._renderSugg();
      this._arret = ""; this._data = null; this._error = ""; this._loadedAt = null;
      try { if (this._config.remember) localStorage.removeItem(this._storageKey()); } catch (e) {}
      this._renderResults();
      input.focus();
    });
    sugg.addEventListener("click", e => {
      const row = e.target.closest(".gk-sugg-row");
      if (row?.dataset.nom) this._select(row.dataset.nom);
    });
  }

  async _callService(service, data) {
    const res = await this._hass.callWS({
      type: "call_service", domain: "ginko", service,
      service_data: data, return_response: true,
    });
    return res?.response ?? res;
  }

  async _search(q) {
    try {
      const resp = await this._callService("chercher_arret", { recherche: q, limite: 8 });
      const input = this.shadowRoot.querySelector(".gk-search-in");
      if (input && input.value.trim() !== q) return;
      this._sugg = Array.isArray(resp?.arrets) ? resp.arrets : [];
      this._hl = -1;
      this._renderSugg();
    } catch (err) {
      this._sugg = [];
      this._renderSugg();
      this._error = `Recherche impossible : ${err?.message ?? err}`;
      this._renderResults();
    }
  }

  _renderSugg() {
    const sugg = this.shadowRoot.querySelector(".gk-sugg");
    if (!sugg) return;
    if (!this._sugg.length) { sugg.classList.remove("on"); sugg.innerHTML = ""; return; }
    sugg.innerHTML = this._sugg.map((a, i) => {
      const meta = [
        a.quais > 1 ? `${a.quais} quais` : "",
        a.accessible ? "PMR" : "",
      ].filter(Boolean).join(" · ");
      return `<div class="gk-sugg-row${i === this._hl ? " hl" : ""}" data-nom="${_esc(a.nom)}">
        ${ICON_BUS}<span class="gk-sugg-name">${_esc(a.nom)}</span>
        ${meta ? `<span class="gk-sugg-meta">${_esc(meta)}</span>` : ""}
      </div>`;
    }).join("");
    sugg.classList.add("on");
  }

  _select(nom, persist = true) {
    this._arret = nom;
    this._sugg = []; this._hl = -1;
    this._renderSugg();
    const input = this.shadowRoot.querySelector(".gk-search-in");
    const clear = this.shadowRoot.querySelector(".gk-search-clear");
    if (input) { input.value = nom; input.blur(); }
    if (clear) clear.classList.add("on");
    if (persist && this._config.remember) {
      try { localStorage.setItem(this._storageKey(), nom); } catch (e) {}
    }
    this._data = null; this._error = ""; this._loadedAt = null;
    this._renderResults();
    this._loadHoraires();
  }

  async _loadHoraires() {
    if (!this._arret || this._loading || !this._hass) return;
    this._loading = true;
    const wanted = this._arret;
    try {
      const resp = await this._callService("get_horaires", { nom: wanted, nb: this._config.nb_passages });
      if (this._arret !== wanted) return;
      this._data = resp;
      this._error = "";
      this._loadedAt = new Date().toISOString();
    } catch (err) {
      if (this._arret !== wanted) return;
      this._error = `Horaires indisponibles : ${err?.message ?? err}`;
    } finally {
      this._loading = false;
      this._renderResults();
    }
  }

  _renderResults() {
    const box = this.shadowRoot.querySelector(".gk-results");
    if (!box) return;
    if (!this._arret) {
      box.innerHTML = `<div class="gk-empty">Tapez le nom d'un arrêt pour afficher ses prochains passages.</div>`;
      return;
    }
    if (this._error && !this._data) {
      box.innerHTML = `<div class="gk-rs-err">${_esc(this._error)}</div>`;
      return;
    }
    if (!this._data) {
      box.innerHTML = `<div class="gk-empty">Chargement des horaires…</div>`;
      return;
    }
    const all = Array.isArray(this._data.passages) ? this._data.passages : [];
    const nom = _capitalize(this._data.nom ?? this._arret);
    box.innerHTML = `
      <div class="gk-rs-title">
        <span class="gk-rs-name">${_esc(nom)}</span>
        <span class="gk-header-upd">màj ${_timeSince(this._loadedAt)}</span>
      </div>
      ${this._passagesInner(all)}`;
  }
}

// ── Etat card ─────────────────────────────────────────────────────────────────

// États officiels Ginko : 0 aucune info · 1 normal · 2 information ·
// 3 hors service (période) · 4 perturbation prévue · 5 perturbation en cours ·
// 6 circulation interrompue.
const ETAT_SEV = { 0:0, 1:0, 2:1, 3:1, 4:2, 5:3, 6:4 };
const ETAT_DOT = { 0:"#9e9e9e", 1:"#22c55e", 2:"#3b82f6", 3:"#9e9e9e", 4:"#9e9e9e", 5:"#f97316", 6:"#ef4444" };
const ETAT_COL = { 0:"#757575", 1:"#16a34a", 2:"#2563eb", 3:"#757575", 4:"#616161", 5:"#ea580c", 6:"#dc2626" };
// Une perturbation « en cours » (badge ⚠) = perturbation active ou ligne interrompue.
const _isDisrupted = (etat) => (etat ?? 1) >= 5;

const ICON_CHECK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>`;
const ICON_INFO  = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>`;

const ETAT_STYLES = `
  :host {
    --gk-bg:     var(--ha-card-background, var(--card-background-color));
    --gk-border: var(--divider-color, rgba(0,0,0,0.12));
    --gk-r-lg:   var(--ha-card-border-radius, 14px);
    --gk-r-md:   10px;
    --gk-r-sm:   6px;
    --gk-txt:    var(--primary-text-color);
    --gk-txt-2:  var(--secondary-text-color);
    --gk-txt-3:  var(--disabled-text-color);
    --gk-blue:   var(--info-color, #3b82f6);
    font-size: 14px; display: block;
  }
  @supports (color: color-mix(in srgb, red 50%, blue)) {
    :host { --gk-txt-3: color-mix(in srgb, var(--primary-text-color) 55%, transparent); }
  }
  * { box-sizing: border-box; }
  .gk-card { background:var(--gk-bg); border:0.5px solid var(--gk-border); border-radius:var(--gk-r-lg); overflow:hidden; font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif); box-shadow:var(--ha-card-box-shadow,none); }
  .gk-header { padding:10px 12px; display:flex; align-items:center; gap:8px; border-bottom:0.5px solid var(--gk-border); }
  .gk-header svg { width:18px; height:18px; flex-shrink:0; }
  .gk-header-title { font-size:13px; font-weight:600; color:var(--gk-txt); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gk-header-upd { font-size:10px; color:var(--gk-txt-3); white-space:nowrap; }
  /* Bannière tout normal */
  .gk-normal-banner { display:flex; align-items:center; gap:10px; padding:12px 14px; background:rgba(34,197,94,0.08); border-bottom:0.5px solid rgba(34,197,94,0.20); }
  .gk-normal-banner svg { width:20px; height:20px; color:#22c55e; flex-shrink:0; }
  .gk-normal-txt { font-size:13px; font-weight:600; color:#16a34a; }
  .gk-normal-sub { font-size:11px; color:var(--gk-txt-3); margin-top:1px; }
  /* Filtres */
  .gk-filters { padding:7px 10px; display:flex; flex-wrap:wrap; gap:5px; border-bottom:0.5px solid var(--gk-border); }
  .gk-chip { font-size:11px; font-weight:500; padding:3px 9px; border-radius:99px; border:0.5px solid var(--gk-border); background:transparent; color:var(--gk-txt-2); cursor:pointer; white-space:nowrap; font-family:inherit; display:inline-flex; align-items:center; gap:5px; }
  .gk-chip.active { color:var(--gk-txt); background:var(--secondary-background-color,rgba(128,128,128,0.12)); border-color:var(--gk-txt-3); font-weight:600; }
  .gk-chip-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; }
  /* Messages */
  .gk-section { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:var(--gk-txt-3); padding:8px 12px 4px; border-top:0.5px solid var(--gk-border); }
  .gk-section:first-of-type { border-top:none; }
  .gk-messages { padding:4px 10px 8px; display:flex; flex-direction:column; gap:6px; }
  .gk-msg { padding:8px 10px; border-radius:var(--gk-r-md); background:rgba(245,158,11,0.08); border:0.5px solid rgba(245,158,11,0.22); cursor:default; }
  .gk-msg-head { display:flex; align-items:flex-start; gap:8px; }
  .gk-msg-head svg { width:13px; height:13px; flex-shrink:0; margin-top:2px; color:#b45309; }
  .gk-msg-meta { flex:1; min-width:0; }
  .gk-msg-titre { font-size:12px; font-weight:600; color:var(--gk-txt); }
  .gk-msg-lignes { font-size:10px; color:var(--gk-txt-3); margin-top:2px; }
  .gk-msg-corps { font-size:11px; color:var(--gk-txt-2); margin-top:6px; line-height:1.5; }
  .gk-msg-corps p { margin:0 0 4px; }
  .gk-msg-corps strong { color:var(--gk-txt); }
  .gk-msg-corps a { color:var(--gk-blue,#3b82f6); }
  .gk-msg-corps.clamp { max-height:5em; overflow:hidden; position:relative; }
  .gk-msg-corps.clamp::after { content:""; position:absolute; bottom:0; left:0; right:0; height:2.2em; background:linear-gradient(transparent, var(--gk-bg,#fff)); pointer-events:none; }
  .gk-msg-toggle { font-size:10px; color:var(--gk-blue); margin-top:4px; cursor:pointer; user-select:none; }
  /* Lignes */
  .gk-lignes { padding:4px 10px 6px; }
  .gk-ligne-row { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:0.5px solid var(--gk-border); }
  .gk-ligne-row:last-child { border-bottom:none; }
  .gk-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
  .gk-badge { font-size:11px; font-weight:700; padding:2px 7px; border-radius:var(--gk-r-sm); line-height:1.4; white-space:nowrap; flex-shrink:0; }
  .gk-ligne-nom { flex:1; font-size:12px; color:var(--gk-txt-2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gk-etat-lbl { font-size:10px; font-weight:600; white-space:nowrap; padding:2px 6px; border-radius:4px; }
  /* Misc */
  .gk-empty { padding:16px 12px; font-size:13px; color:var(--gk-txt-3); text-align:center; }
`;

class GinkoEtatCard extends HTMLElement {
  static getConfigElement() { return document.createElement("ginko-etat-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.ginko_etat_lignes", messages_entity: "sensor.ginko_messages" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._filter = "disrupted";
    this._expandedMsgs = new Set();
    this._refreshTimer = null;
  }

  setConfig(config) {
    this._config = {
      entity:          config.entity ?? "sensor.ginko_etat_lignes",
      messages_entity: config.messages_entity ?? "",
    };
    if (this._hass) this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }
  connectedCallback()    { this._refreshTimer = setInterval(() => this._render(), 30000); }
  disconnectedCallback() { clearInterval(this._refreshTimer); }
  getCardSize()          { return 4; }

  _render() {
    if (!this._config || !this._hass) return;

    const etatEntity = this._hass.states[this._config.entity];
    if (!etatEntity) {
      this.shadowRoot.innerHTML = `<style>${ETAT_STYLES}</style><div class="gk-card"><div class="gk-empty">Entité introuvable : ${_esc(this._config.entity)}</div></div>`;
      return;
    }

    const lignes    = etatEntity.attributes?.lignes ?? [];
    const msgEntity = this._config.messages_entity ? this._hass.states[this._config.messages_entity] : null;
    const messages  = msgEntity?.attributes?.messages ?? [];
    const disrupted = lignes.filter(l => _isDisrupted(l.etat));
    const planned   = lignes.filter(l => (l.etat ?? 1) === 4);
    const infos     = lignes.filter(l => (l.etat ?? 1) === 2);
    const nbDisr    = disrupted.length;
    const nbPlan    = planned.length;
    const nbInfo    = infos.length;

    // Auto-switch vers "all" si le filtre actif n'a plus de contenu
    if (nbDisr === 0 && this._filter === "disrupted") this._filter = "all";
    if (nbPlan === 0 && this._filter === "planned") this._filter = "all";

    // Appliquer le filtre actif
    let shownLignes, shownMsgs;
    if (this._filter === "all") {
      // Perturbées d'abord (sévérité desc), puis alphabétique
      shownLignes = [...lignes].sort((a, b) => {
        const sa = ETAT_SEV[a.etat ?? 1] ?? 0;
        const sb = ETAT_SEV[b.etat ?? 1] ?? 0;
        if (sa !== sb) return sb - sa;
        return String(a.num ?? "").localeCompare(String(b.num ?? ""), "fr", { numeric: true });
      });
      shownMsgs = messages;
    } else if (this._filter === "disrupted") {
      shownLignes = disrupted;
      const nums  = new Set(disrupted.map(l => String(l.num ?? "")));
      shownMsgs   = messages.filter(m => (m.lignes ?? []).some(l => nums.has(String(l))));
    } else if (this._filter === "planned") {
      shownLignes = planned;
      const nums  = new Set(planned.map(l => String(l.num ?? "")));
      shownMsgs   = messages.filter(m => (m.lignes ?? []).some(l => nums.has(String(l))));
    } else {
      shownLignes = lignes.filter(l => String(l.num) === this._filter);
      shownMsgs   = messages.filter(m => (m.lignes ?? []).map(String).includes(this._filter));
    }

    // Chips : Perturbées / Prévues + puces individuelles uniquement si perturbations
    const chips = [{ k: "all", label: `Toutes (${lignes.length})` }];
    if (nbPlan > 0) {
      chips.unshift({ k: "planned", label: `Prévues (${nbPlan})`, dot: ETAT_DOT[4] });
    }
    if (nbDisr > 0) {
      chips.unshift({ k: "disrupted", label: `⚠ Perturbées (${nbDisr})` });
      // Point coloré selon l'état de la ligne (orange = en cours, rouge = interrompue)
      disrupted.slice(0, 8).forEach(l => chips.push({
        k: String(l.num ?? ""), label: String(l.num ?? "?"),
        dot: ETAT_DOT[l.etat ?? 1] ?? "#888",
      }));
    }
    const chipsHtml = chips.map(c =>
      `<button class="gk-chip${this._filter === c.k ? " active" : ""}" data-filter="${_esc(c.k)}">${
        c.dot ? `<span class="gk-chip-dot" style="background:${c.dot}"></span>` : ""
      }${_esc(c.label)}</button>`
    ).join("");

    // Bannière "tout normal"
    const normalSub = nbInfo > 0
      ? `${nbInfo} information${nbInfo > 1 ? "s" : ""} · ${lignes.length} lignes`
      : `${lignes.length} ligne${lignes.length > 1 ? "s" : ""} en service`;
    const normalBanner = nbDisr === 0
      ? `<div class="gk-normal-banner">${ICON_CHECK}
           <div>
             <div class="gk-normal-txt">${nbInfo > 0 ? "Aucune perturbation" : "Tout est normal"}</div>
             <div class="gk-normal-sub">${normalSub}</div>
           </div>
         </div>`
      : "";

    // Messages (affichés avant les lignes — info la plus utile)
    let msgsHtml = "";
    if (shownMsgs.length) {
      const items = shownMsgs.map((m, i) => {
        const ls = (Array.isArray(m.lignes) ? m.lignes : [])
          .map(l => _esc(String(l))).join(" · ");
        const corps = m.corps ?? m.texte ?? m.description ?? "";
        const expanded = this._expandedMsgs.has(i);
        const corpsHtml = corps
          ? `<div class="gk-msg-corps${expanded ? "" : " clamp"}">${_sanitizeHtml(corps)}</div>
             <div class="gk-msg-toggle" data-idx="${i}">${expanded ? "▲ Moins" : "▼ Voir plus"}</div>`
          : "";
        return `<div class="gk-msg">
          <div class="gk-msg-head">${ICON_WARN}
            <div class="gk-msg-meta">
              <div class="gk-msg-titre">${_esc(m.titre ?? "Perturbation")}</div>
              ${ls ? `<div class="gk-msg-lignes">${ls}</div>` : ""}
            </div>
          </div>
          ${corpsHtml}
        </div>`;
      }).join("");
      msgsHtml = `<div class="gk-section">Messages (${shownMsgs.length})</div><div class="gk-messages">${items}</div>`;
    }

    // Lignes
    const lignesHtml = shownLignes.length
      ? shownLignes.map(l => {
          const etat = l.etat ?? 1;
          const dot  = ETAT_DOT[etat] ?? "#888";
          const col  = ETAT_COL[etat] ?? "#888";
          const rgb  = _hexToRgb(dot);
          return `<div class="gk-ligne-row">
            <span class="gk-dot" style="background:${dot}"></span>
            <span class="gk-badge" style="background:rgba(${rgb},0.12);color:${dot};border:0.5px solid rgba(${rgb},0.30)">${_esc(String(l.num ?? "?"))}</span>
            <span class="gk-ligne-nom">${_esc(l.nom ?? "")}</span>
            ${etat > 1 ? `<span class="gk-etat-lbl" style="color:${col};background:rgba(${rgb},0.10)">${_esc(l.etat_label ?? "")}</span>` : ""}
          </div>`;
        }).join("")
      : `<div class="gk-empty">Aucune perturbation en cours.</div>`;

    // Couleur de l'icône header selon pire sévérité
    const worstEtat = disrupted.length
      ? Math.max(...disrupted.map(l => l.etat ?? 1))
      : 1;
    const headerIconColor = ETAT_DOT[worstEtat] ?? "#22c55e";

    this.shadowRoot.innerHTML = `<style>${ETAT_STYLES}</style>
    <div class="gk-card">
      <div class="gk-header">
        <span style="display:contents;color:${headerIconColor}">${ICON_INFO}</span>
        <span class="gk-header-title">${nbDisr > 0 ? `${nbDisr} perturbation${nbDisr > 1 ? "s" : ""} en cours` : "État du réseau"}</span>
        <span class="gk-header-upd">màj ${_timeSince(etatEntity.last_updated)}</span>
      </div>
      ${normalBanner}
      <div class="gk-filters">${chipsHtml}</div>
      ${msgsHtml}
      <div class="gk-lignes">${lignesHtml}</div>
    </div>`;

    // Chips
    this.shadowRoot.querySelectorAll(".gk-chip[data-filter]").forEach(el => {
      el.addEventListener("click", () => { this._filter = el.dataset.filter; this._render(); });
    });

    // Expand/collapse corps du message
    this.shadowRoot.querySelectorAll(".gk-msg-toggle[data-idx]").forEach(el => {
      el.addEventListener("click", () => {
        const i = parseInt(el.dataset.idx, 10);
        if (this._expandedMsgs.has(i)) this._expandedMsgs.delete(i);
        else this._expandedMsgs.add(i);
        this._render();
      });
    });
  }
}

// ── Suivi positions card ──────────────────────────────────────────────────────

const SUIVI_STYLES = `
  :host {
    --gk-bg:     var(--ha-card-background, var(--card-background-color));
    --gk-border: var(--divider-color, rgba(0,0,0,0.12));
    --gk-r-lg:   var(--ha-card-border-radius, 14px);
    --gk-r-md:   10px;
    --gk-r-sm:   6px;
    --gk-txt:    var(--primary-text-color);
    --gk-txt-2:  var(--secondary-text-color);
    --gk-txt-3:  var(--disabled-text-color);
    font-size: 14px; display: block;
  }
  * { box-sizing: border-box; }
  .gk-card { background:var(--gk-bg); border:0.5px solid var(--gk-border); border-radius:var(--gk-r-lg); overflow:hidden; font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif); box-shadow:var(--ha-card-box-shadow,none); }
  .gk-header { padding:10px 12px; display:flex; align-items:center; gap:8px; border-bottom:0.5px solid var(--gk-border); }
  .gk-header svg { width:18px; height:18px; color:var(--gk-txt-3); flex-shrink:0; }
  .gk-header-title { font-size:13px; font-weight:600; color:var(--gk-txt); flex:1; }
  .gk-header-sub { font-size:11px; color:var(--gk-txt-3); white-space:nowrap; }
  .gk-badge { font-size:11px; font-weight:700; padding:2px 7px; border-radius:var(--gk-r-sm); line-height:1.4; white-space:nowrap; flex-shrink:0; }
  /* Filtres sens */
  .gk-filters { padding:6px 10px; display:flex; gap:5px; border-bottom:0.5px solid var(--gk-border); }
  .gk-chip { font-size:11px; font-weight:500; padding:3px 9px; border-radius:99px; border:0.5px solid var(--gk-border); background:transparent; color:var(--gk-txt-2); cursor:pointer; white-space:nowrap; font-family:inherit; display:inline-flex; align-items:center; gap:5px; }
  .gk-chip.active { color:var(--gk-txt); background:var(--secondary-background-color,rgba(128,128,128,0.12)); border-color:var(--gk-txt-3); font-weight:600; }
  .gk-chip-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; }
  /* Bus rows */
  .gk-buses { padding:4px 10px 8px; display:flex; flex-direction:column; gap:4px; }
  .gk-bus { display:flex; align-items:center; gap:8px; padding:7px 8px; border-radius:var(--gk-r-md); background:var(--secondary-background-color, rgba(128,128,128,0.05)); }
  .gk-bus-arrow { font-size:13px; flex-shrink:0; }
  .gk-bus-pos { flex:1; min-width:0; }
  .gk-bus-terminus { font-size:10px; color:var(--gk-txt-3); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .gk-bus-location { font-size:12px; color:var(--gk-txt); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .gk-bus-location b { font-weight:600; }
  .gk-bus-quai { font-size:11px; color:var(--gk-txt-2); font-style:italic; }
  .gk-bus-time { font-size:14px; font-weight:700; color:var(--gk-txt); white-space:nowrap; font-variant-numeric:tabular-nums; flex-shrink:0; }
  .gk-bus-time-unit { font-size:10px; font-weight:400; color:var(--gk-txt-3); }
  /* Misc */
  .gk-empty { padding:20px 14px; font-size:13px; color:var(--gk-txt-3); text-align:center; }
  .gk-unavail { padding:14px; font-size:13px; color:var(--gk-txt-3); }
`;

const ICON_CLOCK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>`;


class GinkoSuiviCard extends HTMLElement {
  static getConfigElement() { return document.createElement("ginko-suivi-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.ginko_bus_ligne_7" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._filter = "all";
    this._refreshTimer = null;
  }

  setConfig(config) {
    this._config = { entity: config.entity ?? "" };
    if (this._hass) this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }
  connectedCallback()    { this._refreshTimer = setInterval(() => this._render(), 10000); }
  disconnectedCallback() { clearInterval(this._refreshTimer); }
  getCardSize()          { return 4; }

  _render() {
    if (!this._config || !this._hass) return;

    if (!this._config.entity) {
      this.shadowRoot.innerHTML = `<style>${SUIVI_STYLES}</style><div class="gk-card"><div class="gk-empty">Sélectionnez un capteur de suivi de ligne.</div></div>`;
      return;
    }

    const entity = this._hass.states[this._config.entity];
    if (!entity) {
      this.shadowRoot.innerHTML = `<style>${SUIVI_STYLES}</style><div class="gk-card"><div class="gk-unavail">Entité introuvable : ${_esc(this._config.entity)}</div></div>`;
      return;
    }

    const attrs    = entity.attributes ?? {};
    const numLigne = attrs.num_ligne ?? "?";
    const allBuses = Array.isArray(attrs.buses) ? attrs.buses : [];

    // Filtres disponibles
    const hasAller  = allBuses.some(b => b.sens === "aller");
    const hasRetour = allBuses.some(b => b.sens === "retour");

    let shown = allBuses;
    if (this._filter === "aller"  && hasAller)  shown = allBuses.filter(b => b.sens === "aller");
    if (this._filter === "retour" && hasRetour) shown = allBuses.filter(b => b.sens === "retour");

    // Chips
    const chips = [{ k: "all", label: `Tous (${allBuses.length})` }];
    if (hasAller)  chips.push({ k: "aller",  label: "→ Aller" });
    if (hasRetour) chips.push({ k: "retour", label: "← Retour" });
    const chipsHtml = chips.map(c =>
      `<button class="gk-chip${this._filter === c.k ? " active" : ""}" data-f="${_esc(c.k)}">${_esc(c.label)}</button>`
    ).join("");

    // Rows
    const busRows = shown.length ? shown.map(b => {
      const arrow   = b.sens === "aller" ? "→" : "←";
      const sec     = b.dans_sec ?? 0;
      const mins    = Math.floor(sec / 60);
      const timeHtml = sec === 0
        ? `<span class="gk-bus-time" style="color:#22c55e">À quai</span>`
        : mins < 1
          ? `<span class="gk-bus-time">&lt; 1<span class="gk-bus-time-unit"> min</span></span>`
          : `<span class="gk-bus-time">${mins}<span class="gk-bus-time-unit"> min</span></span>`;

      let locationHtml;
      if (b.statut === "a_quai") {
        locationHtml = `<div class="gk-bus-quai">À quai : ${_esc(b.prochain_arret ?? "")}</div>`;
      } else if (b.statut === "depart") {
        locationHtml = `<div class="gk-bus-location">Au départ de <b>${_esc(b.prochain_arret)}</b></div>`;
      } else {
        locationHtml = `<div class="gk-bus-location">${_esc(b.arret_precedent)} <b>→</b> ${_esc(b.prochain_arret)}</div>`;
      }

      return `<div class="gk-bus">
        <span class="gk-bus-arrow">${arrow}</span>
        <div class="gk-bus-pos">
          <div class="gk-bus-terminus">${_esc(b.terminus ?? "")}</div>
          ${locationHtml}
        </div>
        ${timeHtml}
      </div>`;
    }).join("")
    : `<div class="gk-empty">Aucun bus en circulation.</div>`;

    const nb = allBuses.length;
    const headerSub = `màj ${_timeSince(entity.last_updated)}`;

    this.shadowRoot.innerHTML = `<style>${SUIVI_STYLES}</style>
    <div class="gk-card">
      <div class="gk-header">${ICON_CLOCK}
        <span class="gk-header-title">Bus ligne ${_esc(numLigne)}&ensp;<span style="font-size:11px;font-weight:400;color:var(--gk-txt-3)">${nb} bus</span></span>
        <span class="gk-header-sub">${headerSub}</span>
      </div>
      ${chips.length > 1 ? `<div class="gk-filters">${chipsHtml}</div>` : ""}
      <div class="gk-buses">${busRows}</div>
    </div>`;

    this.shadowRoot.querySelectorAll(".gk-chip[data-f]").forEach(el => {
      el.addEventListener("click", () => { this._filter = el.dataset.f; this._render(); });
    });
  }
}

// ── Registration ──────────────────────────────────────────────────────────────

customElements.define("ginko-card", GinkoCard);
customElements.define("ginko-etat-card", GinkoEtatCard);
customElements.define("ginko-suivi-card", GinkoSuiviCard);
customElements.define("ginko-recherche-card", GinkoRechercheCard);

window.customCards = window.customCards ?? [];
window.customCards.push({
  type:        "ginko-recherche-card",
  name:        "Ginko Recherche d'arrêt",
  description: "Recherche dynamique d'un arrêt Ginko et affichage de ses prochains passages, sans capteur.",
  preview:     false,
});
window.customCards.push({
  type:        "ginko-card",
  name:        "Ginko Besançon",
  description: "Prochains passages du réseau Ginko (Besançon).",
  preview:     false,
});
window.customCards.push({
  type:        "ginko-etat-card",
  name:        "Ginko État du Réseau",
  description: "État des lignes et messages infotrafic du réseau Ginko.",
  preview:     false,
});
window.customCards.push({
  type:        "ginko-suivi-card",
  name:        "Ginko Positions Bus",
  description: "Positions en temps réel des bus d'une ligne Ginko.",
  preview:     false,
});

console.info(
  `%c GINKO-CARD %c v${VERSION} `,
  "color:#fff;background:#00A5C2;font-weight:700;padding:2px 4px;border-radius:3px 0 0 3px",
  "color:#00A5C2;background:#1c1c1e;font-weight:400;padding:2px 4px;border-radius:0 3px 3px 0",
);
