import { useRef, useState } from 'react';
import { Sparkles, UploadCloud } from 'lucide-react';
import type { ExplainResponse } from '../api/types';
import { endpoints } from '../api/client';
import { formatDate, formatLabel } from '../utils';
import { Badge, Button, Notice, Panel } from './UI';
import { RichText, SpeakButton } from './RichText';

function ExplanationView({ result }: { result: ExplainResponse }) {
  return (
    <div className="explanation-card">
      <div className="explanation-meta">
        <span>Type: <strong>{formatLabel(result.document_type)}</strong></span>
        {result.dates_found.length > 0 && <span className="explanation-dates">Dates: {result.dates_found.map((d) => <Badge key={d} tone="info">{formatDate(d)}</Badge>)}</span>}
        <SpeakButton text={result.explanation} language={result.language} />
      </div>
      {result.truncated && <Notice tone="warning">The document was long, so only the first part was explained.</Notice>}
      <RichText text={result.explanation} />
      <p className="subtle-footnote">{result.mock ? 'Mock explanation (no AI key configured).' : `Explained by ${result.model}.`} Sera is not a lawyer: confirm important steps with the sender or your international office.</p>
    </div>
  );
}

/** Explain any letter: paste text or pick a file. Nothing is stored. */
export function DocumentHelp() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState<'en' | 'hu'>('en');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ExplainResponse | null>(null);

  async function run() {
    setError('');
    setResult(null);
    setBusy(true);
    try {
      setResult(await endpoints.explain(file ? { file, language } : { text, language }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sera could not explain this document.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Explain a letter with Sera" subtitle="Paste an official letter or choose a PDF/TXT. Sera explains it in simple words. Nothing is saved.">
      <div className="explain-form">
        <textarea value={text} rows={5}
          onChange={(e) => { setText(e.target.value); setFile(null); if (fileRef.current) fileRef.current.value = ''; }}
          placeholder="Paste the letter here: a message from the immigration office, your landlord, the university…" />
        <div className="inline-actions">
          <Button variant="secondary" size="sm" onClick={() => fileRef.current?.click()}><UploadCloud size={14} /> {file ? file.name : 'Choose file'}</Button>
          <input ref={fileRef} type="file" accept=".pdf,.txt" className="visually-hidden"
            onChange={(e) => { const f = e.target.files?.[0] ?? null; setFile(f); if (f) setText(''); }} />
          <div className="lang-switch" role="group" aria-label="Explanation language">
            {(['en', 'hu'] as const).map((l) => <button key={l} type="button" className={language === l ? 'active' : ''} onClick={() => setLanguage(l)}>{l.toUpperCase()}</button>)}
          </div>
          <Button size="sm" onClick={() => void run()} disabled={busy || (!file && text.trim().length < 20)}><Sparkles size={14} /> {busy ? 'Explaining…' : 'Explain'}</Button>
        </div>
        {error && <Notice tone="danger">{error}</Notice>}
        {result && <ExplanationView result={result} />}
      </div>
    </Panel>
  );
}

/** "Explain with Sera" for a document already in the library (uses its extracted text). */
export function ExplainStored({ text }: { text: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ExplainResponse | null>(null);

  async function run(language: 'en' | 'hu') {
    setBusy(true);
    setError('');
    try { setResult(await endpoints.explain({ text, language })); }
    catch (err) { setError(err instanceof Error ? err.message : 'Sera could not explain this document.'); }
    finally { setBusy(false); }
  }

  return (
    <div className="explain-stored">
      <div className="inline-actions">
        <Button size="sm" variant="secondary" onClick={() => void run('en')} disabled={busy}><Sparkles size={14} /> {busy ? 'Explaining…' : 'Explain with Sera'}</Button>
        <Button size="sm" variant="ghost" onClick={() => void run('hu')} disabled={busy}>Magyarul</Button>
      </div>
      {error && <Notice tone="danger">{error}</Notice>}
      {result && <ExplanationView result={result} />}
    </div>
  );
}
