import React, { useEffect, useState } from 'react';
import { PresetLibrary } from './appearance';
import { Language, localizeMessage, translations } from './i18n';
import { localSeconds, stamp } from './chapter-editor';

export type Cover = { title: string; subtitle: string; kicker: string; font: string; style: 'clean' | 'editorial' | 'playful'; frame_seconds: number; show_intro: boolean };

export function CoverEditor({ projectName, cut, saved, coverUrl, filmTitle, duration, playTime, library, language, disabled, onApply }: {
  projectName: string; cut: string; saved: Cover | null; coverUrl: string | null; filmTitle: string | null;
  duration: number; playTime: number; library: PresetLibrary | null; language: Language; disabled: boolean;
  onApply: (cover: Cover, cut: string) => Promise<void>;
}) {
  const t = translations(language);
  const offset = saved?.show_intro ? 1 : 0;
  const bodyDuration = Math.max(0, duration - offset);
  const [draft, setDraft] = useState<Cover>(saved || { title: filmTitle || '', subtitle: '', kicker: '', font: language === 'zh' ? 'noto-serif' : 'playfair-display', style: 'clean', frame_seconds: Math.min(3, bodyDuration / 3), show_intro: true });
  const [frame, setFrame] = useState(draft.frame_seconds.toFixed(2));
  const [preview, setPreview] = useState<{ url: string; identity: string } | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const seconds = localSeconds(frame);
  const options = { ...draft, frame_seconds: seconds ?? 0 };
  const identity = JSON.stringify(options);
  const valid = !!draft.title.trim() && seconds !== null && seconds >= 0 && seconds < bodyDuration;
  const changed = !saved || JSON.stringify(options) !== JSON.stringify(saved);
  const previewCurrent = preview?.identity === identity;
  const image = preview?.url || coverUrl;
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);
  const chineseFonts = ['noto-sans', 'noto-serif', 'ma-shan-zheng', 'zcool-xiaowei'];
  const family = chineseFonts.includes(draft.font) || !/[\u3400-\u9fff]/.test(draft.title) ? draft.font : 'noto-sans';
  async function showPreview() {
    setWorking(true); setError('');
    try {
      const response = await fetch(`/api/vlogii/projects/${encodeURIComponent(projectName)}/cover/preview`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cover: options, base_cut: cut }) });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body.detail === 'string' ? body.detail : t.coverPreviewError);
      }
      setPreview({ url: URL.createObjectURL(await response.blob()), identity });
    } catch (reason) { setError(localizeMessage(String(reason instanceof Error ? reason.message : reason), language)); }
    finally { setWorking(false); }
  }
  async function apply() {
    setError('');
    try { await onApply(options, cut); }
    catch (reason) { setError(localizeMessage(String(reason instanceof Error ? reason.message : reason), language)); }
  }
  return <section id="cover" className="cover-editor column" aria-labelledby="cover-title">
    <details><summary><h3 id="cover-title">{t.coverHeading}</h3></summary>
      <div className="cover-layout">
        <fieldset disabled={disabled || working || !library} className="cover-controls">
          <legend className="sr-only">{t.coverEdit}</legend>
          <label className="field"><span>{t.coverTitle}</span><input value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} maxLength={100} placeholder={t.coverTitleExample}/></label>
          <div className="cover-pair">
            <label className="field"><span>{t.coverSubtitle}</span><input value={draft.subtitle} onChange={e => setDraft({ ...draft, subtitle: e.target.value })} maxLength={160} placeholder={t.coverSubtitleExample}/></label>
            <label className="field"><span>{t.coverKicker}</span><input value={draft.kicker} onChange={e => setDraft({ ...draft, kicker: e.target.value })} maxLength={80} placeholder="5:01 AM – 6:22 PM"/></label>
          </div>
          <div className="cover-pair">
            <label className="field"><span>{t.coverFont}</span><select value={draft.font} onChange={e => setDraft({ ...draft, font: e.target.value })}>
              <option value="default">{t.fontDefault}</option>
              {[true, false].map(chinese => <optgroup key={String(chinese)} label={chinese ? t.fontChinese : t.fontEnglish}>{library?.fonts.filter(font => chineseFonts.includes(font.id) === chinese).map(font => <option value={font.id} key={font.id}>{t.fontNames[font.id as keyof typeof t.fontNames] || font.name}</option>)}</optgroup>)}
            </select></label>
            <label className="field"><span>{t.coverStyle}</span><select value={draft.style} onChange={e => setDraft({ ...draft, style: e.target.value as Cover['style'] })}>{(['clean', 'editorial', 'playful'] as const).map(style => <option key={style} value={style}>{t.coverStyles[style]}</option>)}</select></label>
          </div>
          <p className="cover-type-sample" style={{ fontFamily: `"preset-${family === 'default' ? 'noto-sans' : family}"` }}>{draft.title || t.coverTitleExample}</p>
          <label className="field"><span>{t.coverFrame}</span><input type="text" inputMode="decimal" value={frame} onChange={e => setFrame(e.target.value)} placeholder="2.5 / 00:02.50" aria-describedby="cover-frame-hint"/></label>
          <button className="button quiet" onClick={() => setFrame(Math.min(Math.max(0, bodyDuration - .04), Math.max(0, playTime - offset)).toFixed(2))}>{t.coverUseFrame}</button>
          <p id="cover-frame-hint" className="note">{t.coverFrameHint.replace('{end}', stamp(bodyDuration))}{seconds !== null && ` ${t.coverPlayerTime}: ${stamp(seconds + offset)}`}</p>
          <label className="check"><input type="checkbox" checked={draft.show_intro} onChange={e => setDraft({ ...draft, show_intro: e.target.checked })}/>{t.coverIntro}</label>
          <div className="actions"><button className="button quiet" disabled={!valid} onClick={showPreview}>{working ? t.coverPreviewing : t.coverPreview}</button><button className="button primary" disabled={!valid || !changed} onClick={apply}>{t.coverApply}</button></div>
          {!valid && <p className="note">{t.coverValidation}</p>}
          <p className="note">{t.coverApplyHint}</p>
        </fieldset>
        <div className="cover-preview">
          {image ? <><img src={image} alt={t.coverPreviewAlt}/><a className="caps-link" href={preview?.url || `${coverUrl}?download=true`} download={`${projectName}-cover.png`}>{t.coverDownload}</a><p className="note">{preview && !previewCurrent ? t.coverOutdated : previewCurrent ? t.coverDraft : t.coverSaved}</p></> : <div className="cover-placeholder"><p>{t.coverEmpty}</p></div>}
        </div>
      </div>
      {error && <p className="cover-error" role="alert">{error}</p>}
    </details>
  </section>;
}
