# Guia para o Frontend — CampusBridge

Este guia é para quem vai fazer o frontend. O backend já está pronto para a demo. Aqui tens o que precisas para o ligar.

## 1. Pôr o backend a correr (5 minutos)

É preciso Python 3.11 ou mais recente. Na raiz do repositório:

```bash
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt      # Windows
# macOS/Linux: .venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

- **Base URL:** `http://localhost:8000`
- **Documentação interativa:** http://localhost:8000/docs. Aqui dá para experimentar todos os endpoints e ver os formatos exatos.
- **CORS:** está aberto (`*`), por isso o Vite em `localhost:5173` funciona sem configurar nada.
- **Sem chave da OpenAI:** o chat funciona em modo mock (`"mock": true`).
- **Estudante de demo:** usa sempre `stu-demo`. Ainda não há login.

> ⚠️ Os dados ficam **em memória**. Reiniciar o servidor volta aos dados iniciais da demo. É útil para ensaiar a apresentação.

## 2. A história da demo (o que o ecrã tem de contar)

O SDD diz que o importante **não é o chat**. O importante é mostrar que o sistema liga documentos → missões → impacto. A demo tem esta sequência:

1. **Dashboard:** a estudante Amara tem 3 documentos, 3 missões e prazos.
2. **Alerta vermelho:** o passaporte expira antes do que a renovação da autorização de residência exige (**critical**). Por arrasto, a missão do cartão de morada também fica em risco (**high**).
3. **Upload de uma carta em húngaro.** O sistema classifica-a e tira as datas. Essas datas aparecem como **"por confirmar"**.
4. **A estudante confirma a data.** Só agora o valor passa a `confirmed`.
5. **Criar uma missão** a partir da carta.
6. **Simulador "e se?":** "e se eu renovar o passaporte até 2032?" → o risco desaparece. Os dados reais não mudam.
7. **Email para o gabinete:** é preparado e precisa de **aprovação explícita**. O resultado é `simulated`, porque não é enviado de verdade.

Para a carta da demo, guarda isto como `carta.txt`:

```
Országos Idegenrendészeti Főigazgatóság
Tisztelt Amara Demo!
Értesítjük, hogy tartózkodási engedélye 2027. január 20. napján lejár.
A hosszabbítási kérelmet legkésőbb 2027.01.10. határidőig nyújtsa be.
```

## 3. Ecrãs sugeridos → endpoints

| Ecrã | Pedido |
|---|---|
| Dashboard | `GET /api/students/stu-demo` |
| Timeline de prazos | `GET /api/students/stu-demo/deadlines` |
| Painel de riscos | `POST /api/students/stu-demo/impact` com `{"event":{"type":"check"}}` |
| Simulador "e se?" | `POST /api/students/stu-demo/impact` com um evento de cenário (ver §5) |
| Upload de documento | `POST /api/students/stu-demo/documents` (multipart) |
| Rever dados extraídos | `POST /api/documents/{docId}/fields/{field}` |
| Detalhe de missão | `GET /api/missions/{missionId}` |
| Nova missão | `POST /api/students/stu-demo/missions` |
| Mudar estado / tarefa | `POST /api/missions/{id}/status`, `POST /api/missions/{id}/tasks/{taskId}?done=true` |
| Aprovações | `POST /api/students/stu-demo/approvals`, `GET .../approvals`, `POST /api/approvals/{id}/approve` ou `/reject` |
| Chat | `POST /api/students/stu-demo/agent/chat` |

## 4. Tipos (TypeScript)

Copia isto para `src/api/types.ts`. As datas chegam sempre como string `YYYY-MM-DD` e os timestamps em ISO.

```ts
export type Verification =
  | "confirmed" | "extracted_pending_confirmation" | "inferred"
  | "missing" | "expired" | "rejected";

export interface Fact<T = unknown> {
  value: T | null;
  status: Verification;
  source: string;            // "document:doc-passport", "user", "scenario"...
  confidence: number | null;
  updated_at: string;
  updated_by: string;
}

export interface Student {
  id: string; name: string; nationality: string | null; university: string | null;
  program: string | null; academic_year: string | null; preferred_language: string;
}

export type DocumentType =
  | "passport" | "enrollment_certificate" | "accommodation_document"
  | "residence_permit" | "official_letter" | "other";

export interface StudentDocument {
  id: string; student_id: string; type: DocumentType; title: string;
  original_filename: string | null;
  extracted_text: string | null;
  extraction_error: string | null;   // se vier preenchido, MOSTRAR ao utilizador
  fields: Record<string, Fact>;      // ex.: expiry_date, deadline, address, dates_found
  uploaded_at: string;
}

export type MissionStatus =
  | "CREATED" | "ANALYSIS" | "PLANNED" | "IN_PROGRESS" | "WAITING_FOR_USER"
  | "WAITING_FOR_INSTITUTION" | "COMPLETED" | "CANCELLED" | "BLOCKED" | "EXPIRED";

export interface SourceReference {
  title: string; url: string | null; retrieved_at: string | null; official: boolean; note: string | null;
}

export interface Requirement {
  id: string; description: string; document_type: DocumentType;
  min_validity_days_after_deadline: number;
  satisfied_by: string | null;       // id do documento
  source: SourceReference; verified: boolean;
}

export interface Mission {
  id: string; student_id: string; title: string; description: string; institution: string;
  status: MissionStatus; deadline: string | null; depends_on: string[];
  requirements: Requirement[];
  tasks: { id: string; title: string; done: boolean }[];
  completion_criteria: string;
}

export interface Twin { student: Student; documents: StudentDocument[]; missions: Mission[]; }

export interface Deadline {
  kind: "mission" | "document_expiry"; id: string; title: string;
  date: string; days_left: number; status: Verification;
}

export type ImpactLevel = "critical" | "high" | "medium" | "low" | "unknown";

export interface ImpactItem {
  level: ImpactLevel; mission_id: string; mission_title: string; requirement_id: string | null;
  explanation: string;
  evidence: { kind: "fact" | "requirement" | "mission" | "dependency"; description: string;
              status: string | null; source: string | null }[];
  assumptions: string[];             // mostrar como "pressupostos / incertezas"
  recommended_actions: string[];
}

export interface ImpactReport {
  student_id: string; event: Record<string, unknown>; as_of: string;
  overall_level: ImpactLevel; items: ImpactItem[];   // já vêm ordenados do mais grave
  disclaimer: string;                                // mostrar sempre
}

export type ApprovalStatus = "pending" | "approved" | "rejected" | "executed" | "simulated" | "failed";

export interface ApprovalRequest {
  id: string; student_id: string; mission_id: string | null; action_type: "send_email";
  summary: string; payload: { to: string; subject: string; body: string };
  status: ApprovalStatus; result: string | null; created_at: string; decided_at: string | null;
}

export interface ChatReply { reply: string; model: string; mock: boolean; }
```

## 5. Exemplos de pedidos

```ts
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const SID = "stu-demo";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API + path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Pedido inválido");
  return data as T;
}
const post = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// Dashboard
const twin = await api<Twin>(`/api/students/${SID}`);

// Riscos atuais
const report = await post<ImpactReport>(`/api/students/${SID}/impact`, { event: { type: "check" } });

// "E se?": mudar a validade de um documento (não altera nada guardado)
await post<ImpactReport>(`/api/students/${SID}/impact`, {
  event: { type: "document_expiry_change", document_id: "doc-passport", new_expiry_date: "2032-01-01" },
});
// "E se?": perder um documento
await post<ImpactReport>(`/api/students/${SID}/impact`, {
  event: { type: "document_removed", document_id: "doc-housing" },
});

// Upload (NÃO definir Content-Type à mão)
const form = new FormData();
form.append("file", file);              // .pdf .txt .png .jpg .jpeg, máx. 10 MB
form.append("title", "Carta da imigração"); // opcional
const doc = await api<StudentDocument>(`/api/students/${SID}/documents`, { method: "POST", body: form });

// Confirmar, corrigir ou rejeitar um campo extraído
await post(`/api/documents/${doc.id}/fields/expiry_date`, { decision: "confirm" });
await post(`/api/documents/${doc.id}/fields/expiry_date`, { decision: "confirm", value: "2027-01-25" });
await post(`/api/documents/${doc.id}/fields/expiry_date`, { decision: "reject" });

// Nova missão ligada à carta
await post<Mission>(`/api/students/${SID}/missions`, {
  title: "Responder à carta da imigração", institution: "OIF", deadline: "2027-01-10",
  document_ids: [doc.id], depends_on: [], tasks: ["Ler a carta", "Juntar documentos"],
});

// Aprovação de email
const ap = await post<ApprovalRequest>(`/api/students/${SID}/approvals`, {
  mission_id: "mis-permit", to: "office@example.org", subject: "Kérdés", body: "Tisztelt ...",
});
await post<ApprovalRequest>(`/api/approvals/${ap.id}/approve`, {});   // ou /reject

// Chat (history = últimas mensagens, a mais antiga primeiro)
await post<ChatReply>(`/api/students/${SID}/agent/chat`, {
  message: "O que devo resolver primeiro?", language: "auto", history: [],
});
```

## 6. Regras de UI que não podem falhar

Vêm do SDD e um júri vai reparar nelas:

1. **Mostrar o estado de cada dado.** Um `extracted_pending_confirmation` tem de ter um aspeto visual diferente (badge amarelo, "por confirmar") e botões **Confirmar / Corrigir / Rejeitar**.
2. **Mostrar as provas do impacto.** Cada risco deve abrir as `evidence` e as `assumptions`. A ideia é "o sistema mostra porquê".
3. **O `disclaimer` aparece sempre** junto ao relatório de impacto.
4. **Aprovações.** O ecrã mostra o `summary` e o `payload` completo (para quem, assunto, texto) **antes** dos botões Aprovar / Rejeitar.
5. **Nunca escrever "Enviado ✓" quando o estado é `simulated`.** Mostra o texto de `result`, que diz que não foi enviado de verdade.
6. **Se o documento trouxer `extraction_error`** (por exemplo, imagens, que ainda não têm OCR), mostra o erro e deixa o utilizador preencher os campos à mão. Usa o endpoint de campos com `value`.
7. **Cores sugeridas por nível:** critical = vermelho, high = laranja, medium = amarelo, low = verde, unknown = cinzento.

## 7. Erros

- `400`: upload inválido (tipo, tamanho, PDF falso). A mensagem vem em `detail` (string).
- `404`: id não existe.
- `409`: transição não permitida, ou aprovação já decidida. Exemplo: `"Cannot go from CREATED to COMPLETED"`.
- `422`: validação. Aqui `detail` é uma **lista** de erros (formato do FastAPI), não uma string.
- `502`: o serviço de IA falhou. Mostra "tenta outra vez" e não inventes uma resposta.

Transições de estado das missões que são permitidas:
`CREATED → ANALYSIS → PLANNED → IN_PROGRESS → (WAITING_FOR_USER | WAITING_FOR_INSTITUTION ↔ IN_PROGRESS) → COMPLETED`.
Qualquer estado ativo também pode passar para `CANCELLED`. Os estados de `BLOCKED` e `EXPIRED` estão em `backend/app/models.py`.

## 8. Dados de demo (ids fixos)

| id | O que é |
|---|---|
| `doc-passport` | Passaporte, válido até 2027-03-10 (confirmado) |
| `doc-enrollment` | Certificado de matrícula, até 2027-08-31 |
| `doc-housing` | Contrato do dormitório, até 2027-01-31 (**por confirmar**) |
| `mis-permit` | Renovar a autorização de residência, prazo 2027-01-20 |
| `mis-registration` | Inscrição do semestre, prazo 2027-02-05 |
| `mis-addresscard` | Cartão de morada, depende de `mis-permit` |

> A regra "passaporte válido mais 180 dias" é **fictícia**, feita só para a demo.

## 9. Ainda não existe (não contes com isto)

- Login / autenticação. Usa `stu-demo`.
- Persistência: os dados reiniciam com o servidor.
- OCR de imagens.
- Envio real de email.
- Explicação das cartas pelo LLM. Está planeada: vai aparecer como um campo novo no documento.

Dúvidas sobre o backend: falem com quem está no `backend/`, ou vejam `backend/README.md`.
