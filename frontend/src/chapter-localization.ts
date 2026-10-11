import { useEffect, useState } from 'react';
import { Chapter } from './chapter-editor';
import { Language } from './i18n';

type Result = { cut: string; language: Language; chapters: Chapter[] };

export function useChapterLocalization(projectName: string, cut: string, language: Language, chapters: Chapter[]) {
  const fingerprint = JSON.stringify(chapters);
  const identity = JSON.stringify([projectName, cut, language, fingerprint]);
  const [state, setState] = useState<{ identity: string; result?: Result; error?: string }>({ identity: '' });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let retryTimer: number | undefined;
    setState({ identity });
    async function translate(retries = 0) {
      try {
        const response = await fetch(`/api/vlogii/projects/${encodeURIComponent(projectName)}/chapters/localize`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ base_cut: cut, language }), signal: controller.signal,
        });
        if (response.status === 409 && retries < 120) {
          retryTimer = window.setTimeout(() => translate(retries + 1), 3000); return;
        }
        const value = await response.json();
        if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : 'Could not translate chapter text. Retry translation.');
        const result = value as Result;
        if (result.cut !== cut || result.language !== language || result.chapters.length !== chapters.length || result.chapters.some((chapter, index) => chapter.start !== chapters[index].start || chapter.end !== chapters[index].end)) {
          throw new Error('Chapter translation returned mismatched text. Retry translation.');
        }
        if (!controller.signal.aborted) setState({ identity, result });
      } catch (error) {
        if (!controller.signal.aborted) setState({ identity, error: error instanceof Error ? error.message : 'Could not translate chapter text. Retry translation.' });
      }
    }
    void translate();
    return () => { controller.abort(); if (retryTimer !== undefined) window.clearTimeout(retryTimer); };
  }, [identity, attempt]);
  const current = state.identity === identity ? state : undefined;
  return { translated: current?.result?.chapters, loading: !current?.result && !current?.error, error: current?.error, retry: () => setAttempt(value => value + 1) };
}
