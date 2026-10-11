import React, { useEffect, useState } from 'react';
import { Language, localizeMessage, translations } from './i18n';
import { useChapterLocalization } from './chapter-localization';
import { SpeedControl } from './speed-control';

export type Chapter = { start: number; end: number; title: string; summary: string; clip_ids: string[]; kind: 'scene' | 'hook' | 'body' | 'end_card' | 'cover' };
export type ChapterEdit = { chapter_index: number; action: 'remove' | 'remove_range' | 'speed' | 'instruction'; start?: number; end?: number; speed?: number; instruction?: string };
type Draft = { action: '' | ChapterEdit['action']; start: string; end: string; speed: number; range: boolean; instruction: string };

export function stamp(seconds: number) {
  const centiseconds = Math.round(seconds * 100);
  return `${String(Math.floor(centiseconds / 6000)).padStart(2, '0')}:${String(Math.floor(centiseconds / 100) % 60).padStart(2, '0')}.${String(centiseconds % 100).padStart(2, '0')}`;
}

// Refinement can target fractions of a second and the start at zero.
export function localSeconds(text: string): number | null {
  const value = text.trim().toLowerCase();
  if (/^\d+(?:\.\d+)?$/.test(value)) return Number(value);
  const clock = value.match(/^(\d+):([0-5]\d(?:\.\d+)?)$/);
  if (clock) return Number(clock[1]) * 60 + Number(clock[2]);
  const units = value.match(/^(?:(\d+(?:\.\d+)?)\s*(?:分钟|分|minutes?|mins?|m)\s*)?(?:(\d+(?:\.\d+)?)\s*(?:秒钟|秒|seconds?|secs?|s))?$/);
  return units && (units[1] || units[2]) ? Number(units[1] || 0) * 60 + Number(units[2] || 0) : null;
}

export function ChapterEditor({ chapters, projectName, cut, language, disabled, styleFilm, onSeek, playTime, onApply, onUndo, canUndo }: {
  chapters: Chapter[]; projectName: string; cut: string; language: Language; disabled: boolean; styleFilm: boolean;
  onSeek: (time: number) => void; playTime: number; onApply: (edits: ChapterEdit[], baseCut: string) => Promise<void>;
  onUndo: () => Promise<void>; canUndo: boolean;
}) {
  const t = translations(language);
  const localized = useChapterLocalization(projectName, cut, language, chapters);
  const displayed = localized.translated || chapters.map((chapter, index) => ({ ...chapter, title: t.chapterNumber.replace('{number}', String(index + 1)), summary: '' }));
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [error, setError] = useState('');
  useEffect(() => { setDrafts({}); setError(''); }, [cut]);
  const pending = Object.values(drafts).filter(draft => draft.action).length;
  function initial(chapter: Chapter): Draft { return { action: '', start: '0', end: String(Number((chapter.end - chapter.start).toFixed(6))), speed: 2, range: false, instruction: '' }; }
  function update(index: number, change: Partial<Draft>) {
    setDrafts(current => ({ ...current, [index]: { ...(current[index] || initial(chapters[index])), ...change } }));
    setError('');
  }
  async function apply() {
    const edits: ChapterEdit[] = [];
    for (const [key, draft] of Object.entries(drafts)) {
      if (!draft.action) continue;
      const index = Number(key), chapter = chapters[index];
      const edit: ChapterEdit = { chapter_index: index, action: draft.action };
      if (draft.action === 'remove_range' || (draft.action === 'speed' && draft.range)) {
        const start = localSeconds(draft.start), end = localSeconds(draft.end);
        if (start === null || end === null || start < 0 || end <= start || end > chapter.end - chapter.start + 0.000001) {
          setError(t.refineInvalid.replace('{number}', String(index + 1)).replace('{seconds}', String(Number((chapter.end - chapter.start).toFixed(3))))); return;
        }
        edit.start = start; edit.end = end;
      }
      if (draft.action === 'speed') edit.speed = draft.speed;
      if (draft.action === 'instruction') {
        if (!draft.instruction.trim()) { setError(t.refineEmpty.replace('{number}', String(index + 1))); return; }
        edit.instruction = draft.instruction.trim();
      }
      edits.push(edit);
    }
    try { await onApply(edits, cut); } catch (exc) { setError(localizeMessage(exc instanceof Error ? exc.message : t.generic, language)); }
  }
  return <section className="column film-chapters" aria-label={t.chapters}>
    <h3>{t.chapters}</h3>{!styleFilm && <p className="note">{t.refineHint}</p>}
    {localized.loading && <p className="note" role="status">{t.chapterTranslationPending}</p>}
    {localized.error && <div className="note" role="alert">{t.chapterTranslationError} {localizeMessage(localized.error, language)} <button type="button" className="caps-link" onClick={localized.retry}>{t.chapterTranslationRetry}</button></div>}
    {styleFilm && <p className="note">{t.refineStyleHint}</p>}
    <div className="chapter-track" aria-label={t.chapters}>{displayed.map((chapter, index) => <button key={index} style={{ flexGrow: chapter.end - chapter.start }} className={playTime >= chapter.start && playTime < chapter.end ? 'is-current' : ''} aria-label={`${stamp(chapter.start)} ${chapter.title}`} title={`${stamp(chapter.start)} ${chapter.title}`} onClick={() => onSeek(chapter.start)}/>)}</div>
    <ol className="chapter-list">{displayed.map((chapter, index) => {
      const draft = drafts[index] || initial(chapter);
      const start = localSeconds(draft.start), end = localSeconds(draft.end);
      const whole = draft.action === 'remove' || (draft.action === 'speed' && !draft.range);
      const preview = whole ? `${stamp(chapter.start)} – ${stamp(chapter.end)}` : start !== null && end !== null ? `${stamp(chapter.start + start)} – ${stamp(chapter.start + end)}` : '';
      return <li key={index} aria-current={playTime >= chapter.start && playTime < chapter.end ? 'true' : undefined}>
        <button className="chapter-seek" onClick={() => onSeek(chapter.start)}><time>{stamp(chapter.start)} – {stamp(chapter.end)}</time><strong>{chapter.kind !== 'scene' ? t.chapterKinds[chapter.kind] + ' · ' : ''}{chapter.title}</strong></button>
        <p>{chapter.summary}</p>{chapter.kind === 'cover' && <p className="note"><a href="#cover">{t.coverChapterHint}</a></p>}
        {!styleFilm && chapter.kind !== 'cover' && <details className="chapter-refinement"><summary>{t.refineChapter}{draft.action ? ' · ' + t.refinePending : ''}</summary>
          <fieldset disabled={disabled} aria-label={t.refineNumber.replace('{number}', String(index + 1))}>
            <label className="field"><span>{t.refineAction}</span><select value={draft.action} onChange={event => update(index, { action: event.target.value as Draft['action'] })}>
              <option value="">{t.refineKeep}</option><option value="remove">{t.refineDeleteWhole}</option><option value="remove_range">{t.refineDeleteRange}</option><option value="speed">{t.refineSpeed}</option><option value="instruction">{t.refineText}</option>
            </select></label>
            {draft.action === 'speed' && <><SpeedControl id={`chapter-speed-${index}`} label={t.refineSpeed} value={draft.speed} onChange={speed => update(index, { speed })} disabled={disabled}/><p className="note">{t.editSpeedHint}</p><label className="check"><input type="checkbox" checked={draft.range} onChange={event => update(index, { range: event.target.checked })}/>{t.refinePartial}</label></>}
            {(draft.action === 'remove_range' || (draft.action === 'speed' && draft.range)) && <div className="refine-time-fields"><label className="field"><span>{t.refineStart}</span><input value={draft.start} onChange={event => update(index, { start: event.target.value })} placeholder="00:00" maxLength={40}/></label><label className="field"><span>{t.refineEnd}</span><input value={draft.end} onChange={event => update(index, { end: event.target.value })} placeholder="00:02" maxLength={40}/></label></div>}
            {draft.action === 'instruction' && <div className="field"><label htmlFor={`chapter-instruction-${index}`}>{t.refineText}</label><div className="input-examples"><span>{t.examples}</span>{[t.refineDeleteWhole, t.refineSpeedExample].map(example => <button type="button" key={example} onClick={() => update(index, { instruction: example })}>{example}</button>)}</div><textarea id={`chapter-instruction-${index}`} placeholder={t.refineTextPlaceholder} value={draft.instruction} maxLength={1000} onChange={event => update(index, { instruction: event.target.value })}/><p className="note">{t.refineTextHint}</p></div>}
            {draft.action && <>{draft.action !== 'instruction' && <p className="note">{t.refineMapped.replace('{range}', preview)}</p>}<p className="note">{t.refineCount.replace('{count}', String(pending))}</p><div className="actions"><button type="button" className="button primary" disabled={disabled} onClick={apply}>{t.refineApply}</button><button type="button" className="button quiet" onClick={() => update(index, { action: '', instruction: '' })}>{t.refineReset}</button></div>{error && <p className="note invalid" role="alert">{error}</p>}</>}
          </fieldset>
        </details>}
      </li>;
    })}</ol>
    {!styleFilm && <div className={'refine-batch' + (pending ? ' has-pending' : '')}>
      <p role="status">{t.refineCount.replace('{count}', String(pending))}</p>
      {error && <p className="note invalid" role="alert">{error}</p>}
      <div className="actions"><button className="button primary" disabled={disabled || !pending} onClick={apply}>{t.refineApply}</button><button className="button quiet" disabled={disabled || !canUndo} onClick={onUndo}>{t.undo}</button></div>
    </div>}
  </section>;
}
