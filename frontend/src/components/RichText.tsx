import { Fragment, useRef, useState, type ReactNode } from 'react';
import { Loader2, Square, Volume2 } from 'lucide-react';
import { endpoints } from '../api/client';

/** Minimal markdown for AI replies: headings, bullets, numbered lists, **bold**, *italic*, links. */
export function RichText({ text }: { text: string }) {
  const lines = text.replace(/\r/g, '').split('\n');
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; start: number; items: string[] } | null = null;

  const flush = () => {
    if (!list) return;
    const items = list.items.map((item, i) => <li key={i}>{inline(item)}</li>);
    blocks.push(list.ordered ? <ol key={blocks.length} start={list.start}>{items}</ol> : <ul key={blocks.length}>{items}</ul>);
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*(\d+)[.)]\s+(.*)$/);
    if (bullet || numbered) {
      const ordered = Boolean(numbered);
      if (!list || list.ordered !== ordered) { flush(); list = { ordered, start: numbered ? Number(numbered[1]) : 1, items: [] }; }
      list.items.push(bullet ? bullet[1] : numbered![2]);
      continue;
    }
    flush();
    if (!line.trim()) continue;
    const heading = line.match(/^#{1,6}\s+(.*)$/);
    if (heading) { blocks.push(<h4 key={blocks.length}>{inline(heading[1])}</h4>); continue; }
    const quote = line.match(/^>\s?(.*)$/);
    if (quote) { blocks.push(<blockquote key={blocks.length}>{inline(quote[1])}</blockquote>); continue; }
    blocks.push(<p key={blocks.length}>{inline(line)}</p>);
  }
  flush();
  return <div className="rich-text">{blocks}</div>;
}

function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)|(https?:\/\/[^\s)]+)|\*(.+?)\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const key = parts.length;
    if (m[1]) parts.push(<strong key={key}>{m[1]}</strong>);
    else if (m[2]) parts.push(<a key={key} href={m[3]} target="_blank" rel="noreferrer">{m[2]}</a>);
    else if (m[4]) parts.push(<a key={key} href={m[4]} target="_blank" rel="noreferrer">{m[4]}</a>);
    else if (m[5]) parts.push(<em key={key}>{m[5]}</em>);
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.map((p, i) => <Fragment key={i}>{p}</Fragment>);
}

/** 🔊 button: reads a text aloud through POST /api/speak (ElevenLabs). */
export function SpeakButton({ text, language }: { text: string; language: 'en' | 'hu' }) {
  const [state, setState] = useState<'idle' | 'loading' | 'playing'>('idle');
  const [error, setError] = useState('');
  const audioRef = useRef<HTMLAudioElement | null>(null);

  async function toggle() {
    if (state === 'playing') { audioRef.current?.pause(); setState('idle'); return; }
    setError('');
    setState('loading');
    try {
      const blob = await endpoints.speak(text, language);
      const audio = new Audio(URL.createObjectURL(blob));
      audioRef.current = audio;
      audio.onended = () => setState('idle');
      await audio.play();
      setState('playing');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Voice unavailable');
      setState('idle');
    }
  }

  return (
    <span className="speak-wrap">
      <button type="button" className="speak-button" onClick={() => void toggle()} disabled={state === 'loading'}
        aria-label={state === 'playing' ? 'Stop reading' : 'Read aloud'} title={error || (state === 'playing' ? 'Stop' : 'Read aloud')}>
        {state === 'loading' ? <Loader2 size={13} className="spin" /> : state === 'playing' ? <Square size={12} /> : <Volume2 size={13} />}
        {state === 'playing' ? 'Stop' : 'Listen'}
      </button>
      {error && <span className="speak-error">{error}</span>}
    </span>
  );
}
