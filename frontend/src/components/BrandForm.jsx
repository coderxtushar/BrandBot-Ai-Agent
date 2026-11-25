import { useState } from 'react';
import { ChevronDown, Sparkles } from 'lucide-react';
import { PLATFORMS } from '../lib/api';

const FIELDS = [
  { name: 'target_audience', label: 'Target audience', rows: 2, placeholder: 'e.g. Startup founders and senior software engineers' },
  { name: 'expertise', label: 'Areas of expertise', rows: 2, placeholder: 'e.g. AI product development, Python, MLOps' },
  { name: 'tone_of_voice', label: 'Tone of voice', rows: 2, placeholder: 'e.g. Practical and direct, a little witty, never salesy' },
  { name: 'content_pillars', label: 'Content pillars', rows: 3, placeholder: 'e.g. Shipping AI features, Python tips, career growth for engineers' },
];

export default function BrandForm({ value, onChange, onSubmit, isRunning, hasProfile, reuseProfile, onReuseProfile }) {
  const [showVoice, setShowVoice] = useState(Boolean(value.brand.past_posts));
  const setBrand = (name, v) => onChange({ ...value, brand: { ...value.brand, [name]: v } });
  const togglePlatform = (id) => {
    const has = value.platforms.includes(id);
    onChange({ ...value, platforms: has ? value.platforms.filter((p) => p !== id) : [...value.platforms, id] });
  };

  const ready = value.platforms.length > 0 && FIELDS.every((f) => value.brand[f.name].trim().length >= 3);

  return (
    <form
      className="card space-y-5 p-5 sm:p-6"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready && !isRunning) onSubmit();
      }}
    >
      <div>
        <h2 className="text-base font-semibold">Your brand</h2>
        <p className="hint">Saved in this browser so you only type it once.</p>
      </div>

      {FIELDS.map((f) => (
        <div key={f.name}>
          <label htmlFor={f.name} className="label">{f.label}</label>
          <textarea
            id={f.name}
            rows={f.rows}
            className="field resize-y"
            placeholder={f.placeholder}
            value={value.brand[f.name]}
            onChange={(e) => setBrand(f.name, e.target.value)}
            required
            minLength={3}
          />
        </div>
      ))}

      <div>
        <button
          type="button"
          onClick={() => setShowVoice((s) => !s)}
          className="flex w-full items-center justify-between text-sm font-medium text-ink"
          aria-expanded={showVoice}
        >
          <span>Teach it your voice <span className="font-normal text-muted">(optional)</span></span>
          <ChevronDown className={`size-4 text-muted transition ${showVoice ? 'rotate-180' : ''}`} />
        </button>
        {showVoice && (
          <>
            <textarea
              rows={6}
              className="field resize-y"
              placeholder="Paste 3-10 of your own past posts. The writer will mirror your style."
              value={value.brand.past_posts}
              onChange={(e) => setBrand('past_posts', e.target.value)}
            />
            <p className="hint">The more real examples, the less it sounds like AI.</p>
          </>
        )}
      </div>

      <hr className="border-line" />

      <fieldset>
        <legend className="label">Platforms</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {PLATFORMS.map((p) => {
            const on = value.platforms.includes(p.id);
            return (
              <button
                key={p.id}
                type="button"
                aria-pressed={on}
                onClick={() => togglePlatform(p.id)}
                className={`rounded-full border px-3 py-1.5 text-sm transition ${
                  on ? 'border-accent bg-accent-soft text-accent' : 'border-line bg-white text-muted hover:text-ink'
                }`}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      </fieldset>

      <div>
        <label htmlFor="topic" className="label">Topic for this run <span className="font-normal text-muted">(optional)</span></label>
        <input
          id="topic"
          className="field"
          placeholder="Leave empty and the planner picks a timely angle from your pillars"
          value={value.topic}
          onChange={(e) => onChange({ ...value, topic: e.target.value })}
        />
      </div>

      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <div>
          <label htmlFor="variants" className="label">Variants per platform</label>
          <select
            id="variants"
            className="field w-24"
            value={value.variants}
            onChange={(e) => onChange({ ...value, variants: Number(e.target.value) })}
          >
            {[1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        {hasProfile && (
          <label className="flex items-center gap-2 pb-2 text-sm text-ink">
            <input
              type="checkbox"
              className="size-4 accent-accent"
              checked={reuseProfile}
              onChange={(e) => onReuseProfile(e.target.checked)}
            />
            Reuse saved brand profile
          </label>
        )}
      </div>

      <button type="submit" className="btn-primary w-full" disabled={!ready || isRunning}>
        <Sparkles className="size-4" />
        {isRunning ? 'Working…' : `Generate for ${value.platforms.length || 0} platform${value.platforms.length === 1 ? '' : 's'}`}
      </button>
    </form>
  );
}
