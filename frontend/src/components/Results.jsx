import { useState } from 'react';
import { CircleAlert, CircleCheck, ExternalLink } from 'lucide-react';
import { platformLabel } from '../lib/api';
import CopyButton from './CopyButton';
import Preview from './Previews';

function ReviewNote({ result }) {
  if (result.error) {
    return (
      <div className="flex gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-800">
        <CircleAlert className="mt-0.5 size-4 shrink-0" />
        <p>{result.error}</p>
      </div>
    );
  }
  const r = result.review;
  if (!r) return null;
  const tone = r.approved ? 'bg-emerald-50 text-emerald-900' : 'bg-amber-50 text-amber-900';
  return (
    <div className={`rounded-lg p-3 text-sm ${tone}`}>
      <p className="flex items-center gap-2 font-medium">
        {r.approved ? <CircleCheck className="size-4" /> : <CircleAlert className="size-4" />}
        {r.approved ? 'Approved' : 'Needs a human look'} · score {r.score}/10
        {result.attempts > 1 && <span className="font-normal opacity-75">· {result.attempts} drafts</span>}
      </p>
      {r.issues.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px]">
          {r.issues.map((i, n) => <li key={n}>{i}</li>)}
        </ul>
      )}
    </div>
  );
}

function PlatformPanel({ result }) {
  return (
    <div className="space-y-4">
      <ReviewNote result={result} />
      {result.items.map((item, i) => (
        <section key={i} className="card p-4 sm:p-5">
          <div className="mb-4 flex items-center justify-between gap-2">
            <h3 className="text-sm font-medium text-muted">
              {result.items.length > 1 ? `Variant ${i + 1}` : platformLabel(result.platform)}
            </h3>
            <CopyButton text={result.text[i]} />
          </div>
          <Preview platform={result.platform} item={item} />
        </section>
      ))}
    </div>
  );
}

function Strategy({ data }) {
  const { brand_profile: p, plan, sources } = data;
  return (
    <div className="space-y-4">
      <section className="card p-4 sm:p-5">
        <h3 className="text-sm font-medium text-muted">Today's angle</h3>
        <p className="mt-1 font-medium">{plan.angle}</p>
        <p className="mt-1 text-xs text-muted">Pillar: {plan.pillar}</p>
      </section>
      <section className="card space-y-3 p-4 text-sm sm:p-5">
        <h3 className="text-sm font-medium text-muted">Brand profile</h3>
        <p><span className="font-medium">Positioning:</span> {p.positioning}</p>
        <p><span className="font-medium">Audience:</span> {p.audience_persona}</p>
        <p><span className="font-medium">Voice:</span> {p.voice.traits.join(', ')}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <p className="font-medium">Do</p>
            <ul className="mt-1 list-disc pl-5 text-muted">{p.voice.do.map((d, i) => <li key={i}>{d}</li>)}</ul>
          </div>
          <div>
            <p className="font-medium">Don't</p>
            <ul className="mt-1 list-disc pl-5 text-muted">{p.voice.dont.map((d, i) => <li key={i}>{d}</li>)}</ul>
          </div>
        </div>
        <p><span className="font-medium">Pillars:</span> {p.pillars.join(' · ')}</p>
        <p className="text-accent">{p.hashtags.map((h) => `#${h}`).join(' ')}</p>
      </section>
      <section className="card p-4 sm:p-5">
        <h3 className="text-sm font-medium text-muted">Sources ({sources.length})</h3>
        {sources.length === 0 && <p className="mt-2 text-sm text-muted">No web sources were found for this run.</p>}
        <ul className="mt-2 space-y-3">
          {sources.map((s) => (
            <li key={s.url} className="text-sm">
              <a href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-accent hover:underline">
                {s.title || s.url} <ExternalLink className="size-3" />
              </a>
              <p className="mt-0.5 line-clamp-2 text-xs text-muted">{s.snippet}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export default function Results({ data }) {
  const tabs = [...data.results.map((r) => ({ id: r.platform, label: platformLabel(r.platform), result: r })), { id: 'strategy', label: 'Strategy & sources' }];
  const [active, setActive] = useState(tabs[0].id);
  const current = tabs.find((t) => t.id === active) ?? tabs[0];

  return (
    <div>
      <div role="tablist" className="mb-4 flex gap-1 overflow-x-auto border-b border-line">
        {tabs.map((t) => {
          const warn = t.result && (t.result.error || !t.result.review?.approved);
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={t.id === current.id}
              onClick={() => setActive(t.id)}
              className={`-mb-px flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2 text-sm transition ${
                t.id === current.id ? 'border-accent font-medium text-ink' : 'border-transparent text-muted hover:text-ink'
              }`}
            >
              {t.label}
              {warn && <span className="size-1.5 rounded-full bg-amber-500" aria-label="needs attention" />}
            </button>
          );
        })}
      </div>
      {current.result ? <PlatformPanel result={current.result} /> : <Strategy data={data} />}
    </div>
  );
}
