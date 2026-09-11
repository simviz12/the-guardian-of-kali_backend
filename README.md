# The Guardian of Kali — Backend & Policy Engine (`the-guardian-of-kali_backend`)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org)
[![Kali Linux](https://img.shields.io/badge/Kali_Linux-WSL2-557C94.svg?logo=kalilinux&logoColor=white)](https://www.kali.org)
[![Anthropic Claude](https://img.shields.io/badge/Claude_API-3.5_Sonnet-D97706.svg?logo=anthropic&logoColor=white)](https://www.anthropic.com)
[![Tests](https://img.shields.io/badge/Pytest-301_Passed-brightgreen.svg?logo=pytest&logoColor=white)](https://pytest.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Backend service, terminal execution orchestrator, and zero-trust security policy engine for **The Guardian of Kali** — an AI-assisted desktop cybersecurity environment purpose-built for ethical hacking, penetration testing, and CTF training (HackTheBox, TryHackMe, local labs) running natively on **Kali Linux inside WSL2**.

---

## 📋 Table of Contents

- [Architectural Overview](#architectural-overview)
- [Prerequisites (WSL2 + Kali Linux)](#prerequisites-wsl2--kali-linux)
- [Installation Steps](#installation-steps)
- [Secure API Key Configuration](#secure-api-key-configuration)
- [Quickstart Guide](#quickstart-guide)
  - [Operating Modes: Suggestion vs Autonomous](#operating-modes-suggestion-vs-autonomous)
  - [Policy Indicator Colors & Threat Matrix](#policy-indicator-colors--threat-matrix)
- [API Endpoints Reference](#api-endpoints-reference)
- [Running Automated Tests](#running-automated-tests)
- [License](#license)

---

## 🏛️ Architectural Overview

The backend strictly adheres to **Clean Architecture** principles across four concentric layers with internal dependency flow:

```
src/
├── domain/                    # Enterprise business logic (zero external dependencies)
│   ├── entities/              # Command, Session, Target, PolicyRule
│   ├── value_objects/         # RiskLevel, PolicyAction, CommandOrigin, PolicyDecision
│   ├── policies/              # Policy rules, Blacklist regex patterns, Validator, Risk Classifier
│   └── exceptions.py          # Domain exceptions (CommandBlockedException, TargetNotAuthorizedException)
├── application/               # Use cases and orchestration
│   ├── use_cases/             # ExecuteCommandUseCase, EvaluatePolicyUseCase, ChatWithAIUseCase, GetSessionHistoryUseCase
│   ├── ports/                 # Abstract interfaces (ShellExecutor, AIGateway, SessionRepository)
│   └── dtos/                  # Data Transfer Objects (CommandResult, AIResponse, ChatResult)
├── adapters/                  # Concrete infrastructure implementations
│   ├── terminal/              # WSLShellExecutor (wsl.exe -d kali-linux -u ia-user)
│   ├── storage/               # SQLiteSessionRepository (the_guardian_of_kali.db with policy_logs)
│   └── ai/                    # ClaudeAIGateway (Anthropic Python SDK with exponential backoff)
└── infrastructure/            # Delivery mechanisms and entrypoints
    ├── api/                   # FastAPI request/response Pydantic schemas (extra="forbid")
    └── config/                # System prompts and system settings
```

Every command suggested by AI must pass through `EvaluatePolicyUseCase` before reaching the terminal executor. No endpoint exposes raw terminal execution without validation.

---

## ⚙️ Prerequisites (WSL2 + Kali Linux)

Before running the backend, set up your Windows host with WSL2 and the Kali Linux distribution:

1. **Enable WSL2 on Windows 10/11**:
   Open PowerShell as Administrator and run:
   ```powershell
   wsl --install
   ```
2. **Install Kali Linux from Microsoft Store or CLI**:
   ```powershell
   wsl --install -d kali-linux
   ```
3. **Provision the Dedicated Restricted AI User (`ia-user`)**:
   Inside your Kali Linux WSL2 instance (`wsl -d kali-linux`), create the non-root user and configure the strict sudoers whitelist:
   ```bash
   sudo useradd -m -s /bin/bash ia-user
   sudo usermod -aG sudo ia-user

   # Configure strict sudoers whitelist (only ping, nmap, and traceroute permitted without password)
   echo "ia-user ALL=(ALL) NOPASSWD: /usr/bin/ping, /usr/bin/nmap, /usr/sbin/traceroute" | sudo tee /etc/sudoers.d/ia-user
   sudo chmod 0440 /etc/sudoers.d/ia-user
   ```
4. **Python Environment**:
   Python **3.11** or **3.12** installed on Windows.

---

## 📦 Installation Steps

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/simviz12/the-guardian-of-kali_backend.git
   cd the-guardian-of-kali_backend
   ```

2. **Create and Activate a Virtual Environment**:
   ```powershell
   # Windows PowerShell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   *(On Linux/macOS: `source .venv/bin/activate`)*

3. **Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 🔑 Secure API Key Configuration

> [!IMPORTANT]
> **Zero Credential Leaking Policy**: API keys must **NEVER** be hardcoded in code, committed to Git repositories, or logged in terminal outputs.

The backend loads your Anthropic API key dynamically from system environment variables at runtime via `os.environ.get("ANTHROPIC_API_KEY")`.

1. **Copy the Environment Template**:
   ```powershell
   copy .env.example .env
   ```

2. **Set Your Environment Variable**:
   - **Option A: Temporary PowerShell Session**:
     ```powershell
     $env:ANTHROPIC_API_KEY = "sk-ant-api03-your-secret-key-here"
     ```
   - **Option B: Persistent Windows User Environment Variable**:
     ```powershell
     [System.Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', 'sk-ant-api03-your-secret-key-here', 'User')
     ```
   - **Option C: `.env` File** (automatically ignored by `.gitignore`):
     ```env
     ANTHROPIC_API_KEY=sk-ant-api03-your-secret-key-here
     HOST=127.0.0.1
     PORT=8765
     WSL_DISTRO=kali-linux
     WSL_USER=ia-user
     WSL_TIMEOUT_SECONDS=30.0
     DATABASE_PATH=the_guardian_of_kali.db
     ```

---

## 🚀 Quickstart Guide

### Starting the Backend Server
With your virtual environment activated:
```bash
python -m src.main
```
The server will start listening on `http://127.0.0.1:8765`. Verify health status at `http://127.0.0.1:8765/health`.

### Operating Modes: Suggestion vs Autonomous

The Guardian of Kali provides two operational modes chosen during session setup:

| Mode | Autonomous Execution | Required Operator Action | Use Case |
| :--- | :--- | :--- | :--- |
| **Suggestion Mode** (`is_autonomous=False`) | Only **LOW** risk commands (e.g. `whois`, `dig`, `ping`) auto-execute. | **MEDIUM** and **HIGH** risk commands require explicit operator review and confirmation via UI button. | Recommended for beginners, CTF learning, and production penetration testing where step-by-step human oversight is required. |
| **Autonomous Mode** (`is_autonomous=True`) | **LOW** and **MEDIUM** risk commands (e.g. `nmap -sV`, `gobuster`, `nikto`) auto-execute seamlessly. | **HIGH** risk commands (e.g. `sqlmap`, `hydra`, `msfconsole`) **strictly always** pause and require operator confirmation. | Recommended for experienced security researchers running automated reconnaissance pipelines. |

> [!CAUTION]
> **Destructive Commands Are Always Blocked**: Regardless of the mode selected, destructive blacklist commands (`rm -rf /`, `mkfs`, `fdisk`, `dd of=/dev/*`, `shutdown`, `reboot`, `iptables -F`, `sudo nmap --script`) are **immediately rejected** with `HTTP 403 Forbidden`.

### Policy Indicator Colors & Threat Matrix

The frontend terminal status bar renders real-time policy indicators reflecting the policy evaluation:

| Color | Badge Label | Risk Level | Description & Examples | Policy Action |
| :---: | :--- | :---: | :--- | :--- |
| 🟢 **Green** | `LOW` | Low Risk | Non-intrusive passive reconnaissance and diagnostics (`whois`, `dig`, `nslookup`, `ping`, `traceroute`, `uname -s`, `id`). | **Auto-execute** in both Suggestion & Autonomous modes. |
| 🟡 **Yellow** | `MEDIUM` | Medium Risk | Active scanning, port inspection, service enumeration, and web directory fuzzing (`nmap -sV`, `gobuster`, `dirsearch`, `nikto`, `whatweb`, `sslscan`). | **Requires Confirmation** in Suggestion mode; **Auto-executes** in Autonomous mode. |
| 🔴 **Red** | `HIGH` | High Risk | Active exploitation, password brute-forcing, injection attacks, credential gathering (`sqlmap`, `hydra`, `medusa`, `john`, `hashcat`, `msfconsole`, `responder`). | **Strictly Requires Confirmation** in all modes. |
| 🚫 **Black / Dark Red** | `BLOCKED` | Destructive | Mass filesystem deletion (`rm -rf /`), partition wiping (`fdisk`, `dd of=/dev/sd*`), filesystem formatting (`mkfs`), firewall flushing (`iptables -F`), power shutdown, or sudo privilege escalation breakout attempts (`sudo nmap --script`). | **BLOCKED IMMEDIATELY** (returns HTTP 403 Forbidden, never touches shell). |

---

## 📡 API Endpoints Reference

| Method | Endpoint | Description | Guarded by Policy Gate? |
| :--- | :--- | :--- | :---: |
| `GET` | `/health` | Service health and version status (`0.1.0`). | No |
| `POST` | `/execute` | Executes a terminal command in Kali Linux WSL2 under `ia-user` with zero-trust scope and blacklist validation. | **YES (Mandatory for AI origin)** |
| `POST` | `/chat` | Conversational endpoint with Claude 3.5 Sonnet proposing structured tools and commands. | No (chat does not execute) |
| `GET` | `/history` | Audited session history queryable by `session_id`, `user`, `risk_level`, or date range. | No (read-only audit log) |
| `GET` | `/api/di-check` | Diagnostic route verifying dependency injection wiring. | No |

---

## 🧪 Running Automated Tests

The backend includes a comprehensive test suite of **301 tests** with 100% pass rate:

```bash
# Run all tests
pytest

# Run fast smoke test suite (< 4 seconds)
pytest tests/smoke/test_smoke.py -v

# Run adversarial security audit suite
pytest tests/unit/domain/test_policy_engine_security_audit.py -v

# Run end-to-end integration tests against real Kali Linux WSL2
pytest tests/integration/test_full_e2e_flow.py -v
```

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
