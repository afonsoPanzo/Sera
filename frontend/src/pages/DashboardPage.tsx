import { ArrowRight, CalendarClock, CheckCircle2, FileText, ShieldCheck, Sparkles } from 'lucide-react';
import type { Deadline, ImpactReport, Mission, Student, StudentDocument } from '../api/types';
import { formatDate } from '../utils';
import { Badge, EmptyState, Panel, SeverityBadge, StatusBadge, VerificationBadge } from '../components/UI';
import type { PageKey } from '../components/Shell';

export function DashboardPage({
  student,
  documents,
  missions,
  deadlines,
  impact,
  onNavigate,
}: {
  student: Student | null;
  documents: StudentDocument[];
  missions: Mission[];
  deadlines: Deadline[];
  impact: ImpactReport | null;
  onNavigate: (page: PageKey) => void;
}) {
  const pendingCount = documents.reduce((count, document) =>
    count + Object.values(document.fields ?? {}).filter((field) => field.status === 'extracted_pending_confirmation').length, 0);
  const activeMissions = missions.filter((mission) => !['COMPLETED', 'CANCELLED'].includes(mission.status)).length;
  const openDeadlines = [...deadlines].sort((a, b) => a.days_left - b.days_left).slice(0, 4);
  const firstName = student?.name?.split(' ')[0] || 'there';

  return (
    <div className="page-stack">
      <div className="welcome-row">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> YOUR STUDENT LIFE, IN SYNC</div>
          <h1>Good to see you, {firstName}<span className="wave">.</span></h1>
          <p className="page-lede">Here’s what needs your attention today. Let’s keep everything moving.</p>
        </div>
        <div className="welcome-date"><CalendarClock size={16} /> {new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())}</div>
      </div>

      <div className="metric-grid">
        <div className="metric-card metric-purple">
          <div className="metric-top"><span className="metric-icon"><FileText size={18} /></span><span className="metric-trend">Your library</span></div>
          <div className="metric-number">{documents.length}<span> documents</span></div>
          <div className="metric-foot">Academic and personal records</div>
        </div>
        <div className="metric-card metric-blue">
          <div className="metric-top"><span className="metric-icon"><CheckCircle2 size={18} /></span><span className="metric-trend">In progress</span></div>
          <div className="metric-number">{activeMissions}<span> missions</span></div>
          <div className="metric-foot">Actions connected to your documents</div>
        </div>
        <div className="metric-card metric-amber">
          <div className="metric-top"><span className="metric-icon"><CalendarClock size={18} /></span><span className="metric-trend">Coming up</span></div>
          <div className="metric-number">{deadlines.length}<span> deadlines</span></div>
          <div className="metric-foot">Dates that should stay on your radar</div>
        </div>
        <div className="metric-card metric-green">
          <div className="metric-top"><span className="metric-icon"><ShieldCheck size={18} /></span><span className="metric-trend">Needs review</span></div>
          <div className="metric-number">{pendingCount}<span> fields</span></div>
          <div className="metric-foot">Extracted details awaiting confirmation</div>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-main-column">
          {impact?.items?.length ? (
            <Panel title="Priority attention" subtitle="A potential issue has been identified across your records." action={<button className="text-link" onClick={() => onNavigate('risks')}>View analysis <ArrowRight size={14} /></button>}>
              <div className="priority-card">
                <div className="priority-heading"><div className="priority-symbol"><ShieldCheck size={18} /></div><SeverityBadge level={impact.overall_level} /></div>
                <h3>{impact.items[0].mission_title || 'A mission may be at risk'}</h3>
                <p>{impact.items[0].explanation}</p>
                <div className="priority-bottom"><span>{impact.items.length} impact item{impact.items.length === 1 ? '' : 's'} identified</span><button className="button button-secondary button-sm" onClick={() => onNavigate('risks')}>Review why <ArrowRight size={14} /></button></div>
              </div>
            </Panel>
          ) : (
            <Panel title="Priority attention" subtitle="Your current impact assessment.">
              <div className="priority-clear"><span><ShieldCheck size={19} /></span><div><strong>{impact ? 'No active risks identified' : 'Risk assessment not available'}</strong><p>{impact ? 'Your current records show no impact items.' : 'Open Risk analysis to run a fresh assessment.'}</p></div></div>
            </Panel>
          )}

          <Panel title="Your missions" subtitle="The next steps connected to your student journey." action={<button className="text-link" onClick={() => onNavigate('missions')}>All missions <ArrowRight size={14} /></button>}>
            {missions.length ? <div className="mission-preview-list">
              {missions.slice(0, 3).map((mission, index) => (
                <div className="mission-preview" key={mission.id}>
                  <div className={`mission-index mission-index-${index + 1}`}>{String(index + 1).padStart(2, '0')}</div>
                  <div className="mission-preview-copy"><strong>{mission.title}</strong><span>{mission.institution || 'Personal task'} · Due {formatDate(mission.deadline)}</span></div>
                  <StatusBadge status={mission.status} />
                </div>
              ))}
            </div> : <EmptyState title="No missions yet" description="Create a mission to turn a document into a clear next step." />}
          </Panel>

          <Panel title="Your documents" subtitle="The information behind your student profile." action={<button className="text-link" onClick={() => onNavigate('documents')}>Open library <ArrowRight size={14} /></button>}>
            {documents.length ? <div className="document-preview-grid">
              {documents.slice(0, 3).map((document) => (
                <div className="document-preview" key={document.id}>
                  <div className="document-file-icon"><FileText size={18} /></div>
                  <div className="document-preview-copy"><strong>{document.title}</strong><span>{document.original_filename || document.type}</span></div>
                  <VerificationBadge status={Object.values(document.fields ?? {}).some((field) => field.status === 'extracted_pending_confirmation') ? 'extracted_pending_confirmation' : 'confirmed'} />
                </div>
              ))}
            </div> : <EmptyState title="Your library is ready" description="Upload a document to start connecting evidence to your missions." />}
          </Panel>
        </div>

        <aside className="dashboard-side-column">
          <Panel title="Upcoming deadlines" subtitle="Keep the important dates in view." action={<button className="round-arrow" onClick={() => onNavigate('missions')} aria-label="View missions"><ArrowRight size={15} /></button>}>
            {openDeadlines.length ? <div className="deadline-list">
              {openDeadlines.map((deadline) => (
                <div className="deadline-item" key={`${deadline.kind}-${deadline.id}`}>
                  <div className={`deadline-date ${deadline.days_left <= 7 ? 'urgent' : ''}`}><span>{new Date(`${deadline.date.slice(0, 10)}T12:00:00`).toLocaleDateString('en-GB', { day: '2-digit' })}</span><small>{new Date(`${deadline.date.slice(0, 10)}T12:00:00`).toLocaleDateString('en-GB', { month: 'short' })}</small></div>
                  <div className="deadline-copy"><strong>{deadline.title}</strong><span>{deadline.days_left < 0 ? `${Math.abs(deadline.days_left)} days overdue` : deadline.days_left === 0 ? 'Due today' : `${deadline.days_left} days left`}</span></div>
                </div>
              ))}
            </div> : <EmptyState title="No deadlines found" description="Deadlines from your student record will appear here." />}
          </Panel>

          <div className="assistant-promo">
            <div className="promo-orbit orbit-one" /><div className="promo-orbit orbit-two" />
            <div className="promo-content"><div className="promo-icon"><Sparkles size={19} /></div><span className="promo-kicker">SERA INTELLIGENCE</span><h3>Make sense of the next step.</h3><p>Ask a question about your documents, deadlines or missions.</p><button onClick={() => onNavigate('assistant')}>Ask your assistant <ArrowRight size={15} /></button></div>
          </div>

          <Panel title="Student profile" subtitle="Your demo workspace identity.">
            <div className="student-mini-profile"><div className="avatar avatar-large">{student?.name?.split(' ').map((part) => part[0]).slice(0, 2).join('') || 'S'}</div><div><strong>{student?.name || 'Sera'}</strong><span>{student?.university || 'University not specified'}</span></div></div>
            <div className="profile-details"><div><span>Programme</span><strong>{student?.program || 'Not specified'}</strong></div><div><span>Academic year</span><strong>{student?.academic_year || 'Not specified'}</strong></div><div><span>Preferred language</span><strong>{student?.preferred_language || 'Auto'}</strong></div></div>
            <div className="profile-note"><Badge tone="info">Demo account</Badge><span>Authentication is not enabled in this demo.</span></div>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
