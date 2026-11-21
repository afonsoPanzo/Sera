export type Verification =
  | 'confirmed'
  | 'extracted_pending_confirmation'
  | 'inferred'
  | 'missing'
  | 'expired'
  | 'rejected';

export interface Fact<T = unknown> {
  value: T | null;
  status: Verification;
  source: string;
  confidence: number | null;
  updated_at: string;
  updated_by: string;
}

export interface Student {
  id: string;
  name: string;
  nationality: string | null;
  university: string | null;
  program: string | null;
  academic_year: string | null;
  preferred_language: string;
}

export type DocumentType =
  | 'passport'
  | 'enrollment_certificate'
  | 'accommodation_document'
  | 'residence_permit'
  | 'official_letter'
  | 'other';

export interface StudentDocument {
  id: string;
  student_id: string;
  type: DocumentType;
  title: string;
  original_filename: string | null;
  extracted_text: string | null;
  extraction_error: string | null;
  fields: Record<string, Fact>;
  uploaded_at: string;
}

export type MissionStatus =
  | 'CREATED'
  | 'ANALYSIS'
  | 'PLANNED'
  | 'IN_PROGRESS'
  | 'WAITING_FOR_USER'
  | 'WAITING_FOR_INSTITUTION'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'BLOCKED'
  | 'EXPIRED';

export interface SourceReference {
  title: string;
  url: string | null;
  retrieved_at: string | null;
  official: boolean;
  note: string | null;
}

export interface Requirement {
  id: string;
  description: string;
  document_type: DocumentType;
  min_validity_days_after_deadline: number;
  satisfied_by: string | null;
  source: SourceReference;
  verified: boolean;
}

export interface MissionTask {
  id: string;
  title: string;
  done: boolean;
}

export interface Mission {
  id: string;
  student_id: string;
  title: string;
  description: string;
  institution: string;
  status: MissionStatus;
  deadline: string | null;
  depends_on: string[];
  requirements: Requirement[];
  tasks: MissionTask[];
  completion_criteria: string;
}

export interface Twin {
  student: Student;
  documents: StudentDocument[];
  missions: Mission[];
}

export interface Deadline {
  kind: 'mission' | 'document_expiry';
  id: string;
  title: string;
  date: string;
  days_left: number;
  status: Verification;
}

export type ImpactLevel = 'critical' | 'high' | 'medium' | 'low' | 'unknown';

export interface ImpactEvidence {
  kind: 'fact' | 'requirement' | 'mission' | 'dependency';
  description: string;
  status: string | null;
  source: string | null;
}

export interface ImpactItem {
  level: ImpactLevel;
  mission_id: string;
  mission_title: string;
  requirement_id: string | null;
  explanation: string;
  evidence: ImpactEvidence[];
  assumptions: string[];
  recommended_actions: string[];
}

export interface ImpactReport {
  student_id: string;
  event: Record<string, unknown>;
  as_of: string;
  overall_level: ImpactLevel;
  items: ImpactItem[];
  disclaimer: string;
}

export type ApprovalStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'executed'
  | 'simulated'
  | 'failed';

export interface ApprovalRequest {
  id: string;
  student_id: string;
  mission_id: string | null;
  action_type: 'send_email';
  summary: string;
  payload: { to: string; subject: string; body: string };
  status: ApprovalStatus;
  result: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface ChatReply {
  reply: string;
  model: string;
  mock: boolean;
}

export interface ChatHistoryItem {
  role: 'user' | 'assistant';
  content: string;
}

// ---------- Sera AI (/api/chat, /api/topics, /api/explain) ----------

export type Topic = 'general' | 'healthcare' | 'university' | 'immigration' | 'translation';
export type ChatLanguage = 'auto' | 'en' | 'hu';

export interface TopicInfo {
  id: Topic;
  label: { en: string; hu: string };
  examples: { en: string[]; hu?: string[] };
}

export interface SeraChatReply {
  reply: string;
  language: 'en' | 'hu';
  topic: Topic;
  model: string;
  mock: boolean;
  actions?: SeraAction[];
}

export interface ExplainResponse {
  explanation: string;
  document_type: DocumentType;
  dates_found: string[];
  truncated: boolean;
  language: 'en' | 'hu';
  model: string;
  mock: boolean;
  actions?: SeraAction[];
}

export interface SeraAction {
  type: 'email_draft' | 'email' | 'call' | 'map' | 'link' | 'copy';
  label: string;
  href?: string | null;   // mailto:, tel:, https://
  text?: string | null;   // for "copy"
}
