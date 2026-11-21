import type { ReactNode } from 'react';
import {
  ArrowUpRight,
  Bell,
  CheckSquare,
  ChevronDown,
  Command,
  FileText,
  LayoutDashboard,
  MessageCircle,
  PhoneCall,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import { SeraLogo, SeraMark } from './Logo';

export type PageKey = 'live' | 'dashboard' | 'documents' | 'missions' | 'risks' | 'approvals' | 'assistant';

const NAV_ITEMS: { key: PageKey; label: string; icon: typeof LayoutDashboard; group: string }[] = [
  { key: 'live', label: 'Live demo', icon: PhoneCall, group: 'Workspace' },
  { key: 'dashboard', label: 'Overview', icon: LayoutDashboard, group: 'Workspace' },
  { key: 'documents', label: 'My documents', icon: FileText, group: 'Workspace' },
  { key: 'missions', label: 'Missions', icon: CheckSquare, group: 'Workspace' },
  { key: 'risks', label: 'Risk analysis', icon: ShieldAlert, group: 'Intelligence' },
  { key: 'approvals', label: 'Approvals', icon: Bell, group: 'Intelligence' },
  { key: 'assistant', label: 'AI assistant', icon: MessageCircle, group: 'Intelligence' },
];

const PAGE_TITLES: Record<PageKey, string> = {
  live: 'Live demo',
  dashboard: 'Overview',
  documents: 'My documents',
  missions: 'Missions',
  risks: 'Risk analysis',
  approvals: 'Approvals',
  assistant: 'AI assistant',
};

export function Shell({
  page,
  onNavigate,
  onRefresh,
  refreshing,
  studentName,
  children,
}: {
  page: PageKey;
  onNavigate: (page: PageKey) => void;
  onRefresh: () => void;
  refreshing: boolean;
  studentName?: string | null;
  children: ReactNode;
}) {
  const displayName = studentName || 'Demo student';
  const initials = displayName.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand-lockup" onClick={() => onNavigate('dashboard')} aria-label="Sera home">
          <span className="brand-mark"><SeraMark size={40} /></span>
          <span className="brand-text"><SeraLogo tagline="STUDENT CONCIERGE" /></span>
        </button>

        <div className="workspace-pill"><span className="workspace-dot" /> Demo workspace <ChevronDown size={14} /></div>

        <nav className="side-nav" aria-label="Main navigation">
          {(['Workspace', 'Intelligence'] as const).map((group) => (
            <div className="nav-group" key={group}>
              <div className="nav-label">{group}</div>
              {NAV_ITEMS.filter((item) => item.group === group).map((item) => {
                const Icon = item.icon;
                return (
                  <button key={item.key} className={`nav-item ${page === item.key ? 'active' : ''}`} onClick={() => onNavigate(item.key)}>
                    <Icon size={18} strokeWidth={1.85} />
                    <span>{item.label}</span>
                    {item.key === 'risks' && <span className="nav-indicator" />}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-tip">
            <div className="tip-icon"><Sparkles size={17} /></div>
            <strong>Your student life, connected.</strong>
            <p>Keep documents, deadlines and next steps in one place.</p>
            <button onClick={() => onNavigate('assistant')}>Ask your assistant <ArrowUpRight size={14} /></button>
          </div>
          <div className="profile-row">
            <div className="avatar avatar-small">{initials}</div>
            <div className="profile-copy"><strong>{displayName}</strong><span>Demo student</span></div>
            <Command size={15} className="profile-more" />
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>Sera</span><span className="crumb-divider">/</span><strong>{PAGE_TITLES[page]}</strong></div>
          <div className="topbar-actions">
            <span className="api-status"><span className="api-status-dot" /> Demo environment</span>
            <button className="icon-button" title="Refresh data" onClick={onRefresh} disabled={refreshing}>
              <RefreshCw size={17} className={refreshing ? 'spin' : ''} />
            </button>
            <div className="topbar-avatar" title={displayName}>{initials}</div>
          </div>
        </header>
        <div className="page-content">{children}</div>
        <footer className="footer"><span>Sera</span><span>Built for a more connected student experience</span></footer>
      </main>
    </div>
  );
}
