import { Check, CircleAlert, LoaderCircle } from 'lucide-react';
import { platformLabel } from '../lib/api';

function Dot({ status }) {
  if (status === 'done' || status === 'reused') return <Check className="size-4 text-emerald-600" />;
  if (status === 'warn') return <CircleAlert className="size-4 text-amber-600" />;
  if (status === 'running') return <LoaderCircle className="size-4 animate-spin text-accent" />;
  return <span className="mx-1 block size-2 rounded-full bg-line" />;
}

function Row({ status, title, detail }) {
  return (
    <li className="flex gap-3">
      <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center"><Dot status={status} /></span>
      <div className="min-w-0">
        <p className={`text-sm ${status ? 'text-ink' : 'text-muted'}`}>{title}</p>
        {detail && <p className="mt-0.5 text-xs text-muted">{detail}</p>}
      </div>
    </li>
  );
}

const STAGE_TEXT = {
  queued: 'Waiting',
  writing: 'Writing',
  reviewing: 'Reviewing',
  revising: 'Revising after feedback',
};

export default function Progress({ progress }) {
  const { profile, planning, research, platforms } = progress;
  return (
    <div className="card p-5 sm:p-6">
      <h2 className="text-base font-semibold">Working on it</h2>
      <ol className="mt-4 space-y-3">
        <Row
          status={profile?.status}
          title={profile?.status === 'reused' ? 'Using your saved brand profile' : 'Building your brand profile'}
        />
        <Row status={planning?.status} title="Choosing today's angle" detail={planning?.angle} />
        <Row
          status={research?.status}
          title="Researching the web"
          detail={
            research?.status === 'done'
              ? `${research.count} sources found`
              : research?.queries?.map((q) => `“${q}”`).join(' · ')
          }
        />
        {Object.entries(platforms).map(([id, p]) => {
          const status = p.stage === 'done' ? (p.approved ? 'done' : 'warn') : p.stage === 'queued' ? null : 'running';
          const detail =
            p.stage === 'done'
              ? p.approved ? 'Approved by reviewer' : 'Finished, check reviewer notes'
              : STAGE_TEXT[p.stage] + (p.attempt > 1 ? ` (attempt ${p.attempt})` : '');
          return <Row key={id} status={status} title={platformLabel(id)} detail={detail} />;
        })}
      </ol>
    </div>
  );
}
