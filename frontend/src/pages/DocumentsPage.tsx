import { useRef, useState } from 'react';
import { AlertCircle, Check, FileText, FolderOpen, Pencil, Plus, UploadCloud, X } from 'lucide-react';
import type { Fact, StudentDocument } from '../api/types';
import { DocumentHelp, ExplainStored } from '../components/DocumentHelp';
import { endpoints } from '../api/client';
import { formatDate, formatLabel } from '../utils';
import { Badge, Button, EmptyState, Field, Notice, Panel, VerificationBadge } from '../components/UI';

export function DocumentsPage({ documents, onChanged }: { documents: StudentDocument[]; onChanged: () => Promise<void> }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [expanded, setExpanded] = useState<string | null>(documents[0]?.id ?? null);
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState('');
  const [actionError, setActionError] = useState('');
  const [manualDocument, setManualDocument] = useState<string | null>(null);
  const [manualKey, setManualKey] = useState('');
  const [manualValue, setManualValue] = useState('');

  async function handleUpload(file?: File) {
    if (!file) return;
    setUploadError('');
    setUploadSuccess('');
    if (file.size > 10 * 1024 * 1024) {
      setUploadError('The file exceeds the 10 MB upload limit.');
      return;
    }
    const allowed = /\.(pdf|txt|png|jpe?g)$/i.test(file.name);
    if (!allowed) {
      setUploadError('Supported file types are PDF, TXT, PNG, JPG and JPEG.');
      return;
    }
    const form = new FormData();
    form.append('file', file);
    setUploading(true);
    try {
      const uploaded = await endpoints.uploadDocument(form);
      setUploadSuccess(`${uploaded.title || file.name} was uploaded.`);
      setExpanded(uploaded.id);
      await onChanged();
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function verify(documentId: string, fieldKey: string, decision: 'confirm' | 'reject', value?: string) {
    const key = `${documentId}:${fieldKey}`;
    setSavingKey(key);
    setActionError('');
    try {
      await endpoints.verifyField(documentId, fieldKey, { decision, ...(value !== undefined ? { value } : {}) });
      setEditing((current) => { const next = { ...current }; delete next[key]; return next; });
      await onChanged();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Could not update this field.');
    } finally {
      setSavingKey('');
    }
  }

  async function addManualField(documentId: string) {
    if (!manualKey.trim() || !manualValue.trim()) return;
    await verify(documentId, manualKey.trim(), 'confirm', manualValue.trim());
    setManualKey('');
    setManualValue('');
    setManualDocument(null);
  }

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div><div className="eyebrow"><span className="eyebrow-line" /> YOUR SOURCE OF TRUTH</div><h1>My documents</h1><p className="page-lede">Your records are the evidence behind your student journey. Review what the system extracts.</p></div>
        <Button onClick={() => fileRef.current?.click()} disabled={uploading}><UploadCloud size={16} /> {uploading ? 'Uploading…' : 'Upload document'}</Button>
        <input ref={fileRef} type="file" accept=".pdf,.txt,.png,.jpg,.jpeg" className="visually-hidden" onChange={(event) => void handleUpload(event.target.files?.[0])} />
      </div>

      {uploadError && <Notice tone="danger">{uploadError}</Notice>}
      {uploadSuccess && <Notice tone="success">{uploadSuccess}</Notice>}
      {actionError && <Notice tone="danger">{actionError}</Notice>}

      <div className="library-summary-row">
        <div className="library-summary"><span className="summary-icon purple"><FolderOpen size={18} /></span><div><strong>{documents.length} documents</strong><span>In your personal library</span></div></div>
        <div className="library-summary"><span className="summary-icon amber"><AlertCircle size={18} /></span><div><strong>{documents.reduce((n, doc) => n + Object.values(doc.fields ?? {}).filter((field) => field.status === 'extracted_pending_confirmation').length, 0)} pending fields</strong><span>Awaiting your confirmation</span></div></div>
        <div className="library-summary"><span className="summary-icon green"><Check size={18} /></span><div><strong>{documents.reduce((n, doc) => n + Object.values(doc.fields ?? {}).filter((field) => field.status === 'confirmed').length, 0)} verified fields</strong><span>Confirmed information</span></div></div>
      </div>

      <DocumentHelp />

      <Panel title="Document library" subtitle="Select a document to inspect its extracted information.">
        {documents.length ? <div className="document-library-list">
          {documents.map((document) => {
            const isOpen = expanded === document.id;
            const entries = Object.entries(document.fields ?? {});
            const pending = entries.filter(([, field]) => field.status === 'extracted_pending_confirmation').length;
            return (
              <article className={`library-document ${isOpen ? 'is-open' : ''}`} key={document.id}>
                <button className="library-document-header" onClick={() => setExpanded(isOpen ? null : document.id)}>
                  <div className="document-type-icon"><FileText size={20} /></div>
                  <div className="library-document-copy"><strong>{document.title || formatLabel(document.type)}</strong><span>{document.original_filename || formatLabel(document.type)} · Added {formatDate(document.uploaded_at)}</span></div>
                  <div className="library-document-meta">{pending > 0 ? <Badge tone="warning">{pending} to review</Badge> : <Badge tone="success">Up to date</Badge>}<span className={`expand-chevron ${isOpen ? 'expanded' : ''}`}>⌄</span></div>
                </button>
                {isOpen && <div className="document-expanded">
                  {document.extraction_error && <Notice tone="warning"><strong>Extraction issue:</strong> {document.extraction_error} You can add the relevant fields manually below.</Notice>}
                  {entries.length ? <div className="extracted-fields">
                    {entries.map(([fieldKey, fact]) => <ExtractedField key={fieldKey} documentId={document.id} fieldKey={fieldKey} fact={fact} saving={savingKey === `${document.id}:${fieldKey}`} editingValue={editing[`${document.id}:${fieldKey}`]} onEdit={(value) => setEditing((current) => ({ ...current, [`${document.id}:${fieldKey}`]: value }))} onConfirm={(value) => void verify(document.id, fieldKey, 'confirm', value)} onReject={() => void verify(document.id, fieldKey, 'reject')} />)}
                  </div> : <EmptyState title="No fields extracted" description="This document does not currently contain extracted fields." />}
                  {manualDocument === document.id ? <div className="manual-field-form"><Field label="Field name"><input value={manualKey} onChange={(event) => setManualKey(event.target.value)} placeholder="e.g. expiry_date" /></Field><Field label="Field value"><input value={manualValue} onChange={(event) => setManualValue(event.target.value)} placeholder="Enter the verified value" /></Field><div className="inline-actions"><Button size="sm" onClick={() => void addManualField(document.id)} disabled={!manualKey.trim() || !manualValue.trim() || Boolean(savingKey)}>Save field</Button><Button size="sm" variant="ghost" onClick={() => setManualDocument(null)}>Cancel</Button></div></div> : <button className="add-field-button" onClick={() => { setManualDocument(document.id); setManualKey(''); setManualValue(''); }}><Plus size={15} /> Add a field manually</button>}
                  {document.extracted_text && <ExplainStored text={document.extracted_text} />}
                  {document.extracted_text && <details className="source-text"><summary>View extracted text</summary><pre>{document.extracted_text}</pre></details>}
                  <div className="document-id-line">Document ID: <code>{document.id}</code></div>
                </div>}
              </article>
            );
          })}
        </div> : <EmptyState title="Your document library is empty" description="Upload a passport, enrollment certificate, accommodation document or official letter to get started." icon={<UploadCloud size={21} />} />}
      </Panel>
      <p className="subtle-footnote">Supported formats: PDF, TXT, PNG, JPG and JPEG. Maximum file size: 10 MB. Image OCR is not implemented in this demo.</p>
    </div>
  );
}

function ExtractedField({
  documentId,
  fieldKey,
  fact,
  saving,
  editingValue,
  onEdit,
  onConfirm,
  onReject,
}: {
  documentId: string;
  fieldKey: string;
  fact: Fact;
  saving: boolean;
  editingValue?: string;
  onEdit: (value: string) => void;
  onConfirm: (value?: string) => void;
  onReject: () => void;
}) {
  const value = fact.value == null ? '' : String(fact.value);
  const pending = fact.status === 'extracted_pending_confirmation';
  const isEditing = editingValue !== undefined;
  return (
    <div className={`extracted-field ${pending ? 'field-pending' : ''}`}>
      <div className="extracted-field-main">
        <div><span className="field-key">{formatLabel(fieldKey)}</span><div className="field-value">{value || <em>No value</em>}</div><span className="field-source">Source: {fact.source || 'Not specified'}</span></div>
        <VerificationBadge status={fact.status} />
      </div>
      {pending && <div className="field-review-area">
        {isEditing && <input value={editingValue} onChange={(event) => onEdit(event.target.value)} aria-label={`Correct ${formatLabel(fieldKey)}`} />}
        <div className="inline-actions">
          {isEditing ? <><Button size="sm" onClick={() => onConfirm(editingValue)} disabled={saving || !editingValue.trim()}><Check size={14} /> Save correction</Button><Button size="sm" variant="ghost" onClick={() => onEdit(value)}><X size={14} /> Cancel</Button></> : <><Button size="sm" onClick={() => onConfirm()} disabled={saving}><Check size={14} /> Confirm</Button><Button size="sm" variant="secondary" onClick={() => onEdit(value)} disabled={saving}><Pencil size={13} /> Correct</Button><Button size="sm" variant="ghost" onClick={onReject} disabled={saving}><X size={14} /> Reject</Button></>}
          {saving && <span className="saving-label">Saving…</span>}
        </div>
      </div>}
      {!pending && fact.confidence !== null && <div className="field-confidence">Extraction confidence: {Math.round(fact.confidence * 100)}%</div>}
      <span className="sr-only">Document {documentId}</span>
    </div>
  );
}
