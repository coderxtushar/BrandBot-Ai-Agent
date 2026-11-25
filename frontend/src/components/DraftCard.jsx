import { useEffect, useState } from 'react';
import { History, LoaderCircle, Pencil, RotateCcw, Sparkles, ThumbsDown, ThumbsUp } from 'lucide-react';
import { REWRITE_PRESETS, api } from '../lib/api';
import CopyButton from './CopyButton';
import DraftEditor from './DraftEditor';
import Preview from './Previews';

const SOURCE_LABEL = {
  generated: 'Generated',
  edited: 'Edited by you',
  rewrite: 'AI rewrite',
  regenerate: 'Fresh draft',
  restored: 'Restored',
};

const when = (iso) => new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

function StatusBadge({ status }) {
  if (status === 'approved') return <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">Approved</span>;
  if (status === 'rejected') return <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">Rejected</span>;
  return null;
}

function Action({ icon, label, active, ...props }) {
  const Icon = icon;
  return (
    <button
      type="button"
      className={`btn-ghost px-2.5 py-1.5 text-xs ${active ? 'border-accent bg-accent-soft text-accent' : ''}`}
      aria-pressed={active}
      {...props}
    >
      <Icon className="size-3.5" />
      <span>{label}</span>
    </button>
  );
}

function RewritePanel({ onRewrite, busy }) {
  const [instruction, setInstruction] = useState('');
  const go = (body) => onRewrite({ instruction: instruction.trim(), ...body });
  return (
    <div className="space-y-3 rounded-lg bg-canvas p-3">
      <div className="flex flex-wrap gap-2">
        {REWRITE_PRESETS.map((p) => (
          <button key={p.id} type="button" className="btn-ghost px-3 py-1.5 text-xs" disabled={busy} onClick={() => go({ preset: p.id })}>
            {p.label}
          </button>
        ))}
      </div>
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          if (instruction.trim()) go({});
        }}
      >
        <label htmlFor="rewrite-instruction" className="sr-only">Rewrite instruction</label>
        <input
          id="rewrite-instruction"
          className="field mt-0 flex-1"
          placeholder="Or say what to change, e.g. “mention our launch next week”"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          maxLength={500}
        />
        <button type="submit" className="btn-primary px-3 py-2 text-xs" disabled={busy || !instruction.trim()}>Rewrite</button>
      </form>
      <button type="button" className="text-xs text-accent hover:underline disabled:opacity-50" disabled={busy} onClick={() => go({ fresh: true })}>
        Write a completely new draft instead{instruction.trim() ? ' (using your note)' : ''}
      </button>
    </div>
  );
}

function Versions({ draftId, onRestore, busy }) {
  const [versions, setVersions] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let live = true;
    api.listVersions(draftId).then(
      (v) => live && setVersions(v),
      (e) => live && setError(e.message),
    );
    return () => { live = false; };
  }, [draftId]);

  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (!versions) return <p className="text-sm text-muted">Loading history…</p>;

  return (
    <ol className="space-y-2 rounded-lg bg-canvas p-3">
      {versions.map((v, i) => (
        <li key={v.id} className="flex items-start justify-between gap-3 text-sm">
          <div className="min-w-0">
            <p className="font-medium">
              {SOURCE_LABEL[v.source] ?? v.source}
              {i === 0 && <span className="ml-2 text-xs font-normal text-muted">current</span>}
            </p>
            <p className="text-xs text-muted">{when(v.created_at)}{v.note ? ` · ${v.note}` : ''}</p>
            <p className="mt-1 line-clamp-2 text-xs text-muted">{v.text}</p>
          </div>
          {i > 0 && (
            <button type="button" className="btn-ghost shrink-0 px-2.5 py-1 text-xs" disabled={busy} onClick={() => onRestore(v.id)}>
              <RotateCcw className="size-3.5" /> Restore
            </button>
          )}
        </li>
      ))}
    </ol>
  );
}

/** One draft (variant) with its editing loop. */
export default function DraftCard({ title, platform, item, text, draft, onUpdated }) {
  const [mode, setMode] = useState(null); // null | 'edit' | 'rewrite' | 'history'
  const [busy, setBusy] = useState(null); // null | 'rewrite' | 'status' | 'restore'
  const [error, setError] = useState(null);
  const [versionsKey, setVersionsKey] = useState(0);

  const act = async (kind, fn) => {
    setBusy(kind);
    setError(null);
    try {
      const updated = await fn();
      onUpdated(updated);
      setVersionsKey((k) => k + 1);
      return updated;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setBusy(null);
    }
  };

  const toggle = (m) => setMode((cur) => (cur === m ? null : m));
  const setStatus = (status) =>
    act('status', () => api.updateDraft(draft.id, { status: draft.status === status ? 'draft' : status })).catch(() => {});
  const rewrite = (body) => act('rewrite', () => api.rewriteDraft(draft.id, body)).then(() => setMode(null), () => {});
  const restore = (versionId) => act('restore', () => api.restoreVersion(draft.id, versionId)).catch(() => {});
  const saveEdit = (content) => act('edit', () => api.updateDraft(draft.id, { content })).then(() => setMode(null));

  return (
    <section className="card p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-muted">{title}</h3>
          <StatusBadge status={draft.status} />
          {draft.review && (
            <span className={`text-xs ${draft.review.approved ? 'text-emerald-700' : 'text-amber-700'}`}>
              Re-reviewed · {draft.review.score}/10
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Action icon={ThumbsUp} label="Approve" active={draft.status === 'approved'} disabled={!!busy} onClick={() => setStatus('approved')} />
          <Action icon={ThumbsDown} label="Reject" active={draft.status === 'rejected'} disabled={!!busy} onClick={() => setStatus('rejected')} />
          <Action icon={Pencil} label="Edit" active={mode === 'edit'} disabled={!!busy} onClick={() => toggle('edit')} />
          <Action icon={Sparkles} label="Rewrite" active={mode === 'rewrite'} disabled={!!busy} onClick={() => toggle('rewrite')} />
          <Action icon={History} label="History" active={mode === 'history'} disabled={!!busy} onClick={() => toggle('history')} />
          <CopyButton text={text} />
        </div>
      </div>

      {draft.lint?.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-[13px] text-amber-900">
          <p className="font-medium">Breaks platform rules</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">{draft.lint.map((i, n) => <li key={n}>{i}</li>)}</ul>
        </div>
      )}

      {draft.review && !draft.review.approved && draft.review.issues.length > 0 && (
        <ul className="mb-4 list-disc space-y-1 rounded-lg bg-amber-50 p-3 pl-7 text-[13px] text-amber-900">
          {draft.review.issues.map((i, n) => <li key={n}>{i}</li>)}
        </ul>
      )}

      {mode === 'rewrite' && <div className="mb-4"><RewritePanel onRewrite={rewrite} busy={!!busy} /></div>}
      {mode === 'history' && <div className="mb-4"><Versions key={versionsKey} draftId={draft.id} onRestore={restore} busy={!!busy} /></div>}
      {error && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}

      {busy === 'rewrite' ? (
        <div className="flex min-h-40 flex-col items-center justify-center gap-2 text-sm text-muted">
          <LoaderCircle className="size-5 animate-spin text-accent" />
          Rewriting, and the editor agent is reviewing it…
        </div>
      ) : mode === 'edit' ? (
        <DraftEditor key={text} draftId={draft.id} content={item} onSave={saveEdit} onCancel={() => setMode(null)} />
      ) : (
        // overflow-wrap:anywhere keeps long URLs or unbroken words inside the card
        <div className="min-w-0 [overflow-wrap:anywhere]">
          <Preview platform={platform} item={item} />
        </div>
      )}
    </section>
  );
}
