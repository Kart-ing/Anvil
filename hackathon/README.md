# Anvil Enterprise - Hackathon Demo

**"CI/CD for AI Agents"** - When agents break, Anvil catches the crash, fixes it, sandboxes in Daytona, and redeploys.

## Quick Start

```bash
# 1. Install dependencies
pip install -e ".[hackathon]"

# 2. Set API keys
export ANTHROPIC_API_KEY="your-key"
export DAYTONA_API_KEY="your-key"  # Optional but recommended

# 3. Run the demo
cd hackathon
python ingest.py           # Scan & register tools
streamlit run dashboard.py # Start dashboard (new terminal)
python pipeline.py         # Run repair pipeline
```

## What This Demo Shows

### The Problem
Your AI agent has tools that break:
- `stock_tool.py` - Uses a fake API that doesn't exist
- `weather_tool.py` - Wrong endpoint, missing API key

### The Solution: Anvil Enterprise Pipeline

```
[Error Detected] → [Anvil Fix] → [Daytona Sandbox] → [CodeRabbit Audit] → [Deploy]
```

1. **Error Detection**: Tool fails during execution
2. **Anvil Self-Healing**: LLM generates a fixed version
3. **Daytona Sandbox**: Code verified in isolated environment
4. **CodeRabbit Audit**: Security review of the changes
5. **Deploy**: Fixed tool is deployed

## Files

| File | Purpose |
|------|---------|
| `ingest.py` | Scan legacy tools, create manifest |
| `pipeline.py` | The repair pipeline (Anvil → Daytona → CodeRabbit) |
| `dashboard.py` | Streamlit monitoring UI |
| `my_agent/tools/` | Sample broken tools |
| `anvil_managed/` | Where fixed tools live |

## Dashboard Features

- Real-time tool health status (🟢 🟡 🔴)
- Pipeline visualization
- Repair history log
- Auto-refresh mode

## Sponsor Integrations

- **Daytona**: Secure sandbox for code verification
- **CodeRabbit**: AI-powered security audit (simulated via LLM)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Anvil Enterprise                          │
│                                                              │
│  ┌──────────┐    ┌───────────┐    ┌──────────────────────┐  │
│  │ Legacy   │───▶│ Ingest    │───▶│ Anvil Managed Tools  │  │
│  │ Agent    │    │ Scanner   │    │ (Monitored)          │  │
│  └──────────┘    └───────────┘    └──────────────────────┘  │
│                                            │                 │
│                                   [Tool Fails]              │
│                                            ▼                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              REPAIR PIPELINE                          │   │
│  │                                                       │   │
│  │  [Anvil SDK] → [Daytona Sandbox] → [CodeRabbit]      │   │
│  │    Generate      Verify in          Security          │   │
│  │    Fix           Isolation          Audit             │   │
│  └──────────────────────────────────────────────────────┘   │
│                                            │                 │
│                                            ▼                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              DASHBOARD (Streamlit)                    │   │
│  │  • Tool Health Monitor                                │   │
│  │  • Pipeline Visualization                             │   │
│  │  • Repair Logs                                        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```
