import { useState, type FormEvent } from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, ChevronDown, FlaskConical, RefreshCw, ShieldAlert } from 'lucide-react';
import type { ImpactReport, StudentDocument } from '../api/types';
import { endpoints } from '../api/client';
import { formatDate, formatLabel } from '../utils';
import { Button, EmptyState, Field, Notice, Panel, SeverityBadge } from '../components/UI';

export function RisksPage({ documents, impact, onReport }: { documents: StudentDocument[]; impact: ImpactReport | null; onReport: (report: ImpactReport) => void }) {
  const [scenarioType, setScenarioType] = useState<'expiry' | 'remove'>('expiry');
  const [documentId, setDocumentId] = useState(documents.find((doc) => doc.id === 'doc-passport')?.id ?? documents[0]?.id ?? '');
  const [newExpiry, setNewExpiry] = useState('2032-01-01');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [scenarioLabel, setScenarioLabel] = useState('Current assessment');

  async function runCurrent() {
    setBusy(true);
    setError('');
    try {
      const report = await endpoints.impact({ type: 'check' });
      onReport(report);
      setScenarioLabel('Current assessment');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not calculate current impact.');
    } finally {
      setBusy(false);
    }
  }

  async function runScenario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!documentId) return;
    setBusy(true);
    setError('');
    try {
      const eventPayload = scenarioType === 'expiry'
        ? { type: 'document_expiry_change', document_id: documentId, new_expiry_date: newExpiry }
        : { type: 'document_removed', document_id: documentId };
      const report = await endpoints.impact(eventPayload);
      onReport(report);
      const docTitle = documents.find((doc) => doc.id === documentId)?.title || 'selected document';
      setScenarioLabel(scenarioType === 'expiry' ? `Scenario: ${docTitle} valid until ${formatDate(newExpiry)}` : `Scenario: ${docTitle} removed`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not run this scenario.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <div className="page-heading-row">
        <div><div className="eyebrow"><span className="eyebrow-line" /> UNDERSTAND THE CONSEQUENCES</div><h1>Risk analysis</h1><p className="page-lede">See how documents, requirements and deadlines affect your missions—and understand why.</p></div>
        <Button variant="secondary" onClick={() => void runCurrent()} disabled={busy}><RefreshCw size={15} className={busy ? 'spin' : ''} /> Recalculate impact</Button>
      </div>

      {error && <Notice tone="danger">{error}</Notice>}

      <div className="risk-intro-banner"><div className="risk-intro-icon"><ShieldAlert size={22} /></div><div><strong>Impact is connected, not isolated.</strong><p>A document issue can affect a requirement, which can place one or more missions at risk. Each assessment includes its evidence and assumptions.</p></div><span className="risk-flow">DOCUMENTS <ArrowRight size={13} /> MISSIONS <ArrowRight size={13} /> IMPACT</span></div>

      <div className="risk-layout">
        <div className="risk-report-column">
          <Panel title="Impact assessment" subtitle={scenarioLabel} action={impact && <SeverityBadge level={impact.overall_level} />}>
            {impact ? <>
              {impact.items.length ? <div className="impact-list">{impact.items.map((item, index) => <ImpactCard key={`${item.mission_id}-${item.requirement_id ?? index}`} item={item} />)}</div> : <div className="risk-clear-state"><span><CheckCircle2 size={22} /></span><div><strong>No impact items identified</strong><p>The current assessment did not identify affected missions.</p></div></div>}
              <div className="impact-disclaimer"><AlertTriangle size={15} /><p>{impact.disclaimer}</p></div>
              <div className="report-timestamp">Assessment generated: {impact.as_of ? new Date(impact.as_of).toLocaleString('en-GB') : 'Not provided'}</div>
            </> : <EmptyState title="No assessment loaded" description="Run the current assessment to check the impact of your records on active missions." icon={<FlaskConical size={20} />} />}
          </Panel>
        </div>

        <div className="risk-scenario-column">
          <Panel title="What if? simulator" subtitle="Explore a possible change without altering your stored records." className="scenario-panel">
            <form onSubmit={(event) => void runScenario(event)} className="scenario-form">
              <div className="scenario-tabs"><button type="button" className={scenarioType === 'expiry' ? 'active' : ''} onClick={() => setScenarioType('expiry')}>Change expiry date</button><button type="button" className={scenarioType === 'remove' ? 'active' : ''} onClick={() => setScenarioType('remove')}>Remove document</button></div>
              <Field label="Document"><select value={documentId} onChange={(event) => setDocumentId(event.target.value)} required><option value="" disabled>Select a document</option>{documents.map((document) => <option value={document.id} key={document.id}>{document.title || formatLabel(document.type)}</option>)}</select></Field>
              {scenarioType === 'expiry' && <Field label="New expiry date"><input type="date" value={newExpiry} onChange={(event) => setNewExpiry(event.target.value)} required /></Field>}
              {scenarioType === 'remove' && <Notice tone="warning">This scenario temporarily treats the selected document as unavailable. It does not delete the document.</Notice>}
              <Button type="submit" className="button-block" disabled={busy || !documentId}>{busy ? 'Simulating…' : 'Run scenario'} <ArrowRight size={15} /></Button>
            </form>
            <div className="scenario-note"><FlaskConical size={16} /><p>Scenario changes are evaluated by the backend and do not modify the actual student record.</p></div>
          </Panel>
          <Panel title="How to read this report" subtitle="Risk levels used by the assessment engine.">
            <div className="severity-guide"><div><SeverityBadge level="critical" /><span>Immediate or blocking impact</span></div><div><SeverityBadge level="high" /><span>Significant impact on a mission</span></div><div><SeverityBadge level="medium" /><span>Potential issue requiring attention</span></div><div><SeverityBadge level="low" /><span>Limited impact</span></div><div><SeverityBadge level="unknown" /><span>Insufficient information</span></div></div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function ImpactCard({ item }: { item: ImpactReport['items'][number] }) {
  const [expanded, setExpanded] = useState(false);
  return <article className={`impact-card impact-${item.level}`}>
    <div className="impact-card-top"><SeverityBadge level={item.level} /><span className="impact-mission-id">Mission · {item.mission_id}</span></div>
    <h3>{item.mission_title || 'Affected mission'}</h3>
    <p>{item.explanation}</p>
    <button className="evidence-toggle" onClick={() => setExpanded((value) => !value)}><span>{expanded ? 'Hide' : 'Show'} evidence and assumptions</span><ChevronDown size={16} className={expanded ? 'rotate' : ''} /></button>
    {expanded && <div className="impact-evidence">
      <div><h4>Evidence</h4>{item.evidence.length ? <ul>{item.evidence.map((evidence, index) => <li key={`${evidence.kind}-${index}`}><strong>{formatLabel(evidence.kind)}:</strong> {evidence.description}{evidence.status && <span className="evidence-meta"> · {formatLabel(evidence.status)}</span>}{evidence.source && <span className="evidence-meta"> · Source: {evidence.source}</span>}</li>)}</ul> : <p className="muted">No evidence details provided.</p>}</div>
      <div><h4>Assumptions / uncertainties</h4>{item.assumptions.length ? <ul>{item.assumptions.map((assumption, index) => <li key={index}>{assumption}</li>)}</ul> : <p className="muted">No assumptions listed.</p>}</div>
      <div><h4>Recommended actions</h4>{item.recommended_actions.length ? <ul>{item.recommended_actions.map((action, index) => <li key={index}>{action}</li>)}</ul> : <p className="muted">No recommended actions supplied.</p>}</div>
    </div>}
  </article>;
}
