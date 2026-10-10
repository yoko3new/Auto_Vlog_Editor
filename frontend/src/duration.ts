// The API takes seconds; accept common duration notation in the editor.
export function parseTargetSeconds(input: string): number | null {
  const text = input.trim().toLowerCase()
    .replace(/^(?:大约|约|about\s+|approximately\s+|approx\.?\s+|~\s*)/, '')
    .replace(/\s*(?:左右|上下)$/, '').trim();
  if (!text) return null;
  let seconds: number;
  if (/^\d+(?:\.\d+)?$/.test(text)) {
    seconds = Number(text);
  } else {
    const clock = text.match(/^(\d+):([0-5]\d(?:\.\d+)?)$/);
    const units = text.match(/^(?:(\d+(?:\.\d+)?)\s*(?:分钟|分|minutes?|mins?|m)\s*)?(?:(\d+(?:\.\d+)?)\s*(?:秒钟|秒|seconds?|secs?|s))?$/);
    if (clock) seconds = Number(clock[1]) * 60 + Number(clock[2]);
    else if (units && (units[1] || units[2])) seconds = Number(units[1] || 0) * 60 + Number(units[2] || 0);
    else return null;
  }
  return Number.isFinite(seconds) && seconds >= 1 && seconds <= 1800 ? seconds : null;
}
