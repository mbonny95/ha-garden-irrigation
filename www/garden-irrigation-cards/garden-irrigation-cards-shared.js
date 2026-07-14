/**
 * Shared tokens, icons, and render helpers for the Garden Irrigation Lovelace
 * cards (garden-irrigation-zone-card, garden-irrigation-overview-card).
 *
 * Framework-less (no Lit/React/build step) by deliberate choice: this repo is
 * a pure-Python Home Assistant custom integration with no existing frontend
 * tooling, so a zero-dependency Web Component is the least-friction fit - see
 * the cards' own README for the full rationale.
 *
 * Every reader in this file is defensive (`?.`/`??`) because entity state can
 * be `unavailable`/`unknown` at HA startup, before the coordinator's first
 * refresh - callers must treat that the same as "data not ready yet", never
 * throw, never render a stale/invented number.
 */

// ---------------------------------------------------------------------------
// Design tokens (Organic design system) - inlined verbatim, not reinterpreted.
// Scoped to each card's own shadow root :host, per the handoff's instruction
// not to assume the dashboard page exposes them globally.
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

// Status tone -> {bg, fg, dot} per the handoff's fixed semantic mapping.
// Do not add new hues here - the handoff explicitly forbids it.
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
// Icons - inline SVG only (Lucide, stroke-width 2.75), no external font/icon
// request at render time. Only the three icons the handoff actually requires
// (soil-sensor droplet, warning triangle, overview-row chevron) are included;
// no icon is invented for a state the handoff doesn't call out.
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
// Formatting - every numeric figure is an ESTIMATE, never a measurement; the
// "≈" prefix and explicit units are part of that legibility requirement, not
// decoration.
// ---------------------------------------------------------------------------

export function formatMm(value, { fallback = "—" } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return `${Number(value).toFixed(1)} mm`;
}

export function formatLiters(value, { fallback = "—" } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return `≈${Number(value).toFixed(0)} L`;
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

// ---------------------------------------------------------------------------
// Status classification shared between both cards' badges
// ---------------------------------------------------------------------------

export const STATUS = {
  NEEDS_WATER: "needs_water",
  LIMITED: "limited",
  WAITING: "waiting",
  SATISFIED: "satisfied",
  NOT_FINALIZED: "not_finalized",
  DATA_UNAVAILABLE: "data_unavailable",
};

const STATUS_LABEL = {
  [STATUS.NEEDS_WATER]: "Needs water",
  [STATUS.LIMITED]: "Limited — weekly cap",
  [STATUS.WAITING]: "Watered recently — waiting",
  [STATUS.SATISFIED]: "Satisfied",
  [STATUS.NOT_FINALIZED]: "Not finalized yet",
  [STATUS.DATA_UNAVAILABLE]: "Data unavailable",
};

const STATUS_TONE = {
  [STATUS.NEEDS_WATER]: "needs",
  [STATUS.LIMITED]: "limited",
  [STATUS.WAITING]: "limited",
  [STATUS.SATISFIED]: "satisfied",
  [STATUS.NOT_FINALIZED]: "pending",
  [STATUS.DATA_UNAVAILABLE]: "pending",
};

/**
 * Classify a zone's `needs_irrigation_entity` state into one of the state
 * matrix's mutually-exclusive statuses (handoff README §5, rows 1-7).
 *
 * `state` is the needs_irrigation binary_sensor's HA state object; its
 * attributes (`ready`, `reasons`, `limits_applied`, `warnings`,
 * `recommended_mm`, ...) are exactly recommendation.py's ZoneRecommendationResult
 * as serialized today - see the cards' README for the one field this reads
 * that the backend does NOT yet expose (none for `final`; see the preview
 * limitation noted separately in the segmented-control renderer).
 */
export function classifyZoneStatus(state) {
  if (isUnavailable(state)) {
    return { status: STATUS.DATA_UNAVAILABLE, reasonText: null };
  }
  const ready = attr(state, "ready", null);
  const reasons = attr(state, "reasons", []) ?? [];
  const limitsApplied = attr(state, "limits_applied", []) ?? [];

  if (ready === false) {
    if (reasons.includes("et0_unavailable") || reasons.includes("et0_unavailable_today")) {
      return { status: STATUS.DATA_UNAVAILABLE, reasonText: "ET0 unavailable" };
    }
    // Default not-ready reason is "balance_not_yet_available" (row 6).
    return { status: STATUS.NOT_FINALIZED, reasonText: "Not finalized yet" };
  }

  if (limitsApplied.includes("min_interval_not_elapsed")) {
    return { status: STATUS.WAITING, reasonText: null };
  }
  if (
    limitsApplied.includes("weekly_cap_reached") ||
    limitsApplied.includes("weekly_cap_partial")
  ) {
    return { status: STATUS.LIMITED, reasonText: null };
  }

  const needsIrrigation = state.state === "on";
  return {
    status: needsIrrigation ? STATUS.NEEDS_WATER : STATUS.SATISFIED,
    reasonText: null,
  };
}

export function statusLabel(status) {
  return STATUS_LABEL[status] ?? STATUS_LABEL[STATUS.DATA_UNAVAILABLE];
}

export function statusTone(status) {
  return STATUS_TONES[STATUS_TONE[status] ?? "pending"];
}

/** Badge markup: a single pill, text label always present (never color-only). */
export function renderBadge(status) {
  const tone = statusTone(status);
  const label = statusLabel(status);
  return `
    <span class="gi-badge" style="background:${tone.bg};color:${tone.fg};">
      <span class="gi-badge-dot" style="background:${tone.dot};" aria-hidden="true"></span>
      ${escapeHtml(label)}
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
