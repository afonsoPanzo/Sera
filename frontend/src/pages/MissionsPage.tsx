import { useState, type FormEvent } from 'react';
import { ArrowRight, CalendarDays, Check, Circle, Plus } from 'lucide-react';
import type { Mission, MissionStatus, StudentDocument } from '../api/types';
import { endpoints } from '../api/client';
import { formatDate, formatLabel, nextMissionStatus } from '../utils';
import { Badge, Button, EmptyState, Field, Notice, Panel, StatusBadge } from '../components/UI';

export function MissionsPage({ missions, documents, onChanged }: { missions: Mission[]; documents: StudentDocument[]; onChanged: () => Promise<void> }) {
  const [selectedId, setSelectedId] = useState<string | null>(missions[0]?.id ?? null);
  const [selectedDetails, setSelectedDetails] = useState<Mission | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [actionError, setActionError] = useState('');
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: '', institution: '', deadline: '', documentIds: [] as string[], tasks: 'Review the requirements\nGather the required documents' });

  const selected = selectedDetails?.id === selectedId ? selectedDetails : missions.find((mission) => mission.id === selectedId) ?? null;

  async function selectMission(missionId: string) {
    setSelectedId(missionId);
    setLoadingDetails(true);
    setActionError('');
    try {
      const details = await endpoints.missionDetails(missionId);
      setSelectedDetails(details);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Could not load mission details.');
      setSelectedDetails(null);
    } finally {
      setLoadingDetails(false);
    }
  }

  async function updateStatus(status: MissionStatus) {
    if (!selected) return;
    setActionError('');
    try {
      await endpoints.updateMissionStatus(selected.id, status);
      setSelectedDetails(null);
      await onChanged();
      await selectMission(selected.id);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Could not update mission status.');
    }
  }

  async function toggleTask(taskId: string, done: boolean) {
    if (!selected) return;
    setActionError('');
    try {
      await endpoints.updateTask(selected.id, taskId, !done);
      const details = await endpoints.missionDetails(selected.id);
      setSelectedDetails(details);
      await onChanged();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Could not update this task.');
    }
  }

  async function createMission(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.title.trim()) return;
    setCreating(true);
    setActionError('');
    try {
      const created = await endpoints.createMission({
        title: form.title.trim(),
        institution: form.institution.trim() || 'Not specified',
        ...(form.deadline ? { deadline: form.deadline } : {}),
        document_ids: form.documentIds,
        depends_on: [],
        tasks: form.tasks.split('\n').map((task) => task.trim()).filter(Boolean),
      });
      setShowCreate(false);
      setForm({ title: '', institution: '', deadline: '', documentIds: [], tasks: 'Review the requirements\nGather the required documents' });
      await onChanged();
      setSelectedDetails(created);
      setSelectedId(created.id);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Could not create mission.');
    } finally {
      setCreating(false);
    }
  }

  const nextStatus = selected ? nextMissionStatus(selected.status) : null;
  const canCancel = selected ? !['COMPLETED', 'CANCELLED', 'BLOCKED', 'EXPIRED'].includes(selected.status) : false;
  const doneTasks = selected?.tasks.filter((task) => task.done).length ?? 0;

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div><div className="eyebrow"><span className="eyebrow-line" /> TURN INTENT INTO ACTION</div><h1>Missions</h1><p className="page-lede">Track the actions and requirements connected to your student records.</p></div>
        <Button onClick={() => setShowCreate((value) => !value)}><Plus size={16} /> New mission</Button>
      </div>

      {actionError && <Notice tone="danger">{actionError}</Notice>}

      {showCreate && <Panel title="Create a mission" subtitle="Turn a document or student-life requirement into an actionable plan." className="create-mission-panel">
        <form onSubmit={createMission} className="form-grid">
          <Field label="Mission title"><input required value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} placeholder="e.g. Renew residence permit" /></Field>
          <Field label="Institution or organisation"><input value={form.institution} onChange={(event) => setForm((current) => ({ ...current, institution: event.target.value }))} placeholder="e.g. Immigration office" /></Field>
          <Field label="Deadline"><input type="date" value={form.deadline} onChange={(event) => setForm((current) => ({ ...current, deadline: event.target.value }))} /></Field>
          <Field label="Tasks (one per line)"><textarea rows={3} value={form.tasks} onChange={(event) => setForm((current) => ({ ...current, tasks: event.target.value }))} /></Field>
          <div className="form-full"><span className="field-label">Link supporting documents</span><div className="document-checkboxes">{documents.length ? documents.map((document) => <label className="checkbox-row" key={document.id}><input type="checkbox" checked={form.documentIds.includes(document.id)} onChange={(event) => setForm((current) => ({ ...current, documentIds: event.target.checked ? [...current.documentIds, document.id] : current.documentIds.filter((id) => id !== document.id) }))} /><span>{document.title}</span></label>) : <span className="muted">Upload a document to link it to this mission.</span>}</div></div>
          <div className="form-full inline-actions"><Button type="submit" disabled={creating || !form.title.trim()}>{creating ? 'Creating…' : 'Create mission'}</Button><Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button></div>
        </form>
      </Panel>}

      <div className="missions-layout">
        <Panel title="All missions" subtitle={`${missions.length} mission${missions.length === 1 ? '' : 's'} in your workspace`} className="mission-list-panel">
          {missions.length ? <div className="mission-list">
            {missions.map((mission) => {
              const isActive = selectedId === mission.id;
              return <button key={mission.id} className={`mission-list-item ${isActive ? 'active' : ''}`} onClick={() => void selectMission(mission.id)}>
                <span className="mission-list-icon"><CalendarDays size={17} /></span>
                <span className="mission-list-copy"><strong>{mission.title}</strong><small>{mission.institution || 'Personal'} · {formatDate(mission.deadline)}</small><span className="mission-progress-track"><i style={{ width: `${mission.tasks.length ? (mission.tasks.filter((task) => task.done).length / mission.tasks.length) * 100 : mission.status === 'COMPLETED' ? 100 : 0}%` }} /></span></span>
                <span className="mission-list-side"><StatusBadge status={mission.status} /><ArrowRight size={15} /></span>
              </button>;
            })}
          </div> : <EmptyState title="No missions yet" description="Create your first mission to organise what needs to happen next." />}
        </Panel>

        <Panel title="Mission details" subtitle="Requirements, tasks and progress." className="mission-detail-panel">
          {loadingDetails ? <div className="loading-state"><span className="spinner" />Loading mission…</div> : selected ? <div className="mission-detail-content">
            <div className="mission-detail-top"><div className="mission-detail-icon"><CalendarDays size={20} /></div><StatusBadge status={selected.status} /></div>
            <h2>{selected.title}</h2>
            <p className="mission-description">{selected.description || 'No additional description has been provided.'}</p>
            <div className="mission-meta-grid"><div><span>Institution</span><strong>{selected.institution || 'Not specified'}</strong></div><div><span>Deadline</span><strong>{formatDate(selected.deadline)}</strong></div><div><span>Mission ID</span><strong className="mono">{selected.id}</strong></div></div>
            <div className="detail-section-heading"><h3>Tasks</h3><span>{doneTasks}/{selected.tasks.length} completed</span></div>
            {selected.tasks.length ? <div className="task-list">{selected.tasks.map((task) => <label className={`task-row ${task.done ? 'task-done' : ''}`} key={task.id}><input type="checkbox" checked={task.done} onChange={() => void toggleTask(task.id, task.done)} /><span className="task-check">{task.done ? <Check size={13} /> : <Circle size={13} />}</span><span>{task.title}</span></label>)}</div> : <p className="muted">No tasks have been added to this mission.</p>}
            {selected.requirements.length > 0 && <><div className="detail-section-heading"><h3>Requirements</h3><span>{selected.requirements.length} linked</span></div><div className="requirements-list">{selected.requirements.map((requirement) => <div className="requirement-row" key={requirement.id}><div><strong>{requirement.description}</strong><span>{formatLabel(requirement.document_type)} · {requirement.min_validity_days_after_deadline} days validity after deadline</span>{requirement.source?.title && <small>Source: {requirement.source.title}</small>}</div><Badge tone={requirement.verified ? 'success' : 'warning'}>{requirement.verified ? 'Verified' : 'Unverified'}</Badge></div>)}</div></>}
            {selected.depends_on.length > 0 && <div className="dependency-note"><strong>Depends on</strong><span>{selected.depends_on.join(', ')}</span></div>}
            <div className="mission-actions"><div><span className="field-label">Workflow</span><span className="muted">Move this mission through its allowed states.</span></div><div className="mission-workflow-actions">{nextStatus ? <Button size="sm" onClick={() => void updateStatus(nextStatus)}>Move to {formatLabel(nextStatus)} <ArrowRight size={14} /></Button> : selected.status === 'IN_PROGRESS' ? <div className="inline-actions"><Button size="sm" variant="secondary" onClick={() => void updateStatus('WAITING_FOR_USER')}>Waiting for me</Button><Button size="sm" variant="secondary" onClick={() => void updateStatus('WAITING_FOR_INSTITUTION')}>Waiting for institution</Button><Button size="sm" onClick={() => void updateStatus('COMPLETED')}>Complete mission <Check size={14} /></Button></div> : selected.status === 'COMPLETED' ? <Badge tone="success">Mission completed</Badge> : <Badge tone="neutral">No next action</Badge>}{canCancel && <Button size="sm" variant="danger" onClick={() => void updateStatus('CANCELLED')}>Cancel mission</Button>}</div></div>
            {selected.completion_criteria && <div className="completion-criteria"><strong>Completion criteria</strong><p>{selected.completion_criteria}</p></div>}
          </div> : <EmptyState title="Select a mission" description="Choose a mission from the list to inspect its status, evidence and tasks." />}
        </Panel>
      </div>
      <p className="subtle-footnote">Mission status changes follow the backend workflow. Invalid transitions are rejected by the API.</p>
    </div>
  );
}
