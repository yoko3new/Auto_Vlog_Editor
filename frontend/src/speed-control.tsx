import React from 'react';

export function SpeedControl({ id, label, value, onChange, disabled, hintId, enabled = true, onToggle }: {
  id: string; label: string; value: number; onChange: (value: number) => void;
  disabled: boolean; hintId?: string; enabled?: boolean; onToggle?: (enabled: boolean) => void;
}) {
  return <div className="inline-range">
    {onToggle ? <label className="check speed-toggle" htmlFor={`${id}-enabled`}><input id={`${id}-enabled`} type="checkbox" checked={enabled} onChange={event => onToggle(event.target.checked)} disabled={disabled}/>{label}</label> : <label htmlFor={id}>{label}</label>}
    <div className="range-slider">
      <input id={id} type="range" min={0.5} max={2} step={0.1} value={value} aria-label={onToggle ? label : undefined} aria-valuetext={`${value}×`} aria-describedby={hintId} onChange={event => onChange(Number(event.target.value))} disabled={disabled || !enabled}/>
      <output htmlFor={id}>{enabled ? `${value}×` : '—'}</output>
    </div>
  </div>;
}
