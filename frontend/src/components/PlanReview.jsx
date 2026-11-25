import { useState } from 'react';
import { ExternalLink, PenLine, X } from 'lucide-react';
import { platformLabel } from '../lib/api';

/** Shown when a run paused after research: approve or adjust the plan before anything is written. */
export default function PlanReview({ run, onContinue, onCancel, busy }) {
  const [angle, setAngle] = useState(run.plan.angle);
  const [pillar, setPillar] = useState(run.plan.pillar);
  const [keep, setKeep] = useState(() => new Set(run.sources.map((s) => s.url)));
  const [guidance, setGuidance] = useState('');

  const toggle = (url) =>
    setKeep((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });

  const submit = (e) => {
    e.preventDefault();
    onContinue({
      angle: angle.trim() !== run.plan.angle ? angle.trim() : null,
      pillar: pillar.trim() !== run.plan.pillar ? pillar.trim() : null,
      source_urls: keep.size === run.sources.length ? null : [...keep],
      guidance: guidance.trim(),
    });
  };

  return (
    <form onSubmit={submit} className="card space-y-5 p-5 sm:p-6">
      <div>
        <p className="text-xs font-medium tracking-wide text-accent uppercase">Paused for your review</p>
        <h2 className="mt-1 text-base font-semibold">Check the plan before Brand Bot writes</h2>
        <p className="hint">
          Writing for {run.platforms.map(platformLabel).join(', ')} starts when you continue. This run is saved, so
          you can come back to it from History.
        </p>
      </div>

      <div>
        <label htmlFor="plan-angle" className="label">Angle</label>
        <textarea id="plan-angle" rows={3} className="field resize-y" value={angle} onChange={(e) => setAngle(e.target.value)} required maxLength={500} />
      </div>
      <div>
        <label htmlFor="plan-pillar" className="label">Pillar</label>
        <input id="plan-pillar" className="field" value={pillar} onChange={(e) => setPillar(e.target.value)} required maxLength={200} />
      </div>

      <fieldset>
        <legend className="label">
          Sources to use <span className="font-normal text-muted">({keep.size} of {run.sources.length})</span>
        </legend>
        {run.sources.length === 0 && <p className="hint">No sources were found; the writers will rely on general expertise.</p>}
        <ul className="mt-2 space-y-2">
          {run.sources.map((s) => (
            <li key={s.url}>
              <label className="flex cursor-pointer gap-3 rounded-lg border border-line p-3 transition hover:bg-canvas has-[:checked]:border-accent/40">
                <input type="checkbox" className="mt-0.5 size-4 shrink-0 accent-accent" checked={keep.has(s.url)} onChange={() => toggle(s.url)} />
                <span className="min-w-0">
                  <span className="flex items-center gap-1 text-sm font-medium">
                    <span className="truncate">{s.title || s.url}</span>
                    <a href={s.url} target="_blank" rel="noreferrer" className="shrink-0 text-muted hover:text-accent" aria-label="Open source">
                      <ExternalLink className="size-3" />
                    </a>
                  </span>
                  <span className="mt-0.5 line-clamp-2 block text-xs text-muted">{s.snippet}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>

      <div>
        <label htmlFor="plan-guidance" className="label">Anything the writers should know? <span className="font-normal text-muted">(optional)</span></label>
        <textarea
          id="plan-guidance"
          rows={3}
          className="field resize-y"
          placeholder="e.g. Mention that I'm speaking at PyCon next month. Avoid the word “journey”."
          value={guidance}
          onChange={(e) => setGuidance(e.target.value)}
          maxLength={1000}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <button type="submit" className="btn-primary" disabled={busy || !angle.trim() || !pillar.trim()}>
          <PenLine className="size-4" /> Write content
        </button>
        <button type="button" className="btn-ghost" onClick={onCancel} disabled={busy}>
          <X className="size-4" /> Discard run
        </button>
      </div>
    </form>
  );
}
