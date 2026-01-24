"""Local Generator - BYO API Keys mode.

This generator uses your own LLM API keys (Anthropic, OpenAI, Grok)
to generate tool code locally. This is the open-source mode that
works completely standalone without Anvil Cloud.
"""

import os
import re
from typing import Any

from anvil.generators.base import BaseGenerator, GeneratorMode
from anvil.models import GeneratedCode, ToolConfig

# Prompts for LLM
BUILDER_SYSTEM_PROMPT = """You are ANVIL, a JIT Tool Generator for AI agents.

Your task is to write a Python tool function based on the user's intent and any documentation provided.

CRITICAL RULES:
1. Output ONLY a Python code block - no explanations before or after
2. The code MUST define a `run(**kwargs)` function as the entry point
3. Use type hints for all parameters and return values
4. Include a docstring explaining what the function does and its parameters
5. Handle errors gracefully - return meaningful error messages, don't crash
6. If API keys are needed, read from environment: `os.environ.get("KEY_NAME")`
7. Keep the code minimal and focused on the intent
8. Import all required modules at the top of the file

PARAMETERIZATION RULES (CRITICAL - DO NOT HARDCODE VALUES):
9. NEVER hardcode domain-specific values. Examples of values that MUST be parameters:
   - Stock symbols (NVDA, AAPL, TSLA) -> Use: kwargs.get('symbol')
   - City names (New York, London) -> Use: kwargs.get('city')
   - User IDs, account IDs, entity IDs -> Use: kwargs.get('user_id'), etc.
   - URLs or endpoints (unless they are the API base URL) -> Use: kwargs.get('url')
   - Search queries, keywords -> Use: kwargs.get('query')
   - File paths -> Use: kwargs.get('file_path')
   - Date ranges, timestamps -> Use: kwargs.get('start_date'), kwargs.get('end_date')
   - Numeric thresholds, limits -> Use: kwargs.get('limit'), kwargs.get('threshold')
10. Extract the GENERAL capability from specific intents:
    - "Get NVIDIA stock price" -> Tool that gets ANY stock price with symbol as parameter
    - "Search Notion for Project Anvil" -> Tool that searches Notion with query as parameter
    - "Send email to john@example.com" -> Tool that sends email with recipient as parameter
11. Always include validation for required parameters:
    - Check if required kwargs exist: `if not kwargs.get('param_name'): return {{"error": "param_name is required"}}`
    - Document parameters in the docstring with their types and descriptions

IMPORTANT - API KEY HANDLING:
When the tool requires an API key or secret, follow this EXACT pattern:
```python
api_key = os.environ.get("SERVICE_NAME_API_KEY")
if not api_key:
    return {{"error": "SERVICE_NAME_API_KEY environment variable not set", "missing_credential": "SERVICE_NAME_API_KEY"}}
```
- Always use UPPER_SNAKE_CASE for env var names ending in _API_KEY, _KEY, _TOKEN, or _SECRET
- Always include both "error" and "missing_credential" keys in the error response
- This allows the Anvil runtime to prompt the user for the key interactively

DOCUMENTATION CONTEXT:
{documentation}

OUTPUT FORMAT:
```python
# Your complete, working Python code here
def run(**kwargs):
    ...
```
"""

FIXER_SYSTEM_PROMPT = """You are ANVIL, a self-healing code fixer.

The previous tool code FAILED during execution. Fix it based on the error.

PREVIOUS CODE:
```python
{previous_code}
```

ERROR MESSAGE:
{error_message}

CRITICAL RULES:
1. Output ONLY the fixed Python code block
2. Keep the same `run(**kwargs)` signature
3. Fix the specific error - don't rewrite everything
4. If the error is about missing data/API issues, add proper error handling
5. Check for hardcoded values - if you see hardcoded domain-specific values (stock symbols, city names, IDs, URLs, queries, etc.), convert them to kwargs.get() parameters
6. Ensure required parameters have validation: `if not kwargs.get('param'): return {{"error": "param is required"}}`

OUTPUT FORMAT:
```python
# Your fixed Python code here
def run(**kwargs):
    ...
```
"""

# Default models for each provider
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "claude": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "gpt": "gpt-4o",
    "grok": "grok-2-latest",
    "xai": "grok-2-latest",
}

# Environment variable names for API keys
API_KEY_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gpt": "OPENAI_API_KEY",
    "grok": "XAI_API_KEY",
    "xai": "XAI_API_KEY",
}


def _extract_code(text: str) -> str:
    """Extract Python code from LLM response."""
    # Try to find code block
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try without language specifier
    match = re.search(r"```\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Return raw text if no code block found
    return text.strip()


class LocalGenerator(BaseGenerator):
    """Local generator using your own LLM API keys.

    This is the "BYO Keys" mode - you provide your own API keys
    for Anthropic, OpenAI, or Grok, and generation happens locally.

    Supports multiple LLM providers:
    - Anthropic (Claude): provider="anthropic" or "claude"
    - OpenAI (GPT): provider="openai" or "gpt"
    - xAI (Grok): provider="grok" or "xai"

    Example:
        ```python
        # Use with your own Anthropic key
        generator = LocalGenerator(
            api_key="sk-ant-...",
            provider="anthropic"
        )

        # Or read from environment
        generator = LocalGenerator(provider="openai")  # Uses OPENAI_API_KEY
        ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        firecrawl_key: str | None = None,
        model: str | None = None,
        provider: str = "anthropic",
    ):
        """Initialize the local generator.

        Args:
            api_key: LLM API key (or read from env based on provider)
            firecrawl_key: FireCrawl API key (or read from FIRECRAWL_API_KEY env)
            model: Model to use (defaults based on provider)
            provider: LLM provider ('anthropic', 'openai', 'grok')
        """
        self.provider_name = provider.lower()
        self.firecrawl_key = firecrawl_key or os.environ.get("FIRECRAWL_API_KEY")

        # Get API key from env if not provided
        env_var = API_KEY_ENV_VARS.get(self.provider_name, "ANTHROPIC_API_KEY")
        self.api_key = api_key or os.environ.get(env_var)

        # Get default model for provider if not specified
        self.model = model or DEFAULT_MODELS.get(self.provider_name, "claude-sonnet-4-20250514")

        self._provider: Any = None
        self._firecrawl: Any = None

    @property
    def mode(self) -> GeneratorMode:
        """Return the generator mode."""
        return GeneratorMode.LOCAL

    def _get_provider(self) -> Any:
        """Lazy-load LLM provider."""
        if self._provider is None:
            if not self.api_key:
                env_var = API_KEY_ENV_VARS.get(self.provider_name, "API_KEY")
                raise ValueError(
                    f"{self.provider_name.title()} API key required. "
                    f"Set {env_var} env or pass api_key."
                )
            from anvil.llm import get_provider

            self._provider = get_provider(
                self.provider_name,
                self.api_key,
                self.model,
            )
        return self._provider

    def _get_firecrawl(self) -> Any:
        """Lazy-load FireCrawl client."""
        if self._firecrawl is None:
            if not self.firecrawl_key:
                return None  # FireCrawl is optional
            from firecrawl import FirecrawlApp

            self._firecrawl = FirecrawlApp(api_key=self.firecrawl_key)
        return self._firecrawl

    def fetch_documentation(self, docs_url: str | None) -> str:
        """Fetch documentation from URL using FireCrawl.

        Args:
            docs_url: URL to scrape for documentation

        Returns:
            Extracted documentation text, or empty string if unavailable
        """
        if not docs_url:
            return "No documentation URL provided."

        firecrawl = self._get_firecrawl()
        if firecrawl is None:
            return f"Documentation URL: {docs_url} (FireCrawl not configured)"

        try:
            # Scrape the documentation page
            result = firecrawl.scrape_url(docs_url, params={"formats": ["markdown"]})

            # Extract markdown content
            if hasattr(result, "markdown"):
                content = result.markdown
            elif isinstance(result, dict) and "markdown" in result:
                content = result["markdown"]
            else:
                content = str(result)

            # Truncate if too long (keep first 8000 chars for context window)
            if len(content) > 8000:
                content = content[:8000] + "\n\n[... truncated ...]"

            return content

        except Exception as e:
            return f"Failed to fetch docs from {docs_url}: {e}"

    def generate(self, config: ToolConfig) -> GeneratedCode:
        """Generate tool code based on intent and docs.

        Args:
            config: Tool configuration with name, intent, docs_url

        Returns:
            GeneratedCode with the Python code and dependencies
        """
        # Fetch documentation
        docs = self.fetch_documentation(config.docs_url)

        # Build the prompt
        system_prompt = BUILDER_SYSTEM_PROMPT.format(documentation=docs)
        user_prompt = f"""Generate a Python tool for the following:

TOOL NAME: {config.name}
INTENT: {config.intent}

Remember: Output ONLY the Python code block with a `run(**kwargs)` function.
IMPORTANT: Generate a REUSABLE, PARAMETERIZED tool - do not hardcode any domain-specific values from the intent."""

        # Call LLM provider
        provider = self._get_provider()
        response = provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4000,
        )

        # Extract code from response
        code = _extract_code(response.text)

        # Detect dependencies (simple heuristic)
        dependencies = self._detect_dependencies(code)

        return GeneratedCode(code=code, dependencies=dependencies)

    def generate_fix(
        self,
        config: ToolConfig,
        previous_code: str,
        error_message: str,
    ) -> GeneratedCode:
        """Generate fixed code after a failure.

        Args:
            config: Tool configuration
            previous_code: The code that failed
            error_message: The error that occurred

        Returns:
            GeneratedCode with the fixed Python code
        """
        system_prompt = FIXER_SYSTEM_PROMPT.format(
            previous_code=previous_code,
            error_message=error_message,
        )

        user_prompt = f"""Fix this tool:

TOOL NAME: {config.name}
INTENT: {config.intent}

The code failed with the error shown above. Fix it."""

        provider = self._get_provider()
        response = provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4000,
        )

        code = _extract_code(response.text)
        dependencies = self._detect_dependencies(code)

        return GeneratedCode(code=code, dependencies=dependencies)

    def _detect_dependencies(self, code: str) -> list[str]:
        """Detect external dependencies from import statements.

        Args:
            code: Python code to analyze

        Returns:
            List of package names that may need to be installed
        """
        dependencies = []

        # Common external packages to detect
        external_packages = {
            "requests": "requests",
            "httpx": "httpx",
            "aiohttp": "aiohttp",
            "beautifulsoup4": "bs4",
            "pandas": "pandas",
            "numpy": "numpy",
            "anthropic": "anthropic",
            "openai": "openai",
            "firecrawl": "firecrawl-py",
        }

        for package, import_name in external_packages.items():
            if f"import {import_name}" in code or f"from {import_name}" in code:
                dependencies.append(package)

        return dependencies
