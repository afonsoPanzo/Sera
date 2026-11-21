import type { ImpactLevel, MissionStatus, Verification } from './api/types';

export function formatDate(value: string | null | undefined): string {
  if (!value) return 'No deadline';
  const date = new Date(`${value.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).format(date);
}

export function formatLabel(value: string): string {
  return value
    .toLowerCase()
    .split(/[_\s]+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function verificationLabel(status: Verification | string): string {
  const labels: Record<string, string> = {
    confirmed: 'Confirmed',
    extracted_pending_confirmation: 'Pending confirmation',
    inferred: 'Inferred',
    missing: 'Missing',
    expired: 'Expired',
    rejected: 'Rejected',
  };
  return labels[status] ?? formatLabel(status);
}

export function severityLabel(level: ImpactLevel | string): string {
  return level.charAt(0).toUpperCase() + level.slice(1);
}

export function nextMissionStatus(status: MissionStatus): MissionStatus | null {
  const transitions: Partial<Record<MissionStatus, MissionStatus>> = {
    CREATED: 'ANALYSIS',
    ANALYSIS: 'PLANNED',
    PLANNED: 'IN_PROGRESS',
    WAITING_FOR_USER: 'IN_PROGRESS',
    WAITING_FOR_INSTITUTION: 'IN_PROGRESS',
  };
  return transitions[status] ?? null;
}
