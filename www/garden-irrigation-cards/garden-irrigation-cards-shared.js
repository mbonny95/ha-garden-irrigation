/**
 * Shared tokens, icons, and render helpers for the Garden Irrigation Lovelace
 * cards (garden-irrigation-zone-card, garden-irrigation-overview-card).
 *
 * Framework-less (no Lit/React/build step): plain Web Components, no
 * dependency. Every reader is defensive because entity state can be
 * `unavailable`/`unknown`; callers never render an invented number.
 */

// ---------------------------------------------------------------------------
// Design tokens (Organic design system), scoped to each card's shadow root.
// ---------------------------------------------------------------------------

export const TOKENS_CSS = `
  --gi-color-bg: #f5ead8;
  --gi-color-surface: #ebddc5;
  --gi-color-text: #201e1d;
  --gi-color-divider: color-mix(in srgb, #201e1d 16%, transparent);

  --gi-color-accent-100: #fff2eb;
  --gi-color-accent-300: #e3a980;
  --gi-color-accent-600: #b2622d;
  --gi-color-accent-700: #8c491a;
  --gi-color-accent-800: #643312;

  --gi-color-accent-2-100: #f0fae1;
  --gi-color-accent-2-600: #728157;
  --gi-color-accent-2-700: #56633f;

  --gi-color-neutral-200: #eee7db;
  --gi-color-neutral-300: #ddd3c2;
  --gi-color-neutral-400: #c0b6a5;
  --gi-color-neutral-500: #a19786;
  --gi-color-neutral-700: #645c50;
  --gi-color-neutral-900: #2e2b25;

  --gi-font-heading: "Caprasimo", system-ui, sans-serif;
  --gi-font-body: "Figtree", system-ui, sans-serif;

  --gi-radius-sm: 8px;
  --gi-radius-md: 16px;
  --gi-shadow-sm: 0 1px 2px color-mix(in srgb, #2e2b25 14%, transparent);
  --gi-shadow-md: 0 3px 10px color-mix(in srgb, #2e2b25 16%, transparent);
`;

// Status tone -> {bg, fg, dot}.
export const STATUS_TONES = {
  needs: {
    bg: "var(--gi-color-accent-100)",
    fg: "var(--gi-color-accent-700)",
    dot: "var(--gi-color-accent-600)",
  },
  satisfied: {
    bg: "var(--gi-color-accent-2-100)",
    fg: "var(--gi-color-accent-2-700)",
    dot: "var(--gi-color-accent-2-600)",
  },
  pending: {
    bg: "var(--gi-color-neutral-200)",
    fg: "var(--gi-color-neutral-700)",
    dot: "var(--gi-color-neutral-500)",
  },
  limited: {
    bg: "color-mix(in oklch, var(--gi-color-accent-300) 65%, var(--gi-color-neutral-300) 35%)",
    fg: "var(--gi-color-accent-800)",
    dot: "color-mix(in oklch, var(--gi-color-accent-600) 65%, var(--gi-color-neutral-700) 35%)",
  },
};

// ---------------------------------------------------------------------------
// Icons - inline SVG only (Lucide, stroke-width 2.75), no external request.
// ---------------------------------------------------------------------------

const ICON_PATHS = {
  droplet:
    '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.5-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
  "alert-triangle":
    '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  "chevron-right": '<path d="m9 18 6-6-6-6"/>',
};

/** Inline SVG markup for one of ICON_PATHS's keys, sized/stroked per spec. */
export function icon(name, size = 16) {
  const body = ICON_PATHS[name];
  if (!body) return "";
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${body}</svg>`;
}

// ---------------------------------------------------------------------------
// Defensive state/attribute readers
// ---------------------------------------------------------------------------

/** hass.states[entityId], or null if the entity doesn't exist at all. */
export function getState(hass, entityId) {
  if (!entityId || !hass || !hass.states) return null;
  return hass.states[entityId] ?? null;
}

/** True if `state` is missing or in one of HA's non-data placeholder states. */
export function isUnavailable(state) {
  return !state || state.state === "unavailable" || state.state === "unknown";
}

/** Numeric native_value, or null if absent/non-numeric/unavailable. */
export function numericState(state) {
  if (isUnavailable(state)) return null;
  const value = Number(state.state);
  return Number.isFinite(value) ? value : null;
}

/** Attribute reader that never throws on a missing state/attributes object. */
export function attr(state, key, fallback = undefined) {
  return state?.attributes?.[key] ?? fallback;
}

// ---------------------------------------------------------------------------
// Formatting - every figure is an ESTIMATE: "≈" and units are deliberate.
// ---------------------------------------------------------------------------

export function formatMm(value, { fallback = "—" } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return `${Number(value).toFixed(1)} mm`;
}

export function formatLiters(value, { fallback = "—" } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return `≈${Number(value).toFixed(0)} L`;
}

export function formatMinutes(value, { fallback = "—" } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return `≈${Math.round(Number(value))} min`;
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

// ---------------------------------------------------------------------------
// Entity discovery: the cards are configured with a zone *device*; entities
// are found through the entity registry (platform + translation_key), so
// entity_ids can be renamed freely.
// ---------------------------------------------------------------------------

export const DOMAIN = "garden_irrigation";

/** entity_id of the garden_irrigation entity with `translationKey` on `deviceId`. */
export function findEntity(hass, deviceId, translationKey) {
  for (const entry of Object.values(hass?.entities ?? {})) {
    if (
      entry.platform === DOMAIN &&
      entry.translation_key === translationKey &&
      (deviceId === undefined || entry.device_id === deviceId)
    ) {
      return entry.entity_id;
    }
  }
  return null;
}

/** Zone devices: every device with a garden_irrigation needs_irrigation entity. */
export function findZoneDevices(hass) {
  const ids = [];
  for (const entry of Object.values(hass?.entities ?? {})) {
    if (
      entry.platform === DOMAIN &&
      entry.translation_key === "needs_irrigation" &&
      entry.device_id &&
      !ids.includes(entry.device_id)
    ) {
      ids.push(entry.device_id);
    }
  }
  return ids;
}

export function deviceName(hass, deviceId) {
  const device = hass?.devices?.[deviceId];
  return device?.name_by_user || device?.name || "";
}

/** State translated by Home Assistant when possible (enum sensors, on/off). */
export function formatState(hass, state) {
  if (!state) return "—";
  if (typeof hass?.formatEntityState === "function") return hass.formatEntityState(state);
  return state.state;
}

// ---------------------------------------------------------------------------
// Texts (Italian + English; English is the fallback)
// ---------------------------------------------------------------------------

const TEXTS = {
  en: {
    needs_water: "Needs water",
    satisfied: "No irrigation needed",
    no_deficit: "Starting deficit not set",
    unavailable: "Data unavailable",
    estimate_note: "Estimates from the FAO-56 water balance.",
    deficit: "Deficit",
    of_taw: "of",
    minutes_mains: "Mains water",
    minutes_tank: "Rainwater tank",
    blocks: "blocks of",
    pause: "pause",
    why: "Why this recommendation",
    last_day: "Last closed day",
    etc: "ETc",
    effective_rain: "effective rain",
    irrigation_7d: "last 7 days",
    last_irrigation: "last irrigation",
    never: "never",
    soil_sensor: "Soil sensor",
    record: "Record irrigation",
    source: "Source",
    minutes: "Minutes",
    millimeters: "Millimeters",
    save: "Record",
    recorded: "Recorded",
    et0_yesterday: "ET0 yesterday",
    rain_yesterday: "Rain yesterday",
    forecast: "Forecast 24 h",
    data_quality: "Weather data",
    open_repairs: "Open Repairs",
    no_zones: "No Garden Irrigation zone found.",
    pick_zone: "Choose a zone device in the card settings.",
    messages: {
      deficit_unknown: "Starting deficit not set: use the “Set deficit” action (0 after a soaking rain).",
      deficit_below_raw: "Deficit {deficit_mm} mm is below the {raw_mm} mm threshold (RAW).",
      deficit_reached_raw: "Deficit {deficit_mm} mm reached the {raw_mm} mm threshold (RAW).",
      min_interval: "Last irrigation {hours_since} h ago (suggested minimum {min_interval_h} h).",
      weekly_cap: "This would bring the last 7 days to {total_mm} mm, above your {weekly_cap_mm} mm limit.",
      soil_sensor_wet: "Soil sensor reads {value_pct}% (your wet threshold {wet_pct}%): check before watering.",
      soil_sensor_dry: "Soil sensor reads {value_pct}% (your dry threshold {dry_pct}%): check the lawn.",
      rain_forecast: "Rain forecast: {forecast_mm} mm in the next 24 h.",
      no_source_rate: "No application rate set: minutes cannot be computed.",
    },
  },
  it: {
    needs_water: "Da irrigare",
    satisfied: "Non serve irrigare",
    no_deficit: "Deficit iniziale non impostato",
    unavailable: "Dati non disponibili",
    estimate_note: "Stime del bilancio idrico FAO-56.",
    deficit: "Deficit",
    of_taw: "su",
    minutes_mains: "Rete",
    minutes_tank: "Cisterna",
    blocks: "blocchi da",
    pause: "pausa",
    why: "Perché questo consiglio",
    last_day: "Ultimo giorno chiuso",
    etc: "ETc",
    effective_rain: "pioggia efficace",
    irrigation_7d: "ultimi 7 giorni",
    last_irrigation: "ultima irrigazione",
    never: "mai",
    soil_sensor: "Sensore suolo",
    record: "Registra irrigazione",
    source: "Fonte",
    minutes: "Minuti",
    millimeters: "Millimetri",
    save: "Registra",
    recorded: "Registrati",
    et0_yesterday: "ET0 ieri",
    rain_yesterday: "Pioggia ieri",
    forecast: "Prevista 24 h",
    data_quality: "Dati meteo",
    open_repairs: "Apri Riparazioni",
    no_zones: "Nessuna zona di Garden Irrigation trovata.",
    pick_zone: "Scegli il dispositivo della zona nelle impostazioni della card.",
    messages: {
      deficit_unknown: "Deficit iniziale non impostato: usa l'azione “Imposta deficit” (0 dopo una pioggia abbondante).",
      deficit_below_raw: "Deficit {deficit_mm} mm sotto la soglia di {raw_mm} mm (RAW).",
      deficit_reached_raw: "Deficit {deficit_mm} mm: raggiunta la soglia di {raw_mm} mm (RAW).",
      min_interval: "Ultima irrigazione {hours_since} h fa (minimo consigliato {min_interval_h} h).",
      weekly_cap: "Con questa irrigazione gli ultimi 7 giorni arrivano a {total_mm} mm, oltre il tuo limite di {weekly_cap_mm} mm.",
      soil_sensor_wet: "Il sensore suolo segna {value_pct}% (tua soglia umido {wet_pct}%): verifica prima di irrigare.",
      soil_sensor_dry: "Il sensore suolo segna {value_pct}% (tua soglia secco {dry_pct}%): controlla il prato.",
      rain_forecast: "Pioggia prevista: {forecast_mm} mm nelle prossime 24 h.",
      no_source_rate: "Nessuna intensità di irrigazione impostata: minuti non calcolabili.",
    },
  },
};

export function texts(hass) {
  const language = String(hass?.locale?.language ?? hass?.language ?? "en").slice(0, 2);
  return TEXTS[language] ?? TEXTS.en;
}

function formatParam(value) {
  return typeof value === "number" ? String(Math.round(value * 10) / 10) : String(value);
}

/** Human text of a reason/warning attribute item ({code, ...params}). */
export function messageText(t, message) {
  const params = { ...message };
  if (message.code === "weekly_cap") {
    params.total_mm = (message.irrigation_7d_mm ?? 0) + (message.amount_mm ?? 0);
  }
  const template = t.messages[message.code] ?? message.code;
  return template.replace(/\{(\w+)\}/g, (_, key) =>
    key in params ? formatParam(params[key]) : `{${key}}`,
  );
}

// ---------------------------------------------------------------------------
// Status classification shared between both cards' badges
// ---------------------------------------------------------------------------

export const STATUS = {
  NEEDS_WATER: "needs_water",
  SATISFIED: "satisfied",
  NO_DEFICIT: "no_deficit",
  UNAVAILABLE: "unavailable",
};

const STATUS_TONE = {
  [STATUS.NEEDS_WATER]: "needs",
  [STATUS.SATISFIED]: "satisfied",
  [STATUS.NO_DEFICIT]: "pending",
  [STATUS.UNAVAILABLE]: "pending",
};

/** Status from the zone's needs_irrigation binary_sensor. */
export function classifyZoneStatus(state) {
  if (!state || state.state === "unavailable") return STATUS.UNAVAILABLE;
  if (state.state === "on") return STATUS.NEEDS_WATER;
  if (state.state === "off") return STATUS.SATISFIED;
  return STATUS.NO_DEFICIT;
}

export function statusTone(status) {
  return STATUS_TONES[STATUS_TONE[status] ?? "pending"];
}

/** Badge markup: a single pill, text label always present (never color-only). */
export function renderBadge(status, t) {
  const tone = statusTone(status);
  return `
    <span class="gi-badge" style="background:${tone.bg};color:${tone.fg};">
      <span class="gi-badge-dot" style="background:${tone.dot};" aria-hidden="true"></span>
      ${escapeHtml(t[status] ?? status)}
    </span>
  `;
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

/** Standard HA more-info dialog for `entityId` (not a custom modal). */
export function fireMoreInfo(el, entityId) {
  if (!entityId) return;
  el.dispatchEvent(
    new CustomEvent("hass-more-info", {
      detail: { entityId },
      bubbles: true,
      composed: true,
    }),
  );
}

/** Lovelace `navigate` action to an internal path (e.g. /config/repairs). */
export function navigate(el, path) {
  if (!path) return;
  history.pushState(null, "", path);
  el.dispatchEvent(
    new CustomEvent("location-changed", { bubbles: true, composed: true }),
  );
}

// ---------------------------------------------------------------------------
// Misc
// ---------------------------------------------------------------------------

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

/** Shared base CSS (host sizing, focus ring, chips, badge, tap targets). */
export const BASE_CSS = `
  :host {
    ${TOKENS_CSS}
    display: block;
    font-family: var(--gi-font-body);
    color: var(--gi-color-text);
    container-type: inline-size;
  }

  * {
    box-sizing: border-box;
  }

  :focus-visible {
    outline: 2px solid var(--gi-color-accent-600);
    outline-offset: 2px;
  }

  .gi-card {
    background: var(--gi-color-surface);
    border-radius: var(--gi-radius-md);
    box-shadow: var(--gi-shadow-sm);
    overflow: hidden;
  }

  .gi-card:hover {
    box-shadow: var(--gi-shadow-md);
  }

  .gi-tap-target {
    min-height: 44px;
    min-width: 44px;
    display: flex;
    align-items: center;
  }

  .gi-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    line-height: 1.4;
    white-space: normal;
  }

  .gi-badge-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex: none;
  }

  .gi-chip {
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    border-radius: var(--gi-radius-sm);
    background: var(--gi-color-neutral-200);
    color: var(--gi-color-neutral-700);
    font-size: 11px;
    line-height: 1.4;
  }

  .gi-muted {
    color: var(--gi-color-neutral-700);
  }

  .gi-warning-text {
    color: var(--gi-color-accent-800);
  }

  .gi-tabular {
    font-variant-numeric: tabular-nums;
  }

  .gi-visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
`;
