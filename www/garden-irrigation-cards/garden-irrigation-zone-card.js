/**
 * <garden-irrigation-zone-card>
 *
 * Read-only decision-support card for one garden_irrigation zone. Implements
 * the anatomy/state-matrix in design_handoff_garden_irrigation_cards/README.md
 * §3/§5. See that document for the authoritative spec; comments below only
 * cover implementation decisions and the gaps found against the real backend
 * (custom_components/garden_irrigation) - flagged inline and summarized in
 * this folder's own README.
 *
 * No entity is ever written to. The only interactive affordances are:
 *   - zone name tap -> more-info on needs_irrigation_entity
 *   - final/preview segmented control -> local render-only toggle
 *   - disclosure -> local expand/collapse
 *   - (in-progress banner, if configured) no interaction
 */

import {
  BASE_CSS,
  attr,
  classifyZoneStatus,
  clamp,
  escapeHtml,
  fireMoreInfo,
  formatLiters,
  formatMm,
  getState,
  icon,
  isUnavailable,
  numericState,
  renderBadge,
  STATUS,
} from "./garden-irrigation-cards-shared.js";
// Registers <garden-irrigation-zone-card-editor> as a side effect. Only the
// two main card files need to be added as Lovelace resources - the editor
// (referenced below via getConfigElement's document.createElement) has no
// other way to get its own customElements.define() executed by the browser.
import "./garden-irrigation-zone-card-editor.js";

const REQUIRED_FIELDS = [
  "zone",
  "needs_irrigation_entity",
  "deficit_entity",
  "raw_entity",
  "taw_entity",
  "irrigation_7d_entity",
  "weekly_cap_entity",
];

/** `zone_1` -> `Zone 1`; last-resort label when `name` isn't configured and
 * no reliable name attribute exists on the backend entities today (see
 * this folder's README, "Zone name derivation"). */
function prettifyZoneId(zoneId) {
  return String(zoneId)
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/** Best-effort sibling-entity derivation for getStubConfig: garden_irrigation
 * entity_ids share every segment except the "key" (needs_irrigation/deficit/
 * raw/taw/irrigation_7d/weekly_cap_reached) - see the unique_id pattern in
 * sensor.py/binary_sensor.py (`{entry_id}_{key}_{zone_id}`), which HA's own
 * entity_id slugification carries through predictably. This is a client-side
 * convenience heuristic only, not a documented backend contract - if it
 * doesn't match (e.g. a customized entity_id), the user edits the stub YAML. */
function deriveSiblingEntityId(needsIrrigationEntityId, fromKey, toDomain, toKey) {
  const [, objectId] = needsIrrigationEntityId.split(".");
  if (!objectId || !objectId.includes(fromKey)) return null;
  return `${toDomain}.${objectId.replace(fromKey, toKey)}`;
}

class GardenIrrigationZoneCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("garden-irrigation-zone-card-editor");
  }

  static getStubConfig(hass) {
    const entityIds = Object.keys(hass?.states ?? {});
    const needsIrrigationId = entityIds.find(
      (id) => id.startsWith("binary_sensor.") && id.includes("needs_irrigation"),
    );
    if (!needsIrrigationId) {
      return {
        type: "custom:garden-irrigation-zone-card",
        zone: "zone_1",
        needs_irrigation_entity: "",
        deficit_entity: "",
        raw_entity: "",
        taw_entity: "",
        irrigation_7d_entity: "",
        weekly_cap_entity: "",
      };
    }
    return {
      type: "custom:garden-irrigation-zone-card",
      zone: "zone_1",
      needs_irrigation_entity: needsIrrigationId,
      deficit_entity:
        deriveSiblingEntityId(needsIrrigationId, "needs_irrigation", "sensor", "deficit") ??
        "",
      raw_entity:
        deriveSiblingEntityId(needsIrrigationId, "needs_irrigation", "sensor", "raw") ?? "",
      taw_entity:
        deriveSiblingEntityId(needsIrrigationId, "needs_irrigation", "sensor", "taw") ?? "",
      irrigation_7d_entity:
        deriveSiblingEntityId(
          needsIrrigationId,
          "needs_irrigation",
          "sensor",
          "irrigation_7d",
        ) ?? "",
      weekly_cap_entity:
        deriveSiblingEntityId(
          needsIrrigationId,
          "needs_irrigation",
          "binary_sensor",
          "weekly_cap_reached",
        ) ?? "",
    };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._variant = "final";
    this._disclosureOpen = false;
    this._hass = null;
    this._config = null;
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    for (const field of REQUIRED_FIELDS) {
      if (!config[field]) throw new Error(`Missing required field: ${field}`);
    }
    if (config.default_variant && !["final", "preview"].includes(config.default_variant)) {
      throw new Error("default_variant must be 'final' or 'preview'");
    }
    this._config = {
      show_technical_row: true,
      show_wh51: true,
      default_variant: "final",
      ...config,
    };
    this._variant = this._config.default_variant;
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
    return this._disclosureOpen ? 4 : 3;
  }

  connectedCallback() {
    this._render();
  }

  // -- Rendering -----------------------------------------------------------

  _zoneName() {
    return this._config.name || prettifyZoneId(this._config.zone);
  }

  /** Auto-discovered fallback for the in-progress banner when
   * `in_progress_entity` isn't configured - see this folder's README,
   * "Zone card in-progress banner wiring". */
  _resolveInProgressEntity() {
    if (this._config.in_progress_entity) {
      return getState(this._hass, this._config.in_progress_entity);
    }
    const states = this._hass?.states ?? {};
    for (const id of Object.keys(states)) {
      if (!id.startsWith("binary_sensor.")) continue;
      const state = states[id];
      if (state?.attributes?.device_class === "running" && "zone" in (state.attributes ?? {})) {
        return state;
      }
    }
    return null;
  }

  _render() {
    if (!this._config || !this._hass) return;

    const needsState = getState(this._hass, this._config.needs_irrigation_entity);
    const { status, reasonText } = classifyZoneStatus(needsState);
    const ready = attr(needsState, "ready", null) === true;
    const previewNeedsIrrigation = attr(needsState, "preview_needs_irrigation", null);
    const finalNeedsIrrigation = needsState?.state === "on";
    const differs =
      ready &&
      previewNeedsIrrigation !== null &&
      previewNeedsIrrigation !== finalNeedsIrrigation;

    const inProgressState = this._resolveInProgressEntity();
    const inProgressOn =
      inProgressState?.state === "on" &&
      String(attr(inProgressState, "zone", "")) === String(this._config.zone);

    this.shadowRoot.innerHTML = `
      <style>${BASE_CSS}${this._css()}</style>
      <div class="gi-card" part="card">
        ${inProgressOn ? this._renderInProgressBanner(inProgressState) : ""}
        <div class="gi-body">
          ${this._renderHeader()}
          <div class="gi-badge-row">${renderBadge(status)}</div>
          ${this._renderHeadline(needsState, status)}
          ${this._variant === "final" && ready ? this._renderDeficitBar(needsState) : ""}
          ${
            this._config.show_technical_row
              ? this._renderTechnicalRow(status, ready, reasonText)
              : ""
          }
          ${differs ? this._renderDiffersNote(previewNeedsIrrigation) : ""}
          ${this._config.show_wh51 ? this._renderSoilRow(needsState) : ""}
          ${this._renderDisclosure(needsState, ready)}
          ${this._renderFooter()}
        </div>
      </div>
    `;

    this._bindEvents();
  }

  _renderInProgressBanner(inProgressState) {
    const elapsed = attr(inProgressState, "elapsed_minutes", null);
    const elapsedText =
      elapsed === null || elapsed === undefined ? "" : ` · ${Math.round(elapsed)} min elapsed`;
    return `
      <div class="gi-banner" role="status">
        <span>Cycle running${escapeHtml(elapsedText)}</span>
      </div>
    `;
  }

  _renderHeader() {
    return `
      <div class="gi-header">
        <button type="button" class="gi-zone-name gi-tap-target" part="zone-name">
          ${escapeHtml(this._zoneName())}
        </button>
        <div
          class="gi-segmented"
          role="radiogroup"
          aria-label="Recommendation variant"
        >
          <label class="gi-segment ${this._variant === "final" ? "is-active" : ""}">
            <input type="radio" name="gi-variant" value="final" ${
              this._variant === "final" ? "checked" : ""
            } />
            <span>Final</span>
          </label>
          <label class="gi-segment ${this._variant === "preview" ? "is-active" : ""}">
            <input type="radio" name="gi-variant" value="preview" ${
              this._variant === "preview" ? "checked" : ""
            } />
            <span>Preview</span>
          </label>
        </div>
      </div>
    `;
  }

  _renderHeadline(needsState, status) {
    const recommendedMm =
      this._variant === "final" ? attr(needsState, "recommended_mm", null) : null;
    const mmText =
      status === STATUS.DATA_UNAVAILABLE || status === STATUS.NOT_FINALIZED
        ? "—"
        : this._variant === "preview"
          ? "—"
          : formatMm(recommendedMm);

    // Row 2 (cap-partial): secondary line is "of {deficit_mm} mm deficit",
    // not liters - deficit_mm IS available (deficit_entity), unlike
    // estimated_liters, which is never exposed on any entity today (backend
    // gap - see this folder's README) and is never computed client-side
    // from mm x a guessed area.
    const limitsApplied = attr(needsState, "limits_applied", []) ?? [];
    const isCapPartial = this._variant === "final" && limitsApplied.includes("weekly_cap_partial");
    let secondaryText;
    if (isCapPartial) {
      const deficitState = getState(this._hass, this._config.deficit_entity);
      const deficit = numericState(deficitState);
      secondaryText = `of ${formatMm(deficit)} deficit`;
    } else {
      secondaryText = formatLiters(null);
    }

    return `
      <div class="gi-headline">
        <span class="gi-headline-mm gi-tabular" aria-label="${escapeHtml(
          mmText === "—" ? "not available" : `${mmText} recommended`,
        )}">${escapeHtml(mmText)}</span>
        <span class="gi-headline-liters gi-muted">${escapeHtml(secondaryText)}</span>
      </div>
      ${
        this._variant === "preview"
          ? '<p class="gi-muted gi-small-note">Preview recommendation isn\'t exposed by the backend yet - only whether it agrees with today\'s final decision (see the note below, when it differs).</p>'
          : ""
      }
    `;
  }

  _renderDeficitBar(needsState) {
    const deficitState = getState(this._hass, this._config.deficit_entity);
    const rawState = getState(this._hass, this._config.raw_entity);
    const tawState = getState(this._hass, this._config.taw_entity);
    const deficit = numericState(deficitState);
    const raw = numericState(rawState);
    const taw = numericState(tawState);
    if (deficit === null || raw === null || taw === null || taw <= 0) return "";

    const deficitPct = clamp((deficit / taw) * 100, 0, 100);
    const rawPct = clamp((raw / taw) * 100, 0, 100);

    return `
      <div
        class="gi-deficit-bar"
        role="img"
        aria-label="${escapeHtml(
          `Deficit ${deficit.toFixed(1)} of ${taw.toFixed(1)} millimeters total available water, threshold at ${raw.toFixed(1)} millimeters`,
        )}"
      >
        <div class="gi-deficit-bar-track">
          <div class="gi-deficit-bar-fill" style="width:${deficitPct}%;"></div>
          <div class="gi-deficit-bar-tick" style="left:${rawPct}%;"></div>
        </div>
      </div>
    `;
  }

  _renderTechnicalRow(status, ready, reasonText) {
    const rawState = getState(this._hass, this._config.raw_entity);
    const tawState = getState(this._hass, this._config.taw_entity);
    const raw = numericState(rawState);
    const taw = numericState(tawState);

    let deficitText;
    let deficitSuffix = "";
    if (this._variant === "preview") {
      // Preview's projected deficit is never exposed on any entity today
      // (see this folder's README) - never approximated from the final one.
      deficitText = "—";
      deficitSuffix = " (preview not exposed by backend)";
    } else if (status === STATUS.DATA_UNAVAILABLE) {
      // Row 7: show the reason, never a stale number alongside it.
      deficitText = reasonText ?? "Data unavailable";
    } else if (!ready) {
      // Row 6 (pending): still-valid stale figure, clearly labeled as such -
      // this is the one case where a "prior" number is intentional, not
      // invented.
      const deficitState = getState(this._hass, this._config.deficit_entity);
      deficitText = formatMm(numericState(deficitState));
      deficitSuffix = " (as of yesterday)";
    } else {
      const deficitState = getState(this._hass, this._config.deficit_entity);
      deficitText = formatMm(numericState(deficitState));
    }

    return `
      <p class="gi-technical-row gi-tabular gi-muted">
        Deficit ${escapeHtml(deficitText)}${escapeHtml(deficitSuffix)} · RAW ${escapeHtml(
          formatMm(raw),
        )} · TAW ${escapeHtml(formatMm(taw))}
      </p>
    `;
  }

  _renderDiffersNote(previewNeedsIrrigation) {
    const variantLabel = this._variant === "final" ? "final" : "preview";
    const text =
      previewNeedsIrrigation === true
        ? "Tonight's preview currently suggests irrigation may be needed, unlike today's finalized recommendation."
        : "Tonight's preview currently suggests irrigation may not be needed, unlike today's finalized recommendation.";
    return `<p class="gi-differs-note gi-warning-text" data-variant="${variantLabel}">${escapeHtml(text)}</p>`;
  }

  _renderSoilRow(needsState) {
    if (isUnavailable(needsState)) return "";
    const wh51Status = attr(needsState, "wh51_status", "unavailable");
    const wh51Calibrated = attr(needsState, "wh51_calibrated", false);
    const warnings = attr(needsState, "warnings", []) ?? [];
    const contradicts = warnings.includes("wh51_contradicts");

    if (wh51Status === "unavailable") {
      return `<p class="gi-soil-row gi-muted">Soil sensor offline</p>`;
    }
    // The handoff's row 8 wants "Calibrating (day N/14)" - the day count
    // needs the calibration start timestamp, which recommendation.py keeps
    // internally (_Wh51CalibrationState.first_seen) but never serializes
    // onto any entity attribute (a further gap beyond README §6's list).
    // Never fabricated/estimated client-side - shown without a day count.
    let text;
    if (!wh51Calibrated) {
      text = "Calibrating soil sensor (baseline in progress)";
    } else {
      text = `Soil sensor: ${wh51Status}`;
    }
    return `
      <p class="gi-soil-row ${contradicts ? "gi-warning-text" : "gi-muted"}">
        ${icon("droplet", 14)}
        <span>${escapeHtml(text)}</span>
      </p>
    `;
  }

  _renderDisclosure(needsState, ready) {
    const reasons = this._variant === "final" ? attr(needsState, "reasons", []) ?? [] : [];
    const limitsApplied =
      this._variant === "final" ? attr(needsState, "limits_applied", []) ?? [] : [];
    const warnings = this._variant === "final" ? attr(needsState, "warnings", []) ?? [] : [];
    const allTags = [...reasons, ...limitsApplied, ...warnings];

    const tagsMarkup = allTags.length
      ? allTags.map((tag) => `<span class="gi-chip">${escapeHtml(tag)}</span>`).join(" ")
      : `<span class="gi-muted">${
          this._variant === "preview"
            ? "Not available for the preview variant."
            : "No reasons/limits recorded."
        }</span>`;

    return `
      <details class="gi-disclosure" ${this._disclosureOpen ? "open" : ""}>
        <summary class="gi-tap-target">Why this recommendation</summary>
        <div class="gi-disclosure-body">
          <div class="gi-tag-row">${tagsMarkup}</div>
          <p class="gi-muted gi-small-note">
            Per-source minutes/block plan aren't exposed by the backend yet - see this
            card's README.
          </p>
        </div>
      </details>
    `;
  }

  _renderFooter() {
    const irrigationState = getState(this._hass, this._config.irrigation_7d_entity);
    const weeklyCapState = getState(this._hass, this._config.weekly_cap_entity);
    const irrigation7d = numericState(irrigationState);
    const capMm =
      attr(irrigationState, "cap_mm", null) ?? attr(weeklyCapState, "weekly_cap_mm", null);
    return `
      <p class="gi-footer gi-tabular gi-muted">
        ${escapeHtml(formatMm(irrigation7d))} / ${escapeHtml(formatMm(capMm))} this week
      </p>
    `;
  }

  _css() {
    return `
      .gi-body { padding: 16px; display: flex; flex-direction: column; gap: 10px; }
      .gi-banner {
        background: var(--gi-color-accent-100);
        color: var(--gi-color-accent-700);
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
      }
      .gi-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
      }
      .gi-zone-name {
        font-family: var(--gi-font-heading);
        font-size: 20px;
        line-height: 1.2;
        background: none;
        border: none;
        padding: 4px 0;
        color: inherit;
        cursor: pointer;
        text-align: left;
      }
      .gi-segmented {
        display: inline-flex;
        border: 1px solid var(--gi-color-divider);
        border-radius: 999px;
        overflow: hidden;
      }
      .gi-segment {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 44px;
        padding: 0 14px;
        font-size: 13px;
        cursor: pointer;
      }
      .gi-segment.is-active {
        background: var(--gi-color-accent-100);
        color: var(--gi-color-accent-700);
        font-weight: 600;
      }
      .gi-segment input {
        position: absolute;
        opacity: 0;
        width: 100%;
        height: 100%;
        margin: 0;
        cursor: pointer;
      }
      .gi-badge-row { display: flex; }
      .gi-headline { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
      .gi-headline-mm { font-size: 28px; font-weight: 700; }
      .gi-headline-liters { font-size: 13px; }
      .gi-small-note { font-size: 12px; margin: 0; }
      .gi-deficit-bar-track {
        position: relative;
        height: 8px;
        border-radius: 999px;
        background: var(--gi-color-neutral-200);
        overflow: visible;
      }
      .gi-deficit-bar-fill {
        position: absolute;
        inset: 0 auto 0 0;
        height: 100%;
        border-radius: 999px;
        background: var(--gi-color-accent-2-600);
      }
      .gi-deficit-bar-tick {
        position: absolute;
        top: -2px;
        bottom: -2px;
        width: 2px;
        background: var(--gi-color-neutral-900);
      }
      .gi-technical-row, .gi-footer { font-size: 13px; margin: 0; }
      .gi-differs-note { font-size: 12px; margin: 0; }
      .gi-soil-row {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        margin: 0;
      }
      .gi-disclosure summary {
        cursor: pointer;
        font-size: 13px;
        font-weight: 600;
        list-style: none;
      }
      .gi-disclosure summary::-webkit-details-marker { display: none; }
      .gi-disclosure-body { padding-top: 8px; display: flex; flex-direction: column; gap: 8px; }
      .gi-tag-row { display: flex; flex-wrap: wrap; gap: 6px; }

      @container (max-width: 340px) {
        .gi-header { flex-direction: column; align-items: flex-start; }
      }
    `;
  }

  // -- Events ----------------------------------------------------------------

  _bindEvents() {
    const zoneNameEl = this.shadowRoot.querySelector(".gi-zone-name");
    zoneNameEl?.addEventListener("click", () => {
      fireMoreInfo(this, this._config.needs_irrigation_entity);
    });

    const radios = this.shadowRoot.querySelectorAll('input[name="gi-variant"]');
    radios.forEach((radio) => {
      radio.addEventListener("change", (event) => {
        this._variant = event.target.value;
        this._render();
      });
    });

    const details = this.shadowRoot.querySelector(".gi-disclosure");
    details?.addEventListener("toggle", () => {
      this._disclosureOpen = details.open;
    });
  }
}

customElements.define("garden-irrigation-zone-card", GardenIrrigationZoneCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "garden-irrigation-zone-card",
  name: "Garden Irrigation - Zone Card",
  description: "Read-only irrigation decision-support summary for one zone.",
  preview: true,
});
