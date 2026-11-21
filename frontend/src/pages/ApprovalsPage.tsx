import { useState, type FormEvent } from 'react';
import { Check, Mail, Plus, ShieldCheck, X } from 'lucide-react';
import type { ApprovalRequest, Mission } from '../api/types';
import { endpoints } from '../api/client';
import { formatDate } from '../utils';
import { Badge, Button, EmptyState, Field, Notice, Panel, StatusBadge } from '../components/UI';

export function ApprovalsPage({ approvals, missions, onChanged }: { approvals: ApprovalRequest[]; missions: Mission[]; onChanged: () => Promise<void> }) {
  const [showComposer, setShowComposer] = useState(false);
  const [busyId, setBusyId] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [form, setForm] = useState({ missionId: '', to: '', subject: '', body: '' });

  async function createRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setError('');
    setSuccess('');
    try {
      const created = await endpoints.createApproval({
        mission_id: form.missionId || null,
        to: form.to.trim(),
        subject: form.subject.trim(),
        body: form.body.trim(),
      });
      setShowComposer(false);
      setForm({ missionId: '', to: '', subject: '', body: '' });
      setSuccess(`Approval request ${created.id} was created. Review its full contents below before deciding.`);
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create approval request.');
    } finally {
      setCreating(false);
    }
  }

  async function decide(approvalId: string, decision: 'approve' | 'reject') {
    setBusyId(approvalId);
    setError('');
    setSuccess('');
    try {
      await endpoints.decideApproval(approvalId, decision);
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record this decision.');
    } finally {
      setBusyId('');
    }
  }

  const pendingCount = approvals.filter((approval) => approval.status === 'pending').length;

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div><div className="eyebrow"><span className="eyebrow-line" /> HUMAN CONTROL, ALWAYS</div><h1>Approvals</h1><p className="page-lede">Review prepared actions before they are approved. Nothing is sent automatically.</p></div>
        <Button onClick={() => setShowComposer((value) => !value)}><Plus size={16} /> Prepare an email</Button>
      </div>

      {error && <Notice tone="danger">{error}</Notice>}
      {success && <Notice tone="success">{success}</Notice>}
      <div className="approval-banner"><div className="approval-banner-icon"><ShieldCheck size={21} /></div><div><strong>You're in control.</strong><p>Every prepared email displays its recipient, subject and full message before the approval decision.</p></div><Badge tone="warning">{pendingCount} awaiting review</Badge></div>

      {showComposer && <Panel title="Prepare an email for approval" subtitle="Create a draft action. The backend does not send real email in this demo." className="approval-composer">
        <form onSubmit={createRequest} className="form-grid">
          <Field label="Related mission"><select value={form.missionId} onChange={(event) => setForm((current) => ({ ...current, missionId: event.target.value }))}><option value="">No linked mission</option>{missions.map((mission) => <option value={mission.id} key={mission.id}>{mission.title}</option>)}</select></Field>
          <Field label="Recipient email"><input type="email" required value={form.to} onChange={(event) => setForm((current) => ({ ...current, to: event.target.value }))} placeholder="office@example.org" /></Field>
          <div className="form-full"><Field label="Subject"><input required value={form.subject} onChange={(event) => setForm((current) => ({ ...current, subject: event.target.value }))} placeholder="Subject of your email" /></Field></div>
          <div className="form-full"><Field label="Message body"><textarea rows={6} required value={form.body} onChange={(event) => setForm((current) => ({ ...current, body: event.target.value }))} placeholder="Write the message you want reviewed…" /></Field></div>
          <div className="form-full inline-actions"><Button type="submit" disabled={creating || !form.to.trim() || !form.subject.trim() || !form.body.trim()}>{creating ? 'Preparing…' : 'Create approval request'}</Button><Button type="button" variant="ghost" onClick={() => setShowComposer(false)}>Cancel</Button></div>
        </form>
      </Panel>}

      <Panel title="Approval requests" subtitle="Every request remains visible with its decision and execution result.">
        {approvals.length ? <div className="approval-list">{approvals.map((approval) => <article className="approval-card" key={approval.id}>
          <div className="approval-card-heading"><div className="approval-mail-icon"><Mail size={18} /></div><div className="approval-title-copy"><strong>{approval.summary || 'Email approval request'}</strong><span>Created {formatDate(approval.created_at)} · {approval.mission_id ? `Mission ${approval.mission_id}` : 'No linked mission'}</span></div><StatusBadge status={approval.status} /></div>
          <div className="email-preview">
            <div className="email-field"><span>To</span><strong>{approval.payload?.to || 'Recipient not provided'}</strong></div>
            <div className="email-field"><span>Subject</span><strong>{approval.payload?.subject || 'No subject'}</strong></div>
            <div className="email-body-preview"><span>Message</span><p>{approval.payload?.body || 'No message body provided.'}</p></div>
          </div>
          {approval.status === 'pending' ? <div className="approval-decision-row"><span className="decision-hint">Review the full email above before deciding.</span><div className="inline-actions"><Button size="sm" variant="secondary" onClick={() => void decide(approval.id, 'reject')} disabled={busyId === approval.id}><X size={14} /> Reject</Button><Button size="sm" onClick={() => void decide(approval.id, 'approve')} disabled={busyId === approval.id}><Check size={14} /> Approve</Button></div></div> : <div className="approval-result"><div className="approval-result-heading"><strong>Decision result</strong><StatusBadge status={approval.status} /></div><p>{approval.result || `This request is marked as ${approval.status}.`}</p>{approval.status === 'simulated' && <Notice tone="info">This action was simulated. The email was not actually sent.</Notice>}</div>}
          <div className="approval-id">Request ID: <code>{approval.id}</code></div>
        </article>)}</div> : <EmptyState title="No approval requests" description="Prepare an email when you need to contact an institution. Review and approval controls will appear here." icon={<Mail size={21} />} />}
      </Panel>
      <p className="subtle-footnote">In this demo, approving an email produces a simulated result. The application must never display a simulated action as successfully sent.</p>
    </div>
  );
}
