export const NEW_BRAND = '__new__';

export const EMPTY_BRAND_INPUT = {
  target_audience: '',
  expertise: '',
  tone_of_voice: '',
  content_pillars: '',
  past_posts: '',
};

export const brandInput = (brand) => ({ ...EMPTY_BRAND_INPUT, ...(brand?.input ?? {}) });

export const sameInput = (a, b) =>
  Object.keys(EMPTY_BRAND_INPUT).every((k) => (a[k] ?? '').trim() === (b[k] ?? '').trim());
