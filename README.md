# Anvil SDK

**JIT Infrastructure & Self-Healing SDK for AI Agents**

[![PyPI version](https://badge.fury.io/py/anvil-agent.svg)](https://pypi.org/project/anvil-agent/)
[![Documentation](https://img.shields.io/badge/docs-anvil--sdk-blue)](https://anvil-docs-theta.vercel.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**[Documentation](https://anvil-docs-theta.vercel.app/)** | **[PyPI](https://pypi.org/project/anvil-agent/)** | **[GitHub](https://github.com/Kart-ing/anvil-sdk)**

Anvil prevents "Tool Rot" in AI agents. Instead of hard-coding tool implementations that break when APIs change, define **intents** and Anvil generates the code on the fly.

## Features

- **JIT Code Generation** - Generate tool code at runtime using LLMs
- **Smart Parameterization** - Automatically generates reusable, parameterized tools (no hardcoded values)
- **Self-Healing** - Automatic regeneration when tools fail
- **Multi-Provider** - Works with Claude, GPT, Grok (BYO API keys)
- **Glass-Box** - All generated code is visible and editable
- **Framework Adapters** - Works with LangChain, CrewAI, AutoGen, OpenAI Agents SDK
- **Beautiful CLI** - Professional terminal experience with Rich

## Quick Start

### 1. Install

```bash
pip install anvil-agent
```

With Claude support (recommended):
```bash
pip install "anvil-agent[anthropic]"
```

### 2. Initialize Your Project

```bash
anvil init
```

This interactive wizard will:
- Create the `anvil_tools/` directory for generated tools
- Set up `.gitignore` to protect your API keys
- Securely prompt for your API keys and save them to `.env`
- Create an example script to get you started

### 3. Start Building

```python
from dotenv import load_dotenv
from anvil import Anvil

load_dotenv()

# Initialize Anvil
anvil = Anvil(tools_dir="./anvil_tools")

# Define what you want, not how
search_tool = anvil.use_tool(
    name="search_notion",
    intent="Search the user's Notion workspace using the official API",
    docs_url="https://developers.notion.com/reference/post-search"
)

# Execute
result = search_tool.run(query="Project Anvil")

# Code is saved to ./anvil_tools/search_notion.py
print(anvil.get_tool_code("search_notion"))
```

## CLI Commands

```bash
anvil init      # Initialize a new project with interactive setup
anvil doctor    # Check system requirements and API keys
anvil list      # List all generated tools
anvil clean     # Clear tool cache to force regeneration
anvil verify    # Verify tool code in sandbox
```

## Installation Options

```bash
# Basic installation
pip install anvil-agent

# With LLM provider
pip install "anvil-agent[anthropic]"  # Claude (recommended)
pip install "anvil-agent[openai]"     # GPT-4

# With framework adapter
pip install "anvil-agent[langchain]"
pip install "anvil-agent[crewai]"
pip install "anvil-agent[autogen]"
pip install "anvil-agent[openai-agents]"

# Everything
pip install "anvil-agent[all]"
```

## Multi-Provider Support

```python
# Use Claude (default)
anvil = Anvil(provider="anthropic")

# Use OpenAI GPT-4
anvil = Anvil(provider="openai", model="gpt-4o")

# Use Grok
anvil = Anvil(provider="grok", model="grok-2")
```

## Framework Integration

```python
# LangChain
lc_tool = search_tool.to_langchain()

# CrewAI
crew_tool = search_tool.to_crewai()

# AutoGen
autogen_tool = search_tool.to_autogen()

# OpenAI Agents SDK
oai_tool = search_tool.to_openai_agents()
```

## Testing Without API Keys

```python
anvil = Anvil(use_stub=True)  # Returns mock implementations
```

## Anvil Cloud (Coming Soon)

For instant cached tools without LLM latency:

```bash
pip install anvil-cloud
```

```python
anvil = Anvil(mode="cloud")  # Instant retrieval from global cache
```

## Development

```bash
# Clone the repository
git clone https://github.com/Kart-ing/anvil-sdk.git
cd anvil-sdk

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Run examples
python examples/basic_usage.py --stub
```

## Documentation

Full documentation is available at **[anvil-sdk-docs.vercel.app](https://anvil-sdk-docs.vercel.app)**

- [Getting Started](https://anvil-sdk-docs.vercel.app/getting-started/introduction/)
- [How It Works](https://anvil-sdk-docs.vercel.app/concepts/how-it-works/)
- [Self-Healing](https://anvil-sdk-docs.vercel.app/concepts/self-healing/)
- [LangChain Integration](https://anvil-sdk-docs.vercel.app/adapters/langchain/)
- [CrewAI Integration](https://anvil-sdk-docs.vercel.app/adapters/crewai/)
- [AutoGen Integration](https://anvil-sdk-docs.vercel.app/adapters/autogen/)
- [OpenAI Agents SDK](https://anvil-sdk-docs.vercel.app/adapters/openai-agents/)
- [API Reference](https://anvil-sdk-docs.vercel.app/reference/anvil/)

## Building & Publishing

```bash
# Build the package
python -m build

# Upload to TestPyPI first
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

## License

MIT License - See [LICENSE](LICENSE) for details.
