import React from 'react';
import { Language, translations } from './i18n';

export type Appearance = { font: string; music: string; music_volume: number; duck_music: boolean };
export type Preset = { id: string; name: string; url: string; author?: string; license: string; source: string; duration_seconds?: number };
export type PresetLibrary = { fonts: Preset[]; music: Preset[] };
export const defaultAppearance: Appearance = { font: 'default', music: 'auto', music_volume: 0.16, duck_music: true };

export function AppearanceControls({ value, onChange, library, language, disabled, muted, id, styleMusic = false, uploadedName }: {
  value: Appearance; onChange: (value: Appearance) => void; library: PresetLibrary | null;
  language: Language; disabled: boolean; muted: boolean; id: string; styleMusic?: boolean; uploadedName?: string;
}) {
  const t = translations(language);
  const musicId = value.music === 'auto' ? (muted ? 'holizna-dancing' : 'holizna-day-jobs') : value.music;
  const music = library?.music.find(item => item.id === musicId);
  const fontId = value.font === 'default' ? 'noto-sans' : value.font;
  const chineseFonts = ['noto-sans', 'noto-serif', 'ma-shan-zheng', 'zcool-xiaowei'];
  const englishOnly = !chineseFonts.includes(fontId);
  const styleDefault = styleMusic && value.font === 'default';
  const family = (identifier: string) => `"preset-${identifier}"`;
  return <fieldset className="appearance-controls" disabled={disabled || !library}>
    <legend>{t.appearance}</legend>
    <style>{library?.fonts.map(font => `@font-face{font-family:"preset-${font.id}";src:url("${font.url}");font-display:swap;}`).join('\n')}</style>
    <label className="field"><span>{t.captionFont}</span><select value={value.font} onChange={event => onChange({ ...value, font: event.target.value })}>
      <option value="default">{styleMusic ? t.styleFontDefault : t.fontDefault}</option>
      {[true, false].map(chinese => <optgroup key={String(chinese)} label={chinese ? t.fontChinese : t.fontEnglish}>{library?.fonts.filter(font => chineseFonts.includes(font.id) === chinese).map(font => <option key={font.id} value={font.id}>{t.fontNames[font.id as keyof typeof t.fontNames] || font.name}</option>)}</optgroup>)}
    </select></label>
    {styleDefault ? <p className="note font-style-default">{t.styleFontPreview}</p> : <div className="font-sample" aria-label={t.fontPreview}>
      <span style={{ fontFamily: family(englishOnly ? 'noto-sans' : fontId) }}>记录今天的美好时刻</span>
      <span style={{ fontFamily: family(fontId) }}>A little film of my day.</span>
    </div>}
    <label className="field"><span>{t.backgroundMusic}</span><select value={value.music} onChange={event => onChange({ ...value, music: event.target.value })}>
      <option value="auto">{t.musicAuto}</option>{!styleMusic && <option value="none">{t.musicNone}</option>}
      {styleMusic && uploadedName && <option value="uploaded">{t.musicUploaded}: {uploadedName}</option>}
      {library?.music.map(track => <option key={track.id} value={track.id}>{track.name} — {track.author}</option>)}
    </select></label>
    {music && <div className="music-preview">
      <p>{t.listen}: {music.name} — {music.author}</p>
      <audio key={music.id + id} src={music.url} controls preload="metadata" aria-label={`${t.listen}: ${music.name}`}/>
    </div>}
    {value.music !== 'none' && <div className="music-settings">
      <div className="inline-range"><label htmlFor={`music-volume-${id}`}>{t.musicVolume}</label><div className="range-slider"><input id={`music-volume-${id}`} type="range" min={0} max={100} step={1} value={Math.round(value.music_volume * 100)} aria-valuetext={`${Math.round(value.music_volume * 100)}%`} onChange={event => onChange({ ...value, music_volume: Number(event.target.value) / 100 })}/><output htmlFor={`music-volume-${id}`}>{Math.round(value.music_volume * 100)}%</output></div></div>
      {!styleMusic && <label className="check"><input type="checkbox" checked={value.duck_music} onChange={event => onChange({ ...value, duck_music: event.target.checked })}/>{t.duckMusic}</label>}
      {music && <p className="note"><a href={music.source} target="_blank" rel="noreferrer">{music.license} · {t.resourceSource}</a></p>}
    </div>}
  </fieldset>;
}
