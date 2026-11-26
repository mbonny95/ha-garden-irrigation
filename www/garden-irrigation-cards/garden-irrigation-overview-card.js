/**
 * <garden-irrigation-overview-card>
 *
 * Whole-garden summary: yesterday's ET0 and rain, forecast rain (if
 * configured), weather data quality with a link to Repairs, and one row per
 * zone (status, recommended amount, deficit). Zones are discovered
 * automatically from the Garden Irrigation devices.
 *
 * Configuration:
 *   type: custom:garden-irrigation-overview-card
 *   title: Garden                     # optional
 */

import {
  BASE_CSS,
  classifyZoneStatus,
  deviceName,
  escapeHtml,
  findEntity,
  findZoneDevices,
  fireMoreInfo,
  formatMm,
  formatState,
  getState,
  icon,
  navigate,
  numericState,
  renderBadge,
  STATUS,
  texts,
} from "./garden-irrigation-cards-shared.js";
// Registers <garden-irrigation-overview-card-editor> as a side effect.
import "./garden-irrigation-overview-card-editor.js";

class GardenIrrigationOverviewCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("garden-irrigation-overview-card-editor");
  }

  static getStubConfig() {
    return { type: "custom:garden-irrigation-overview-card" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 2 + findZoneDevices(this._hass).length;
  }

  _render() {
    if (!this._config || !this._hass) return;
    const t = texts(this._hass);
    const zones = findZoneDevices(this._hass);

    this.shadowRoot.innerHTML = `
      <style>${BASE_CSS}${this._css()}</style>
      <div class="gi-card" part="card">
        <div class="gi-body">
          ${this._config.title ? `<h2 class="gi-title">${escapeHtml(this._config.title)}</h2>` : ""}
          ${this._renderWeather(t)}
          ${this._renderDataQuality(t)}
          ${
            zones.length
              ? `<ul class="gi-zones">${zones.map((id) => this._renderZone(t, id)).join("")}</ul>`
              : `<p class="gi-muted">${escapeHtml(t.no_zones)}</p>`
          }
        </div>
      </div>
    `;
    this._bindEvents();
  }

  _renderWeather(t) {
    const items = [
      ["et0_yesterday", t.et0_yesterday],
      ["rain_yesterday", t.rain_yesterday],
      ["forecast_rain", t.forecast],
    ]
      .map(([key, label]) => {
        const entityId = findEntity(this._hass, undefined, key);
        if (!entityId) return "";
        const value = numericState(getState(this._hass, entityId));
        return `
          <button type="button" class="gi-stat" data-entity="${escapeHtml(entityId)}">
            <span class="gi-small-note gi-muted">${escapeHtml(label)}</span>
            <span class="gi-tabular gi-stat-value">${escapeHtml(formatMm(value))}</span>
          </button>
        `;
      })
      .join("");
    return `<div class="gi-stats">${items}</div>`;
  }

  _renderDataQuality(t) {
    const entityId = findEntity(this._hass, undefined, "data_quality");
    const state = getState(this._hass, entityId);
    if (!state || state.state === "ok") return "";
    const repairs =
      state.state === "incomplete"
        ? `<button type="button" class="gi-link gi-repairs">${escapeHtml(t.open_repairs)}</button>`
        : "";
    return `
      <p class="gi-quality gi-warning-text">
        ${icon("alert-triangle", 14)}
        <span>${escapeHtml(`${t.data_quality}: ${formatState(this._hass, state)}`)}</span>
        ${repairs}
      </p>
    `;
  }

  _renderZone(t, deviceId) {
    const needsId = findEntity(this._hass, deviceId, "needs_irrigation");
    const status = classifyZoneStatus(getState(this._hass, needsId));
    const recommended = numericState(
      getState(this._hass, findEntity(this._hass, deviceId, "recommended_irrigation")),
    );
    const deficit = numericState(
      getState(this._hass, findEntity(this._hass, deviceId, "deficit")),
    );
    const detail =
      status === STATUS.NEEDS_WATER
        ? formatMm(recommended)
        : deficit !== null
          ? `${t.deficit} ${formatMm(deficit)}`
          : "";
    return `
      <li>
        <button type="button" class="gi-zone gi-tap-target" data-entity="${escapeHtml(
          findEntity(this._hass, deviceId, "recommended_irrigation") ?? needsId,
        )}">
          <span class="gi-zone-name">${escapeHtml(deviceName(this._hass, deviceId))}</span>
          ${renderBadge(status, t)}
          <span class="gi-tabular gi-zone-detail">${escapeHtml(detail)}</span>
          <span class="gi-muted" aria-hidden="true">${icon("chevron-right", 16)}</span>
        </button>
      </li>
    `;
  }

  _css() {
    return `
      .gi-body { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
      .gi-title { font-family: var(--gi-font-heading); font-size: 20px; margin: 0; font-weight: 400; }
      .gi-small-note { font-size: 12px; }
      .gi-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 8px; }
      .gi-stat {
        display: flex; flex-direction: column; align-items: flex-start; gap: 2px; padding: 8px 10px;
        border: none; border-radius: var(--gi-radius-sm); background: var(--gi-color-neutral-200);
        color: inherit; font: inherit; cursor: pointer; text-align: left;
      }
      .gi-stat-value { font-size: 18px; font-weight: 700; }
      .gi-quality { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; margin: 0; }
      .gi-link {
        background: none; border: none; padding: 0; color: inherit; font: inherit;
        text-decoration: underline; cursor: pointer;
      }
      .gi-zones { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
      .gi-zones li + li { border-top: 1px solid var(--gi-color-divider); }
      .gi-zone {
        width: 100%; display: grid; grid-template-columns: 1fr auto auto 16px; gap: 8px; align-items: center;
        background: none; border: none; padding: 8px 0; color: inherit; font: inherit; cursor: pointer; text-align: left;
      }
      .gi-zone-name { font-weight: 600; }
      .gi-zone-detail { font-size: 13px; }
      @container (max-width: 340px) {
        .gi-zone { grid-template-columns: 1fr 16px; }
        .gi-zone .gi-badge, .gi-zone-detail { grid-column: 1; }
      }
    `;
  }

  _bindEvents() {
    this.shadowRoot.querySelectorAll("[data-entity]").forEach((el) => {
      el.addEventListener("click", () => fireMoreInfo(this, el.dataset.entity));
    });
    this.shadowRoot.querySelector(".gi-repairs")?.addEventListener("click", () => {
      navigate(this, "/config/repairs");
    });
  }
}

customElements.define("garden-irrigation-overview-card", GardenIrrigationOverviewCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "garden-irrigation-overview-card",
  name: "Garden Irrigation - Overview",
  description: "Yesterday's weather, data quality and the status of every zone.",
  preview: true,
});
