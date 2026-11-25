import { useState } from 'react';
import { ChevronDown, Pencil } from 'lucide-react';

const lines = (list) => list.join('\n');
const fromLines = (text) => text.split('\n').map((s) => s.trim()).filter(Boolean);
const fromCommas = (text) => text.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
const fromTags = (text) => text.split(/[\s,]+/).map((s) => s.replace(/^#/, '').trim()).filter(Boolean);

function toDraft(p) {
  return {
    positioning: p.positioning,
    audience_persona: p.audience_persona,
    traits: p.voice.traits.join(', '),
    do: lines(p.voice.do),
    dont: lines(p.voice.dont),
    pillars: lines(p.pillars),
    hashtags: p.hashtags.map((h) => `#${h}`).join(' '),
  };
}

function fromDraft(d) {
  return {
    positioning: d.positioning.trim(),
    audience_persona: d.audience_persona.trim(),
    voice: { traits: fromCommas(d.traits), do: fromLines(d.do), dont: fromLines(d.dont) },
    pillars: fromLines(d.pillars),
    hashtags: fromTags(d.hashtags),
  };
}

const FIELDS = [
  { key: 'positioning', label: 'Positioning', rows: 3 },
  { key: 'audience_persona', label: 'Audience persona', rows: 3 },
  { key: 'traits', label: 'Voice traits', rows: 1, hint: 'Comma-separated' },
  { key: 'do', label: 'Do', rows: 3, hint: 'One per line' },
  { key: 'dont', label: "Don't", rows: 3, hint: 'One per line' },
  { key: 'pillars', label: 'Content pillars', rows: 3, hint: 'One per line' },
  { key: 'hashtags', label: 'Hashtag bank', rows: 2 },
];

/** View and hand-edit the brand profile that every run is written from. */
export default function ProfileEditor({ profile, onSave, disabled }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(null); // non-null while editing
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const startEdit = () => {
    setDraft(toDraft(profile));
    setOpen(true);
    setError(null);
  };

  const save = async () => {
    const next = fromDraft(draft);
    if (!next.positioning || !next.audience_persona || next.pillars.length === 0) {
      setError('Positioning, audience persona and at least one pillar are required.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSave(next);
      setDraft(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex flex-1 items-center gap-2 text-left"
          aria-expanded={open}
        >
          <h2 className="text-base font-semibold">Brand profile</h2>
          <ChevronDown className={`size-4 text-muted transition ${open ? 'rotate-180' : ''}`} />
        </button>
        {!draft && (
          <button type="button" className="btn-ghost px-3 py-1.5 text-xs" onClick={startEdit} disabled={disabled}>
            <Pencil className="size-3.5" /> Edit
          </button>
        )}
      </div>
      {!open && <p className="mt-2 line-clamp-2 text-sm text-muted">{profile.positioning}</p>}

      {open && !draft && (
        <dl className="mt-3 space-y-3 text-sm">
          <div><dt className="font-medium">Positioning</dt><dd className="text-muted">{profile.positioning}</dd></div>
          <div><dt className="font-medium">Audience</dt><dd className="text-muted">{profile.audience_persona}</dd></div>
          <div><dt className="font-medium">Voice</dt><dd className="text-muted">{profile.voice.traits.join(', ')}</dd></div>
          <div><dt className="font-medium">Pillars</dt><dd className="text-muted">{profile.pillars.join(' · ')}</dd></div>
          <div><dt className="font-medium">Hashtags</dt><dd className="text-accent">{profile.hashtags.map((h) => `#${h}`).join(' ')}</dd></div>
        </dl>
      )}

      {draft && (
        <form
          className="mt-3 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <p className="hint">Your edits are used for every future run, until you change the brand details above.</p>
          {FIELDS.map((f) => (
            <div key={f.key}>
              <label htmlFor={`profile-${f.key}`} className="label">
                {f.label} {f.hint && <span className="font-normal text-muted">({f.hint})</span>}
              </label>
              <textarea
                id={`profile-${f.key}`}
                rows={f.rows}
                className="field resize-y"
                value={draft[f.key]}
                onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
              />
            </div>
          ))}
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <div className="flex gap-2">
            <button type="submit" className="btn-primary flex-1" disabled={saving}>
              {saving ? 'Saving…' : 'Save profile'}
            </button>
            <button type="button" className="btn-ghost" onClick={() => setDraft(null)} disabled={saving}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
