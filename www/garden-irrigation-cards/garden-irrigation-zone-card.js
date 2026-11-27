/**
 * <garden-irrigation-zone-card>
 *
 * One Garden Irrigation zone: decision, recommended amount and minutes per
 * water source, deficit against RAW/TAW, reasons and warnings, and an
 * optional form to record an irrigation just done.
 *
 * Configuration:
 *   type: custom:garden-irrigation-zone-card
 *   device_id: <zone device>          # required
 *   name: Front lawn                  # optional, defaults to the device name
 *   show_record_form: true            # optional
 *
 * Entities are found on the zone device by translation_key, so they can be
 * renamed freely. The only write is the record_irrigation action, with the
 * duration typed by the user.
 */

import {
  BASE_CSS,
  DOMAIN,
  attr,
  classifyZoneStatus,
  clamp,
  deviceName,
  escapeHtml,
  findEntity,
  findZoneDevices,
  fireMoreInfo,
  formatLiters,
  formatMinutes,
  formatMm,
  formatState,
  getState,
  icon,
  isUnavailable,
  messageText,
  numericState,
  renderBadge,
  STATUS,
  texts,
} from "./garden-irrigation-cards-shared.js?v=2.0.1";
// The ?v= query busts the browser cache (HA serves /local for 31 days):
// keep it equal to the integration version. Registers <garden-irrigation-zone-card-editor> as a side effect.
import "./garden-irrigation-zone-card-editor.js?v=2.0.1";

const SOURCES = [
  { key: "mains", minutes: "recommended_minutes_mains", label: "minutes_mains" },
  { key: "tank", minutes: "recommended_minutes_tank", label: "minutes_tank" },
];

class GardenIrrigationZoneCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("garden-irrigation-zone-card-editor");
  }

  static getStubConfig(hass) {
    const [deviceId] = findZoneDevices(hass);
    return { type: "custom:garden-irrigation-zone-card", device_id: deviceId ?? "" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._disclosureOpen = false;
    this._form = { source: "mains", value: "", busy: false, message: "", error: false };
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = { show_record_form: true, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    // Do not redraw while the user is typing in the record form.
    if (this.shadowRoot.activeElement?.closest?.(".gi-record")) return;
    this._render();
  }

  get hass() {
    return this._hass;
  }

  getCardSize() {
    return this._config?.show_record_form ? 6 : 4;
  }

  _entity(key) {
    return findEntity(this._hass, this._config.device_id, key);
  }

  _state(key) {
    return getState(this._hass, this._entity(key));
  }

  // -- Rendering -----------------------------------------------------------

  _render() {
    if (!this._config || !this._hass) return;
    const t = texts(this._hass);

    if (!this._config.device_id || !this._entity("needs_irrigation")) {
      this.shadowRoot.innerHTML = `
        <style>${BASE_CSS}${this._css()}</style>
        <div class="gi-card"><div class="gi-body gi-muted">${escapeHtml(t.pick_zone)}</div></div>
      `;
      return;
    }

    const needs = this._state("needs_irrigation");
    const status = classifyZoneStatus(needs);
    const recommended = this._state("recommended_irrigation");

    this.shadowRoot.innerHTML = `
      <style>${BASE_CSS}${this._css()}</style>
      <div class="gi-card" part="card">
        <div class="gi-body">
          <div class="gi-header">
            <button type="button" class="gi-zone-name gi-tap-target">
              ${escapeHtml(this._config.name || deviceName(this._hass, this._config.device_id))}
            </button>
            ${renderBadge(status, t)}
          </div>
          ${this._renderHeadline(t, status, recommended)}
          ${status === STATUS.NEEDS_WATER ? this._renderSources(t) : ""}
          ${this._renderDeficit(t)}
          ${this._renderWarnings(t, recommended)}
          ${this._renderSoil(t)}
          ${this._renderDisclosure(t, needs)}
          ${this._renderFooter(t)}
          ${this._config.show_record_form ? this._renderRecordForm(t) : ""}
        </div>
      </div>
    `;
    this._bindEvents();
  }

  _renderHeadline(t, status, recommended) {
    if (status === STATUS.NO_DEFICIT) {
      const reasons = attr(this._state("needs_irrigation"), "reasons", []) ?? [];
      return reasons
        .map((reason) => `<p class="gi-small-note">${escapeHtml(messageText(t, reason))}</p>`)
        .join("");
    }
    if (status !== STATUS.NEEDS_WATER) return "";
    const mm = numericState(recommended);
    return `
      <div class="gi-headline">
        <span class="gi-headline-mm gi-tabular">${escapeHtml(formatMm(mm))}</span>
        <span class="gi-muted">${escapeHtml(formatLiters(attr(recommended, "liters", null)))}</span>
      </div>
      <p class="gi-muted gi-small-note">${escapeHtml(t.estimate_note)}</p>
    `;
  }

  _renderSources(t) {
    const rows = SOURCES.map((source) => {
      const state = this._state(source.minutes);
      if (!state) return "";
      const blocks = attr(state, "block_minutes", []) ?? [];
      const pause = attr(state, "block_pause_min", null);
      const plan =
        blocks.length > 1
          ? `${blocks.length} ${t.blocks} ${formatMinutes(blocks[0])} · ${t.pause} ${pause} min`
          : "";
      return `
        <div class="gi-source">
          <span>${escapeHtml(t[source.label])}</span>
          <span class="gi-tabular"><strong>${escapeHtml(formatMinutes(numericState(state)))}</strong></span>
          ${plan ? `<span class="gi-muted gi-small-note">${escapeHtml(plan)}</span>` : ""}
        </div>
      `;
    }).join("");
    return rows ? `<div class="gi-sources">${rows}</div>` : "";
  }

  _renderDeficit(t) {
    const deficit = numericState(this._state("deficit"));
    const raw = numericState(this._state("raw"));
    const taw = numericState(this._state("taw"));
    if (deficit === null || raw === null || taw === null || taw <= 0) return "";
    const deficitPct = clamp((deficit / taw) * 100, 0, 100);
    const rawPct = clamp((raw / taw) * 100, 0, 100);
    return `
      <div class="gi-deficit" role="img" aria-label="${escapeHtml(
        `${t.deficit} ${deficit.toFixed(1)} mm, RAW ${raw.toFixed(1)} mm, TAW ${taw.toFixed(1)} mm`,
      )}">
        <div class="gi-deficit-bar-track">
          <div class="gi-deficit-bar-fill" style="width:${deficitPct}%;"></div>
          <div class="gi-deficit-bar-tick" style="left:${rawPct}%;"></div>
        </div>
        <p class="gi-technical-row gi-tabular gi-muted">
          ${escapeHtml(t.deficit)} ${escapeHtml(formatMm(deficit))} ·
          RAW ${escapeHtml(formatMm(raw))} · TAW ${escapeHtml(formatMm(taw))}
        </p>
      </div>
    `;
  }

  _renderWarnings(t, recommended) {
    const warnings = attr(recommended, "warnings", []) ?? [];
    if (!warnings.length) return "";
    return `
      <ul class="gi-warnings">
        ${warnings
          .map(
            (warning) => `
              <li class="gi-warning-text">
                ${icon("alert-triangle", 14)}
                <span>${escapeHtml(messageText(t, warning))}</span>
              </li>`,
          )
          .join("")}
      </ul>
    `;
  }

  _renderSoil(t) {
    const soil = this._state("soil_moisture_status");
    if (!soil) return "";
    const value = attr(soil, "value_pct", null);
    const valueText = value === null || isUnavailable(soil) ? "" : ` · ${value}%`;
    return `
      <p class="gi-soil-row gi-muted">
        ${icon("droplet", 14)}
        <span>${escapeHtml(`${t.soil_sensor}: ${formatState(this._hass, soil)}${valueText}`)}</span>
      </p>
    `;
  }

  _renderDisclosure(t, needs) {
    const reasons = attr(needs, "reasons", []) ?? [];
    const etc = numericState(this._state("etc_yesterday"));
    const rain = numericState(this._state("effective_rain_yesterday"));
    const day = attr(this._state("etc_yesterday"), "date", null);
    const lastDay = day
      ? `<p class="gi-muted gi-small-note">${escapeHtml(
          `${t.last_day} ${day}: ${t.etc} ${formatMm(etc)} · ${t.effective_rain} ${formatMm(rain)}`,
        )}</p>`
      : "";
    return `
      <details class="gi-disclosure" ${this._disclosureOpen ? "open" : ""}>
        <summary class="gi-tap-target">${escapeHtml(t.why)}</summary>
        <div class="gi-disclosure-body">
          ${reasons.map((reason) => `<p class="gi-small-note">${escapeHtml(messageText(t, reason))}</p>`).join("")}
          ${lastDay}
        </div>
      </details>
    `;
  }

  _renderFooter(t) {
    const week = numericState(this._state("irrigation_7d"));
    const last = this._state("last_irrigation");
    const lastText = isUnavailable(last) ? t.never : formatState(this._hass, last);
    return `
      <p class="gi-footer gi-tabular gi-muted">
        ${escapeHtml(`${formatMm(week)} ${t.irrigation_7d} · ${t.last_irrigation}: ${lastText}`)}
      </p>
    `;
  }

  _renderRecordForm(t) {
    const form = this._form;
    const usesMinutes = Boolean(this._entity(SOURCES.find((s) => s.key === form.source).minutes));
    return `
      <form class="gi-record">
        <p class="gi-record-title">${escapeHtml(t.record)}</p>
        <div class="gi-record-row">
          <label>
            <span class="gi-small-note gi-muted">${escapeHtml(t.source)}</span>
            <select name="source">
              ${SOURCES.map(
                (s) =>
                  `<option value="${s.key}" ${s.key === form.source ? "selected" : ""}>${escapeHtml(t[s.label])}</option>`,
              ).join("")}
            </select>
          </label>
          <label>
            <span class="gi-small-note gi-muted">${escapeHtml(usesMinutes ? t.minutes : t.millimeters)}</span>
            <input name="value" type="number" inputmode="decimal" min="0.1" step="0.1" value="${escapeHtml(form.value)}" required />
          </label>
          <button type="submit" class="gi-button" ${form.busy ? "disabled" : ""}>${escapeHtml(t.save)}</button>
        </div>
        ${
          form.message
            ? `<p class="gi-small-note ${form.error ? "gi-warning-text" : "gi-muted"}" role="status">${escapeHtml(form.message)}</p>`
            : ""
        }
      </form>
    `;
  }

  async _record(t) {
    const value = Number(this._form.value);
    if (!Number.isFinite(value) || value <= 0) return;
    const source = SOURCES.find((s) => s.key === this._form.source);
    const field = this._entity(source.minutes) ? "minutes" : "mm";
    this._form = { ...this._form, busy: true, message: "", error: false };
    this._render();
    try {
      const result = await this._hass.callService(
        DOMAIN,
        "record_irrigation",
        { zone: this._config.device_id, source: source.key, [field]: value },
        undefined,
        false,
        true,
      );
      const mm = result?.response?.mm;
      this._form = {
        source: source.key,
        value: "",
        busy: false,
        error: false,
        message: `${t.recorded} ${formatMm(mm)}`,
      };
    } catch (err) {
      this._form = { ...this._form, busy: false, error: true, message: err?.message ?? String(err) };
    }
    this._render();
  }

  _css() {
    return `
      .gi-body { padding: 16px; display: flex; flex-direction: column; gap: 10px; }
      .gi-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
      .gi-zone-name {
        font-family: var(--gi-font-heading); font-size: 20px; line-height: 1.2;
        background: none; border: none; padding: 4px 0; color: inherit; cursor: pointer; text-align: left;
      }
      .gi-headline { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
      .gi-headline-mm { font-size: 28px; font-weight: 700; }
      .gi-small-note { font-size: 12px; margin: 0; }
      .gi-sources { display: flex; flex-direction: column; gap: 6px; }
      .gi-source {
        display: grid; grid-template-columns: 1fr auto; gap: 2px 8px; align-items: baseline;
        padding: 8px 10px; border-radius: var(--gi-radius-sm); background: var(--gi-color-neutral-200);
      }
      .gi-source .gi-small-note { grid-column: 1 / -1; }
      .gi-deficit-bar-track {
        position: relative; height: 8px; border-radius: 999px; background: var(--gi-color-neutral-200);
      }
      .gi-deficit-bar-fill {
        position: absolute; inset: 0 auto 0 0; border-radius: 999px; background: var(--gi-color-accent-2-600);
      }
      .gi-deficit-bar-tick {
        position: absolute; top: -2px; bottom: -2px; width: 2px; background: var(--gi-color-neutral-900);
      }
      .gi-technical-row, .gi-footer { font-size: 13px; margin: 6px 0 0; }
      .gi-warnings { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
      .gi-warnings li, .gi-soil-row { display: flex; align-items: flex-start; gap: 6px; font-size: 13px; margin: 0; }
      .gi-disclosure summary { cursor: pointer; font-size: 13px; font-weight: 600; list-style: none; }
      .gi-disclosure summary::-webkit-details-marker { display: none; }
      .gi-disclosure-body { padding-top: 4px; display: flex; flex-direction: column; gap: 6px; }
      .gi-record { border-top: 1px solid var(--gi-color-divider); padding-top: 10px; display: flex; flex-direction: column; gap: 6px; }
      .gi-record-title { margin: 0; font-size: 13px; font-weight: 600; }
      .gi-record-row { display: flex; gap: 8px; align-items: flex-end; flex-wrap: wrap; }
      .gi-record label { display: flex; flex-direction: column; gap: 2px; flex: 1 1 100px; }
      .gi-record select, .gi-record input {
        min-height: 44px; padding: 0 10px; border-radius: var(--gi-radius-sm);
        border: 1px solid var(--gi-color-divider); background: var(--gi-color-bg); color: inherit; font: inherit;
      }
      .gi-button {
        min-height: 44px; padding: 0 16px; border: none; border-radius: var(--gi-radius-sm);
        background: var(--gi-color-accent-600); color: #fff; font: inherit; font-weight: 600; cursor: pointer;
      }
      .gi-button[disabled] { opacity: 0.6; cursor: default; }
      @container (max-width: 340px) {
        .gi-header { flex-direction: column; align-items: flex-start; }
      }
    `;
  }

  // -- Events ----------------------------------------------------------------

  _bindEvents() {
    const t = texts(this._hass);
    this.shadowRoot.querySelector(".gi-zone-name")?.addEventListener("click", () => {
      fireMoreInfo(this, this._entity("recommended_irrigation"));
    });

    const details = this.shadowRoot.querySelector(".gi-disclosure");
    details?.addEventListener("toggle", () => {
      this._disclosureOpen = details.open;
    });

    const form = this.shadowRoot.querySelector(".gi-record");
    if (!form) return;
    form.querySelector("select")?.addEventListener("change", (event) => {
      this._form = { ...this._form, source: event.target.value, message: "" };
      this._render();
    });
    form.querySelector("input")?.addEventListener("input", (event) => {
      this._form.value = event.target.value;
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      this._record(t);
    });
  }
}

customElements.define("garden-irrigation-zone-card", GardenIrrigationZoneCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "garden-irrigation-zone-card",
  name: "Garden Irrigation - Zone",
  description: "FAO-56 irrigation recommendation for one zone, with irrigation recording.",
  preview: true,
});
