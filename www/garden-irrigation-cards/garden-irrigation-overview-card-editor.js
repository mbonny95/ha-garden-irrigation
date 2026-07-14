/**
 * <garden-irrigation-overview-card-editor>
 *
 * GUI config editor for garden-irrigation-overview-card's top-level fields,
 * built on <ha-form>. The `zones:` array (name/entity/navigate_to per zone)
 * is intentionally NOT built as a nested add/remove-row GUI here - ha-form
 * has no first-class array-of-objects widget, and hand-rolling one for what
 * is an optional, "recommended" editor (per the handoff) isn't a good time
 * trade-off. Editing `zones:` is done via the dashboard's YAML editor; this
 * editor covers everything else and leaves `zones:` untouched if already set.
 */

const SCHEMA = [
  { name: "mode_entity", required: true, selector: { entity: { domain: "select" } } },
  {
    name: "data_quality_entity",
    required: true,
    selector: { entity: { domain: "sensor" } },
  },
  { name: "et0_entity", required: true, selector: { entity: { domain: "sensor" } } },
  {
    name: "in_progress_entity",
    selector: { entity: { domain: "binary_sensor" } },
  },
];

const LABELS = {
  mode_entity: "Mode select entity",
  data_quality_entity: "Data quality entity",
  et0_entity: "ET0 (daily) entity",
  in_progress_entity: "Irrigation-in-progress entity (optional)",
};

class GardenIrrigationOverviewCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass) return;
    if (!this._note) {
      this._note = document.createElement("p");
      this._note.textContent =
        "Edit the zones: array (name/entity ids/navigate_to per zone) in the dashboard's YAML editor - it isn't covered by this GUI form.";
      this._note.style.fontSize = "12px";
      this._note.style.opacity = "0.75";
      this.appendChild(this._note);
    }
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schemaItem) => LABELS[schemaItem.name] ?? schemaItem.name;
      this._form.addEventListener("value-changed", (event) => {
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: { ...this._config, ...event.detail.value } },
            bubbles: true,
            composed: true,
          }),
        );
      });
      this.insertBefore(this._form, this._note);
    }
    this._form.hass = this._hass;
    this._form.schema = SCHEMA;
    this._form.data = this._config ?? {};
  }
}

customElements.define(
  "garden-irrigation-overview-card-editor",
  GardenIrrigationOverviewCardEditor,
);
