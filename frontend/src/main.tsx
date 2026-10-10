import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import { Language, translations, localizeMessage } from './i18n';

type Job = { status: 'queued' | 'running' | 'complete' | 'failed'; message: string; error: string | null; retryable: boolean; kind: 'generate' | 'edit' | null };
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
  const [language, setLanguage] = useState<Language>(() => localStorage.getItem('vlogii-language') === 'en' ? 'en' : 'zh');
  const t = translations(language);
  useEffect(() => { localStorage.setItem('vlogii-language', language); document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'; }, [language]);
  const [project, setProject] = useState<Project | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState('my-day');
  const [direction, setDirection] = useState('');
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
      request<Project>(`/projects/${encodeURIComponent(project.name)}`).then(value => {
        if (!cancelled) setProject(value);
      }).catch(exc => { if (!cancelled) setError(exc.message); });
    }, 1500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [project?.name, active]);

  async function perform(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); } catch (exc) { setError(exc instanceof Error ? exc.message : t.generic); }
    finally { setBusy(false); }
  }

  function choose(items: File[]) {
    const videos = items.filter(item => /\.(mp4|mov|m4v|mkv)$/i.test(item.name));
    setFiles(videos); setError(videos.length === items.length ? '' : t.unsupported);
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
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ direction, target_seconds: seconds, language }) });
      setProject({ ...project, job });
    });
  }

  async function applyEdit() {
    if (!project) return;
    await perform(async () => {
      const job = await request<Job>(`/projects/${encodeURIComponent(project.name)}/edit`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim() || null, exclude_clip_ids: excluded, warmth: warmer ? 0.5 : null, language }) });
      setProject({ ...project, job }); setExcluded([]);
    });
  }

  return <div className="page">
    <header><a className="brand" href="/">vlogii<span> / </span></a><p>{t.tagline}</p><div className="language-switch" aria-label="Language / 语言"><button aria-pressed={language === 'zh'} onClick={() => setLanguage('zh')}>中文</button><button aria-pressed={language === 'en'} onClick={() => setLanguage('en')}>English</button></div><span className="edition">{t.edition}</span></header>
    <section className="intro"><span className="eyebrow">{t.eyebrow}</span><h1>{t.heading1}<br/><em>{t.heading2}</em></h1><p>{t.intro}<br/>{t.intro2}</p></section>
    <main>
      <aside>
        <section className="panel">
          <div className="section-heading"><span>01</span><h2>{t.moments}</h2></div>
          {projects.length > 0 && <label>{t.open}<select value={project?.name || ''} onChange={event => {if (event.target.value) {request<Project>(`/projects/${encodeURIComponent(event.target.value)}`).then(setProject).catch(exc=>setError(exc.message));} else {setProject(null);} setTitle('');setExcluded([]);}} disabled={busy || active}><option value="">{t.newProject}</option>{projects.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label>}
          {!project ? <>
            <label>{t.name}<input value={name} onChange={event => setName(event.target.value)} maxLength={64} /></label>
            <div className="dropzone" onDragOver={event => event.preventDefault()} onDrop={event => {event.preventDefault();if (!busy) choose(Array.from(event.dataTransfer.files));}}>
              <span className="plus">＋</span><p>{t.bring}</p><small>{t.drop}</small>
              <button className="secondary" onClick={() => fileInput.current?.click()} disabled={busy}>{t.choose}</button>
              <input ref={fileInput} type="file" multiple accept=".mp4,.mov,.m4v,.mkv" onChange={event => choose(Array.from(event.target.files || []))} hidden/>
            </div>
            {files.length > 0 && <p className="hint">{files.length} {t.selected} · {(files.reduce((sum,file)=>sum+file.size,0)/1024**2).toFixed(0)} MB</p>}
            <label>{t.frame}<select value={orientation} onChange={event => setOrientation(event.target.value)} disabled={busy}><option value="portrait">{t.portrait}</option><option value="landscape">{t.landscape}</option></select></label>
            <details><summary>{t.compatibility}</summary><label>{t.color}<select value={color} onChange={event => setColor(event.target.value)}><option value="sdr">{t.sdr}</option><option value="auto">{t.hdr}</option></select></label><p className="hint">{t.hdrHint}</p></details>
            <button className="primary" disabled={!files.length || busy || !/^[\p{L}\p{N}][\p{L}\p{N}_-]{0,63}$/u.test(name)} onClick={create}>{busy ? t.importing : t.import}</button>
          </> : <>
            <p className="project-name">{project.name}</p><p className="hint">{project.clips.length} {t.selected} · {Math.round(project.clips.reduce((sum,clip)=>sum+clip.duration,0))} {t.footage}</p>
            <ul className="clips">{project.clips.map(clip => <li key={clip.id}><span title={clip.name}>{clip.name}</span><small>{clip.duration.toFixed(1)}s</small></li>)}</ul>
            <button className="text-button" disabled={busy || active} onClick={() => {setProject(null);setTitle('');setExcluded([]);}}>{t.another}</button>
          </>}
        </section>
        <section className="panel"><div className="section-heading"><span>02</span><h2>{t.directionHeading}</h2></div>
          <label>{t.direction}<textarea placeholder={t.directionPlaceholder} value={direction} onChange={event => setDirection(event.target.value)} maxLength={2000} disabled={active}/></label>
          <label>{t.target}<select value={seconds} onChange={event => setSeconds(Number(event.target.value))} disabled={active}><option value={30}>{t.sec30}</option><option value={60}>{t.sec60}</option><option value={150}>{t.sec150}</option></select></label>
          <p className="hint">{t.targetHint}</p><p className="hint">{t.audioHint}</p>
          <p className="hint">{t.privacy}</p>
          <button className="primary" onClick={generateFilm} disabled={!project || busy || active}>{active ? t.making : project?.latest ? t.newVersion : t.generate}</button>
        </section>
      </aside>
      <div className="workspace">
        <div className="player-card">
          <div className="player-heading"><span>{t.film}</span><span>{project?.latest?.cut.replace('cut_', t.version + ' ') || t.slate}</span></div>
          {project?.video_url ? <video key={project.video_url} controls preload="metadata" src={project.video_url} onError={() => setError(t.playbackError)} /> : <div className="empty-player"><span className="frame-mark">v.</span><h2>{t.emptyHeading}</h2><p>{active ? t.emptyWorking : t.empty}</p></div>}
          <div className="player-footer"><p>{project?.latest ? `${project.duration_seconds?.toFixed(1) || '—'} ${t.ready}` : t.footerEmpty}</p>{project?.video_url && <a className="download" href={project.video_url + '?download=true'}>{t.download}</a>}</div>
        </div>
        <div aria-live="polite" className={'status ' + (active ? 'working' : '')}>
          <span className="status-dot"/><p>{project?.job?.message ? localizeMessage(project.job.message, language) : t.begin}</p>
        </div>
        {(error || project?.job?.error) && <div role="alert" className="error">{localizeMessage(error || project?.job?.error || '', language)}</div>}
        {project?.job?.status === 'failed' && project.job.retryable && <div className="retry-panel"><button className="primary" disabled={busy || active} onClick={() => perform(async () => {
          const job = await request<Job>(`/projects/${encodeURIComponent(project.name)}/retry`, { method: 'POST' });
          setProject({ ...project, job });
        })}>{t.retry}</button><p className="hint">{t.retryHint}</p></div>}
        {project?.latest && <section className="panel edits"><div className="section-heading"><span>03</span><h2>{t.edits}</h2></div>
          <label>{t.title}<input placeholder={t.titlePlaceholder} value={title} onChange={event => setTitle(event.target.value)} maxLength={100} disabled={active}/></label>
          <label className="check"><input type="checkbox" checked={warmer} onChange={event => setWarmer(event.target.checked)} disabled={active}/>{t.warmer}</label>
          <details><summary>{t.exclude}</summary>{project.clips.map(clip => <label className="check" key={clip.id}><input type="checkbox" disabled={active} checked={excluded.includes(clip.id)} onChange={event => setExcluded(items => event.target.checked ? [...items,clip.id] : items.filter(id=>id!==clip.id))}/>{clip.name}</label>)}</details>
          <div className="edit-actions"><button className="primary" disabled={busy || active || (!title.trim() && !excluded.length && !warmer)} onClick={applyEdit}>{t.apply}</button>
          <button className="secondary" disabled={busy || active || project.latest.history.length < 2} onClick={() => perform(async () => { setProject(await request<Project>(`/projects/${encodeURIComponent(project.name)}/undo`, { method: 'POST' })); })}>{t.undo}</button></div>
          <p className="hint">{t.editHint}</p>
        </section>}
      </div>
    </main><footer>{t.made}<span>{t.local}</span></footer>
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
