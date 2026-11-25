import { useState } from 'react';
import { Plus, X } from 'lucide-react';

/*
 * One editor for every platform: it walks the draft's own structure.
 *   string            -> textarea
 *   hashtags / tags   -> space-separated input
 *   list of strings   -> one textarea per item (tweets, Threads posts)
 *   list of objects   -> a group of fields per item (carousel slides, Shorts beats)
 */

const TAG_KEYS = new Set(['hashtags', 'tags']);
const LONG_KEYS = { body: 8, body_markdown: 16, caption: 6, description: 4, image_prompt: 3 };

const humanize = (key) => key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
const singular = (key) => humanize(key).replace(/s$/, '');

function TagInput({ id, value, onChange }) {
  const [raw, setRaw] = useState(() => value.map((t) => `#${t}`).join(' '));
  return (
    <input
      id={id}
      className="field"
      value={raw}
      onChange={(e) => {
        setRaw(e.target.value);
        onChange(e.target.value.split(/[\s,]+/).map((t) => t.replace(/^#/, '')).filter(Boolean));
      }}
    />
  );
}

function Text({ id, name, value, onChange }) {
  return (
    <textarea
      id={id}
      rows={LONG_KEYS[name] ?? (value.length > 90 ? 3 : 2)}
      className={`field resize-y ${name === 'body_markdown' ? 'font-mono text-xs' : ''}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

function ListControls({ onRemove, label }) {
  return (
    <button type="button" onClick={onRemove} className="rounded p-1 text-muted hover:bg-canvas hover:text-red-600" aria-label={`Remove ${label}`}>
      <X className="size-3.5" />
    </button>
  );
}

function Field({ path, name, value, onChange }) {
  const id = `edit-${path}`;

  if (typeof value === 'string') {
    return (
      <div>
        <label htmlFor={id} className="label">{humanize(name)}</label>
        <Text id={id} name={name} value={value} onChange={onChange} />
      </div>
    );
  }

  if (Array.isArray(value) && TAG_KEYS.has(name)) {
    return (
      <div>
        <label htmlFor={id} className="label">{humanize(name)}</label>
        <TagInput id={id} value={value} onChange={onChange} />
      </div>
    );
  }

  if (Array.isArray(value)) {
    const objects = value.length > 0 && typeof value[0] === 'object';
    const blank = objects ? Object.fromEntries(Object.keys(value[0]).map((k) => [k, ''])) : '';
    const set = (i, v) => onChange(value.map((x, j) => (j === i ? v : x)));
    return (
      <fieldset>
        <legend className="label">{humanize(name)} <span className="font-normal text-muted">({value.length})</span></legend>
        <div className="mt-1.5 space-y-2">
          {value.map((item, i) => (
            <div key={i} className={objects ? 'rounded-lg border border-line p-3' : 'flex items-start gap-1'}>
              {objects ? (
                <>
                  <div className="mb-1 flex items-center justify-between text-xs text-muted">
                    <span>{singular(name)} {i + 1}</span>
                    <ListControls label={`${singular(name)} ${i + 1}`} onRemove={() => onChange(value.filter((_, j) => j !== i))} />
                  </div>
                  <div className="space-y-2">
                    {Object.entries(item).map(([k, v]) => (
                      <Field key={k} path={`${path}-${i}-${k}`} name={k} value={v} onChange={(nv) => set(i, { ...item, [k]: nv })} />
                    ))}
                  </div>
                </>
              ) : (
                <>
                  <textarea
                    aria-label={`${singular(name)} ${i + 1}`}
                    rows={2}
                    className="field mt-0 resize-y"
                    value={item}
                    onChange={(e) => set(i, e.target.value)}
                  />
                  <ListControls label={`${singular(name)} ${i + 1}`} onRemove={() => onChange(value.filter((_, j) => j !== i))} />
                </>
              )}
            </div>
          ))}
          <button type="button" className="btn-ghost px-3 py-1.5 text-xs" onClick={() => onChange([...value, blank])}>
            <Plus className="size-3.5" /> Add {singular(name).toLowerCase()}
          </button>
        </div>
      </fieldset>
    );
  }

  return null; // numbers/booleans don't occur in content models
}

export default function DraftEditor({ draftId, content, onSave, onCancel }) {
  const [value, setValue] = useState(content);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSave(value);
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  };

  return (
    <form onSubmit={save} className="space-y-4">
      {Object.entries(value).map(([k, v]) => (
        <Field key={k} path={`${draftId}-${k}`} name={k} value={v} onChange={(nv) => setValue({ ...value, [k]: nv })} />
      ))}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</button>
        <button type="button" className="btn-ghost" onClick={onCancel} disabled={saving}>Cancel</button>
      </div>
    </form>
  );
}
