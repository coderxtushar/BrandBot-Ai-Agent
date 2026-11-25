import { useEffect, useReducer, useRef, useState } from 'react';
import { CircleAlert, Square } from 'lucide-react';
import BrandForm from './components/BrandForm';
import Progress from './components/Progress';
import { initialProgress, progressReducer } from './lib/progress';
import Results from './components/Results';
import { streamRun } from './lib/api';
import { load, save } from './lib/storage';

const EMPTY_FORM = {
  brand: { target_audience: '', expertise: '', tone_of_voice: '', content_pillars: '', past_posts: '' },
  platforms: ['linkedin', 'x'],
  topic: '',
  variants: 1,
};

export default function App() {
  const [form, setForm] = useState(() => {
    const saved = load('brandbot.form', null);
    return saved ? { ...EMPTY_FORM, ...saved, brand: { ...EMPTY_FORM.brand, ...saved.brand } } : EMPTY_FORM;
  });
  const [profile, setProfile] = useState(() => load('brandbot.profile', null));
  const [reuseProfile, setReuseProfile] = useState(true);
  const [progress, dispatch] = useReducer(progressReducer, initialProgress);
  const [status, setStatus] = useState('idle'); // idle | running | done | error
  const [result, setResult] = useState(() => load('brandbot.lastResult', null));
  const [error, setError] = useState(null);
  const [runId, setRunId] = useState(0);
  const abortRef = useRef(null);

  useEffect(() => save('brandbot.form', form), [form]);

  // Editing the brand invalidates the saved profile.
  const handleFormChange = (next) => {
    if (profile && JSON.stringify(next.brand) !== JSON.stringify(form.brand)) {
      setProfile(null);
      save('brandbot.profile', null);
    }
    setForm(next);
  };

  const run = async () => {
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus('running');
    setError(null);
    dispatch({ reset: true, platforms: form.platforms });

    try {
      const data = await streamRun(
        { ...form, brand_profile: reuseProfile && profile ? profile : null },
        { onProgress: dispatch, signal: controller.signal },
      );
      setResult(data);
      setProfile(data.brand_profile);
      save('brandbot.profile', data.brand_profile);
      save('brandbot.lastResult', data);
      setRunId((n) => n + 1);
      setStatus('done');
    } catch (err) {
      if (err.name === 'AbortError') {
        setStatus('idle');
        return;
      }
      setError(
        err instanceof TypeError
          ? 'Could not reach the API. Is the backend running on port 8000?'
          : err.message,
      );
      setStatus('error');
    }
  };

  const running = status === 'running';

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Brand Bot</h1>
            <p className="text-xs text-muted">Researched, platform-native content in your voice</p>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[400px_1fr] lg:py-8">
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <BrandForm
            value={form}
            onChange={handleFormChange}
            onSubmit={run}
            isRunning={running}
            hasProfile={Boolean(profile)}
            reuseProfile={reuseProfile}
            onReuseProfile={setReuseProfile}
          />
        </aside>

        <section className="min-w-0 space-y-6">
          {running && (
            <>
              <Progress progress={progress} />
              <button type="button" className="btn-ghost" onClick={() => abortRef.current?.abort()}>
                <Square className="size-3.5" /> Stop
              </button>
            </>
          )}

          {status === 'error' && (
            <div role="alert" className="flex gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              <CircleAlert className="mt-0.5 size-4 shrink-0" />
              <p>{error}</p>
            </div>
          )}

          {!running && result && <Results key={runId} data={result} />}

          {!running && !result && status !== 'error' && (
            <div className="card flex min-h-80 flex-col items-center justify-center p-8 text-center">
              <p className="font-medium">Your content will appear here</p>
              <p className="mt-1 max-w-sm text-sm text-muted">
                Describe your brand, pick platforms, and Brand Bot will research a timely angle, write for each
                platform, and have an editor agent review every draft.
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
