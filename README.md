# Anvil SDK

**JIT Infrastructure & Self-Healing SDK for AI Agents**

Anvil prevents "Tool Rot" in AI agents. Instead of hard-coding tool implementations that break when APIs change, define **intents** and Anvil generates the code on the fly.

## Features

- **JIT Code Generation** - Generate tool code at runtime using LLMs
- **Self-Healing** - Automatic regeneration when tools fail
- **Multi-Provider** - Works with Claude, GPT, Grok (BYO API keys)
- **Glass-Box** - All generated code is visible and editable
- **Framework Adapters** - Works with LangChain, CrewAI, AutoGen, OpenAI Agents SDK

## Installation

```bash
# Basic installation
pip install anvil-sdk

# With LLM provider
pip install "anvil-sdk[anthropic]"  # or [openai]

# With framework adapter
pip install "anvil-sdk[langchain]"  # or [crewai], [autogen], [openai-agents]

# Everything
pip install "anvil-sdk[all]"
```

## Quick Start

```python
from anvil import Anvil

# Initialize (reads API key from ANTHROPIC_API_KEY env)
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
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Run examples
python examples/basic_usage.py --stub
```

## License

MIT License - See [LICENSE](LICENSE) for details.