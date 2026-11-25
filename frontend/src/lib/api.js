const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

async function errorDetail(res) {
  let detail = `Request failed (${res.status})`;
  try {
    const body = await res.json();
    detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
  } catch { /* not JSON */ }
  return detail;
}

async function request(path, { method = 'GET', body } = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await errorDetail(res));
  return res.status === 204 ? null : res.json();
}

export const api = {
  listBrands: () => request('/brands'),
  createBrand: (name, input) => request('/brands', { method: 'POST', body: { name, input } }),
  updateBrand: (id, patch) => request(`/brands/${id}`, { method: 'PATCH', body: patch }),
  deleteBrand: (id) => request(`/brands/${id}`, { method: 'DELETE' }),
  saveProfile: (id, profile) => request(`/brands/${id}/profile`, { method: 'PUT', body: profile }),
  listRuns: (brandId, limit = 30) => request(`/brands/${brandId}/runs?limit=${limit}`),
  getRun: (id) => request(`/runs/${id}`),
  deleteRun: (id) => request(`/runs/${id}`, { method: 'DELETE' }),
};

/** Start a saved run for a brand and stream its progress. Resolves with the RunDetail. */
export function streamBrandRun(brandId, body, handlers) {
  return streamSSE(`/brands/${brandId}/runs/stream`, body, handlers);
}

/**
 * POST and parse Server-Sent Events from the response body.
 * (EventSource only supports GET, so we read the stream manually.)
 */
export async function streamSSE(path, payload, { onProgress, onRun, signal }) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok) throw new Error(await errorDetail(res));

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');

    let sep;
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let event = 'message';
      const data = [];
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
      }
      if (!data.length) continue;
      const parsed = JSON.parse(data.join('\n'));
      if (event === 'progress') onProgress?.(parsed);
      else if (event === 'run') onRun?.(parsed.run_id);
      else if (event === 'result') return parsed;
      else if (event === 'error') throw new Error(parsed.detail || 'The workflow failed');
    }
  }
  throw new Error('Connection closed before the result arrived');
}

export const PLATFORMS = [
  { id: 'linkedin', label: 'LinkedIn', short: 'LinkedIn' },
  { id: 'x', label: 'X (Twitter)', short: 'X' },
  { id: 'threads', label: 'Threads', short: 'Threads' },
  { id: 'instagram', label: 'Instagram', short: 'Instagram' },
  { id: 'medium', label: 'Medium', short: 'Medium' },
  { id: 'youtube_shorts', label: 'YouTube Shorts', short: 'Shorts' },
];

export const platformLabel = (id) => PLATFORMS.find((p) => p.id === id)?.label ?? id;
