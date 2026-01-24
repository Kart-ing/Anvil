# Anvil SDK

## Overview

Anvil SDK is a **JIT (Just-In-Time) Infrastructure & Self-Healing SDK for AI Agents** that solves the "Tool Rot" problem. Instead of hardcoding tool implementations that break when APIs change, Anvil generates tool code on the fly using LLMs.

**GitHub:** https://github.com/Kart-ing/Anvil
**PyPI:** https://pypi.org/project/anvil-agent/ (v0.1.1)

---

## Recent Changes (Session Summary)

### 1. Smart Parameterization Guardrails (v0.1.1) - DEPLOYED TO MAIN

**Problem:** Tools were being generated with hardcoded values (e.g., `symbol = "NVDA"` instead of `kwargs.get('symbol')`).

**Solution:** Added parameterization rules to the LLM prompts in `anvil/generators/local.py`:

**File:** `anvil/generators/local.py`
- Lines 30-46: Added PARAMETERIZATION RULES (9-11) to `BUILDER_SYSTEM_PROMPT`
- Lines 69-70: Added rules 5-6 to `FIXER_SYSTEM_PROMPT`
- Line 257: Added reminder to user prompt

**Key Rules Added:**
```
9. NEVER hardcode domain-specific values (stock symbols, city names, IDs, URLs, queries)
10. Extract the GENERAL capability from specific intents
11. Always include validation for required parameters
```

**Status:** ✅ Merged to main, published to PyPI v0.1.1

---

### 2. Daytona Sandbox Integration - HACKATHON BRANCH

**Branch:** `hackathon-enterprise`

**Purpose:** Real integration with Daytona (hackathon sponsor) for secure code execution.

**File:** `anvil/sandbox.py`
- Lines 421-524: New `DaytonaSandbox` class
- Lines 527-566: Updated `SandboxManager` with `prefer_daytona` option
- Lines 583-602: Updated `get_status()` to include Daytona

**DaytonaSandbox Features:**
- Uses official `daytona-sdk` package
- Lazy-loads client on first use
- Auto-cleanup of sandboxes in `finally` block
- Falls back gracefully if API key not set

**Usage:**
```python
from anvil.sandbox import DaytonaSandbox, SandboxManager

# Direct usage
sandbox = DaytonaSandbox(api_key="your-key")
result = sandbox.execute("print('hello')")

# Via manager (with priority)
manager = SandboxManager(prefer_daytona=True)
driver = manager.get_driver()  # Returns Daytona if available
```

**Status:** ✅ On `hackathon-enterprise` branch

---

### 3. Hackathon Demo ("Anvil Enterprise") - HACKATHON BRANCH

**Branch:** `hackathon-enterprise`
**Location:** `hackathon/` directory

**Pitch:** "CI/CD for AI Agents" - When agents break, Anvil catches the crash, fixes it, sandboxes in Daytona, and redeploys.

#### Files Created:

| File | Purpose | Lines |
|------|---------|-------|
| `hackathon/ingest.py` | Scans legacy tools, creates manifest, wraps for management | ~150 |
| `hackathon/pipeline.py` | Repair pipeline: Anvil → Daytona → CodeRabbit | ~250 |
| `hackathon/dashboard.py` | Streamlit monitoring UI with auto-refresh | ~180 |
| `hackathon/my_agent/tools/stock_tool.py` | Intentionally broken tool (fake API) | ~10 |
| `hackathon/my_agent/tools/weather_tool.py` | Intentionally broken tool (wrong endpoint) | ~10 |
| `hackathon/README.md` | Demo instructions | ~100 |

#### Pipeline Flow:
```
[Error Detected] → [ANVIL Fix] → [DAYTONA Sandbox] → [CODERABBIT Audit] → [Deploy]
```

#### How to Run:
```bash
git checkout hackathon-enterprise
pip install -e ".[hackathon]"

export ANTHROPIC_API_KEY="your-key"
export DAYTONA_API_KEY="your-key"

cd hackathon
python ingest.py           # Scan & register tools
streamlit run dashboard.py # Start dashboard (new terminal)
python pipeline.py         # Run repair pipeline
```

**Status:** ✅ On `hackathon-enterprise` branch

---

## Git Branches

| Branch | Purpose | Status |
|--------|---------|--------|
| `main` | Production SDK (v0.1.1 with parameterization) | ✅ Published to PyPI |
| `hackathon-enterprise` | Daytona + Enterprise demo | ✅ Ready for hackathon |

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes (for Claude) | LLM provider for code generation |
| `OPENAI_API_KEY` | Optional | Alternative LLM provider |
| `DAYTONA_API_KEY` | For hackathon | Daytona sandbox execution |
| `FIRECRAWL_API_KEY` | Optional | Documentation scraping |

---

## Core Architecture

### File Structure
```
anvil/
├── __init__.py          # Main Anvil class export
├── core.py              # Anvil class - main entry point (use_tool, run, etc.)
├── models.py            # ToolConfig, GeneratedCode, InputParam dataclasses
├── tool_manager.py      # Tool file management, versioning, headers
├── generators/
│   ├── base.py          # BaseGenerator abstract class
│   ├── local.py         # LocalGenerator - BYO API keys (MAIN GENERATOR)
│   └── stub.py          # StubGenerator - for testing
├── llm/
│   ├── __init__.py      # get_provider() factory
│   ├── base.py          # BaseLLMProvider abstract class
│   ├── anthropic.py     # Claude provider
│   ├── openai.py        # GPT-4 provider
│   └── grok.py          # Grok provider
├── sandbox.py           # SandboxDriver, LocalSandbox, DockerSandbox, DaytonaSandbox
├── adapters/            # Framework adapters (LangChain, CrewAI, AutoGen, OpenAI)
├── chain.py             # Tool chaining (tool1 | tool2)
├── credentials.py       # Interactive credential collection
├── cli.py               # CLI commands (anvil init, doctor, run, etc.)
└── logger.py            # Logging utilities
```

### Key Classes

**`Anvil` (core.py)**
- Main entry point
- `use_tool(name, intent, docs_url)` - Generate or retrieve a tool
- `run(tool_name, **kwargs)` - Execute a tool
- Auto-regenerates on failure (self-healing)

**`LocalGenerator` (generators/local.py)**
- Uses your own LLM API keys
- `BUILDER_SYSTEM_PROMPT` - Instructions for generating tools
- `FIXER_SYSTEM_PROMPT` - Instructions for self-healing
- Supports Claude, GPT-4, Grok

**`SandboxManager` (sandbox.py)**
- Manages multiple sandbox drivers
- Priority: Daytona > Docker > Local
- `verify_code()` - Static analysis + execution

---

## What's Built vs What's Needed

### ✅ Built (Execution Engine)

| Feature | Location |
|---------|----------|
| JIT Code Generation | `anvil/generators/local.py` |
| Self-Healing | `anvil/core.py` |
| Smart Parameterization | `anvil/generators/local.py` (lines 30-46) |
| Credential Resolution | `anvil/credentials.py` |
| Multi-Provider LLM | `anvil/llm/` |
| Framework Adapters | `anvil/adapters/` |
| Sandbox (Local/Docker/Daytona) | `anvil/sandbox.py` |
| Tool Chaining | `anvil/chain.py` |
| CLI | `anvil/cli.py` |

### 🚧 Needed (Control Plane)

| Feature | Priority | Notes |
|---------|----------|-------|
| Health Monitor Dashboard | HIGH | Streamlit prototype in hackathon/ |
| Telemetry Link | HIGH | Send events to cloud |
| Policy-as-Code | CRITICAL | Human-in-the-loop gates |
| Private Registry | MEDIUM | Golden tools versioning |
| SSO/RBAC | MEDIUM | Enterprise auth |

---

## Testing

```bash
# Run all tests
.venv/bin/python -m pytest tests/ -v

# Run specific test file
.venv/bin/python -m pytest tests/test_sandbox.py -v

# Known failures (pre-existing):
# - test_executes_safe_code: Uses 'python' instead of 'python3'
# - test_handles_runtime_errors: Same issue
```

---

## Publishing

```bash
# Build
python -m build

# Upload to PyPI
TWINE_USERNAME=__token__ TWINE_PASSWORD="pypi-xxx" python -m twine upload dist/*
```

**PyPI Token:** User has one (starts with `pypi-AgEIcHlwaS5vcmc...`)

---

## Hackathon Strategy

### Sponsor Integrations
- **Daytona:** Real SDK integration in `anvil/sandbox.py`
- **CodeRabbit:** LLM-simulated security audit in `hackathon/pipeline.py`

### Demo Flow
1. Show broken tools in `my_agent/tools/`
2. Run `ingest.py` → Tools appear in dashboard as 🔴
3. Run `pipeline.py` → Watch repair pipeline:
   - `[ANVIL]` generates fix
   - `[DAYTONA]` verifies in sandbox
   - `[CODERABBIT]` security audit
4. Dashboard updates to 🟢

### Key Selling Points
- Real Daytona integration (not mocked)
- Visual pipeline with colored logs
- Streamlit dashboard for monitoring
- Self-healing with audit trail

---

## Next Steps

### For Hackathon
1. Test full demo flow with real Daytona API key
2. Polish dashboard visuals
3. Prepare 3-minute demo script

### For Production
1. Merge Daytona to main after hackathon
2. Add telemetry endpoints
3. Build real CodeRabbit integration
4. Implement policy-as-code

---

## Pricing Model (Proposed)

| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0 | SDK only, local execution |
| **Team** | $20/agent/month | Dashboard, telemetry, basic policies |
| **Enterprise** | Custom | Private registry, SSO, RBAC, SLA |

---

## Useful Commands

```bash
# Switch branches
git checkout main                    # Production
git checkout hackathon-enterprise    # Hackathon demo

# Install for development
pip install -e ".[dev]"

# Install for hackathon
pip install -e ".[hackathon]"

# Run CLI
anvil --help
anvil doctor
anvil init
anvil run tool_name --arg1 value1

# Run hackathon demo
cd hackathon
python ingest.py
python pipeline.py
streamlit run dashboard.py
```
