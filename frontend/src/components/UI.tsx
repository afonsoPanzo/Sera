import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { AlertCircle, CheckCircle2, Info } from 'lucide-react';
import type { ImpactLevel, Verification } from '../api/types';
import { formatLabel, severityLabel, verificationLabel } from '../utils';

export function Panel({
  title,
  subtitle,
  action,
  children,
  className = '',
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || subtitle || action) && (
        <div className="panel-heading">
          <div>
            {title && <h2 className="panel-title">{title}</h2>}
            {subtitle && <p className="panel-subtitle">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function VerificationBadge({ status }: { status: Verification | string }) {
  const tone = status === 'confirmed' ? 'success'
    : status === 'extracted_pending_confirmation' ? 'warning'
      : status === 'expired' || status === 'rejected' ? 'danger'
        : status === 'inferred' ? 'info' : 'neutral';
  return <Badge tone={tone}>{verificationLabel(status)}</Badge>;
}

export function SeverityBadge({ level }: { level: ImpactLevel | string }) {
  return <Badge tone={`severity-${level}`}>{severityLabel(level)}</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  const tone = status === 'COMPLETED' || status === 'approved' || status === 'executed' ? 'success'
    : status === 'pending' || status === 'WAITING_FOR_USER' || status === 'WAITING_FOR_INSTITUTION' ? 'warning'
      : status === 'BLOCKED' || status === 'EXPIRED' || status === 'failed' || status === 'rejected' ? 'danger'
        : status === 'simulated' ? 'info' : 'neutral';
  return <Badge tone={tone}>{formatLabel(status)}</Badge>;
}

export function LoadingState({ label = 'Loading workspace…' }: { label?: string }) {
  return <div className="loading-state"><span className="spinner" />{label}</div>;
}

export function EmptyState({ title, description, icon }: { title: string; description: string; icon?: ReactNode }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon ?? <Info size={20} />}</div>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

export function Notice({ tone = 'info', children }: { tone?: 'info' | 'warning' | 'danger' | 'success'; children: ReactNode }) {
  const Icon = tone === 'success' ? CheckCircle2 : tone === 'danger' ? AlertCircle : Info;
  return <div className={`notice notice-${tone}`}><Icon size={17} /><div>{children}</div></div>;
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'sm' | 'md' }) {
  return <button className={`button button-${variant} button-${size} ${className}`} {...props}>{children}</button>;
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="field"><span className="field-label">{label}</span>{children}{hint && <span className="field-hint">{hint}</span>}</label>;
}
