import Markdown from 'react-markdown';
import { Download } from 'lucide-react';

const tags = (list = []) => list.map((t) => `#${t.replace(/^#/, '').replace(/\s+/g, '')}`).join(' ');

function Avatar() {
  return <div className="size-10 shrink-0 rounded-full bg-gradient-to-br from-slate-200 to-slate-300" />;
}

function Counter({ value, max }) {
  const over = value > max;
  return <span className={`text-[11px] tabular-nums ${over ? 'font-medium text-red-600' : 'text-muted'}`}>{value}/{max}</span>;
}

function LinkedIn({ item }) {
  const full = `${item.hook}\n\n${item.body}\n\n${item.closing_question}`;
  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="min-w-0 flex-1 whitespace-pre-wrap text-sm leading-6">
        <p className="font-semibold">{item.hook}</p>
        <p className="mt-3">{item.body}</p>
        <p className="mt-3">{item.closing_question}</p>
        <p className="mt-3 text-accent">{tags(item.hashtags)}</p>
        <div className="mt-2 text-right"><Counter value={full.length + tags(item.hashtags).length + 2} max={3000} /></div>
      </div>
    </div>
  );
}

function XThread({ item }) {
  const n = item.tweets.length;
  return (
    <ol className="space-y-0">
      {item.tweets.map((t, i) => {
        const text = (i > 0 && n > 1 ? `${i + 1}/${n} ` : '') + t + (i === n - 1 && item.hashtags?.length ? ` ${tags(item.hashtags)}` : '');
        return (
          <li key={i} className="flex gap-3">
            <div className="flex flex-col items-center">
              <Avatar />
              {i < n - 1 && <div className="w-px flex-1 bg-line" />}
            </div>
            <div className="min-w-0 flex-1 pb-4">
              <p className="whitespace-pre-wrap text-sm leading-6">{text}</p>
              <div className="mt-1 text-right"><Counter value={text.length} max={280} /></div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function Threads({ item }) {
  return (
    <ol>
      {item.posts.map((p, i) => (
        <li key={i} className="flex gap-3">
          <div className="flex flex-col items-center">
            <Avatar />
            {i < item.posts.length - 1 && <div className="w-px flex-1 bg-line" />}
          </div>
          <div className="min-w-0 flex-1 pb-4">
            <p className="whitespace-pre-wrap text-sm leading-6">{p}</p>
            {i === 0 && item.topic_tag && <p className="mt-1 text-sm text-muted">› {item.topic_tag}</p>}
            <div className="mt-1 text-right"><Counter value={p.length} max={500} /></div>
          </div>
        </li>
      ))}
    </ol>
  );
}

function Instagram({ item }) {
  return (
    <div className="space-y-4">
      <div className="-mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-2">
        {item.slides.map((s, i) => (
          <div
            key={i}
            className="flex aspect-[4/5] w-48 shrink-0 snap-start flex-col justify-between rounded-lg bg-gradient-to-br from-slate-800 to-slate-950 p-4 text-white"
          >
            <span className="text-[10px] text-white/50">{i + 1}/{item.slides.length}</span>
            <div>
              <p className="text-base font-bold leading-tight">{s.headline}</p>
              <p className="mt-2 text-xs leading-snug text-white/75">{s.text}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="text-sm leading-6">
        <p className="whitespace-pre-wrap">{item.caption}</p>
        <p className="mt-2 text-accent">{tags(item.hashtags)}</p>
      </div>
      <details className="rounded-lg bg-canvas p-3 text-xs text-muted">
        <summary className="cursor-pointer font-medium text-ink">Cover image prompt &amp; alt text</summary>
        <p className="mt-2"><span className="font-medium text-ink">Prompt:</span> {item.image_prompt}</p>
        <p className="mt-1"><span className="font-medium text-ink">Alt text:</span> {item.alt_text}</p>
      </details>
    </div>
  );
}

function downloadMarkdown(item) {
  const md = `# ${item.title}\n\n_${item.subtitle}_\n\n${item.body_markdown}\n`;
  const url = URL.createObjectURL(new Blob([md], { type: 'text/markdown' }));
  const a = Object.assign(document.createElement('a'), {
    href: url,
    download: `${item.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 60) || 'article'}.md`,
  });
  a.click();
  URL.revokeObjectURL(url);
}

function Medium({ item }) {
  const words = item.body_markdown.split(/\s+/).filter(Boolean).length;
  return (
    <article className="prose-medium mx-auto max-w-prose font-serif text-[15px] text-ink">
      <h1 className="font-sans">{item.title}</h1>
      <p className="mt-1 font-sans text-base text-muted">{item.subtitle}</p>
      <div className="mt-2 flex items-center justify-between font-sans text-xs text-muted">
        <span>{words} words · {Math.max(1, Math.round(words / 230))} min read</span>
        <button type="button" onClick={() => downloadMarkdown(item)} className="btn-ghost px-3 py-1.5 text-xs">
          <Download className="size-3.5" /> .md
        </button>
      </div>
      <hr className="my-4 border-line" />
      <Markdown>{item.body_markdown}</Markdown>
      <div className="mt-6 flex flex-wrap gap-2 font-sans">
        {item.tags.map((t) => <span key={t} className="rounded-full bg-canvas px-3 py-1 text-xs">{t}</span>)}
      </div>
    </article>
  );
}

function Shorts({ item }) {
  const words = item.hook.split(/\s+/).length + item.beats.reduce((n, b) => n + b.voiceover.split(/\s+/).length, 0);
  return (
    <div className="space-y-4 text-sm">
      <div>
        <p className="font-semibold">{item.title}</p>
        <p className="text-xs text-muted">~{Math.round(words / 2.5)}s of voiceover · {words} words</p>
      </div>
      <div className="rounded-lg bg-accent-soft p-3">
        <p className="text-xs font-medium text-accent">HOOK · 0–2s</p>
        <p className="mt-1 font-medium">{item.hook}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-xs">
          <thead className="text-muted">
            <tr className="border-b border-line">
              <th className="py-2 pr-3 font-medium">Time</th>
              <th className="py-2 pr-3 font-medium">Voiceover</th>
              <th className="py-2 pr-3 font-medium">On screen</th>
              <th className="py-2 font-medium">Visual</th>
            </tr>
          </thead>
          <tbody>
            {item.beats.map((b, i) => (
              <tr key={i} className="border-b border-line align-top last:border-0">
                <td className="py-2 pr-3 whitespace-nowrap tabular-nums text-muted">{b.seconds}s</td>
                <td className="py-2 pr-3 leading-5">{b.voiceover}</td>
                <td className="py-2 pr-3 font-medium leading-5">{b.on_screen_text}</td>
                <td className="py-2 leading-5 text-muted">{b.visual}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p><span className="font-medium">CTA:</span> {item.cta}</p>
      <div className="rounded-lg bg-canvas p-3 text-xs">
        <p className="font-medium">Description</p>
        <p className="mt-1 whitespace-pre-wrap text-muted">{item.description}</p>
        <p className="mt-2 text-accent">{tags(item.hashtags)}</p>
      </div>
    </div>
  );
}

const PREVIEWS = {
  linkedin: LinkedIn,
  x: XThread,
  threads: Threads,
  instagram: Instagram,
  medium: Medium,
  youtube_shorts: Shorts,
};

export default function Preview({ platform, item }) {
  const Component = PREVIEWS[platform];
  return Component ? <Component item={item} /> : <pre className="text-xs">{JSON.stringify(item, null, 2)}</pre>;
}
