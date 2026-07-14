/**
 * <garden-irrigation-zone-card-editor>
 *
 * GUI config editor for garden-irrigation-zone-card, built on HA's own
 * <ha-form> (per the handoff's instruction to reuse ha-form/ha-entity-picker
 * rather than hand-rolling entity pickers). Light DOM: <ha-form> is a
 * globally-registered element supplied by the HA frontend at runtime, not
 * bundled by this card.
 */

const SCHEMA = [
  { name: "zone", required: true, selector: { text: {} } },
  { name: "name", selector: { text: {} } },
  {
    name: "needs_irrigation_entity",
    required: true,
    selector: { entity: { domain: "binary_sensor" } },
  },
  { name: "deficit_entity", required: true, selector: { entity: { domain: "sensor" } } },
  { name: "raw_entity", required: true, selector: { entity: { domain: "sensor" } } },
  { name: "taw_entity", required: true, selector: { entity: { domain: "sensor" } } },
  {
    name: "irrigation_7d_entity",
    required: true,
    selector: { entity: { domain: "sensor" } },
  },
  {
    name: "weekly_cap_entity",
    required: true,
    selector: { entity: { domain: "binary_sensor" } },
  },
  {
    name: "in_progress_entity",
    selector: { entity: { domain: "binary_sensor" } },
  },
  {
    name: "default_variant",
    selector: { select: { options: ["final", "preview"], mode: "dropdown" } },
  },
  { name: "show_technical_row", selector: { boolean: {} } },
  { name: "show_wh51", selector: { boolean: {} } },
];

const LABELS = {
  zone: "Zone id (matches backend zone_1/zone_2)",
  name: "Display name (optional)",
  needs_irrigation_entity: "Needs-irrigation entity",
  deficit_entity: "Deficit entity",
  raw_entity: "RAW entity",
  taw_entity: "TAW entity",
  irrigation_7d_entity: "Irrigation (7d) entity",
  weekly_cap_entity: "Weekly cap reached entity",
  in_progress_entity: "Irrigation-in-progress entity (optional)",
  default_variant: "Default variant",
  show_technical_row: "Show technical row",
  show_wh51: "Show soil sensor row",
};

class GardenIrrigationZoneCardEditor extends HTMLElement {
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
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schemaItem) => LABELS[schemaItem.name] ?? schemaItem.name;
      this._form.addEventListener("value-changed", (event) => {
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: event.detail.value },
            bubbles: true,
            composed: true,
          }),
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = SCHEMA;
    this._form.data = {
      show_technical_row: true,
      show_wh51: true,
      default_variant: "final",
      ...this._config,
    };
  }
}

customElements.define("garden-irrigation-zone-card-editor", GardenIrrigationZoneCardEditor);
