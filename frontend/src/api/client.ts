import type {
  ApprovalRequest,
  ChatReply,
  Deadline,
  ImpactReport,
  Mission,
  StudentDocument,
  Twin,
  TopicInfo,
  ChatLanguage,
  Topic,
  SeraChatReply,
  ExplainResponse,
  TriageResult,
  MissionLive,
} from './types';

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
export const STUDENT_ID = 'stu-demo';

function readableError(data: unknown, fallback: string): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg: unknown }).msg);
          }
          return JSON.stringify(item);
        })
        .join('; ');
    }
  }
  return fallback;
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new Error(`Cannot reach the Sera API at ${API_BASE_URL}. Check that the backend is running.`);
  }

  const payload: unknown = response.status === 204
    ? null
    : await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(readableError(payload, `Request failed (${response.status}). Please try again.`));
  }

  return payload as T;
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function upload<T>(path: string, formData: FormData): Promise<T> {
  // Do not set Content-Type manually; the browser supplies the multipart boundary.
  return request<T>(path, { method: 'POST', body: formData });
}

export const endpoints = {
  twin: () => get<Twin>(`/api/students/${STUDENT_ID}`),
  deadlines: () => get<Deadline[]>(`/api/students/${STUDENT_ID}/deadlines`),
  impact: (event: Record<string, unknown>) =>
    post<ImpactReport>(`/api/students/${STUDENT_ID}/impact`, { event }),
  uploadDocument: (formData: FormData) =>
    upload<StudentDocument>(`/api/students/${STUDENT_ID}/documents`, formData),
  verifyField: (documentId: string, field: string, body: { decision: 'confirm' | 'reject'; value?: string }) =>
    post<unknown>(`/api/documents/${documentId}/fields/${encodeURIComponent(field)}`, body),
  createMission: (body: unknown) =>
    post<Mission>(`/api/students/${STUDENT_ID}/missions`, body),
  // The Python API returns { mission, missing_requirements, progress }.
  missionDetails: (missionId: string) =>
    get<{ mission: Mission } | Mission>(`/api/missions/${missionId}`)
      .then((d) => ('mission' in d ? d.mission : d)),
  updateMissionStatus: (missionId: string, status: string) =>
    post<Mission>(`/api/missions/${missionId}/status`, { status }),
  updateTask: (missionId: string, taskId: string, done: boolean) =>
    request<unknown>(`/api/missions/${missionId}/tasks/${taskId}?done=${done}`, { method: 'POST' }),
  approvals: () => get<ApprovalRequest[]>(`/api/students/${STUDENT_ID}/approvals`),
  createApproval: (body: unknown) =>
    post<ApprovalRequest>(`/api/students/${STUDENT_ID}/approvals`, body),
  decideApproval: (approvalId: string, decision: 'approve' | 'reject') =>
    post<ApprovalRequest>(`/api/approvals/${approvalId}/${decision}`, {}),
  // Context chat (rule-based, uses the demo student's missions/documents)
  chat: (message: string, history: { role: string; content: string }[]) =>
    post<ChatReply>(`/api/students/${STUDENT_ID}/agent/chat`, { message, language: 'auto', history }),

  // Sera AI (Gemini/OpenAI + verified knowledge base)
  topics: () => get<TopicInfo[]>('/api/topics'),
  askSera: (body: { message: string; language: ChatLanguage; topic: Topic; history: { role: string; content: string }[] }) =>
    post<SeraChatReply>('/api/chat', body),
  explain: (input: { file?: File; text?: string; language: 'en' | 'hu' }) => {
    const form = new FormData();
    if (input.file) form.append('file', input.file);
    if (input.text) form.append('text', input.text);
    form.append('language', input.language);
    return upload<ExplainResponse>('/api/explain', form);
  },
  // Live demo mission
  triage: (message: string) => post<TriageResult>('/api/chat-triage', { message }),
  confirmAndExecute: (body: {
    doctor_phone: string; student_phone?: string; lecturer_email?: string; student_name: string;
    course_name: string; symptoms: string; allergies: string; preferred_window: string;
  }) => post<{ status: string; conversation_id: string | null }>('/api/confirm-and-execute', body),
  missionStatus: () => get<MissionLive>('/api/mission-status'),
  simulateCallComplete: (appointment_time?: string) =>
    post<MissionLive>('/api/simulate-call-complete', appointment_time ? { appointment_time } : {}),
  missionReset: () => post<MissionLive>('/api/mission-reset', {}),
  speak: async (text: string, language: 'en' | 'hu'): Promise<Blob> => {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/api/speak`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, language }),
      });
    } catch {
      throw new Error(`Cannot reach the Sera API at ${API_BASE_URL}.`);
    }
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(readableError(data, `Voice failed (${response.status}).`));
    }
    return response.blob();
  },
};

export { API_BASE_URL };
