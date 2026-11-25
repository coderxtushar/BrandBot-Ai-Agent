export const initialProgress = { profile: null, planning: null, research: null, platforms: {} };

/** Fold one SSE progress event into the progress state. */
export function progressReducer(state, ev) {
  if (ev.reset) return { ...initialProgress, platforms: Object.fromEntries(ev.platforms.map((p) => [p, { stage: 'queued' }])) };
  if (ev.platform) {
    return { ...state, platforms: { ...state.platforms, [ev.platform]: { ...state.platforms[ev.platform], ...ev } } };
  }
  if (['profile', 'planning', 'research'].includes(ev.stage)) {
    return { ...state, [ev.stage]: { ...state[ev.stage], ...ev } };
  }
  return state;
}
