// custom_components/ginko/lovelace/ginko-card-editor.js

const EDITOR_STYLES = `
  :host { display: block; }
  .gk-editor { padding: 16px 0; font-size: 14px; color: var(--primary-text-color); }
  .gk-field { margin-bottom: 16px; }
  label { display: block; font-size: 12px; font-weight: 500; color: var(--secondary-text-color); margin-bottom: 5px; text-transform: uppercase; letter-spacing: .04em; }
  input[type="text"], input[type="number"], select {
    width: 100%; box-sizing: border-box; padding: 8px 10px; border-radius: 6px;
    border: 1px solid var(--divider-color, rgba(255,255,255,0.2));
    background: var(--secondary-background-color, #2c2c2e);
    color: var(--primary-text-color, #e5e5ea); font-size: 14px; outline: none;
  }
  input[type="text"]:focus, input[type="number"]:focus, select:focus { border-color: var(--primary-color, #03a9f4); }
  input[type="number"] { width: 80px; }
  .gk-hint { font-size: 11px; color: var(--disabled-text-color, rgba(255,255,255,0.38)); margin-top: 4px; line-height: 1.4; }
  .gk-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .gk-section { font-size: 11px; font-weight: 600; color: var(--disabled-text-color); text-transform: uppercase; letter-spacing: .06em; border-top: 1px solid var(--divider-color, rgba(255,255,255,0.1)); padding-top: 14px; margin: 18px 0 10px; }
  pre { font-family: monospace; font-size: 11px; color: var(--secondary-text-color); line-height: 1.8; background: var(--secondary-background-color, rgba(255,255,255,0.05)); padding: 10px 12px; border-radius: 8px; overflow-x: auto; margin: 0; white-space: pre; }
  .gk-suivi-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
  .gk-suivi-del { background: none; border: 1px solid var(--divider-color, rgba(255,255,255,0.2)); border-radius: 4px; color: var(--secondary-text-color); cursor: pointer; padding: 4px 8px; font-size: 12px; flex-shrink: 0; }
  .gk-checks { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
  .gk-check-label { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 99px; border: 1px solid var(--divider-color, rgba(255,255,255,0.2)); background: var(--secondary-background-color, rgba(255,255,255,0.05)); font-size: 12px; font-weight: 500; cursor: pointer; color: var(--primary-text-color); }
  .gk-check-label input { margin: 0; accent-color: var(--primary-color, #03a9f4); }
`;

// ── GinkoCardEditor ───────────────────────────────────────────────────────────

class GinkoCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass   = null;
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(h) {
    if (!this._hass) {
      this._hass = h;
      this._autoFill();
      this._render();
    } else {
      this._hass = h;
    }
  }

  // Pré-remplir les champs évidents dès que hass est disponible
  _autoFill() {
    if (!this._hass) return;
    const upd = { ...this._config };
    let changed = false;
    const cardMode = upd.mode ?? "lieu";

    if (!upd.messages_entity && this._hass.states["sensor.ginko_messages"]) {
      upd.messages_entity = "sensor.ginko_messages";
      changed = true;
    }
    if (!upd.entity) {
      const sensors = this._passageSensors(cardMode);
      if (sensors.length === 1) { upd.entity = sensors[0]; changed = true; }
    }
    if (!upd.suivi_entity) {
      const suivis = this._suiviSensors();
      if (suivis.length === 1) { upd.suivi_entity = suivis[0]; changed = true; }
    }
    if (changed) {
      this._config = upd;
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: upd }, bubbles: true, composed: true }));
    }
  }

  // Liste des capteurs de passages filtrés par ginko_mode
  _passageSensors(cardMode) {
    if (!this._hass) return [];
    return Object.keys(this._hass.states)
      .filter(id => {
        const s = this._hass.states[id];
        if (!id.startsWith("sensor.ginko_")) return false;
        const gm = s.attributes?.ginko_mode;
        if (!gm) return false; // ignorer les capteurs sans attribut (messages, etat…)
        if (!cardMode) return gm === "lieu" || gm === "liste" || gm === "proximity";
        return gm === cardMode;
      })
      .sort();
  }

  // Liste des capteurs de suivi de position (ginko_mode: "suivi")
  _suiviSensors() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states)
      .filter(id => {
        const s = this._hass.states[id];
        return id.startsWith("sensor.ginko_") && s.attributes?.ginko_mode === "suivi";
      })
      .sort();
  }

  // Extrait les lignes disponibles depuis les passages de l'entité courante
  _lignesDisponibles() {
    const entity = this._hass?.states[this._config?.entity ?? ""];
    const passages = entity?.attributes?.passages ?? [];
    const seen = new Map(); // numLignePublic → {label, mode}
    for (const p of passages) {
      const id = String(p.numLignePublic ?? p.idLigne ?? "");
      if (id && !seen.has(id)) {
        seen.set(id, { id, label: id, mode: p.modeTransport ?? 0 });
      }
    }
    // Trier : trams (mode=1) d'abord, puis bus, puis par label
    return [...seen.values()].sort((a, b) => {
      if (a.mode !== b.mode) return b.mode - a.mode; // tram=1 avant bus=0
      return a.label.localeCompare(b.label, undefined, { numeric: true });
    });
  }

  _render() {
    const cfg     = this._config;
    const mode    = cfg.mode ?? "lieu";
    const isProx  = mode === "proximity";
    const isLieu  = mode === "lieu";
    // Filtrer les capteurs selon le mode de la carte
    const ginkoMode = mode === "proximity" ? "proximity" : mode === "liste" ? "liste" : "lieu";
    const sensors = this._passageSensors(ginkoMode);
    const sensorOpts = sensors.map(id => `<option value="${this._esc(id)}">`).join("");
    const suivis     = this._suiviSensors();
    const suiviOpts  = suivis.map(id => `<option value="${this._esc(id)}">`).join("");
    const msgOpts    = this._hass?.states["sensor.ginko_messages"]
      ? `<option value="sensor.ginko_messages">`
      : "";

    this.shadowRoot.innerHTML = `<style>${EDITOR_STYLES}</style>
    <datalist id="gk-sensors">${sensorOpts}</datalist>
    <datalist id="gk-suivi-sensors">${suiviOpts}</datalist>
    <datalist id="gk-msg-sensors">${msgOpts}</datalist>
    <div class="gk-editor">

      <div class="gk-field">
        <label>Mode</label>
        <select id="mode">
          <option value="lieu"      ${mode === "lieu"      ? "selected" : ""}>Arrêt fixe — toutes lignes</option>
          <option value="liste"     ${mode === "liste"     ? "selected" : ""}>Ligne spécifique</option>
          <option value="proximity" ${mode === "proximity" ? "selected" : ""}>Arrêts à proximité</option>
        </select>
      </div>

      <div class="gk-field">
        <label>Entité capteur Ginko</label>
        <input id="entity" type="text" list="gk-sensors"
          value="${this._esc(cfg.entity ?? "")}"
          placeholder="${isProx ? "sensor.ginko_arrets_proches" : "sensor.ginko_..."}">
        <div class="gk-hint">${
          sensors.length > 0
            ? `${sensors.length} capteur(s) compatible(s) avec ce mode — cliquez dans le champ pour les suggestions.`
            : `Aucun capteur de type « ${ginkoMode} » trouvé. Créez d'abord une entrée Ginko correspondante.`
        }</div>
      </div>

      <div class="gk-field">
        <label>Entité messages infotrafic <span style="font-weight:400;text-transform:none">(optionnel)</span></label>
        <input id="messages_entity" type="text" list="gk-msg-sensors"
          value="${this._esc(cfg.messages_entity ?? "")}" placeholder="sensor.ginko_messages">
        <div class="gk-hint">Bandeau perturbation si des messages sont actifs.</div>
      </div>

      <div class="gk-field">
        <label>Position des bus <span style="font-weight:400;text-transform:none">(optionnel)</span></label>
        ${(() => {
          const suiviList = Array.isArray(cfg.suivi_entities)
            ? cfg.suivi_entities
            : (cfg.suivi_entity ? [cfg.suivi_entity] : []);
          const rows = [...suiviList, ""].map((val, i) => {
            const isLast = i === suiviList.length;
            return `<div class="gk-suivi-row">
              <input class="gk-suivi-input" type="text" list="gk-suivi-sensors"
                data-idx="${i}" value="${this._esc(val)}"
                placeholder="sensor.ginko_bus_ligne_t1"
                style="flex:1">
              ${!isLast ? `<button class="gk-suivi-del" data-idx="${i}" title="Supprimer">✕</button>` : ""}
            </div>`;
          }).join("");
          return rows;
        })()}
        <div class="gk-hint">Une ligne par capteur de suivi. Ajouter un capteur par ligne desservant cet arrêt.</div>
      </div>


      <div class="gk-row-2">
        <div class="gk-field">
          <label>Passages</label>
          <input id="max_passages" type="number" min="1" max="5" value="${cfg.max_passages ?? 3}">
          <div class="gk-hint">1 à 5</div>
        </div>
        ${isProx
          ? `<div class="gk-field"><label>Arrêts proches</label><input id="max_stops" type="number" min="1" max="5" value="${cfg.max_stops ?? 3}"><div class="gk-hint">1 à 5</div></div>`
          : "<div></div>"
        }
      </div>

      ${isLieu ? (() => {
        const lignes = this._lignesDisponibles();
        const filtre = cfg.lignes_filtre ?? [];
        if (!lignes.length) return `
          <div class="gk-section">Filtrer les lignes</div>
          <div class="gk-field">
            <div class="gk-hint">⚠ Aucune ligne détectée. Les lignes apparaissent ici une fois l'entité sélectionnée et en service. Les lignes inactives (dimanche, après ~21h) ne sont pas disponibles.</div>
          </div>`;
        const icoTram = `<svg style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:3px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 1.5L12 3.8l3.5-2.3"/><path d="M12 3.8V5"/><rect x="5" y="5" width="14" height="12.5" rx="2.4"/><path d="M5 11h14"/><circle cx="8.3" cy="14.4" r=".9" fill="currentColor" stroke="none"/><circle cx="15.7" cy="14.4" r=".9" fill="currentColor" stroke="none"/><path d="M9.5 17.5L8 21M14.5 17.5L16 21"/><path d="M5.5 21h13"/></svg>`;
        const icoBus  = `<svg style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:3px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17.5V5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v12a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5Z"/><path d="M4 11.5h16"/><path d="M12 3v8.5"/><circle cx="7.6" cy="15.2" r=".9" fill="currentColor" stroke="none"/><circle cx="16.4" cy="15.2" r=".9" fill="currentColor" stroke="none"/><path d="M6.2 19v1.2a.9.9 0 0 1-.9.9h-.4a.9.9 0 0 1-.9-.9V19"/><path d="M20 19v1.2a.9.9 0 0 1-.9.9h-.4a.9.9 0 0 1-.9-.9V19"/></svg>`;
        const boxes = lignes.map(l => {
          const checked = filtre.length === 0 || filtre.includes(l.id) ? "checked" : "";
          const ico = l.mode === 1 ? icoTram : icoBus;
          return `<label class="gk-check-label"><input type="checkbox" class="gk-ligne-cb" data-id="${this._esc(l.id)}" ${checked}>${ico}${this._esc(l.label)}</label>`;
        }).join("");
        return `
          <div class="gk-section">Filtrer les lignes</div>
          <div class="gk-field">
            <div class="gk-checks">${boxes}</div>
            <div class="gk-hint">⚠ Liste limitée aux lignes en service actuellement. Les lignes inactives (dimanche, après ~21h) n'apparaissent pas ici.</div>
          </div>`;
      })() : ""}

      <div class="gk-section">Présentation</div>
      <div class="gk-field">
        <label>Infotrafic</label>
        <select id="show_traffic">
          <option value="if_disrupted" ${(cfg.show_traffic ?? "if_disrupted") === "if_disrupted" ? "selected" : ""}>Si perturbation</option>
          <option value="always"       ${cfg.show_traffic === "always" ? "selected" : ""}>Toujours</option>
          <option value="never"        ${cfg.show_traffic === "never"  ? "selected" : ""}>Jamais</option>
        </select>
      </div>

      <div class="gk-section">Aperçu YAML</div>
      <pre id="yaml-preview">${this._yaml()}</pre>
    </div>`;

    this._listen();
  }

  _listen() {
    const bind = (id, key, fn) => {
      const el = this.shadowRoot.querySelector(`#${id}`);
      if (!el) return;
      el.addEventListener("change", e => this._update(key, fn ? fn(e.target.value) : e.target.value));
    };
    bind("mode",            "mode");
    bind("entity",          "entity");
    bind("messages_entity", "messages_entity");
    bind("show_traffic",    "show_traffic");
    bind("max_passages",     "max_passages", v => Math.min(5, Math.max(1, parseInt(v) || 3)));
    bind("max_stops",        "max_stops",    v => Math.min(5, Math.max(1, parseInt(v) || 3)));

    // Inputs suivi_entities
    const _getSuiviList = () => {
      const inputs = [...this.shadowRoot.querySelectorAll(".gk-suivi-input")];
      return inputs.map(i => i.value.trim()).filter(v => v !== "");
    };
    this.shadowRoot.querySelectorAll(".gk-suivi-input").forEach(inp => {
      inp.addEventListener("change", () => this._update("suivi_entities", _getSuiviList()));
    });
    this.shadowRoot.querySelectorAll(".gk-suivi-del").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.idx);
        const list = _getSuiviList();
        list.splice(idx, 1);
        this._update("suivi_entities", list);
        this._render();
      });
    });

    // Checkboxes lignes
    this.shadowRoot.querySelectorAll(".gk-ligne-cb").forEach(cb => {
      cb.addEventListener("change", () => {
        const all = [...this.shadowRoot.querySelectorAll(".gk-ligne-cb")];
        const checked = all.filter(c => c.checked).map(c => c.dataset.id);
        // Si tout est coché = pas de filtre (tableau vide)
        const filtre = checked.length === all.length ? [] : checked;
        this._update("lignes_filtre", filtre.length ? filtre : undefined);
      });
    });
  }

  _update(key, value) {
    const cfg = { ...this._config };
    if (value === "" || value == null || (Array.isArray(value) && value.length === 0)) delete cfg[key]; else cfg[key] = value;
    this._config = cfg;
    const pre = this.shadowRoot.querySelector("#yaml-preview");
    if (pre) pre.textContent = this._yaml();
    if (key === "mode") this._render();
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg }, bubbles: true, composed: true }));
  }

  _yaml() {
    const c = this._config;
    const filtre = Array.isArray(c.lignes_filtre) && c.lignes_filtre.length ? c.lignes_filtre : null;
    return [
      `type: custom:ginko-card`,
      `mode: ${c.mode ?? "lieu"}`,
      c.entity          ? `entity: ${c.entity}`                   : null,
      c.messages_entity ? `messages_entity: ${c.messages_entity}` : null,
      (() => {
        const list = Array.isArray(c.suivi_entities) && c.suivi_entities.length ? c.suivi_entities
                   : c.suivi_entity ? [c.suivi_entity] : [];
        if (!list.length) return null;
        if (list.length === 1) return `suivi_entity: ${list[0]}`;
        return `suivi_entities:\n${list.map(e => `  - ${e}`).join("\n")}`;
      })(),
      filtre            ? `lignes_filtre:\n${filtre.map(l => `  - "${l}"`).join("\n")}` : null,
      `max_passages: ${c.max_passages ?? 3}`,
      c.mode === "proximity" ? `max_stops: ${c.max_stops ?? 3}` : null,
      `show_traffic: ${c.show_traffic ?? "if_disrupted"}`,
    ].filter(Boolean).join("\n");
  }

  _esc(s) { return String(s).replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
}

customElements.define("ginko-card-editor", GinkoCardEditor);

// ── GinkoEtatCardEditor ───────────────────────────────────────────────────────

class GinkoEtatCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass   = null;
  }

  setConfig(config) { this._config = { ...config }; this._render(); }

  set hass(h) {
    if (!this._hass) {
      this._hass = h;
      this._autoFill();
      this._render();
    } else {
      this._hass = h;
    }
  }

  _autoFill() {
    if (!this._hass) return;
    const upd = { ...this._config };
    let changed = false;
    if (!upd.entity && this._hass.states["sensor.ginko_etat_lignes"]) {
      upd.entity = "sensor.ginko_etat_lignes"; changed = true;
    }
    if (!upd.messages_entity && this._hass.states["sensor.ginko_messages"]) {
      upd.messages_entity = "sensor.ginko_messages"; changed = true;
    }
    if (changed) {
      this._config = upd;
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: upd }, bubbles: true, composed: true }));
    }
  }

  _render() {
    const cfg = this._config;
    this.shadowRoot.innerHTML = `<style>${EDITOR_STYLES}</style>
    <div class="gk-editor">

      <div class="gk-field">
        <label>Entité état des lignes</label>
        <input id="entity" type="text"
          value="${this._esc(cfg.entity ?? "sensor.ginko_etat_lignes")}"
          placeholder="sensor.ginko_etat_lignes">
        <div class="gk-hint">Créée automatiquement par l'intégration Ginko.</div>
      </div>

      <div class="gk-field">
        <label>Entité messages infotrafic <span style="font-weight:400;text-transform:none">(optionnel)</span></label>
        <input id="messages_entity" type="text"
          value="${this._esc(cfg.messages_entity ?? "sensor.ginko_messages")}"
          placeholder="sensor.ginko_messages">
      </div>

      <div class="gk-section">Aperçu YAML</div>
      <pre>${this._yaml()}</pre>
    </div>`;

    const bind = (id, key) => {
      const el = this.shadowRoot.querySelector(`#${id}`);
      if (!el) return;
      el.addEventListener("change", e => {
        const cfg = { ...this._config };
        const v = e.target.value;
        if (v === "" || v == null) delete cfg[key]; else cfg[key] = v;
        this._config = cfg;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg }, bubbles: true, composed: true }));
      });
    };
    bind("entity",          "entity");
    bind("messages_entity", "messages_entity");
  }

  _yaml() {
    const c = this._config;
    return [
      `type: custom:ginko-etat-card`,
      `entity: ${c.entity ?? "sensor.ginko_etat_lignes"}`,
      c.messages_entity ? `messages_entity: ${c.messages_entity}` : null,
    ].filter(Boolean).join("\n");
  }

  _esc(s) { return String(s).replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
}

customElements.define("ginko-etat-card-editor", GinkoEtatCardEditor);

// ── GinkoSuiviCardEditor ──────────────────────────────────────────────────────

class GinkoSuiviCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass   = null;
  }

  setConfig(config) { this._config = { ...config }; this._render(); }

  set hass(h) {
    if (!this._hass) {
      this._hass = h;
      this._autoFill();
      this._render();
    } else {
      this._hass = h;
    }
  }

  _autoFill() {
    if (!this._hass) return;
    const upd = { ...this._config };
    if (!upd.entity) {
      const sensors = this._suiviSensors();
      if (sensors.length === 1) { upd.entity = sensors[0]; }
    }
    if (upd.entity !== this._config.entity) {
      this._config = upd;
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: upd }, bubbles: true, composed: true }));
    }
  }

  _suiviSensors() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states)
      .filter(id => {
        const s = this._hass.states[id];
        return id.startsWith("sensor.ginko_bus_") ||
          (id.startsWith("sensor.ginko_") && s.attributes?.buses !== undefined);
      })
      .sort();
  }

  _render() {
    const cfg     = this._config;
    const sensors = this._suiviSensors();
    const opts    = sensors.map(id => `<option value="${this._esc(id)}">`).join("");

    this.shadowRoot.innerHTML = `<style>${EDITOR_STYLES}</style>
    <datalist id="gk-suivi-sensors">${opts}</datalist>
    <div class="gk-editor">
      <div class="gk-field">
        <label>Entité capteur de suivi</label>
        <input id="entity" type="text" list="gk-suivi-sensors"
          value="${this._esc(cfg.entity ?? "")}" placeholder="sensor.ginko_bus_ligne_7">
        <div class="gk-hint">${
          sensors.length > 0
            ? `${sensors.length} capteur(s) de suivi disponible(s).`
            : "Créez une entrée mode « Positions des bus » dans l'intégration Ginko."
        }</div>
      </div>
      <div class="gk-section">Aperçu YAML</div>
      <pre>${this._yaml()}</pre>
    </div>`;

    const el = this.shadowRoot.querySelector("#entity");
    if (el) el.addEventListener("change", e => {
      const c = { ...this._config };
      const v = e.target.value;
      if (v) c.entity = v; else delete c.entity;
      this._config = c;
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: c }, bubbles: true, composed: true }));
    });
  }

  _yaml() {
    const c = this._config;
    return [`type: custom:ginko-suivi-card`, c.entity ? `entity: ${c.entity}` : null]
      .filter(Boolean).join("\n");
  }

  _esc(s) { return String(s).replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
}

customElements.define("ginko-suivi-card-editor", GinkoSuiviCardEditor);

// ── GinkoRechercheCardEditor ──────────────────────────────────────────────────

class GinkoRechercheCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass   = null;
  }

  setConfig(config) { this._config = { ...config }; this._render(); }

  set hass(h) {
    if (!this._hass) {
      this._hass = h;
      this._autoFill();
      this._render();
    } else {
      this._hass = h;
    }
  }

  _autoFill() {
    if (!this._hass) return;
    if (!this._config.messages_entity && this._hass.states["sensor.ginko_messages"]) {
      const upd = { ...this._config, messages_entity: "sensor.ginko_messages" };
      this._config = upd;
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: upd }, bubbles: true, composed: true }));
    }
  }

  _render() {
    const cfg = this._config;
    const sel = (v, cur) => v === cur ? "selected" : "";
    const traffic = cfg.show_traffic ?? "if_disrupted";
    this.shadowRoot.innerHTML = `<style>${EDITOR_STYLES}</style>
    <div class="gk-editor">

      <div class="gk-field">
        <label>Arrêt prédéfini <span style="font-weight:400;text-transform:none">(optionnel)</span></label>
        <input id="arret" type="text" value="${this._esc(cfg.arret ?? "")}" placeholder="ex. Gare Viotte">
        <div class="gk-hint">Laissez vide pour laisser l'utilisateur chercher l'arrêt de son choix.</div>
      </div>

      <div class="gk-field">
        <label>Passages par ligne et direction</label>
        <input id="nb_passages" type="number" min="1" max="5" value="${Number(cfg.nb_passages ?? 3)}">
      </div>

      <div class="gk-field">
        <label>Rafraîchissement (secondes)</label>
        <input id="refresh" type="number" min="10" max="300" step="5" value="${Number(cfg.refresh ?? 30)}">
        <div class="gk-hint">Les horaires ne sont interrogés que lorsqu'un arrêt est affiché.</div>
      </div>

      <div class="gk-field">
        <label>Bandeau infotrafic</label>
        <select id="show_traffic">
          <option value="if_disrupted" ${sel("if_disrupted", traffic)}>Si perturbation</option>
          <option value="always" ${sel("always", traffic)}>Toujours</option>
          <option value="never" ${sel("never", traffic)}>Jamais</option>
        </select>
      </div>

      <div class="gk-field">
        <label>Entité messages infotrafic <span style="font-weight:400;text-transform:none">(optionnel)</span></label>
        <input id="messages_entity" type="text" value="${this._esc(cfg.messages_entity ?? "")}" placeholder="sensor.ginko_messages">
      </div>

      <div class="gk-field">
        <label class="gk-check-label"><input id="remember" type="checkbox" ${(cfg.remember ?? true) ? "checked" : ""}> Mémoriser le dernier arrêt consulté (navigateur)</label>
      </div>

      <div class="gk-section">Aperçu YAML</div>
      <pre>${this._yaml()}</pre>
    </div>`;

    const emit = (cfg) => {
      this._config = cfg;
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg }, bubbles: true, composed: true }));
      const pre = this.shadowRoot.querySelector("pre");
      if (pre) pre.textContent = this._yaml();
    };
    const bindText = (id, key, numeric = false) => {
      const el = this.shadowRoot.querySelector(`#${id}`);
      if (!el) return;
      el.addEventListener("change", e => {
        const cfg = { ...this._config };
        const v = e.target.value;
        if (v === "" || v == null) delete cfg[key];
        else cfg[key] = numeric ? Number(v) : v;
        emit(cfg);
      });
    };
    bindText("arret",           "arret");
    bindText("nb_passages",     "nb_passages", true);
    bindText("refresh",         "refresh", true);
    bindText("show_traffic",    "show_traffic");
    bindText("messages_entity", "messages_entity");
    const rem = this.shadowRoot.querySelector("#remember");
    if (rem) rem.addEventListener("change", e => {
      const cfg = { ...this._config };
      if (e.target.checked) delete cfg.remember; else cfg.remember = false;
      emit(cfg);
    });
  }

  _yaml() {
    const c = this._config;
    return [
      `type: custom:ginko-recherche-card`,
      c.arret ? `arret: ${c.arret}` : null,
      c.nb_passages != null ? `nb_passages: ${c.nb_passages}` : null,
      c.refresh != null ? `refresh: ${c.refresh}` : null,
      c.show_traffic ? `show_traffic: ${c.show_traffic}` : null,
      c.messages_entity ? `messages_entity: ${c.messages_entity}` : null,
      c.remember === false ? `remember: false` : null,
    ].filter(Boolean).join("\n");
  }

  _esc(s) { return String(s).replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
}

customElements.define("ginko-recherche-card-editor", GinkoRechercheCardEditor);
