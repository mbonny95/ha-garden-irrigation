/**
 * <garden-irrigation-overview-card-editor>: GUI editor built on <ha-form>.
 * Zones are discovered automatically, so only the title is configurable.
 */

const SCHEMA = [{ name: "title", selector: { text: {} } }];

const LABELS = {
  en: { title: "Title (optional)" },
  it: { title: "Titolo (facoltativo)" },
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
    this._form.data = this._config ?? {};
  }
}

customElements.define(
  "garden-irrigation-overview-card-editor",
  GardenIrrigationOverviewCardEditor,
);
