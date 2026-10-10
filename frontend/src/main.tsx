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

type Job = { status: 'queued' | 'running' | 'complete' | 'failed'; message: string; error: string | null };
type Project = { name: string; clips: { id: string; name: string; duration: number }[]; job: Job | null;
  latest: { cut: string; history: string[] } | null; video_url: string | null; duration_seconds: number | null };

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const result = await fetch('/api/vlogii' + url, options);
  if (!result.ok) {
    const body = await result.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${result.status}).`);
  }
  return result.json();
}

function Film({ src, onError }: { src: string; onError: () => void }) {
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
    <video ref={video} src={src + '#t=0.1'} preload="metadata" playsInline controls={started || failed} aria-label="Your film"
      onError={() => { setFailed(true); onError(); }}/>
    {!started && !failed && <button className="play" onClick={play} aria-label="Play your film">
      <span className="play-ring" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M9 6.5v11l8.5-5.5z"/></svg></span>
      <span className="play-label">Play</span>
    </button>}
  </div>;
}

function App() {
  const [project, setProject] = useState<Project | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState('my-day');
  const [direction, setDirection] = useState('A calm chronological diary. Keep the little moments and natural conversations.');
  const [seconds, setSeconds] = useState(30);
  const [orientation, setOrientation] = useState('portrait');
  const [color, setColor] = useState('sdr');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // Counts errors caused by the user's own actions; only these move the page to the alert.
  const [errorTick, setErrorTick] = useState(0);
  const [title, setTitle] = useState('');
  const [excluded, setExcluded] = useState<string[]>([]);
  const [warmer, setWarmer] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const progress = useRef<HTMLSpanElement>(null);
  const alertBox = useRef<HTMLDivElement>(null);
  const active = project?.job?.status === 'queued' || project?.job?.status === 'running';

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
      request<Project>(`/projects/${project.name}`).then(value => {
        if (!cancelled) { setProject(value); setError(''); }
      }).catch(exc => { if (!cancelled) setError(exc.message); });
    }, 1500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [project?.name, active]);

  // Actions sit far below the status area in the single-column layout, so show an action's error where it is.
  // Background errors (playback, polling) only update the alert and masthead, without moving the page.
  useEffect(() => { if (errorTick) alertBox.current?.scrollIntoView({ block: 'center' }); }, [errorTick]);
  useEffect(() => setError(''), [project?.name]);

  function report(message: string) {
    setError(message); setErrorTick(count => count + 1);
  }

  // Reading progress, as in the masthead of a long-form feature.
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

  async function perform(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); } catch (exc) { report(exc instanceof Error ? exc.message : 'Something went wrong.'); }
    finally { setBusy(false); }
  }

  function choose(items: File[]) {
    const videos = items.filter(item => /\.(mp4|mov|m4v|mkv)$/i.test(item.name));
    setFiles(videos);
    if (videos.length === items.length) setError(''); else report('Choose MP4, MOV, M4V or MKV video clips.');
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
      const job = await request<Job>(`/projects/${project.name}/generate`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ direction, target_seconds: seconds }) });
      setProject({ ...project, job });
    });
  }

  async function applyEdit() {
    if (!project) return;
    await perform(async () => {
      const job = await request<Job>(`/projects/${project.name}/edit`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim() || null, exclude_clip_ids: excluded, warmth: warmer ? 0.5 : null }) });
      setProject({ ...project, job }); setExcluded([]);
    });
  }

  const footage = project ? Math.round(project.clips.reduce((sum, clip) => sum + clip.duration, 0)) : 0;
  const version = project?.latest?.cut.replace('cut_', 'Version ') || null;
  const failed = !!error || project?.job?.status === 'failed';
  const state = active ? 'Working' : failed ? 'Needs attention' : project?.latest ? 'Film ready' : project ? 'Clips imported' : 'Ready';

  return <>
    <header className="masthead">
      <nav className="sections" aria-label="Sections">
        <a href="#film">Film</a><a href="#moments">Moments</a><a href="#direction">Direction</a>
        {project?.latest && <><span className="divider" aria-hidden="true"/><a href="#edit">Make it yours</a></>}
      </nav>
      <p className="feature">{project ? <><span className="kicker">Project</span>{' '}<b>{project.name}</b>{version && <span className="feature-version"> | {version}</span>}</> : <span className="kicker">Local studio</span>}</p>
      <div className="mast-end">
        <p className={'state' + (active ? ' working' : '') + (failed ? ' failed' : '')}><span className="state-dot" aria-hidden="true"/>{state}</p>
        <a className="brand" href="/" aria-label="Vlogii home"><img src="/brand/vlogii-logo.png" alt="vlogii" width="118" height="32"/></a>
      </div>
      <span className="read" ref={progress} aria-hidden="true"/>
    </header>

    <main>
      <section className="titles">
        <h1><span className="title">Your Day</span><span className="subheading">A Little Film Worth Keeping</span></h1>
        <p className="byline">by you, and the clips on your phone</p>
        <p className="edition">The everyday, kept</p>
      </section>

      <section id="film" className={'band' + (project?.video_url ? ' has-film' : '')} aria-label="Your little film">
        {project?.video_url
          ? <Film key={project.video_url} src={project.video_url} onError={() => setError('This browser may not support the export format. Download the film to play it locally, or create an SDR project.')}/>
          : <div className="band-empty">
            <img src="/brand/vlogii-mark-180.png" alt="" width="72" height="72"/>
            <h2>A day becomes a story.</h2>
            <p>{active ? 'We’re finding the moments that belong together.' : 'Your finished film will appear here.'}</p>
            {!project && <a className="caps-link" href="#moments">Start with your moments ↓</a>}
          </div>}
      </section>
      <div className="caption">
        <p><span className="kicker">{version || 'A clean slate'}</span>{' '}{project?.latest ? `${project.duration_seconds?.toFixed(1) || '—'} seconds · Ready for a closer look.` : 'A few moments. A little meaning.'}</p>
        {project?.video_url && <a className="caps-link" href={project.video_url + '?download=true'}>Download MP4 ↓</a>}
      </div>

      <div className="column">
        <p aria-live="polite" className={'status' + (active ? ' working' : '')}><span className="state-dot" aria-hidden="true"/>{project?.job?.message || 'Import your clips to begin.'}</p>
        {(error || project?.job?.error) && <div role="alert" ref={alertBox} className="alert"><span className="kicker">Needs attention</span>{error || project?.job?.error}</div>}

        <p className="lede"><span className="lead-in">Turn the clips</span> on your phone into a small story. Your moments, your words, your rhythm.</p>

        <section id="moments" className="chapter" aria-labelledby="moments-title">
          <div className="break"><span className="no">No. 1</span><h2 id="moments-title">Your Moments</h2></div>
          {projects.length > 0 && <label className="field"><span>Open a saved project</span><select value={project?.name || ''} onChange={event => {if (event.target.value) {request<Project>(`/projects/${event.target.value}`).then(setProject).catch(exc=>report(exc.message));} else {setProject(null);} setTitle('');setExcluded([]);}} disabled={busy || active}><option value="">New project</option>{projects.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label>}
          {!project ? <>
            <label className="field"><span>Project name</span><input value={name} onChange={event => setName(event.target.value)} maxLength={64} pattern="[A-Za-z0-9][A-Za-z0-9_-]*"/></label>
            <div className={'dropzone' + (dragging ? ' is-over' : '')} onDragOver={event => {event.preventDefault();setDragging(true);}} onDragLeave={() => setDragging(false)} onDrop={event => {event.preventDefault();setDragging(false);if (!busy) choose(Array.from(event.dataTransfer.files));}}>
              <span className="plus" aria-hidden="true">+</span>
              <p>Bring your day here.</p>
              <small>Drop your clips, or choose files.</small>
              <button className="button quiet" onClick={() => fileInput.current?.click()} disabled={busy}>Choose video clips</button>
              <input ref={fileInput} type="file" multiple accept=".mp4,.mov,.m4v,.mkv" onChange={event => choose(Array.from(event.target.files || []))} hidden/>
            </div>
            {files.length > 0 && <p className="note">{files.length} clips selected · {(files.reduce((sum,file)=>sum+file.size,0)/1024**2).toFixed(0)} MB</p>}
            <label className="field"><span>Frame</span><select value={orientation} onChange={event => setOrientation(event.target.value)} disabled={busy}><option value="portrait">Portrait · 9:16</option><option value="landscape">Landscape · 16:9</option></select></label>
            <details><summary>Video compatibility</summary><label className="field"><span>Color</span><select value={color} onChange={event => setColor(event.target.value)}><option value="sdr">Standard · widest browser compatibility</option><option value="auto">Preserve HLG when all clips support it</option></select></label><p className="note">HDR exports use HEVC. Playback depends on your browser and display.</p></details>
            <button className="button primary" disabled={!files.length || busy || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(name)} onClick={create}>{busy ? 'Saving your clips…' : 'Import my moments'}</button>
          </> : <>
            <p className="project-name">{project.name}</p>
            <p className="note">{project.clips.length} clips · {footage} seconds of footage</p>
            <ul className="clips">{project.clips.map(clip => <li key={clip.id}><span title={clip.name}>{clip.name}</span><small>{clip.duration.toFixed(1)}s</small></li>)}</ul>
            <button className="caps-link" disabled={busy || active} onClick={() => {setProject(null);setTitle('');setExcluded([]);}}>Start another project ↗</button>
          </>}
        </section>
      </div>

      <blockquote className="pull"><p>Your camera roll remembers what happened. Vlogii helps you keep how it felt.</p></blockquote>

      <div className="column">
        <section id="direction" className="chapter" aria-labelledby="direction-title">
          <div className="break"><span className="no">No. 2</span><h2 id="direction-title">Your Direction</h2></div>
          <label className="field"><span>What would you like to remember?</span><textarea value={direction} onChange={event => setDirection(event.target.value)} maxLength={2000} disabled={active}/></label>
          <label className="field"><span>Aim for</span><select value={seconds} onChange={event => setSeconds(Number(event.target.value))} disabled={active}><option value={30}>30 seconds · a small glimpse</option><option value={60}>60 seconds · a little story</option><option value={150}>150 seconds · a longer diary</option></select></label>
          <div className="aside">
            <p>Natural audio, speech captions and occasional text. Your direction guides the edit; it does not add background music.</p>
            <p>AI analysis sends low-resolution copies to Google Gemini. Originals and exports stay on this computer. Your API key stays on the server.</p>
          </div>
          <button className="button primary" onClick={generateFilm} disabled={!project || busy || active}>{active ? 'Making your film…' : project?.latest ? 'Make a new version ↗' : 'Make my film ↗'}</button>
        </section>

        {project?.latest && <section id="edit" className="chapter" aria-labelledby="edit-title">
          <div className="break"><span className="no">No. 3</span><h2 id="edit-title">Make It Yours</h2></div>
          <label className="field"><span>A new title</span><input placeholder="e.g. Slow Sunday" value={title} onChange={event => setTitle(event.target.value)} maxLength={100} disabled={active}/></label>
          <label className="check"><input type="checkbox" checked={warmer} onChange={event => setWarmer(event.target.checked)} disabled={active}/> A little warmer</label>
          <details><summary>Leave a clip out</summary>{project.clips.map(clip => <label className="check" key={clip.id}><input type="checkbox" disabled={active} checked={excluded.includes(clip.id)} onChange={event => setExcluded(items => event.target.checked ? [...items,clip.id] : items.filter(id=>id!==clip.id))}/>{clip.name}</label>)}</details>
          <div className="actions"><button className="button primary" disabled={busy || active || (!title.trim() && !excluded.length && !warmer)} onClick={applyEdit}>Apply changes</button>
          <button className="button quiet" disabled={busy || active || project.latest.history.length < 2} onClick={() => perform(async () => { setProject(await request<Project>(`/projects/${project.name}/undo`, { method: 'POST' })); })}>Undo last version</button></div>
          <p className="note">Edits keep the other selected moments. Undo restores the previous successful film.</p>
        </section>}
      </div>
    </main>

    <footer className="colophon">
      <img src="/brand/vlogii-mark-180.png" alt="" width="36" height="36"/>
      <p>Made from your moments.</p>
      <span className="kicker">Vlogii / Local MVP</span>
    </footer>
  </>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
