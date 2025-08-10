# Prototype Spec

## Phase 2 – System Design Proposal (Prototype Spec)

### 1) Scope ของ Prototype (MVP)
- Flow Builder (เว็บ): แคนวาสลาก-วาง + ฟอร์มตั้งค่าของโหนด + Run/Debug ได้
- Prompt-to-Flow: ช่อง “พิมพ์ไอเดีย” → ได้ FlowSpec (JSON) เป็น Draft
- Agent/Flow Runtime: รันตามลำดับโหนด, เก็บ log/ผลลัพธ์
- RAG (Vertex AI Vector Search): ingest เอกสาร → chunk → embed → upsert → query
- Tools รอบแรก: Microsoft 365 Email/Calendar (ผ่าน Graph API) + HTTP generic
- LLM Gateway: OpenAI-compatible ผ่าน LiteLLM (รวม logging/cost)
- Dashboard เบื้องต้น: ดู run history + token/cost (ดึงจาก LiteLLM)

### 2) สถาปัตยกรรม & บริการ (localhost)
**Services**
- web (Next.js/React + React Flow) – :3000
- core (FastAPI) – :8000 (REST + WebSocket)
- litellm (LiteLLM Gateway) – :4000 (/v1/*)
- worker (ออปชัน) – Celery + Redis สำหรับงาน async/ingest
- db – SQLite (ไฟล์) สำหรับ PoC (เปลี่ยนเป็น Postgres ภายหลัง)

**External:**
- Vertex AI Vector Search (GCP project/env ของ Dev)
- Microsoft Graph (App registration บน Entra ID)

**โฟลว์หลัก**
- Web สร้าง/แก้ FlowSpec → Core บันทึกเวอร์ชัน
- Web สั่งรัน → Core ประมวลผลโหนดทีละ step → ส่ง event ผ่าน WebSocket
- โหนด LLM → เรียก litellm /v1/chat/completions
- โหนด RAG → เรียก vector_store.query() ไป Vertex
- โหนด Email/Calendar → เรียก Microsoft Graph ด้วย user token

### 3) Data Model (สรุปสคีมาหลัก)
#### 3.1 FlowSpec (JSON)
```json
{
  "id": "flow_123",
  "name": "KM Chatbot",
  "version": 3,
  "nodes": [
    {"id":"n1","type":"input","params":{}},
    {"id":"n2","type":"rag.retrieve","params":{"top_k":5,"filters":{}}},
    {"id":"n3","type":"llm.chat","params":{
      "model":"gpt-4o-mini",
      "system":"Answer concisely with citations.",
      "temperature":0.2
    }},
    {"id":"n4","type":"output","params":{}}
  ],
  "edges": [
    {"from":"n1","to":"n2"},
    {"from":"n2","to":"n3"},
    {"from":"n3","to":"n4"}
  ],
  "created_by":"user_1","created_at":"2025-08-10T04:00:00Z"
}
```
**ข้อกำหนด**
- nodes[].type ต้องเป็นชนิดที่ระบบรองรับ (ดู 3.3)
- พอร์ต: ทุกโหนดถือว่า single-in / single-out (PoC)
- ค่าใน params ตรวจตาม JSON Schema ของแต่ละโหนด

#### 3.2 RunRecord (บันทึกการรัน)
```json
{
  "run_id":"run_abc",
  "flow_id":"flow_123",
  "status":"running|succeeded|failed",
  "started_at":"...",
  "ended_at":"...",
  "inputs":{"message":"..."},
  "outputs":{"answer":"...","citations":[...]},
  "steps":[
    {"node_id":"n2","status":"succeeded","latency_ms":120,"logs":["..."]},
    {"node_id":"n3","status":"succeeded","latency_ms":450,"token_usage":{"prompt":800,"completion":120}}
  ],
  "cost":{"usd":0.0031}
}
```

#### 3.3 Node Catalog (PoC)
| type | params (schema) | output |
|------|-----------------|--------|
| input | {} | {payload: any} |
| rag.retrieve | {"top_k": int>=1, "filters": object?} | {chunks:[{text,meta}], citations:[...]} |
| llm.chat | {"model":string,"system":string?,"temperature":0-2} | {text:string,raw?:object} |
| email.read | {"since":ISO8601?,"until":ISO8601?,"max":int<=100} | {messages:[{id,subject,body,from,dt}]} |
| email.send | {"to":[string],"subject":string,"body":string} | {message_id:string} |
| calendar.create | {"title":string,"start":ISO8601,"end":ISO8601,"attendees":[string]?} | {event_id:string,web_link:string} |
| http.request | `{ "url":string,"method":"GET\tPOST","headers":object?,"body":any?}` | – |
| code.exec | {"language":"python","code":string,"timeout_ms":<=5000} | {stdout:string,stderr:string,artifacts?:object} |
| output | {} | passthrough |

หมายเหตุ: rag.retrieve ทำงานกับ Vertex AI Vector Search ผ่าน adapter ใน core.

### 4) สเปก API (Core Service)
#### 4.1 Auth (PoC แบบง่าย)
- POST /auth/login → {username,password} → {access_token,jwt_exp}
- Roles: admin|builder|user (ฝังใน JWT)
- ภายหลังจะเปลี่ยนเป็น SSO/OAuth

#### 4.2 Flow Management
- POST /flows – สร้าง FlowSpec
  - Req: {name, nodes, edges}
  - Res: {id, version}
- GET /flows/{id} – ดึง FlowSpec ล่าสุด
- PUT /flows/{id} – อัปเดต (auto version++)
- POST /flows/validate – ส่ง FlowSpec → คืน {valid:bool, errors:[...]}
- POST /flows/gen – Prompt-to-Flow
  - Req: {idea:string, constraints?:object}
  - Res: {flow_spec:FlowSpec, rationale:string}
  - ภายในใช้ LLM ผ่าน LiteLLM + few-shot

#### 4.3 Run/Execution
- POST /runs – สั่งรันโฟลว์
  - Req: {flow_id, inputs}
  - Res: {run_id}
- GET /runs/{run_id} – สถานะ/ผลลัพธ์
- WS /runs/{run_id}/events – สตรีม step events
  - Event ตัวอย่าง:
```json
{"type":"step_started","node_id":"n2"}
{"type":"step_log","node_id":"n2","msg":"retrieved 5 chunks"}
{"type":"step_succeeded","node_id":"n2","latency_ms":120}
```
- POST /runs/{run_id}/cancel

#### 4.4 RAG Ingest & Search
- POST /ingest/files – อัปไฟล์เอกสาร (PoC: PDF/TXT)
  - Req: form-data: file, metadata?:json
  - Res: {task_id}
- GET /ingest/{task_id} – สถานะ ingest
- POST /search – ทดสอบค้น (debug)
  - Req: {query:string, top_k:int, filters?:object}
  - Res: {chunks:[{text,meta}], citations:[...]}
- Internal Adapter (ไม่เปิดเป็น REST): vector_store.upsert(chunks) / vector_store.query(embedding, top_k, filters)

#### 4.5 Tools (ทดสอบโดยตรงได้ใน PoC)
- POST /tools/email.read
  - Req: {"since":"2025-08-09T00:00:00Z","until":"2025-08-10T00:00:00Z","max":20}
  - Res: {"messages":[{id,subject,from,body,receivedDateTime}]}
- POST /tools/email.send
  - Req: {"to":["a@org.com"],"subject":"...","body":"..."}
  - Res: {"message_id":"..."}
- POST /tools/calendar.create
  - Req: {"title":"Standup","start":"2025-08-11T02:00:00Z","end":"2025-08-11T02:15:00Z","attendees":["a@org.com"]}
  - Res: {"event_id":"...","web_link":"..."}
- POST /tools/http.request – ตัวช่วย debug HTTP

#### 4.6 Admin/Observability
- GET /metrics – RUN count, success rate, avg latency
- GET /costs – token/cost โดยสรุป (ดึงจาก LiteLLM logs)
- GET /health – health of core, vector, litellm

**มาตรฐาน API**
- Auth: Authorization: Bearer <token>
- Error format:
```json
{"error":{"code":"VALIDATION_ERROR","message":"...","details":{}}}
```

### 5) การเรียกภายนอก (Integration Contracts)
#### 5.1 LiteLLM (OpenAI-compatible)
- Base URL: http://localhost:4000/v1
- Chat: POST /v1/chat/completions
```json
{"model":"gpt-4o-mini","messages":[{"role":"system","content":"..."},{"role":"user","content":"..."}]}
```
- Embeddings: POST /v1/embeddings
```json
{"model":"text-embedding-3-small","input":["chunk text 1","chunk text 2"]}
```
- เก็บ log/token/cost ให้ dashboard ใช้งานภายหลัง

#### 5.2 Vertex AI Vector Search (ผ่าน Python SDK/REST)
ฟังก์ชันใน vector_store.py (ให้ทีม Dev ทำเป็น abstraction):
- create_index_if_not_exists(index_name)
- upsert(datapoints: List[Chunk]) -> task_id
- query(embedding: List[float], top_k: int, filters: dict|None) -> List[Chunk]

Chunk structure (ที่เรา upsert):
```json
{"id":"doc1_p3_004",
 "embedding":[...],
 "metadata":{"source":"gs://bucket/doc1.pdf","page":3,"title":"...","acl":["group:sales"]}}
```
Query return:
```json
[{"text":"...", "meta":{"source":"...","page":3}, "score":0.82}]
```

#### 5.3 Microsoft Graph (Email/Calendar)
- OAuth 2.0 Authorization Code (localhost callback):
  - Scopes: Mail.Read, Mail.Send, Calendars.ReadWrite, offline_access
- Read mail: GET https://graph.microsoft.com/v1.0/me/messages?$top=20&$filter=receivedDateTime ge 2025-08-09T00:00:00Z
- Send mail: POST /v1.0/me/sendMail (payload: message, saveToSentItems)
- Create event: POST /v1.0/me/events (payload: subject, start, end, attendees)
- PoC: เก็บ user token ไว้ใน local db แบบเข้ารหัส, หมดอายุแล้ว refresh token อัตโนมัติ

### 6) Execution Contract ของโหนด (สำคัญสำหรับ Dev)
**อินเทอร์เฟซมาตรฐาน**
```ts
type NodeContext = {
  runId: string
  nodeId: string
  inputs: any      // payload จากโหนดก่อนหน้า
  params: any      // ค่าตาม schema ของโหนด
  secrets: Record<string,string> // เช่น GRAPH_CLIENT_ID
  user: { id:string, email:string, roles:string[] }
  logger: (msg:string)=>void
  emit: (event:object)=>void // ส่ง event กลับไปหา WS
  timeoutMs: number // กำหนดโดย runtime
}

type NodeHandler = (ctx: NodeContext) => Promise<any>
```
**สัญญา**
- โหนดต้อง pure (เท่าที่ทำได้), คืนค่า JSON ที่ชัดเจน
- ต้องโยน Error เป็น {code,message,details} เพื่อให้ runtime แปลเป็น HTTP/WS error ได้
- Timeouts: โหนดใด ๆ ไม่เกิน 30s (PoC), code.exec จำกัด 5s

**Sandbox code.exec**
- Language: Python เท่านั้น
- ไม่มี network, จำกัดหน่วยความจำ (เช่น 128MB), exec ใน subprocess/Docker
- allowlist packages: numpy, pandas (ถ้าจำเป็น), อื่น ๆ ค่อยเพิ่ม

### 7) Prompt-to-Flow (สเปกฝั่ง Core)
- Endpoint: POST /flows/gen
- Input: {idea:string, context?:{use_case?: "km"|"automation"}}
- Behavior:
  - สร้างคำสั่ง system + few-shot (เรากำหนดชุดโหนดที่ใช้ได้)
  - เรียก litellm /v1/chat/completions
  - ตรวจ FlowSpec ด้วย schema → ถ้าพลาด เติมค่า default/ซ่อม topology
- Output: {flow_spec, rationale}

**Few-shot (แนว)**
1. ตัวอย่าง 1: “บอทตอบคำถามจากเอกสาร” → input → rag.retrieve(top_k=5) → llm.chat(system='ตอบพร้อม citations') → output
2. ตัวอย่าง 2: “สรุปอีเมลเช้าและสร้างนัด” → email.read → llm.chat(สรุป) → calendar.create → output

### 8) Frontend (Web) สเปกจอ & พฤติกรรม
**หน้าหลัก**
- Canvas (React Flow): เพิ่ม/ลบ/ลากโหนด, ต่อเส้น, เลือกโหนดใด ๆ จะเปิด Inspector Panel (ฟอร์มจาก schema)
- Toolbar: Run, Run from Node, Validate, Save, Generate from Idea
- Console: แสดง WS events (step_started/log/succeeded/failed)

**จอ Chat Test (KM)**
- ช่องถาม, ดูคำตอบ + citations, ปุ่ม “View flow” → เปิด FlowSpec ที่ใช้

**Validation**
- ฝั่ง browser ตรวจ schema (AJV) ก่อนส่งเซิร์ฟเวอร์
- ป้องกันวางโหนดต้องห้าม (เช่น email.send สำหรับ role user)

### 9) Security & RBAC (PoC)
- Roles: admin, builder, user

**Mapping:**
- user: ใช้ได้เฉพาะ flow ที่อนุญาต, โหนด input, rag.retrieve, llm.chat, output
- builder: ใช้ได้ทุกโหนดยกเว้น code.exec ถ้าไม่ได้เปิด
- admin: ทั้งหมด + admin APIs

**Secrets:** เก็บใน .env (PoC) → เป้าในอนาคตย้ายเข้า secret vault

**Audit log:** บันทึกสำคัญ (สร้าง/แก้ flow, run, เรียก tools)

### 10) ตัวอย่างสคริปต์การรัน (Sample Calls)
**สร้าง Flow**
```bash
POST /flows
{ "name":"KM Bot", "nodes":[...], "edges":[...] }
```
**สั่งรัน**
```bash
POST /runs
{ "flow_id":"flow_123", "inputs":{"message":"สวัสดี เอกสารตัวไหนอธิบายขั้นตอนเบิกค่าเดินทาง?"} }
```
**สตรีมผล**
```bash
WS /runs/run_abc/events
-- รับ event ต่อเนื่องจนจบ
```
**Ingest เอกสาร**
```bash
POST /ingest/files (multipart)
file=@handbook.pdf
```

### 11) งานพัฒนา (Backlog ย่อย + Acceptance)
**EPIC A – Core Runtime**
- Story A1: สร้างโครง FastAPI + JWT auth + /health
  - AC: /health คืน {"status":"ok"}; login ได้ role-based
- Story A2: สคีมา FlowSpec + /flows CRUD + /flows/validate
  - AC: ส่ง spec ผิด schema จะได้ VALIDATION_ERROR
- Story A3: Engine รัน sequential nodes + WS events
  - AC: เดโม่โหนด mock 3 ตัวแล้วเห็น events step-by-step

**EPIC B – LLM & RAG**
- Story B1: ต่อ LiteLLM /v1/chat/completions
  - AC: โหนด llm.chat ตอบข้อความได้, เก็บ token usage
- Story B2: Embedding & Vertex Query adapter
  - AC: /search คืน top_k chunks พร้อม meta, latency < 300ms (บนชุดทดสอบเล็ก)
- Story B3: โหนด rag.retrieve
  - AC: ร้อยกับ llm.chat แล้วตอบพร้อม citations

**EPIC C – Tools**
- Story C1: OAuth (localhost) สำหรับ Graph + เก็บ token
  - AC: ล็อกอินแล้วเรียก Graph API ได้
- Story C2: email.read, email.send, calendar.create nodes
  - AC: Flow “สรุปอีเมลเช้า→สร้างนัด” รันจบ

**EPIC D – Prompt-to-Flow**
- Story D1: /flows/gen + few-shot 2 เคส
  - AC: ป้อนไอเดีย ได้ FlowSpec ถูก schema ≥80% ของครั้งลอง

**EPIC E – Web Builder**
- Story E1: Canvas + Inspector + Validate/Run
  - AC: ต่อเส้น/ตั้งค่า/กด Run แล้ว WS โชว์ log ตามโหนด
- Story E2: Chat Test (KM)
  - AC: ถาม-ตอบได้, แสดง citations

**EPIC F – Observability**
- Story F1: /metrics, /costs
  - AC: เห็นจำนวนรัน, success rate, token/cost ต่อผู้ใช้/โปรเจกต์

### 12) ค่าเริ่มต้น/ENV ที่ Dev ต้องตั้ง (ตัวอย่าง)
```ini
# core
CORE_PORT=8000
JWT_SECRET=changeme
ALLOWED_ORIGINS=http://localhost:3000

# litellm
LITELLM_PORT=4000
OPENAI_API_KEY=sk-...

# gcp / vertex
GCP_PROJECT=your-dev-project
GCP_LOCATION=us-central1
VERTEX_INDEX_NAME=regista_poc_index
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json

# microsoft graph (app reg)
GRAPH_CLIENT_ID=...
GRAPH_CLIENT_SECRET=...
GRAPH_TENANT_ID=...
GRAPH_REDIRECT_URI=http://localhost:8000/auth/callback
```

### 13) เดโมที่ต้องแสดง (Acceptance ของ MVP)
- KM Chatbot: อัป handbook.pdf → ถามคำถาม → ตอบพร้อม citations
- Automation: ไอเดีย “สรุปอีเมลเช้าและจองประชุม 15 นาที” → gen flow → แก้เล็กน้อย → รัน → อีเมลถูกสรุป + สร้างนัดสำเร็จ
- Dashboard: แสดง run count, success rate, token/cost (จาก LiteLLM)

---

## แพ็กสเปกเพิ่มเติม (Prompt templates, JSON Schemas, Samples)
### 1) Prompt Templates สำหรับ /flows/gen
#### 1.1 System Prompt (ฝั่ง core)
```typescript
You are "Flow Composer" that converts a natural-language idea into a valid FlowSpec JSON for an internal AI-agent workflow builder.

STRICT RULES:
- Output JSON ONLY. No prose, no comments.
- Use this FlowSpec schema: 
  {
    "name": string,
    "nodes": Array<Node>,
    "edges": Array<Edge>
  }
  Node = { "id": string, "type": one of [ "input","rag.retrieve","llm.chat","email.read","email.send","calendar.create","http.request","code.exec","output" ], "params": object }
  Edge = { "from": string, "to": string }
- Single linear path only (one incoming and one outgoing per node) for PoC.
- Always include an "input" as the first node and "output" as the last node.
- Only use allowed params per node (see CATALOG below). If unsure, use defaults.

CATALOG (defaults):
- input: params {}
- rag.retrieve: { "top_k": 5, "filters": {} }
- llm.chat: { "model": "gpt-4o-mini", "system": "Answer concisely.", "temperature": 0.2 }
- email.read: { "since": null, "until": null, "max": 20 }
- email.send: { "to": [], "subject": "", "body": "" }
- calendar.create: { "title": "", "start": "", "end": "", "attendees": [] }
- http.request: { "url": "", "method": "GET", "headers": {}, "body": null }
- code.exec: { "language": "python", "code": "", "timeout_ms": 3000 }
- output: {}

CONSTRAINTS:
- Use meaningful, unique node ids like "n1","n2".
- Prefer minimal nodes to satisfy the idea.
- For KM/RAG use: input -> rag.retrieve -> llm.chat -> output.
- For email summary + meeting: email.read -> llm.chat -> calendar.create -> output.

Return only valid JSON.
```

#### 1.2 User Prompt Template
```css
IDEA:
{{idea}}

CONTEXT (optional):
{{context_json_or_empty}}
```

### 2) Few-shot Examples
#### 2.1 KM Chatbot (GenAI + RAG)
**User IDEA:**
“ทำแชตบอทตอบจากคู่มือพนักงานและให้ใส่ citation”

**Expected JSON**
```json
{
  "name": "KM Chatbot with RAG",
  "nodes": [
    {"id":"n1","type":"input","params":{}},
    {"id":"n2","type":"rag.retrieve","params":{"top_k":5,"filters":{}}},
    {"id":"n3","type":"llm.chat","params":{"model":"gpt-4o-mini","system":"Answer concisely with citations.","temperature":0.2}},
    {"id":"n4","type":"output","params":{}}
  ],
  "edges": [
    {"from":"n1","to":"n2"},
    {"from":"n2","to":"n3"},
    {"from":"n3","to":"n4"}
  ]
}
```

#### 2.2 Summary Email → Create Calendar
**User IDEA:**
“สรุปอีเมลเช้าวันนี้แล้วสร้างนัดประชุม 15 นาทีช่วงบ่าย”

**Expected JSON**
```json
{
  "name": "Morning Email Summary and Schedule",
  "nodes": [
    {"id":"n1","type":"email.read","params":{"since":null,"until":null,"max":20}},
    {"id":"n2","type":"llm.chat","params":{"model":"gpt-4o-mini","system":"Summarize emails briefly.","temperature":0.2}},
    {"id":"n3","type":"calendar.create","params":{"title":"Quick sync","start":"","end":"","attendees":[]}},
    {"id":"n4","type":"output","params":{}}
  ],
  "edges": [
    {"from":"n1","to":"n2"},
    {"from":"n2","to":"n3"},
    {"from":"n3","to":"n4"}
  ]
}
```

### 3) JSON Schemas
#### 3.1 FlowSpec Schema (Draft-07)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://regista/poc/flowspec.schema.json",
  "type": "object",
  "required": ["name","nodes","edges"],
  "properties": {
    "name": { "type":"string", "minLength":1, "maxLength":120 },
    "nodes": {
      "type": "array",
      "minItems": 2,
      "items": { "$ref": "#/definitions/node" }
    },
    "edges": {
      "type": "array",
      "minItems": 1,
      "items": { "$ref": "#/definitions/edge" }
    }
  },
  "definitions": {
    "node": {
      "type":"object",
      "required":["id","type","params"],
      "properties":{
        "id":{"type":"string","pattern":"^n[0-9]+$"},
        "type":{
          "type":"string",
          "enum":["input","rag.retrieve","llm.chat","email.read","email.send","calendar.create","http.request","code.exec","output"]
        },
        "params":{"type":"object"}
      },
      "additionalProperties": false
    },
    "edge": {
      "type":"object",
      "required":["from","to"],
      "properties":{
        "from":{"type":"string","pattern":"^n[0-9]+$"},
        "to":{"type":"string","pattern":"^n[0-9]+$"}
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

#### 3.2 Node Catalog (params schema)
```json
{
  "version": 1,
  "nodes": {
    "input": {
      "schema": {
        "type": "object",
        "properties": {},
        "additionalProperties": false
      },
      "ui": {}
    },
    "rag.retrieve": {
      "schema": {
        "type": "object",
        "properties": {
          "top_k": { "type":"integer", "minimum":1, "maximum":50, "default":5 },
          "filters": { "type":"object", "default": {} }
        },
        "required": ["top_k"],
        "additionalProperties": false
      },
      "ui": {
        "order": ["top_k","filters"],
        "help": "Query Vertex AI Vector Search"
      }
    },
    "llm.chat": {
      "schema": {
        "type": "object",
        "properties": {
          "model": { "type":"string", "default":"gpt-4o-mini" },
          "system": { "type":"string", "default":"Answer concisely." },
          "temperature": { "type":"number", "minimum":0, "maximum":2, "default":0.2 }
        },
        "required": ["model"],
        "additionalProperties": false
      },
      "ui": { "order": ["model","system","temperature"] }
    },
    "email.read": {
      "schema": {
        "type": "object",
        "properties": {
          "since": { "type":["string","null"], "pattern":"^$|^\\d{4}-\\d{2}-\\d{2}T.*Z$" },
          "until": { "type":["string","null"], "pattern":"^$|^\\d{4}-\\d{2}-\\d{2}T.*Z$" },
          "max": { "type":"integer", "minimum":1, "maximum":100, "default":20 }
        },
        "additionalProperties": false
      },
      "ui": { "help": "Microsoft Graph: Mail.Read" }
    },
    "email.send": {
      "schema": {
        "type":"object",
        "properties": {
          "to": { "type":"array", "items":{"type":"string","format":"email"}, "default":[] },
          "subject": { "type":"string", "default":"" },
          "body": { "type":"string", "default":"" }
        },
        "required": ["to","subject","body"],
        "additionalProperties": false
      },
      "ui": {}
    },
    "calendar.create": {
      "schema": {
        "type":"object",
        "properties": {
          "title": { "type":"string", "default":"Meeting" },
          "start": { "type":"string", "pattern":"^\\d{4}-\\d{2}-\\d{2}T.*Z$", "default":"" },
          "end": { "type":"string", "pattern":"^\\d{4}-\\d{2}-\\d{2}T.*Z$", "default":"" },
          "attendees": { "type":"array", "items":{"type":"string","format":"email"}, "default":[] }
        },
        "required": ["title","start","end"],
        "additionalProperties": false
      },
      "ui": { "help": "Graph: Calendars.ReadWrite" }
    },
    "http.request": {
      "schema": {
        "type":"object",
        "properties": {
          "url": { "type":"string", "minLength":1 },
          "method": { "type":"string", "enum":["GET","POST"], "default":"GET" },
          "headers": { "type":"object", "default":{} },
          "body": {}
        },
        "required":["url","method"],
        "additionalProperties": false
      },
      "ui": {}
    },
    "code.exec": {
      "schema": {
        "type":"object",
        "properties": {
          "language": { "type":"string", "enum":["python"], "default":"python" },
          "code": { "type":"string", "minLength":1 },
          "timeout_ms": { "type":"integer", "minimum":100, "maximum":5000, "default":3000 }
        },
        "required":["language","code"],
        "additionalProperties": false
      },
      "ui": { "help": "Sandboxed, no-network" }
    },
    "output": {
      "schema": {
        "type":"object",
        "properties": {},
        "additionalProperties": false
      },
      "ui": {}
    }
  }
}
```

### 4) Auto-Repair/Validation (ฝั่ง core)
**ลอจิก (pseudo-code):**
```python
def validate_and_repair(flow, catalog):
    assert schema_validate(flow, FlowSpecSchema)
    ids = {n["id"] for n in flow["nodes"]}
    # unique id
    if len(ids) != len(flow["nodes"]):
        raise BadRequest("DUPLICATE_NODE_ID")
    # edges reference check
    for e in flow["edges"]:
        if e["from"] not in ids or e["to"] not in ids:
            raise BadRequest("EDGE_REF_INVALID")
    # required input/output
    types = [n["type"] for n in flow["nodes"]]
    if types[0] != "input": raise BadRequest("FIRST_NODE_MUST_BE_INPUT")
    if types[-1] != "output": raise BadRequest("LAST_NODE_MUST_BE_OUTPUT")
    # params schema + defaults
    for n in flow["nodes"]:
        node_schema = catalog["nodes"][n["type"]]["schema"]
        n["params"] = apply_defaults_and_validate(n["params"], node_schema)
    # linear topology (PoC)
    deg_in = {nid:0 for nid in ids}; deg_out = {nid:0 for nid in ids}
    for e in flow["edges"]:
        deg_out[e["from"]] += 1; deg_in[e["to"]] += 1
    if any(v>1 for v in deg_in.values()): raise BadRequest("MULTI_IN_NOT_ALLOWED")
    if any(v>1 for v in deg_out.values()): raise BadRequest("MULTI_OUT_NOT_ALLOWED")
    return flow
```

### 5) ตัวอย่างเรียกใช้งาน (cURL/HTTP) สำหรับทดสอบ
#### 5.1 สร้าง Flow (KM)
```bash
curl -X POST http://localhost:8000/flows \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name":"KM Bot",
    "nodes":[
      {"id":"n1","type":"input","params":{}},
      {"id":"n2","type":"rag.retrieve","params":{"top_k":5}},
      {"id":"n3","type":"llm.chat","params":{"model":"gpt-4o-mini","system":"Answer concisely with citations."}},
      {"id":"n4","type":"output","params":{}}
    ],
    "edges":[
      {"from":"n1","to":"n2"},
      {"from":"n2","to":"n3"},
      {"from":"n3","to":"n4"}
    ]
  }'
```
#### 5.2 Ingest เอกสาร (PoC)
```bash
curl -X POST http://localhost:8000/ingest/files \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/handbook.pdf"
```
#### 5.3 รันโฟลว์ (ถามคำถาม)
```bash
curl -X POST http://localhost:8000/runs \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{ "flow_id":"<FLOW_ID>", "inputs":{ "message":"สิทธิ์ลาพักร้อนมีกี่วัน?" } }'
```
#### 5.4 Prompt-to-Flow
```bash
curl -X POST http://localhost:8000/flows/gen \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{ "idea":"สรุปอีเมลเช้าและจองประชุม 15 นาทีช่วงบ่าย", "context":{"use_case":"automation"} }'
```
#### 5.5 เครื่องมือ M365 (ทดสอบตรง ๆ)
```bash
curl -X POST http://localhost:8000/tools/email.read \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{ "max": 10 }'
```

### 6) ตัวอย่าง Handler Signatures
```python
# core/runtime/contracts.py
from typing import Any, Dict

class NodeContext:
    def __init__(self, run_id:str, node_id:str, inputs:Any, params:Dict, secrets:Dict[str,str], user:Dict, logger, emit, timeout_ms:int):
        self.run_id = run_id
        self.node_id = node_id
        self.inputs = inputs
        self.params = params
        self.secrets = secrets
        self.user = user
        self.logger = logger
        self.emit = emit
        self.timeout_ms = timeout_ms

NodeHandler = callable  # (ctx: NodeContext) -> Any
```
**ตัวอย่าง llm.chat**
```python
async def node_llm_chat(ctx: NodeContext):
    body = {
        "model": ctx.params.get("model","gpt-4o-mini"),
        "messages": [
            {"role":"system","content":ctx.params.get("system","Answer concisely.")},
            {"role":"user","content": ctx.inputs.get("message") if isinstance(ctx.inputs, dict) else str(ctx.inputs)}
        ],
        "temperature": ctx.params.get("temperature", 0.2)
    }
    ctx.logger("calling litellm...")
    resp = await http_post("http://localhost:4000/v1/chat/completions", json=body, timeout=ctx.timeout_ms/1000)
    text = resp["choices"][0]["message"]["content"]
    return {"text": text, "raw": resp}
```
**ตัวอย่าง rag.retrieve**
```python
async def node_rag_retrieve(ctx: NodeContext):
    query_text = ctx.inputs.get("message") if isinstance(ctx.inputs, dict) else str(ctx.inputs)
    embedding = await embed(query_text)  # call /v1/embeddings via LiteLLM
    chunks = await vertex_query(embedding, top_k=ctx.params["top_k"], filters=ctx.params.get("filters", {}))
    ctx.logger(f"retrieved {len(chunks)} chunks")
    return {"chunks": chunks, "citations": [{"source":c["meta"]["source"],"page":c["meta"].get("page")} for c in chunks]}
```
**ตัวอย่าง email.read**
```python
async def node_email_read(ctx: NodeContext):
    token = await ensure_user_token(ctx.user["id"])  # PoC
    url = "https://graph.microsoft.com/v1.0/me/messages?$top={}".format(ctx.params.get("max",20))
    data = await http_get(url, headers={"Authorization": f"Bearer {token}"})
    msgs = [{"id":m["id"],"subject":m.get("subject",""),"from":m.get("from",{}).get("emailAddress",{}).get("address",""),
             "body": m.get("bodyPreview",""), "receivedDateTime": m.get("receivedDateTime",""} for m in data.get("value",[])]
    return {"messages": msgs}
```

### 7) Test Checklist
- ✅ Schema Validation: ส่ง FlowSpec ที่ผิด (เช่น ไม่มี output) แล้วต้องได้ VALIDATION_ERROR
- ✅ Run Engine: โฟลว์ mock 3 โหนด (input→llm.chat→output) ต้องส่ง WS events: step_started, step_succeeded ตามลำดับ
- ✅ RAG: /ingest/files แล้ว /search ต้องคืน chunks ≥ 1 สำหรับคีย์เวิร์ดที่มีในไฟล์
- ✅ M365: email.read คืนรายการอีเมล, calendar.create สร้างนัดแล้วตอบ event_id
- ✅ Prompt-to-Flow: ไอเดีย 2 เคส (KM / Automation) ได้ FlowSpec ถูก schema ≥80% ครั้งลอง
- ✅ Observability: /metrics คืน run count/success rate; /costs รวมค่าใช้จ่ายจาก LiteLLM log
