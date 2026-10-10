import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
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
  const [title, setTitle] = useState('');
  const [excluded, setExcluded] = useState<string[]>([]);
  const [warmer, setWarmer] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
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
        if (!cancelled) setProject(value);
      }).catch(exc => { if (!cancelled) setError(exc.message); });
    }, 1500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [project?.name, active]);

  async function perform(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); } catch (exc) { setError(exc instanceof Error ? exc.message : 'Something went wrong.'); }
    finally { setBusy(false); }
  }

  function choose(items: File[]) {
    const videos = items.filter(item => /\.(mp4|mov|m4v|mkv)$/i.test(item.name));
    setFiles(videos); setError(videos.length === items.length ? '' : 'Choose MP4, MOV, M4V or MKV video clips.');
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

  return <div className="page">
    <header><a className="brand" href="/">vlogii<span> / </span></a><p>A little film of your day.</p><span className="edition">LOCAL STUDIO · 01</span></header>
    <section className="intro"><span className="eyebrow">THE EVERYDAY, KEPT.</span><h1>Your day.<br/><em>Worth keeping.</em></h1><p>Turn the clips on your phone into a small story.<br/>Your moments, your words, your rhythm.</p></section>
    <main>
      <aside>
        <section className="panel">
          <div className="section-heading"><span>01</span><h2>Your moments</h2></div>
          {projects.length > 0 && <label>Open a saved project<select value={project?.name || ''} onChange={event => {if (event.target.value) {request<Project>(`/projects/${event.target.value}`).then(setProject).catch(exc=>setError(exc.message));} else {setProject(null);} setTitle('');setExcluded([]);}} disabled={busy || active}><option value="">New project</option>{projects.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label>}
          {!project ? <>
            <label>Project name<input value={name} onChange={event => setName(event.target.value)} maxLength={64} pattern="[A-Za-z0-9][A-Za-z0-9_-]*"/></label>
            <div className="dropzone" onDragOver={event => event.preventDefault()} onDrop={event => {event.preventDefault();if (!busy) choose(Array.from(event.dataTransfer.files));}}>
              <span className="plus">＋</span><p>Bring your day here.</p><small>Drop your clips, or choose files.</small>
              <button className="secondary" onClick={() => fileInput.current?.click()} disabled={busy}>Choose video clips</button>
              <input ref={fileInput} type="file" multiple accept=".mp4,.mov,.m4v,.mkv" onChange={event => choose(Array.from(event.target.files || []))} hidden/>
            </div>
            {files.length > 0 && <p className="hint">{files.length} clips selected · {(files.reduce((sum,file)=>sum+file.size,0)/1024**2).toFixed(0)} MB</p>}
            <label>Frame<select value={orientation} onChange={event => setOrientation(event.target.value)} disabled={busy}><option value="portrait">Portrait · 9:16</option><option value="landscape">Landscape · 16:9</option></select></label>
            <details><summary>Video compatibility</summary><label>Color<select value={color} onChange={event => setColor(event.target.value)}><option value="sdr">Standard · widest browser compatibility</option><option value="auto">Preserve HLG when all clips support it</option></select></label><p className="hint">HDR exports use HEVC. Playback depends on your browser and display.</p></details>
            <button className="primary" disabled={!files.length || busy || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(name)} onClick={create}>{busy ? 'Saving your clips…' : 'Import my moments'}</button>
          </> : <>
            <p className="project-name">{project.name}</p><p className="hint">{project.clips.length} clips · {Math.round(project.clips.reduce((sum,clip)=>sum+clip.duration,0))} seconds of footage</p>
            <ul className="clips">{project.clips.map(clip => <li key={clip.id}><span title={clip.name}>{clip.name}</span><small>{clip.duration.toFixed(1)}s</small></li>)}</ul>
            <button className="text-button" disabled={busy || active} onClick={() => {setProject(null);setTitle('');setExcluded([]);}}>Start another project ↗</button>
          </>}
        </section>
        <section className="panel"><div className="section-heading"><span>02</span><h2>Your direction</h2></div>
          <label>What would you like to remember?<textarea value={direction} onChange={event => setDirection(event.target.value)} maxLength={2000} disabled={active}/></label>
          <label>Aim for<select value={seconds} onChange={event => setSeconds(Number(event.target.value))} disabled={active}><option value={30}>30 seconds · a small glimpse</option><option value={60}>60 seconds · a little story</option><option value={150}>150 seconds · a longer diary</option></select></label>
          <p className="hint">Natural audio, speech captions and occasional text. Your direction guides the edit; it does not add background music.</p>
          <p className="hint">AI analysis sends low-resolution copies to Google Gemini. Originals and exports stay on this computer. Your API key stays on the server.</p>
          <button className="primary" onClick={generateFilm} disabled={!project || busy || active}>{active ? 'Making your film…' : project?.latest ? 'Make a new version ↗' : 'Make my film ↗'}</button>
        </section>
      </aside>
      <div className="workspace">
        <div className="player-card">
          <div className="player-heading"><span>YOUR LITTLE FILM</span><span>{project?.latest?.cut.replace('cut_', 'VERSION ') || 'A CLEAN SLATE'}</span></div>
          {project?.video_url ? <video key={project.video_url} controls preload="metadata" src={project.video_url} onError={() => setError('This browser may not support the export format. Download the film to play it locally, or create an SDR project.')} /> : <div className="empty-player"><span className="frame-mark">v.</span><h2>A day becomes a story.</h2><p>{active ? 'We’re finding the moments that belong together.' : 'Your finished film will appear here.'}</p></div>}
          <div className="player-footer"><p>{project?.latest ? `${project.duration_seconds?.toFixed(1) || '—'} seconds · Ready for a closer look.` : 'A few moments. A little meaning.'}</p>{project?.video_url && <a className="download" href={project.video_url + '?download=true'}>Download MP4 ↓</a>}</div>
        </div>
        <div aria-live="polite" className={'status ' + (active ? 'working' : '')}>
          <span className="status-dot"/><p>{project?.job?.message || 'Import your clips to begin.'}</p>
        </div>
        {(error || project?.job?.error) && <div role="alert" className="error">{error || project?.job?.error}</div>}
        {project?.latest && <section className="panel edits"><div className="section-heading"><span>03</span><h2>Make it yours</h2></div>
          <label>A new title<input placeholder="e.g. Slow Sunday" value={title} onChange={event => setTitle(event.target.value)} maxLength={100} disabled={active}/></label>
          <label className="check"><input type="checkbox" checked={warmer} onChange={event => setWarmer(event.target.checked)} disabled={active}/> A little warmer</label>
          <details><summary>Leave a clip out</summary>{project.clips.map(clip => <label className="check" key={clip.id}><input type="checkbox" disabled={active} checked={excluded.includes(clip.id)} onChange={event => setExcluded(items => event.target.checked ? [...items,clip.id] : items.filter(id=>id!==clip.id))}/>{clip.name}</label>)}</details>
          <div className="edit-actions"><button className="primary" disabled={busy || active || (!title.trim() && !excluded.length && !warmer)} onClick={applyEdit}>Apply changes</button>
          <button className="secondary" disabled={busy || active || project.latest.history.length < 2} onClick={() => perform(async () => { setProject(await request<Project>(`/projects/${project.name}/undo`, { method: 'POST' })); })}>Undo last version</button></div>
          <p className="hint">Edits keep the other selected moments. Undo restores the previous successful film.</p>
        </section>}
      </div>
    </main><footer>Made from your moments.<span>VLOGII / LOCAL MVP</span></footer>
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
