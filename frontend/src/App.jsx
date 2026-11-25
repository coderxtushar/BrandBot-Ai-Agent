import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { CircleAlert, Square } from 'lucide-react';
import BrandBar from './components/BrandBar';
import BrandForm from './components/BrandForm';
import History from './components/History';
import ProfileEditor from './components/ProfileEditor';
import Progress from './components/Progress';
import Results from './components/Results';
import { api, streamBrandRun } from './lib/api';
import { EMPTY_BRAND_INPUT, NEW_BRAND, brandInput, sameInput } from './lib/brands';
import { initialProgress, progressReducer } from './lib/progress';
import { load, save } from './lib/storage';

const DEFAULT_SETTINGS = { platforms: ['linkedin', 'x'], topic: '', variants: 1 };

function initialForm() {
  const settings = { ...DEFAULT_SETTINGS, ...load('brandbot.settings', {}) };
  // Pre-fill from the pre-database version of the app, if the user had typed a brand there.
  const legacy = load('brandbot.form', null);
  return { name: '', brand: { ...EMPTY_BRAND_INPUT, ...(legacy?.brand ?? {}) }, ...settings };
}

export default function App() {
  const [brands, setBrands] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [reuseProfile, setReuseProfile] = useState(true);

  const [runs, setRuns] = useState([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [result, setResult] = useState(null);

  const [progress, dispatch] = useReducer(progressReducer, initialProgress);
  const [status, setStatus] = useState('loading'); // loading | idle | running | error
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const activeBrand = brands.find((b) => b.id === activeId) ?? null;
  const inputChanged = activeBrand ? !sameInput(form.brand, brandInput(activeBrand)) : true;
  const profileUpdatedAt = activeBrand && !inputChanged ? activeBrand.profile_updated_at : null;
  const running = status === 'running';

  // Run settings (platforms, topic, variants) are a per-browser convenience.
  useEffect(() => {
    save('brandbot.settings', { platforms: form.platforms, topic: form.topic, variants: form.variants });
  }, [form.platforms, form.topic, form.variants]);

  const fail = (err) => {
    setError(err instanceof TypeError ? 'Could not reach the API. Is the backend running?' : err.message);
    setStatus('error');
  };

  const loadRuns = useCallback(async (brandId, { openLatest = false } = {}) => {
    setRunsLoading(true);
    try {
      const list = await api.listRuns(brandId);
      setRuns(list);
      if (openLatest) {
        const latest = list.find((r) => r.status === 'completed');
        setResult(latest ? await api.getRun(latest.id) : null);
      }
    } finally {
      setRunsLoading(false);
    }
  }, []);

  const openBrand = useCallback(
    (brand) => {
      setActiveId(brand.id);
      save('brandbot.activeBrand', brand.id);
      setForm((f) => ({ ...f, name: brand.name, brand: brandInput(brand) }));
      setResult(null);
      setRuns([]);
      return loadRuns(brand.id, { openLatest: true });
    },
    [loadRuns],
  );

  const startNewBrand = () => {
    setActiveId(NEW_BRAND);
    setForm((f) => ({ ...f, name: '', brand: { ...EMPTY_BRAND_INPUT } }));
    setRuns([]);
    setResult(null);
  };

  // Initial load.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await api.listBrands();
        if (cancelled) return;
        setBrands(list);
        const saved = list.find((b) => b.id === load('brandbot.activeBrand', null));
        if (saved || list[0]) await openBrand(saved ?? list[0]);
        else setActiveId(NEW_BRAND);
        setStatus('idle');
      } catch (err) {
        if (!cancelled) fail(err);
      }
    })();
    return () => { cancelled = true; };
  }, [openBrand]);

  const selectBrand = (id) => {
    if (id === NEW_BRAND) return startNewBrand();
    const brand = brands.find((b) => b.id === id);
    if (brand) openBrand(brand).catch(fail);
  };

  const deleteBrand = async () => {
    if (!activeBrand || !window.confirm(`Delete “${activeBrand.name}” and all of its runs?`)) return;
    try {
      await api.deleteBrand(activeBrand.id);
      const rest = brands.filter((b) => b.id !== activeBrand.id);
      setBrands(rest);
      if (rest[0]) await openBrand(rest[0]);
      else startNewBrand();
    } catch (err) {
      fail(err);
    }
  };

  /** Create or update the brand so the server has exactly what's in the form. */
  const saveBrand = async () => {
    const name = form.name.trim();
    if (!activeBrand) {
      const created = await api.createBrand(name, form.brand);
      setBrands((list) => [created, ...list]);
      setActiveId(created.id);
      save('brandbot.activeBrand', created.id);
      save('brandbot.form', null); // legacy pre-fill no longer needed
      return created;
    }
    if (name === activeBrand.name && !inputChanged) return activeBrand;
    const updated = await api.updateBrand(activeBrand.id, { name, input: form.brand });
    setBrands((list) => list.map((b) => (b.id === updated.id ? updated : b)));
    return updated;
  };

  const run = async () => {
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus('running');
    setError(null);
    dispatch({ reset: true, platforms: form.platforms });
    let brandId = activeBrand?.id;

    try {
      const brand = await saveBrand();
      brandId = brand.id;
      const detail = await streamBrandRun(
        brand.id,
        {
          platforms: form.platforms,
          topic: form.topic,
          variants: form.variants,
          regenerate_profile: !reuseProfile,
        },
        { onProgress: dispatch, signal: controller.signal },
      );
      setResult(detail);
      setStatus('idle');
      // The run may have created/updated the profile.
      const fresh = await api.listBrands();
      setBrands(fresh);
      await loadRuns(brand.id);
    } catch (err) {
      if (err.name === 'AbortError') setStatus('idle');
      else fail(err);
      if (brandId) loadRuns(brandId).catch(() => {});
    }
  };

  const saveProfile = async (profile) => {
    const updated = await api.saveProfile(activeBrand.id, profile);
    setBrands((list) => list.map((b) => (b.id === updated.id ? updated : b)));
    setReuseProfile(true);
  };

  const openRun = async (id) => {
    try {
      setResult(await api.getRun(id));
    } catch (err) {
      fail(err);
    }
  };

  const deleteRun = async (id) => {
    if (!window.confirm('Delete this run?')) return;
    try {
      await api.deleteRun(id);
      const rest = runs.filter((r) => r.id !== id);
      setRuns(rest);
      if (result?.id === id) {
        // Show the next most recent completed run instead of an empty panel.
        const next = rest.find((r) => r.status === 'completed');
        setResult(next ? await api.getRun(next.id) : null);
      }
    } catch (err) {
      fail(err);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Brand Bot</h1>
            <p className="text-xs text-muted">Researched, platform-native content in your voice</p>
          </div>
          {status !== 'loading' && (brands.length > 0 || activeId === NEW_BRAND) && (
            <BrandBar
              brands={brands}
              activeId={activeId}
              onSelect={selectBrand}
              onDelete={deleteBrand}
              disabled={running}
            />
          )}
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[400px_1fr] lg:py-8">
        <aside className="space-y-6 lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto">
          <BrandForm
            value={form}
            onChange={setForm}
            onSubmit={run}
            isRunning={running}
            isNew={!activeBrand}
            profileUpdatedAt={profileUpdatedAt}
            reuseProfile={reuseProfile}
            onReuseProfile={setReuseProfile}
          />
          {activeBrand?.profile && !inputChanged && (
            <ProfileEditor key={activeBrand.id} profile={activeBrand.profile} onSave={saveProfile} disabled={running} />
          )}
          {activeBrand && (
            <History runs={runs} activeId={result?.id} onOpen={openRun} onDelete={deleteRun} loading={runsLoading} />
          )}
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

          {!running && result && <Results key={result.id} data={result} />}

          {!running && !result && status !== 'error' && (
            <div className="card flex min-h-80 flex-col items-center justify-center p-8 text-center">
              <p className="font-medium">{status === 'loading' ? 'Loading…' : 'Your content will appear here'}</p>
              {status !== 'loading' && (
                <p className="mt-1 max-w-sm text-sm text-muted">
                  Describe your brand, pick platforms, and Brand Bot will research a timely angle, write for each
                  platform, and have an editor agent review every draft. Every run is saved to your history.
                </p>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
