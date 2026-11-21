import { useCallback, useEffect, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import type { ApprovalRequest, Deadline, ImpactReport, Mission, StudentDocument, Twin } from './api/types';
import { API_BASE_URL, endpoints } from './api/client';
import { Shell, type PageKey } from './components/Shell';
import { Button, LoadingState, Notice } from './components/UI';
import { DashboardPage } from './pages/DashboardPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { MissionsPage } from './pages/MissionsPage';
import { RisksPage } from './pages/RisksPage';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { AssistantPage } from './pages/AssistantPage';
import { LiveDemoPage } from './pages/LiveDemoPage';
import { VoiceWidget } from './components/VoiceWidget';
import './index.css';

export default function App() {
  const [page, setPage] = useState<PageKey>('dashboard');
  const [twin, setTwin] = useState<Twin | null>(null);
  const [deadlines, setDeadlines] = useState<Deadline[]>([]);
  const [impact, setImpact] = useState<ImpactReport | null>(null);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState('');

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    const results = await Promise.allSettled([
      endpoints.twin(),
      endpoints.deadlines(),
      endpoints.impact({ type: 'check' }),
      endpoints.approvals(),
    ]);
    const labels = ['student dashboard', 'deadlines', 'impact assessment', 'approvals'];
    const errors: string[] = [];

    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        errors.push(`${labels[index]}: ${result.reason instanceof Error ? result.reason.message : 'Request failed'}`);
        return;
      }
      switch (index) {
        case 0: setTwin(result.value as Twin); break;
        case 1: setDeadlines(Array.isArray(result.value) ? result.value as Deadline[] : []); break;
        case 2: setImpact(result.value as ImpactReport); break;
        case 3: setApprovals(Array.isArray(result.value) ? result.value as ApprovalRequest[] : []); break;
      }
    });

    setLoadError(errors.join(' '));
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { void refreshAll(); }, [refreshAll]);

  const student = twin?.student ?? null;
  const documents: StudentDocument[] = twin?.documents ?? [];
  const missions: Mission[] = twin?.missions ?? [];

  function renderPage() {
    switch (page) {
      case 'documents': return <DocumentsPage documents={documents} onChanged={refreshAll} />;
      case 'missions': return <MissionsPage missions={missions} documents={documents} onChanged={refreshAll} />;
      case 'risks': return <RisksPage documents={documents} impact={impact} onReport={setImpact} />;
      case 'approvals': return <ApprovalsPage approvals={approvals} missions={missions} onChanged={refreshAll} />;
      case 'assistant': return <AssistantPage />;
      case 'live': return <LiveDemoPage />;
      case 'dashboard':
      default: return <DashboardPage student={student} documents={documents} missions={missions} deadlines={deadlines} impact={impact} onNavigate={setPage} />;
    }
  }

  return (
    <Shell page={page} onNavigate={setPage} onRefresh={() => void refreshAll()} refreshing={refreshing} studentName={student?.name}>
      {loadError && <div className="global-api-alert"><Notice tone="warning"><div><strong>Some workspace data could not be loaded.</strong><p>{loadError}</p><Button size="sm" variant="secondary" onClick={() => void refreshAll()} disabled={refreshing}>Retry requests</Button></div></Notice></div>}
      {loading ? <div className="initial-loading"><LoadingState label="Connecting to your Sera workspace…" /><span><AlertCircle size={14} /> Backend expected at {API_BASE_URL}</span></div> : renderPage()}
      <VoiceWidget />
    </Shell>
  );
}
