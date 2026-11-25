import { Trash2 } from 'lucide-react';
import { PLATFORMS } from '../lib/api';

const short = (id) => PLATFORMS.find((p) => p.id === id)?.short ?? id;

const STATUS = {
  completed: null,
  running: { text: 'Running', cls: 'bg-accent-soft text-accent' },
  failed: { text: 'Failed', cls: 'bg-red-50 text-red-700' },
  cancelled: { text: 'Stopped', cls: 'bg-canvas text-muted' },
};

function when(iso) {
  const d = new Date(iso);
  const today = new Date().toDateString() === d.toDateString();
  return today
    ? d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export default function History({ runs, activeId, onOpen, onDelete, loading }) {
  return (
    <div className="card p-4 sm:p-5">
      <h2 className="text-base font-semibold">History</h2>
      {loading && <p className="mt-3 text-sm text-muted">Loading…</p>}
      {!loading && runs.length === 0 && <p className="mt-3 text-sm text-muted">Your past runs will be listed here.</p>}
      <ul className="mt-3 -mx-2 space-y-1">
        {runs.map((r) => {
          const badge = STATUS[r.status];
          const active = r.id === activeId;
          return (
            <li key={r.id} className="group relative">
              <button
                type="button"
                onClick={() => onOpen(r.id)}
                disabled={r.status !== 'completed'}
                className={`w-full rounded-lg px-2 py-2 pr-9 text-left transition disabled:cursor-default ${
                  active ? 'bg-accent-soft' : 'hover:bg-canvas'
                }`}
              >
                <p className="line-clamp-2 text-sm text-ink">{r.angle || r.topic || 'Untitled run'}</p>
                <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                  <span>{when(r.created_at)}</span>
                  <span>·</span>
                  <span>{r.platforms.map(short).join(', ')}</span>
                  {r.status === 'completed' && (
                    <>
                      <span>·</span>
                      <span>{r.approved}/{r.platforms.length} approved</span>
                    </>
                  )}
                  {badge && <span className={`rounded px-1.5 py-0.5 text-[11px] ${badge.cls}`}>{badge.text}</span>}
                </p>
              </button>
              <button
                type="button"
                onClick={() => onDelete(r.id)}
                className="absolute top-2 right-1 rounded p-1.5 text-muted opacity-0 transition group-hover:opacity-100 hover:bg-white hover:text-red-600 focus:opacity-100"
                aria-label="Delete run"
              >
                <Trash2 className="size-3.5" />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
