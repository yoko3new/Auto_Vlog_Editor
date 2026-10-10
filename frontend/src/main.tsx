import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/newsreader/500.css';
import '@fontsource/newsreader/500-italic.css';
import '@fontsource/newsreader/800.css';
import '@fontsource/libre-franklin/400.css';
import '@fontsource/libre-franklin/500.css';
import '@fontsource/libre-franklin/600.css';
import '@fontsource/libre-franklin/700.css';
import '@fontsource/courier-prime/400.css';
import './style.css';

import { Language, translations, localizeMessage } from './i18n';

type Job = { status: 'queued' | 'running' | 'complete' | 'failed'; message: string; error: string | null; retryable: boolean; kind: 'generate' | 'edit' | null };
type EditMode = 'auto' | 'highlights' | 'keep_most' | 'keep_all';
type Project = { name: string; clips: { id: string; name: string; duration: number }[]; job: Job | null;
  latest: { cut: string; history: string[] } | null; video_url: string | null; duration_seconds: number | null;
  selection: { mode: EditMode; target_seconds: number | null; remove_no_speech: boolean; speed: number; shot_seconds: number } | null };

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const result = await fetch('/api/vlogii' + url, options);
  if (!result.ok) {
    const body = await result.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${result.status}).`);
  }
  return result.json();
}

function Film({ src, onError, labels }: { src: string; onError: () => void; labels: ReturnType<typeof translations> }) {
  const video = useRef<HTMLVideoElement>(null);
  const [started, setStarted] = useState(false);
  const [failed, setFailed] = useState(false);

  // Keep keyboard focus on the player once the overlay button disappears.
  useEffect(() => { if (started) video.current?.focus({ preventScroll: true }); }, [started]);

  function play() {
    setStarted(true);
    const element = video.current;
    if (!element) return;
    element.currentTime = 0;
    element.play().catch(() => undefined);
  }

  // The media fragment asks Safari to paint the first frame as a poster; the request itself is unchanged.
  return <div className={'film' + (started ? ' is-playing' : '')}>
    <video ref={video} src={src + '#t=0.1'} preload="metadata" playsInline controls={started || failed} aria-label={labels.film}
      onError={() => { setFailed(true); onError(); }}/>
    {!started && !failed && <button className="play" onClick={play} aria-label={labels.play}>
      <span className="play-ring" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M9 6.5v11l8.5-5.5z"/></svg></span>
      <span className="play-label">{labels.play}</span>
    </button>}
  </div>;
}

function App() {
  const [language, setLanguage] = useState<Language>(() => localStorage.getItem('vlogii-language') === 'en' ? 'en' : 'zh');
  const t = translations(language);
  useEffect(() => { localStorage.setItem('vlogii-language', language); document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'; }, [language]);
  const [project, setProject] = useState<Project | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState('my-day');
  const [direction, setDirection] = useState('');
  const [seconds, setSeconds] = useState('');
  const [speed, setSpeed] = useState(1);
  const [editSpeed, setEditSpeed] = useState<number | null>(null);
  const [shotSeconds, setShotSeconds] = useState(0.5);
  const [mode, setMode] = useState<EditMode>('auto');
  const [removeNoSpeech, setRemoveNoSpeech] = useState(false);
  const [orientation, setOrientation] = useState('portrait');
  const [color, setColor] = useState('sdr');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [errorTick, setErrorTick] = useState(0);
  const [dragging, setDragging] = useState(false);
  const progress = useRef<HTMLSpanElement>(null);
  const alertBox = useRef<HTMLDivElement>(null);
  const [title, setTitle] = useState('');
  const [excluded, setExcluded] = useState<string[]>([]);
  const [warmer, setWarmer] = useState(false);
  const [instruction, setInstruction] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  const active = project?.job?.status === 'queued' || project?.job?.status === 'running';
  const retention = mode === 'keep_all' || mode === 'keep_most';
  const validSeconds = !seconds.trim() || (Number.isFinite(Number(seconds)) && Number(seconds) >= 1 && Number(seconds) <= 1800);
  const examples: { text: string; mode: EditMode; removeNoSpeech?: boolean }[] = [
    { text: t.exampleAll, mode: 'keep_all' },
    { text: t.exampleMost, mode: 'keep_most' },
    { text: t.exampleNoSpeech, mode: 'keep_most', removeNoSpeech: true },
    { text: t.exampleHighlights, mode: 'highlights' },
    { text: t.exampleLong, mode: 'auto' },
  ];
  function addExample(example: typeof examples[number]) {
    const presetLines = (['en', 'zh'] as Language[]).flatMap(locale => {
      const labels = translations(locale);
      return [labels.exampleAll, labels.exampleMost, labels.exampleNoSpeech, labels.exampleHighlights, labels.exampleLong];
    });
    setDirection(value => {
      const ownText = value.split('\n').filter(line => !presetLines.includes(line.trim())).join('\n').trim();
      return ownText ? ownText + '\n' + example.text : example.text;
    });
    setMode(example.mode); setSeconds(''); setRemoveNoSpeech(example.removeNoSpeech || false);
  }
  useEffect(() => { setInstruction(''); setExcluded([]); setTitle(''); setWarmer(false); setEditSpeed(null); }, [project?.name]);

  useEffect(() => {
    request<Project[]>('/projects').then(items => {
      setProjects(items);
      const last = localStorage.getItem('vlogii-project');
      if (last) setProject(items.find(item => item.name === last) || null);
    }).catch(exc => setError(exc.message));
  }, []);

  useEffect(() => {
    if (!project) return;
    localStorage.setItem('vlogii-project', project.name);
    if (!active) return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      request<Project>(`/projects/${encodeURIComponent(project.name)}`).then(value => {
        if (!cancelled) { setProject(value); setError(''); }
      }).catch(exc => { if (!cancelled) setError(exc.message); });
    }, 1500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [project?.name, active]);

  async function perform(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); } catch (exc) { report(exc instanceof Error ? exc.message : t.generic); }
    finally { setBusy(false); }
  }

  function choose(items: File[]) {
    const videos = items.filter(item => /\.(mp4|mov|m4v|mkv)$/i.test(item.name));
    setFiles(videos);
    if (videos.length === items.length) setError(''); else report(t.unsupported);
  }

  async function create() {
    await perform(async () => {
      const data = new FormData();
      data.append('name', name); data.append('orientation', orientation); data.append('color', color);
      files.forEach(file => data.append('files', file));
      const item = await request<Project>('/projects', { method: 'POST', body: data });
      setProject(item); setProjects(items => [...items, item]); setFiles([]);
    });
  }

  async function generateFilm() {
    if (!project) return;
    await perform(async () => {
      const job = await request<Job>(`/projects/${encodeURIComponent(project.name)}/generate`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ direction, mode, target_seconds: retention || !seconds.trim() ? null : Number(seconds), speed, shot_seconds: shotSeconds, remove_no_speech: mode === 'keep_most' && removeNoSpeech, language }) });
      setProject({ ...project, job });
    });
  }

  async function applyEdit() {
    if (!project) return;
    await perform(async () => {
      const job = await request<Job>(`/projects/${encodeURIComponent(project.name)}/edit`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim() || null, exclude_clip_ids: excluded, warmth: warmer ? 0.5 : null, instruction, speed: editSpeed, language }) });
      setProject({ ...project, job }); setExcluded([]); setInstruction(''); setEditSpeed(null);
    });
  }

  function report(message: string) {
    setError(message); setErrorTick(count => count + 1);
  }

  // Only user-triggered errors move focus into view; polling and playback do not scroll.
  useEffect(() => { if (errorTick) alertBox.current?.scrollIntoView({ block: 'center' }); }, [errorTick]);
  useEffect(() => setError(''), [project?.name]);
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const room = document.documentElement.scrollHeight - window.innerHeight;
      progress.current?.style.setProperty('--read', String(room > 0 ? Math.min(1, window.scrollY / room) : 0));
    };
    const schedule = () => { if (!frame) frame = window.requestAnimationFrame(update); };
    update();
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    return () => { window.removeEventListener('scroll', schedule); window.removeEventListener('resize', schedule); window.cancelAnimationFrame(frame); };
  }, []);

  const footage = project ? Math.round(project.clips.reduce((sum, clip) => sum + clip.duration, 0)) : 0;
  const version = project?.latest?.cut.replace('cut_', t.version + ' ') || null;
  const failed = !!error || project?.job?.status === 'failed';
  const state = active ? t.stateWorking : failed ? t.stateAttention : project?.latest ? t.stateFilmReady : project ? t.stateImported : t.stateReady;

  return <>
    <header className="masthead">
      <nav className="sections" aria-label={t.sections}>
        <a href="#film">{t.film}</a><a href="#moments">{t.moments}</a><a href="#direction">{t.directionHeading}</a>
        {project?.latest && <><span className="divider" aria-hidden="true"/><a href="#edit">{t.edits}</a></>}
      </nav>
      <p className="feature">{project ? <><span className="kicker">{t.project}</span>{' '}<b>{project.name}</b>{version && <span className="feature-version"> | {version}</span>}</> : <span className="kicker">{t.localStudio}</span>}</p>
      <div className="mast-end"><div className="language-switch" aria-label="Language"><button aria-pressed={language === 'zh'} onClick={() => setLanguage('zh')}>中文</button><button aria-pressed={language === 'en'} onClick={() => setLanguage('en')}>English</button></div>
        <p className={'state' + (active ? ' working' : '') + (failed ? ' failed' : '')}><span className="state-dot" aria-hidden="true"/>{state}</p>
        <a className="brand" href="/" aria-label={t.home}><img src="/brand/vlogii-logo.png" alt="vlogii" width="118" height="32"/></a>
      </div>
      <span className="read" ref={progress} aria-hidden="true"/>
    </header>

    <main>
      <section className="titles">
        <h1><span className="title">{t.heading1}</span><span className="subheading">{t.heading2}</span></h1>
        <p className="byline">{t.byline}</p>
        <p className="edition">{t.eyebrow}</p>
      </section>

      <section id="film" className={'band' + (project?.video_url ? ' has-film' : '')} aria-label={t.film}>
        {project?.video_url
          ? <Film key={project.video_url} src={project.video_url} labels={t} onError={() => setError(t.playbackError)}/>
          : <div className="band-empty">
            <img src="/brand/vlogii-mark-180.png" alt="" width="72" height="72"/>
            <h2>{t.emptyHeading}</h2>
            <p>{active ? t.emptyWorking : t.empty}</p>
            {!project && <a className="caps-link" href="#moments">{t.startMoments}</a>}
          </div>}
      </section>
      <div className="caption">
        <p><span className="kicker">{version || t.slate}</span>{' '}{project?.latest ? `${project.duration_seconds?.toFixed(1) || '—'} ${t.ready}` : t.footerEmpty}</p>
        {project?.video_url && <a className="caps-link" href={project.video_url + '?download=true'}>{t.download}</a>}
      </div>

      <div className="column">
        <p aria-live="polite" className={'status' + (active ? ' working' : '')}><span className="state-dot" aria-hidden="true"/>{project?.job?.message ? localizeMessage(project.job.message, language) : project ? (project.latest ? t.stateFilmReady : t.stateImported) : t.begin}</p>
        {(error || project?.job?.error) && <div role="alert" ref={alertBox} className="alert"><span className="kicker">{t.stateAttention}</span>{localizeMessage(error || project?.job?.error || '', language)}</div>}

        {project?.job?.status === 'failed' && project.job.retryable && <div className="retry-panel"><button className="button primary" disabled={busy || active} onClick={() => perform(async () => {
          const job = await request<Job>(`/projects/${encodeURIComponent(project.name)}/retry`, { method: 'POST' });
          setProject({ ...project, job });
        })}>{t.retry}</button><p className="note">{t.retryHint}</p></div>}
        <p className="lede">{t.intro} {t.intro2}</p>

        <section id="moments" className="chapter" aria-labelledby="moments-title">
          <div className="break"><span className="no">No. 1</span><h2 id="moments-title">{t.moments}</h2></div>
          {projects.length > 0 && <label className="field"><span>{t.open}</span><select value={project?.name || ''} onChange={event => {if (event.target.value) {request<Project>(`/projects/${encodeURIComponent(event.target.value)}`).then(setProject).catch(exc=>report(exc.message));} else {setProject(null);} setTitle('');setExcluded([]);}} disabled={busy || active}><option value="">{t.newProject}</option>{projects.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label>}
          {!project ? <>
            <label className="field"><span>{t.name}</span><input value={name} onChange={event => setName(event.target.value)} maxLength={64} disabled={busy}/></label>
            <div className={'dropzone' + (dragging ? ' is-over' : '')} onDragOver={event => {event.preventDefault();setDragging(true);}} onDragLeave={() => setDragging(false)} onDrop={event => {event.preventDefault();setDragging(false);if (!busy) choose(Array.from(event.dataTransfer.files));}}>
              <span className="plus" aria-hidden="true">+</span>
              <p>{t.bring}</p>
              <small>{t.drop}</small>
              <button className="button quiet" onClick={() => fileInput.current?.click()} disabled={busy}>{t.choose}</button>
              <input ref={fileInput} type="file" multiple accept=".mp4,.mov,.m4v,.mkv" onChange={event => choose(Array.from(event.target.files || []))} hidden/>
            </div>
            {files.length > 0 && <p className="note">{files.length} {t.selected} · {(files.reduce((sum,file)=>sum+file.size,0)/1024**2).toFixed(0)} MB</p>}
            <label className="field"><span>{t.frame}</span><select value={orientation} onChange={event => setOrientation(event.target.value)} disabled={busy}><option value="portrait">{t.portrait}</option><option value="landscape">{t.landscape}</option></select></label>
            <details><summary>{t.compatibility}</summary><label className="field"><span>{t.color}</span><select value={color} onChange={event => setColor(event.target.value)}><option value="sdr">{t.sdr}</option><option value="auto">{t.hdr}</option></select></label><p className="note">{t.hdrHint}</p></details>
            <button className="button primary" disabled={!files.length || busy || !/^[\p{L}\p{N}][\p{L}\p{N}_-]{0,63}$/u.test(name)} onClick={create}>{busy ? t.importing : t.import}</button>
          </> : <>
            <p className="project-name">{project.name}</p>
            <p className="note">{project.clips.length} {t.selected} · {footage} {t.footage}</p>
            <ul className="clips">{project.clips.map(clip => <li key={clip.id}><span title={clip.name}>{clip.name}</span><small>{clip.duration.toFixed(1)}s</small></li>)}</ul>
            <button className="caps-link" disabled={busy || active} onClick={() => {setProject(null);setTitle('');setExcluded([]);}}>{t.another}</button>
          </>}
        </section>
      </div>

      <blockquote className="pull"><p>{t.pullQuote}</p></blockquote>

      <div className="column">
        <section id="direction" className="chapter" aria-labelledby="direction-title">
          <div className="break"><span className="no">No. 2</span><h2 id="direction-title">{t.directionHeading}</h2></div>
          <label className="field"><span>{t.mode}</span><select value={mode} onChange={event => {setMode(event.target.value as EditMode);setSeconds('');}} disabled={busy || active}><option value="auto">{t.modeAuto}</option><option value="highlights">{t.modeHighlights}</option><option value="keep_most">{t.modeMost}</option><option value="keep_all">{t.modeAll}</option></select></label>
          <p className="note">{mode === 'keep_all' ? t.allHint : mode === 'keep_most' ? t.mostHint : mode === 'highlights' ? t.highlightsHint : t.autoHint}</p>
          {mode === 'keep_most' && <label className="check"><input type="checkbox" checked={removeNoSpeech} onChange={event => setRemoveNoSpeech(event.target.checked)} disabled={busy || active}/>{t.removeNoSpeech}</label>}
          <label className="field"><span>{t.direction}</span><textarea placeholder={t.directionPlaceholder} value={direction} onChange={event => setDirection(event.target.value)} maxLength={2000} disabled={busy || active}/></label>
          <div className="input-examples" aria-label={t.examples}><span>{t.examples}</span>{examples.map(example => <button type="button" key={example.text} disabled={busy || active || (direction.length + example.text.length + 1 > 2000)} onClick={() => addExample(example)}>{example.text}</button>)}</div>
          {!retention && <><label className="field"><span>{t.target}</span><input type="number" min={1} max={1800} step="any" placeholder={t.targetPlaceholder} value={seconds} onChange={event => setSeconds(event.target.value)} disabled={busy || active}/></label><p className="note">{t.targetHint}</p></>}
          {mode === 'highlights' && <fieldset className="radio-bar" disabled={busy || active}><legend>{t.cadence}</legend>{[0.25, 0.35, 0.5, 0.8].map(value => <label key={value}><input type="radio" name="cadence" value={value} checked={shotSeconds === value} onChange={() => setShotSeconds(value)}/>{value}s</label>)}</fieldset>}
          <fieldset className="radio-bar" disabled={busy || active}><legend>{t.speed}</legend>{[0.5, 1, 1.5, 2, 4, 8].map(value => <label key={value}><input type="radio" name="generate-speed" value={value} checked={speed === value} onChange={() => setSpeed(value)}/>{value}×</label>)}</fieldset><p className="note">{t.speedHint}</p>
          <p className="note">{mode === 'highlights' ? t.highlightsAudioHint : t.audioHint}</p>
          <p className="note">{t.privacy}</p>
          <button className="button primary" onClick={generateFilm} disabled={!project || busy || active || (!retention && !validSeconds)}>{active ? t.making : project?.latest ? t.newVersion : t.generate}</button>
        </section>

        {project?.latest && <section id="edit" className="chapter" aria-labelledby="edit-title">
          <div className="break"><span className="no">No. 3</span><h2 id="edit-title">{t.edits}</h2></div>
          <fieldset className="radio-bar" disabled={busy || active}><legend>{t.editSpeed}</legend><label><input type="radio" name="edit-speed" checked={editSpeed === null} onChange={() => setEditSpeed(null)}/>{t.unchanged}</label>{[0.5, 1, 1.5, 2, 4, 8].map(value => <label key={value}><input type="radio" name="edit-speed" value={value} checked={editSpeed === value} onChange={() => setEditSpeed(value)}/>{value}×</label>)}</fieldset><p className="note">{t.editSpeedHint}</p>
          <label className="field"><span>{t.timeEdits}</span><textarea placeholder={t.timeEditsPlaceholder} value={instruction} onChange={event => setInstruction(event.target.value)} maxLength={1000} disabled={busy || active}/></label><p className="note">{t.timeEditsHint}</p>
          <div className="input-examples" aria-label={t.examples}><span>{t.examples}</span>{[t.exampleRemove, t.exampleSpeed].map(example => <button type="button" key={example} disabled={busy || active || instruction.length + example.length + 2 > 1000} onClick={() => setInstruction(value => value.trim() ? value.trim() + '; ' + example : example)}>{example}</button>)}</div>
          <label className="field"><span>{t.title}</span><input placeholder={t.titlePlaceholder} value={title} onChange={event => setTitle(event.target.value)} maxLength={100} disabled={busy || active}/></label>
          <label className="check"><input type="checkbox" checked={warmer} onChange={event => setWarmer(event.target.checked)} disabled={busy || active}/> {t.warmer}</label>
          <details><summary>{t.exclude}</summary>{project.clips.map(clip => <label className="check" key={clip.id}><input type="checkbox" disabled={busy || active} checked={excluded.includes(clip.id)} onChange={event => setExcluded(items => event.target.checked ? [...items,clip.id] : items.filter(id=>id!==clip.id))}/>{clip.name}</label>)}</details>
          <div className="actions"><button className="button primary" disabled={busy || active || (!title.trim() && !excluded.length && !warmer && !instruction.trim() && editSpeed === null)} onClick={applyEdit}>{t.apply}</button>
          <button className="button quiet" disabled={busy || active || project.latest.history.length < 2} onClick={() => perform(async () => { setProject(await request<Project>(`/projects/${encodeURIComponent(project.name)}/undo`, { method: 'POST' })); })}>{t.undo}</button></div>
          <p className="note">{t.editHint}</p>
        </section>}
      </div>
    </main>

    <footer className="colophon">
      <img src="/brand/vlogii-mark-180.png" alt="" width="36" height="36"/>
      <p>{t.made}</p>
      <span className="kicker">{t.local}</span>
    </footer>
  </>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
