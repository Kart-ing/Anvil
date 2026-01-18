"""Main Anvil class - entry point for the SDK."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from anvil.credentials import CredentialResolver, get_default_resolver
from anvil.generators import (
    BaseGenerator,
    GeneratorMode,
    LocalGenerator,
    StubGenerator,
)
from anvil.jit_generator import JITGenerator, StubJITGenerator  # Backward compat
from anvil.loader import ToolLoader
from anvil.logger import AnvilEvent, AnvilLogger, EventType
from anvil.models import InputParam, ToolConfig, ToolResult
from anvil.sandbox import SandboxManager, SecurityPolicy
from anvil.tool_manager import ToolManager

if TYPE_CHECKING:
    from anvil.chain import ToolChain


class Tool:
    """A loaded tool that can be executed.

    This is the object returned by Anvil.use_tool(). It wraps
    the underlying tool module and provides a clean interface.
    """

    def __init__(
        self,
        name: str,
        config: ToolConfig,
        loader: ToolLoader,
        anvil: "Anvil",
    ):
        self.name = name
        self.config = config
        self._loader = loader
        self._anvil = anvil

    def _check_missing_credential(self, result: ToolResult) -> str | None:
        """Check if the result indicates a missing credential.

        Args:
            result: The ToolResult from execution

        Returns:
            The missing credential name, or None
        """
        if result.success and isinstance(result.data, dict):
            # Check for the standardized missing_credential key
            if "missing_credential" in result.data:
                return result.data["missing_credential"]
            # Also check error messages for credential patterns
            if "error" in result.data:
                resolver = self._anvil._credential_resolver
                return resolver.detect_missing_credential(result.data)
        return None

    def run(self, **kwargs: Any) -> Any:
        """Execute the tool with the given arguments.

        Args:
            **kwargs: Arguments to pass to the tool's run() function

        Returns:
            The result from the tool execution

        Raises:
            RuntimeError: If the tool fails and self-healing is disabled/exhausted
        """
        start_time = time.perf_counter()
        result = self._loader.execute(self.name, **kwargs)
        duration_ms = (time.perf_counter() - start_time) * 1000

        if result.success:
            # Check if successful execution still returned a missing credential error
            # (tools often return {"error": "..."} as a successful dict result)
            missing_cred = self._check_missing_credential(result)
            if missing_cred and self._anvil.interactive_credentials:
                resolved_result = self._anvil._resolve_credential_and_retry(
                    missing_cred, self.name, kwargs
                )
                if resolved_result is not None:
                    # Credential was resolved and tool was retried
                    self._anvil._log_event(
                        EventType.TOOL_EXECUTED,
                        self.name,
                        duration_ms=(time.perf_counter() - start_time) * 1000,
                        metadata={
                            "args_keys": list(kwargs.keys()),
                            "credential_resolved": missing_cred,
                        },
                    )
                    return resolved_result

            self._anvil._log_event(
                EventType.TOOL_EXECUTED,
                self.name,
                duration_ms=duration_ms,
                metadata={"args_keys": list(kwargs.keys())},
            )
            return result.data

        # Log failure
        self._anvil._log_event(
            EventType.TOOL_FAILED,
            self.name,
            duration_ms=duration_ms,
            error=result.error,
            metadata={"args_keys": list(kwargs.keys())},
        )

        # Tool failed - attempt self-healing if enabled
        if self._anvil.self_healing:
            healed_result = self._anvil._attempt_heal(
                self.name, self.config, kwargs, result.error
            )
            if healed_result.success:
                return healed_result.data
            raise RuntimeError(f"Tool failed after healing attempt: {healed_result.error}")

        raise RuntimeError(f"Tool execution failed: {result.error}")

    def run_safe(self, **kwargs: Any) -> ToolResult:
        """Execute the tool and return a ToolResult (no exceptions).

        Args:
            **kwargs: Arguments to pass to the tool's run() function

        Returns:
            ToolResult with success status and data/error
        """
        start_time = time.perf_counter()
        result = self._loader.execute(self.name, **kwargs)
        duration_ms = (time.perf_counter() - start_time) * 1000

        if result.success:
            self._anvil._log_event(
                EventType.TOOL_EXECUTED,
                self.name,
                duration_ms=duration_ms,
                metadata={"args_keys": list(kwargs.keys())},
            )
        else:
            self._anvil._log_event(
                EventType.TOOL_FAILED,
                self.name,
                duration_ms=duration_ms,
                error=result.error,
                metadata={"args_keys": list(kwargs.keys())},
            )

        if not result.success and self._anvil.self_healing:
            return self._anvil._attempt_heal(
                self.name, self.config, kwargs, result.error
            )

        return result

    def run_interactive(self) -> Any:
        """Prompt user for inputs via CLI, then execute.

        Collects required inputs from the user through the terminal,
        then executes the tool with the collected arguments.

        Returns:
            The result from the tool execution

        Raises:
            RuntimeError: If tool execution fails
            ValueError: If input casting fails
        """
        kwargs = self._collect_inputs()
        return self.run(**kwargs)

    def _collect_inputs(self) -> dict[str, Any]:
        """Prompt user for each input parameter.

        Returns:
            Dictionary of collected input values
        """
        kwargs: dict[str, Any] = {}

        if not self.config.inputs:
            return kwargs

        print(f"\n--- Input required for '{self.name}' ---")

        for param in self.config.inputs:
            if param.required:
                # Required parameter - must provide value
                prompt = f"{param.name}"
                if param.description:
                    prompt += f" ({param.description})"
                prompt += ": "

                raw = input(prompt)
                kwargs[param.name] = self._cast(raw, param.param_type)
            elif param.default is not None:
                # Optional with default - show default, allow override
                prompt = f"{param.name}"
                if param.description:
                    prompt += f" ({param.description})"
                prompt += f" [{param.default}]: "

                raw = input(prompt)
                if raw.strip():
                    kwargs[param.name] = self._cast(raw, param.param_type)
                else:
                    kwargs[param.name] = param.default
            else:
                # Optional without default - skip if empty
                prompt = f"{param.name} (optional"
                if param.description:
                    prompt += f", {param.description}"
                prompt += "): "

                raw = input(prompt)
                if raw.strip():
                    kwargs[param.name] = self._cast(raw, param.param_type)

        return kwargs

    def _cast(self, value: str, param_type: str) -> Any:
        """Convert string input to the correct type.

        Args:
            value: String value from user input
            param_type: Target type ("str", "int", "float", "bool", "list")

        Returns:
            Converted value

        Raises:
            ValueError: If conversion fails
        """
        value = value.strip()

        if param_type == "int":
            return int(value)
        elif param_type == "float":
            return float(value)
        elif param_type == "bool":
            return value.lower() in ("true", "yes", "1", "y")
        elif param_type == "list":
            # Simple comma-separated list
            return [item.strip() for item in value.split(",") if item.strip()]
        else:
            # Default to string
            return value

    def get_inputs(self) -> list[InputParam]:
        """Get the list of input parameters for this tool.

        Returns:
            List of InputParam objects
        """
        return self.config.inputs

    def has_required_inputs(self) -> bool:
        """Check if the tool has any required inputs.

        Returns:
            True if there are required inputs without defaults
        """
        return any(p.required for p in self.config.inputs)

    def pipe(self, other: "Tool") -> "ToolChain":
        """Chain this tool with another tool.

        Creates a ToolChain where this tool's output becomes
        the input to the next tool.

        Args:
            other: The tool to pipe output to

        Returns:
            A ToolChain containing both tools
        """
        from anvil.chain import ToolChain

        return ToolChain([self, other])

    async def run_async(self, **kwargs: Any) -> Any:
        """Execute the tool asynchronously.

        Runs the tool in a thread pool executor to avoid blocking
        the event loop.

        Args:
            **kwargs: Arguments to pass to the tool's run() function

        Returns:
            The result from the tool execution

        Raises:
            RuntimeError: If the tool fails and self-healing is disabled/exhausted
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.run(**kwargs))

    async def run_safe_async(self, **kwargs: Any) -> ToolResult:
        """Execute the tool asynchronously and return a ToolResult (no exceptions).

        Args:
            **kwargs: Arguments to pass to the tool's run() function

        Returns:
            ToolResult with success status and data/error
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.run_safe(**kwargs))

    # Framework Adapters

    def to_langchain(self) -> Any:
        """Convert this tool to a LangChain BaseTool.

        Creates a LangChain-compatible tool that can be used with
        LangChain agents and chains.

        Returns:
            LangChain BaseTool instance

        Raises:
            ImportError: If langchain-core is not installed

        Example:
            ```python
            anvil = Anvil()
            search = anvil.use_tool(name="search", intent="Search the web")

            # Use with LangChain
            lc_tool = search.to_langchain()
            agent = create_react_agent(llm, [lc_tool])
            ```
        """
        from anvil.adapters.langchain import to_langchain_tool

        return to_langchain_tool(self)

    def to_crewai(self) -> Any:
        """Convert this tool to a CrewAI Tool.

        Creates a CrewAI-compatible tool that can be used with
        CrewAI agents and crews.

        Returns:
            CrewAI BaseTool instance

        Raises:
            ImportError: If crewai is not installed

        Example:
            ```python
            anvil = Anvil()
            search = anvil.use_tool(name="search", intent="Search the web")

            # Use with CrewAI
            crew_tool = search.to_crewai()
            agent = Agent(role="Researcher", tools=[crew_tool])
            ```
        """
        from anvil.adapters.crewai import to_crewai_tool

        return to_crewai_tool(self)

    def to_autogen(self) -> Any:
        """Convert this tool to an AutoGen FunctionTool.

        Creates an AutoGen-compatible tool that can be used with
        AutoGen agents.

        Returns:
            AutoGen FunctionTool instance

        Raises:
            ImportError: If autogen-core is not installed

        Example:
            ```python
            anvil = Anvil()
            search = anvil.use_tool(name="search", intent="Search the web")

            # Use with AutoGen
            autogen_tool = search.to_autogen()
            agent = AssistantAgent(name="assistant", tools=[autogen_tool])
            ```
        """
        from anvil.adapters.autogen import to_autogen_tool

        return to_autogen_tool(self)

    def to_openai_agents(self) -> Any:
        """Convert this tool to an OpenAI Agents SDK function tool.

        Creates an OpenAI Agents SDK-compatible tool that can be used
        with OpenAI Agents.

        Returns:
            OpenAI Agents SDK FunctionTool instance

        Raises:
            ImportError: If openai-agents is not installed

        Example:
            ```python
            anvil = Anvil()
            search = anvil.use_tool(name="search", intent="Search the web")

            # Use with OpenAI Agents
            oai_tool = search.to_openai_agents()
            agent = Agent(name="assistant", tools=[oai_tool])
            ```
        """
        from anvil.adapters.openai_agents import to_openai_agents_tool

        return to_openai_agents_tool(self)


class Anvil:
    """Main Anvil SDK class.

    The entry point for the JIT tool infrastructure. Manages tool
    generation, persistence, loading, and self-healing.

    Example:
        anvil = Anvil(api_key="...", tools_dir="./anvil_tools")

        search_tool = anvil.use_tool(
            name="search_notion",
            intent="Search the user's Notion workspace",
            docs_url="https://developers.notion.com/reference/post-search"
        )

        result = search_tool.run(query="Project Anvil")
    """

    def __init__(
        self,
        api_key: str | None = None,
        firecrawl_key: str | None = None,
        tools_dir: str | Path = "./anvil_tools",
        self_healing: bool = True,
        max_heal_attempts: int = 2,
        use_stub: bool = False,
        model: str | None = None,
        provider: str = "anthropic",
        log_file: str | Path | None = None,
        interactive_credentials: bool = True,
        env_file: str | Path | None = None,
        verified_mode: bool = False,
        security_policy: SecurityPolicy | None = None,
        mode: str = "local",
    ):
        """Initialize Anvil.

        Args:
            api_key: LLM API key for code generation (or set from env based on provider)
            firecrawl_key: FireCrawl API key for doc fetching (or set FIRECRAWL_API_KEY env)
            tools_dir: Directory to store generated tools
            self_healing: If True, attempt to regenerate failed tools
            max_heal_attempts: Maximum regeneration attempts per failure
            use_stub: If True, use stub generator (for testing without API keys)
            model: Model to use for generation (defaults based on provider)
            provider: LLM provider to use ('anthropic', 'openai', 'grok')
            log_file: Optional path to write logs to (JSON lines format)
            interactive_credentials: If True, prompt user for missing API keys
            env_file: Path to .env file for credential persistence (default: ./.env)
            verified_mode: If True, run generated code in sandbox before saving
            security_policy: Custom security policy for sandbox (default: restrictive)
            mode: Generator mode ('local', 'stub'). For 'cloud' mode, install anvil-cloud.

        Note:
            For Anvil Cloud mode (instant cached tools), install the anvil-cloud package:
                pip install anvil-cloud
        """
        self.api_key = api_key
        self.firecrawl_key = firecrawl_key
        self.tools_dir = Path(tools_dir)
        self.self_healing = self_healing
        self.max_heal_attempts = max_heal_attempts
        self.model = model
        self.provider = provider.lower()
        self.interactive_credentials = interactive_credentials
        self.verified_mode = verified_mode
        self.mode = mode.lower()

        # Initialize components
        self._manager = ToolManager(self.tools_dir)
        self._loader = ToolLoader(self.tools_dir)
        self._logger = AnvilLogger(log_file=log_file)
        self._credential_resolver = CredentialResolver(
            env_file=env_file,
            interactive=interactive_credentials,
        )

        # Initialize sandbox for verified mode
        self._sandbox = SandboxManager(
            policy=security_policy,
            prefer_docker=True,
        )

        # Initialize generator based on mode
        self._generator: BaseGenerator = self._create_generator(use_stub)

        # Track healing attempts per tool
        self._heal_attempts: dict[str, int] = {}

    def _create_generator(self, use_stub: bool) -> BaseGenerator:
        """Create the appropriate generator based on mode.

        Args:
            use_stub: If True, override mode and use stub generator

        Returns:
            Configured generator instance
        """
        # Stub mode takes precedence (for backward compatibility)
        if use_stub or self.mode == "stub":
            return StubGenerator()

        # Cloud mode - requires anvil-cloud package
        if self.mode == "cloud":
            try:
                from anvil_cloud import CloudGenerator

                fallback = LocalGenerator(
                    api_key=self.api_key,
                    firecrawl_key=self.firecrawl_key,
                    model=self.model,
                    provider=self.provider,
                )
                return CloudGenerator(fallback_generator=fallback)
            except ImportError:
                raise ImportError(
                    "Anvil Cloud mode requires the anvil-cloud package. "
                    "Install it with: pip install anvil-cloud"
                )

        # Default: local mode (BYO keys)
        return LocalGenerator(
            api_key=self.api_key,
            firecrawl_key=self.firecrawl_key,
            model=self.model,
            provider=self.provider,
        )

    def use_tool(
        self,
        name: str,
        intent: str,
        docs_url: str | None = None,
        inputs: list[InputParam | dict[str, Any]] | None = None,
    ) -> Tool:
        """Load or generate a tool based on intent.

        This is the main entry point. It will:
        1. Check if the tool exists and is managed
        2. If missing or intent changed, generate new code
        3. Load and return the tool

        Args:
            name: Unique name for the tool (becomes filename)
            intent: Natural language description of what the tool should do
            docs_url: Optional URL to API documentation
            inputs: Optional list of input parameters (InputParam or dict)

        Returns:
            Tool object that can be executed with .run() or .run_interactive()
        """
        # Convert dict inputs to InputParam objects
        input_params: list[InputParam] = []
        if inputs:
            for inp in inputs:
                if isinstance(inp, dict):
                    input_params.append(InputParam.from_dict(inp))
                else:
                    input_params.append(inp)

        config = ToolConfig(name=name, intent=intent, docs_url=docs_url, inputs=input_params)

        # Check if we need to generate/regenerate
        if self._manager.should_regenerate(name, intent):
            self._generate_and_save(name, config)

        # Clear loader cache to ensure fresh load after generation
        self._loader.clear_cache(name)

        return Tool(
            name=name,
            config=config,
            loader=self._loader,
            anvil=self,
        )

    def _generate_and_save(self, name: str, config: ToolConfig) -> None:
        """Generate tool code and save to disk.

        Args:
            name: Tool name
            config: Tool configuration

        Raises:
            RuntimeError: If verified_mode is enabled and code fails verification
        """
        start_time = time.perf_counter()

        # Generate code
        generated = self._generator.generate(config)

        # Verified mode: run in sandbox before saving
        if self.verified_mode:
            verification = self._sandbox.verify_code(generated.code)
            if not verification.success:
                self._log_event(
                    EventType.TOOL_FAILED,
                    name,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    error=verification.error,
                    metadata={
                        "security_violations": verification.security_violations,
                        "verification_failed": True,
                    },
                )
                raise RuntimeError(
                    f"Code verification failed for '{name}': {verification.error}"
                    + (f"\nViolations: {verification.security_violations}"
                       if verification.security_violations else "")
                )

        # Determine version
        existing_meta = self._manager.get_metadata(name)
        if existing_meta:
            # Increment version
            major, minor = existing_meta.version.split(".")
            version = f"{major}.{int(minor) + 1}"
        else:
            version = "1.0"

        # Write to disk
        self._manager.write_tool(name, generated.code, config, version)

        duration_ms = (time.perf_counter() - start_time) * 1000
        self._log_event(
            EventType.TOOL_GENERATED,
            name,
            duration_ms=duration_ms,
            metadata={
                "version": version,
                "intent": config.intent,
                "verified": self.verified_mode,
            },
        )

    def _attempt_heal(
        self,
        name: str,
        config: ToolConfig,
        kwargs: dict[str, Any],
        error_message: str | None,
    ) -> ToolResult:
        """Attempt to heal a failed tool by regenerating it with error context.

        Args:
            name: Tool name
            config: Tool configuration
            kwargs: Original arguments that caused the failure
            error_message: The error that occurred

        Returns:
            ToolResult from the retry attempt
        """
        start_time = time.perf_counter()

        # Check heal attempt limit
        attempts = self._heal_attempts.get(name, 0)
        if attempts >= self.max_heal_attempts:
            return ToolResult(
                success=False,
                error=f"Max heal attempts ({self.max_heal_attempts}) exceeded for '{name}'",
            )

        self._heal_attempts[name] = attempts + 1

        # Check if we're allowed to regenerate (not ejected)
        if not self._manager.is_managed(name):
            return ToolResult(
                success=False,
                error=f"Tool '{name}' is not managed by Anvil (user-controlled)",
            )

        # Get the current code for context
        current_code = self._manager.read_tool_code(name)

        # Generate fixed code using error context
        if current_code and error_message:
            generated = self._generator.generate_fix(
                config=config,
                previous_code=current_code,
                error_message=error_message,
            )
        else:
            # Fall back to fresh generation if no code/error
            generated = self._generator.generate(config)

        # Determine new version
        existing_meta = self._manager.get_metadata(name)
        if existing_meta:
            major, minor = existing_meta.version.split(".")
            version = f"{major}.{int(minor) + 1}"
        else:
            version = "1.0"

        # Write fixed code to disk
        self._manager.write_tool(name, generated.code, config, version)

        duration_ms = (time.perf_counter() - start_time) * 1000
        self._log_event(
            EventType.TOOL_HEALED,
            name,
            duration_ms=duration_ms,
            metadata={
                "version": version,
                "attempt": attempts + 1,
                "original_error": error_message,
            },
        )

        # Reload and retry
        self._loader.clear_cache(name)
        return self._loader.execute(name, **kwargs)

    def _resolve_credential_and_retry(
        self,
        credential_name: str,
        tool_name: str,
        kwargs: dict[str, Any],
    ) -> Any | None:
        """Attempt to resolve a missing credential and retry tool execution.

        Args:
            credential_name: The name of the missing environment variable
            tool_name: The tool that needs the credential
            kwargs: Original arguments to pass to the tool

        Returns:
            The result from retry if credential was resolved, None otherwise
        """
        # Prompt user for the credential
        value = self._credential_resolver.prompt_for_credential(credential_name)

        if not value:
            # User declined to provide credential
            return None

        # Clear loader cache to pick up new env var
        self._loader.clear_cache(tool_name)

        # Retry the tool
        result = self._loader.execute(tool_name, **kwargs)

        if result.success:
            return result.data

        # If still failed, return None to let normal error handling proceed
        return None

    def get_tool_info(self, name: str) -> dict[str, Any] | None:
        """Get metadata about a tool.

        Args:
            name: Tool name

        Returns:
            Dict with tool metadata, or None if not found
        """
        meta = self._manager.get_metadata(name)
        if meta is None:
            return None
        return meta.to_dict()

    def list_tools(self) -> list[str]:
        """List all available tools.

        Returns:
            List of tool names
        """
        tools = []
        for path in self.tools_dir.glob("*.py"):
            if path.name != "__init__.py":
                tools.append(path.stem)
        return sorted(tools)

    def reset_heal_attempts(self, name: str | None = None) -> None:
        """Reset the heal attempt counter.

        Args:
            name: If provided, reset only this tool. Otherwise reset all.
        """
        if name is not None:
            self._heal_attempts.pop(name, None)
        else:
            self._heal_attempts.clear()

    def get_tool_code(self, name: str) -> str | None:
        """Get the source code of a tool.

        Args:
            name: Tool name

        Returns:
            The tool's source code, or None if not found
        """
        return self._manager.read_tool_code(name)

    @property
    def logger(self) -> AnvilLogger:
        """Get the logger instance for querying event history.

        Returns:
            The AnvilLogger instance
        """
        return self._logger

    @property
    def sandbox(self) -> SandboxManager:
        """Get the sandbox manager instance.

        Returns:
            The SandboxManager instance
        """
        return self._sandbox

    def get_sandbox_status(self) -> dict[str, Any]:
        """Get the status of the sandbox system.

        Returns:
            Dict with sandbox availability and configuration
        """
        return self._sandbox.get_status()

    def _log_event(
        self,
        event_type: EventType,
        tool_name: str,
        duration_ms: float | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an event to the internal logger.

        Args:
            event_type: Type of event
            tool_name: Name of the tool involved
            duration_ms: Optional duration in milliseconds
            error: Optional error message
            metadata: Optional additional metadata
        """
        event = AnvilEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            tool_name=tool_name,
            duration_ms=duration_ms,
            error=error,
            metadata=metadata or {},
        )
        self._logger.log(event)
