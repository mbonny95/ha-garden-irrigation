/**
 * <garden-irrigation-overview-card>
 *
 * Read-only whole-garden summary: mode chip, ET0/data-quality status strip,
 * and one navigable row per zone. See
 * design_handoff_garden_irrigation_cards/README.md §3/§5 (rows 14-16) for the
 * authoritative spec; this folder's own README documents the gaps found
 * against the real backend (custom_components/garden_irrigation).
 */

import {
  BASE_CSS,
  attr,
  classifyZoneStatus,
  escapeHtml,
  fireMoreInfo,
  formatMm,
  getState,
  icon,
  isUnavailable,
  navigate,
  numericState,
  renderBadge,
  statusLabel,
  statusTone,
} from "./garden-irrigation-cards-shared.js";
// Registers <garden-irrigation-overview-card-editor> as a side effect - see
// the identical comment in garden-irrigation-zone-card.js.
import "./garden-irrigation-overview-card-editor.js";

const REQUIRED_FIELDS = ["mode_entity", "data_quality_entity", "et0_entity", "zones"];

const MODE_LABEL = {
  monitoring: "Monitoring",
  calibration: "Calibration",
};

/**
 * Today's backend only ever emits "initializing"/"not_configured" for
 * data_quality (see const.py DATA_QUALITY_STATES) - both are normal startup
 * placeholders, not failures, so this banner condition is effectively
 * dormant except for genuine entity unavailability. See this folder's
 * README, "Data-quality / Repairs banner" for the full explanation and what
 * a future backend milestone would need to add for this to do more.
 */
function isDataQualityDegraded(state) {
  return isUnavailable(state);
}

class GardenIrrigationOverviewCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("garden-irrigation-overview-card-editor");
  }

  static getStubConfig(hass) {
    const entityIds = Object.keys(hass?.states ?? {});
    const modeEntity = entityIds.find((id) => id.startsWith("select.") && id.includes("mode"));
    const dataQualityEntity = entityIds.find(
      (id) => id.startsWith("sensor.") && id.includes("data_quality"),
    );
    const et0Entity = entityIds.find(
      (id) => id.startsWith("sensor.") && id.includes("et0_daily"),
    );
    const inProgressEntity = entityIds.find(
      (id) => id.startsWith("binary_sensor.") && id.includes("irrigation_in_progress"),
    );
    const needsIrrigationEntities = entityIds.filter(
      (id) => id.startsWith("binary_sensor.") && id.includes("needs_irrigation"),
    );

    return {
      type: "custom:garden-irrigation-overview-card",
      mode_entity: modeEntity ?? "",
      data_quality_entity: dataQualityEntity ?? "",
      et0_entity: et0Entity ?? "",
      in_progress_entity: inProgressEntity ?? "",
      zones: needsIrrigationEntities.slice(0, 2).map((id, index) => ({
        zone: `zone_${index + 1}`,
        name: `Zone ${index + 1}`,
        needs_irrigation_entity: id,
      })),
    };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    for (const field of REQUIRED_FIELDS) {
      if (!config[field]) throw new Error(`Missing required field: ${field}`);
    }
    if (!Array.isArray(config.zones) || config.zones.length === 0) {
      throw new Error("Missing required field: zones");
    }
    for (const zone of config.zones) {
      if (!zone.zone || !zone.needs_irrigation_entity) {
        throw new Error("Each zones[] entry needs zone and needs_irrigation_entity");
      }
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  get hass() {
    return this._hass;
  }

  getCardSize() {
    return 4;
  }

  connectedCallback() {
    this._render();
  }

  _render() {
    if (!this._config || !this._hass) return;

    const inProgressState = this._config.in_progress_entity
      ? getState(this._hass, this._config.in_progress_entity)
      : null;
    const dataQualityState = getState(this._hass, this._config.data_quality_entity);
    const et0State = getState(this._hass, this._config.et0_entity);
    const modeState = getState(this._hass, this._config.mode_entity);

    this.shadowRoot.innerHTML = `
      <style>${BASE_CSS}${this._css()}</style>
      <div class="gi-card" part="card">
        <div class="gi-body">
          ${this._renderBanner(inProgressState, dataQualityState)}
          ${this._renderHeader(modeState)}
          ${this._renderStatusStrip(et0State, dataQualityState)}
          <div class="gi-zone-rows">
            ${this._config.zones.map((zoneConfig) => this._renderZoneRow(zoneConfig)).join("")}
          </div>
        </div>
      </div>
    `;

    this._bindEvents();
  }

  _renderBanner(inProgressState, dataQualityState) {
    if (inProgressState?.state === "on") {
      const zone = attr(inProgressState, "zone", null);
      const elapsed = attr(inProgressState, "elapsed_minutes", null);
      const elapsedText =
        elapsed === null || elapsed === undefined ? "" : ` · ${Math.round(elapsed)} min elapsed`;
      return `
        <div class="gi-banner gi-banner-info" role="status">
          <span>Cycle running${zone ? ` (${escapeHtml(zone)})` : ""}${escapeHtml(elapsedText)}</span>
        </div>
      `;
    }
    if (isDataQualityDegraded(dataQualityState)) {
      return `
        <button type="button" class="gi-banner gi-banner-warning gi-repairs-banner">
          ${icon("alert-triangle", 16)}
          <span>Data quality needs attention - open Repairs</span>
        </button>
      `;
    }
    return "";
  }

  _renderHeader(modeState) {
    const mode = modeState?.state ?? null;
    const modeLabel = MODE_LABEL[mode] ?? "Unknown";
    return `
      <div class="gi-header">
        <h2 class="gi-title">Garden Irrigation</h2>
        <span class="gi-mode-chip gi-chip">${escapeHtml(modeLabel)}</span>
      </div>
    `;
  }

  _renderStatusStrip(et0State, dataQualityState) {
    const et0 = numericState(et0State);
    const et0Text = et0 === null ? "—" : `${et0.toFixed(1)} mm`;
    const dataQualityText = dataQualityState?.attributes?.friendly_name
      ? (dataQualityState.state ?? "—")
      : "—";
    return `
      <p class="gi-status-strip gi-muted gi-tabular">
        ET0 today: ${escapeHtml(et0Text)} (in progress) · Data: ${escapeHtml(dataQualityText)}
      </p>
    `;
  }

  _renderZoneRow(zoneConfig) {
    const needsState = getState(this._hass, zoneConfig.needs_irrigation_entity);
    const { status } = classifyZoneStatus(needsState);
    const tone = statusTone(status);
    const label = statusLabel(status);
    const recommendedMm =
      attr(needsState, "ready", null) === true ? attr(needsState, "recommended_mm", null) : null;
    const mmText = formatMm(recommendedMm);
    const name = zoneConfig.name || zoneConfig.zone;

    return `
      <button
        type="button"
        class="gi-zone-row gi-tap-target"
        data-zone="${escapeHtml(zoneConfig.zone)}"
        aria-label="${escapeHtml(`${name}: ${label}, ${mmText === "—" ? "not available" : mmText + " recommended"}`)}"
      >
        <span class="gi-zone-dot" style="background:${tone.dot};" aria-hidden="true"></span>
        <span class="gi-zone-name">${escapeHtml(name)}</span>
        <span class="gi-zone-chip gi-chip" style="background:${tone.bg};color:${tone.fg};">${escapeHtml(label)}</span>
        <span class="gi-zone-mm gi-tabular">${escapeHtml(mmText)}</span>
        <span class="gi-zone-chevron" aria-hidden="true">${icon("chevron-right", 18)}</span>
      </button>
    `;
  }

  _css() {
    return `
      .gi-body { padding: 16px; display: flex; flex-direction: column; gap: 10px; }
      .gi-banner {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        margin: -16px -16px 0 -16px;
        font-size: 13px;
        font-weight: 600;
        border: none;
        width: calc(100% + 32px);
        text-align: left;
        font-family: inherit;
        cursor: default;
      }
      .gi-banner-info {
        background: var(--gi-color-accent-100);
        color: var(--gi-color-accent-700);
      }
      .gi-banner-warning {
        background: var(--gi-color-neutral-200);
        color: var(--gi-color-accent-800);
        cursor: pointer;
      }
      .gi-repairs-banner { min-height: 44px; }
      .gi-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }
      .gi-title {
        font-family: var(--gi-font-heading);
        font-size: 20px;
        margin: 0;
        font-weight: normal;
      }
      .gi-mode-chip { font-size: 12px; }
      .gi-status-strip { font-size: 13px; margin: 0; }
      .gi-zone-rows { display: flex; flex-direction: column; gap: 8px; }
      .gi-zone-row {
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
        min-height: 44px;
        padding: 8px 10px;
        border: 1px solid var(--gi-color-divider);
        border-radius: var(--gi-radius-sm);
        background: var(--gi-color-bg);
        color: inherit;
        font-family: inherit;
        cursor: pointer;
        text-align: left;
      }
      .gi-zone-dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
      .gi-zone-name { flex: 1 1 auto; font-size: 14px; font-weight: 600; }
      .gi-zone-chip { font-size: 11px; flex: none; }
      .gi-zone-mm { font-size: 13px; flex: none; }
      .gi-zone-chevron { flex: none; display: flex; }
    `;
  }

  _bindEvents() {
    const banner = this.shadowRoot.querySelector(".gi-repairs-banner");
    banner?.addEventListener("click", () => navigate(this, "/config/repairs"));

    const rows = this.shadowRoot.querySelectorAll(".gi-zone-row");
    rows.forEach((row) => {
      row.addEventListener("click", () => {
        const zoneId = row.dataset.zone;
        const zoneConfig = this._config.zones.find((zone) => zone.zone === zoneId);
        if (zoneConfig?.navigate_to) {
          navigate(this, zoneConfig.navigate_to);
        } else {
          fireMoreInfo(this, zoneConfig?.needs_irrigation_entity);
        }
      });
    });
  }
}

customElements.define("garden-irrigation-overview-card", GardenIrrigationOverviewCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "garden-irrigation-overview-card",
  name: "Garden Irrigation - Overview Card",
  description: "Read-only whole-garden irrigation status summary.",
  preview: true,
});
