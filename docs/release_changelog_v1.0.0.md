# 🛡️ Release v1.0.0 — The Guardian of Kali

Official first production release of **The Guardian of Kali**, an AI-assisted desktop terminal application and zero-trust security policy engine tailored for ethical hacking, penetration testing, and CTF challenges natively running on **Kali Linux inside WSL2**.

---

## 📦 What's Changed

### 🚀 Backend & Policy Engine (`the-guardian-of-kali_backend`)

#### 🌟 Features (`feat`)
* **Core Domain Models**: Add `Command`, `Session`, `Target` entities with CIDR/IP validation, and `RiskLevel` / `PolicyAction` value objects.
* **Policy Engine & Rules**: Add `PolicyRule` entity, domain exceptions, destructive blacklist regex patterns, and zero-trust target authorization.
* **Command Risk Classifier**: Add extensible risk classification dictionary categorizing commands into `LOW`, `MEDIUM`, and `HIGH` severity.
* **Central Policy Validator**: Add `validate_command` combining blacklist verification, scope boundaries, and suggestion vs autonomous mode enforcement.
* **Mandatory AI Policy Gate**: Enforce strict policy evaluation in `ExecuteCommandUseCase` so AI-proposed commands cannot bypass safety rules.
* **WSL2 Shell Executor**: Implement native `WSLShellExecutor` executing under unprivileged `ia-user` with strict process timeouts and output capture.
* **Persistence & Auditing**: Implement `SQLiteSessionRepository` supporting parameterized search, date filtering, and forensic `policy_logs`.
* **FastAPI Server & Dependency Injection**: Bootstrap FastAPI server with strict Pydantic schemas, dependency injection graph, and CORS middleware for local Electron origins.
* **AI Co-Pilot Integration**: Implement `ClaudeAIGateway` with Anthropic Claude 3.5 Sonnet, exponential backoff retries, and structured `propose_command` tool use.
* **API Endpoints**: Add `/health`, `/execute`, `/chat`, `/history`, and `/api/di-check` routes.

#### 🐛 Fixes & Security Hardening (`fix`)
* **Zero-Trust Target Gate**: Resolve session target scope evaluation in `POST /execute` so that out-of-scope executions are blocked immediately with `HTTP 403 Forbidden`.
* **Sudo Privilege Escalation Defense**: Add `block-privilege-escalation` policy rule preventing `ia-user` from abusing `sudo nmap --script` or interactive shell escapes (GTFOBins).
* **Forensic Audit Logging**: Ensure every command decision and reasoning is committed to the SQLite `policy_logs` table.
* **Credential Isolation**: Guarantee zero secrets or API tokens leak into Git trees, terminal outputs, or persistence logs.

#### 🧪 Testing (`test`)
* **Domain & Application Suites**: 100% unit test coverage for entities, value objects, use cases, and ports.
* **Adversarial Security Suite**: Add 24 penetration testing and adversarial evasion tests (`test_policy_engine_security_audit.py`).
* **End-to-End Real WSL2 Suite**: Add full pipeline integration tests executing real diagnostic commands in Kali Linux WSL2.
* **High-Speed Smoke Tests**: Add startup and DI validation suite executing in under 3.5 seconds (`test_smoke.py`).
* **Total backend tests**: **301 passing tests**.

#### 📚 Documentation (`docs`)
* Comprehensive English setup and usage guide with prerequisites (WSL2 + Kali Linux), installation steps, and secure API key configuration.
* Explanation of Suggestion vs Autonomous operational modes and full Policy Indicator color threat matrix.
* High-assurance security audit report (`docs/final_security_review.md`).

---

### 🖥️ Desktop Frontend (`the-guardian-of-kali_frontend`)

#### 🌟 Features (`feat`)
* **Terminal View**: Hardware-accelerated terminal emulator using `@xterm/xterm`, `@xterm/addon-fit`, and `node-pty`.
* **Native WSL2 PTY Spawning**: Spawn real Kali Linux pseudo-terminals in Electron main process under the operator account (`carlos`).
* **Secure Preload Bridge**: Implement Electron IPC communication with `contextIsolation: true` and `nodeIntegration: false`.
* **Backend API Client**: Typed HTTP client communicating with FastAPI endpoints (`/execute`, `/chat`, `/history`, `/health`).
* **Interactive AI Chat Panel**: Full-featured chat interface with conversational guidance, code formatting, and one-click execution of proposed commands.
* **Visual Policy Indicator**: Safety traffic light badge rendering real-time risk levels (`LOW`, `MEDIUM`, `HIGH`, `BLOCKED`) and policy reasons.
* **Session Setup Screen**: Zero-trust session initialization modal for configuring target scopes and toggling Suggestion vs Autonomous modes.
* **Session History Component**: Paginated, filterable audit table displaying past commands, risk ratings, and outcomes.

#### 🐛 Fixes & UX Polish (`fix`)
* **Global Error Handling**: Comprehensive error banners and modals with actionable instructions for WSL2 downtime, Claude rate limits (HTTP 429), backend disconnection, and Pydantic validation errors.
* **Full UX Walkthrough**: Refine terminal layout resizing, message auto-scrolling, and policy indicator transitions.

#### 📚 Documentation (`docs`)
* Complete English README with Electron + React 18 architecture, development workflows (`npm run dev`, `npm run build`, `npm run lint`), and security considerations.
* Quickstart guide and environment configuration template (`.env.example`).

---

## 📋 Tag & Commit Reference
- **Backend Tag**: [`v1.0.0`](https://github.com/simviz12/the-guardian-of-kali_backend/releases/tag/v1.0.0)
- **Frontend Tag**: [`v1.0.0`](https://github.com/simviz12/the-guardian-of-kali_frontend/releases/tag/v1.0.0)
- **Final Release Commit**: `chore: release v1.0.0`
