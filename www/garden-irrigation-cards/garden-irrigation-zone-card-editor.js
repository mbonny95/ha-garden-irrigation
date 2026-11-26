/**
 * <garden-irrigation-zone-card-editor>: GUI editor built on <ha-form>.
 */

const SCHEMA = [
  {
    name: "device_id",
    required: true,
    selector: { device: { integration: "garden_irrigation" } },
  },
  { name: "name", selector: { text: {} } },
  { name: "show_record_form", selector: { boolean: {} } },
];

const LABELS = {
  en: { device_id: "Zone", name: "Name (optional)", show_record_form: "Show the record form" },
  it: { device_id: "Zona", name: "Nome (facoltativo)", show_record_form: "Mostra il modulo di registrazione" },
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
    const language = String(this._hass.locale?.language ?? "en").slice(0, 2);
    const labels = LABELS[language] ?? LABELS.en;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (event) => {
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: { ...this._config, ...event.detail.value } },
            bubbles: true,
            composed: true,
          }),
        );
      });
      this.appendChild(this._form);
    }
    this._form.computeLabel = (item) => labels[item.name] ?? item.name;
    this._form.hass = this._hass;
    this._form.schema = SCHEMA;
    this._form.data = { show_record_form: true, ...(this._config ?? {}) };
  }
}

customElements.define("garden-irrigation-zone-card-editor", GardenIrrigationZoneCardEditor);
