export type ProgressStage = 'prepare' | 'speech' | 'visual' | 'planning' | 'render';

// Analysis stages alternate for each clip. Never infer a global percentage.
export function jobProgress(message: string) {
  let stage: ProgressStage | null = null;
  if (/^(Preparing video|Inspecting)/.test(message)) stage = 'prepare';
  else if (/^Speech (recognition|cached)/.test(message)) stage = 'speech';
  else if (/^(AI analysis|Analysis cached|Checking black frames)/.test(message)) stage = 'visual';
  else if (/^(Planning your film|Resuming the saved plan)/.test(message)) stage = 'planning';
  else if (/^(Rendering|Joining segments|Checking video and audio|Complete:)/.test(message)) stage = 'render';
  const counts = message.match(/^(?:Preparing video|Inspecting|AI analysis|Analysis cached:|Speech recognition|Speech cached:|Checking black frames|Rendering(?: cached)?) (\d+)\/(\d+)/);
  if (!counts || Number(counts[2]) < 1 || Number(counts[1]) < 1 || Number(counts[1]) > Number(counts[2])) return { stage, current: null, total: null, percent: null };
  const current = Number(counts[1]), total = Number(counts[2]);
  const completed = /cached/.test(message) ? current : current - 1;
  return { stage, current, total, percent: Math.floor(completed / total * 100) };
}
