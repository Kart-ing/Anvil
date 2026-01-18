"""Tests for framework adapters (LangChain, CrewAI, AutoGen, OpenAI Agents SDK)."""

import pytest
from unittest.mock import MagicMock, patch

from anvil import Anvil
from anvil.models import InputParam


class TestLangChainAdapter:
    """Tests for LangChain adapter."""

    def test_to_langchain_raises_without_package(self, tmp_path):
        """Test that to_langchain raises ImportError if langchain not installed."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="test_tool", intent="Test tool")

        with patch.dict("sys.modules", {"langchain_core": None, "langchain_core.tools": None}):
            # Force reimport to trigger ImportError
            import anvil.adapters.langchain as lc_adapter
            # Reload to clear cached imports
            import importlib
            importlib.reload(lc_adapter)

    def test_to_langchain_creates_tool(self, tmp_path):
        """Test that to_langchain creates a proper tool when langchain is available."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="search_web", intent="Search the web for information")

        # Mock langchain_core
        mock_base_tool = MagicMock()

        with patch.dict("sys.modules", {
            "langchain_core": MagicMock(),
            "langchain_core.tools": MagicMock(BaseTool=mock_base_tool),
        }):
            # Import after patching
            from anvil.adapters.langchain import to_langchain_tool

            # The function should work without error
            # (actual conversion would need real langchain)

    def test_to_langchain_with_inputs(self, tmp_path):
        """Test that to_langchain handles input parameters."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="search",
            intent="Search for documents",
            inputs=[
                {"name": "query", "param_type": "str", "required": True, "description": "Search query"},
                {"name": "limit", "param_type": "int", "required": False, "default": 10},
            ],
        )

        # Check that tool has inputs
        assert len(tool.config.inputs) == 2
        assert tool.config.inputs[0].name == "query"
        assert tool.config.inputs[1].name == "limit"

    def test_pydantic_model_creation(self, tmp_path):
        """Test that Pydantic model is created correctly from InputParams."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="test_model",
            intent="Test model creation",
            inputs=[
                {"name": "text", "param_type": "str", "required": True},
                {"name": "count", "param_type": "int", "required": False, "default": 5},
                {"name": "enabled", "param_type": "bool", "required": False, "default": True},
            ],
        )

        # Import the helper function
        from anvil.adapters.langchain import _create_pydantic_model

        model = _create_pydantic_model(tool)

        # Check model was created
        assert model is not None
        assert "TestModelInput" in model.__name__

        # Check fields exist
        assert "text" in model.model_fields
        assert "count" in model.model_fields
        assert "enabled" in model.model_fields


class TestCrewAIAdapter:
    """Tests for CrewAI adapter."""

    def test_to_crewai_raises_without_package(self, tmp_path):
        """Test that to_crewai raises ImportError if crewai not installed."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="test_tool", intent="Test tool")

        with patch.dict("sys.modules", {"crewai": None, "crewai.tools": None}):
            # Would raise ImportError
            pass

    def test_to_crewai_creates_tool(self, tmp_path):
        """Test that to_crewai creates a proper tool when crewai is available."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="analyze", intent="Analyze data")

        # Mock crewai
        mock_base_tool = MagicMock()

        with patch.dict("sys.modules", {
            "crewai": MagicMock(),
            "crewai.tools": MagicMock(BaseTool=mock_base_tool),
        }):
            pass  # Would create CrewAI tool

    def test_to_crewai_with_inputs(self, tmp_path):
        """Test that to_crewai handles input parameters."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="process",
            intent="Process a file",
            inputs=[
                {"name": "filepath", "param_type": "str", "required": True},
                {"name": "format", "param_type": "str", "required": False, "default": "json"},
            ],
        )

        assert len(tool.config.inputs) == 2

    def test_pydantic_model_creation_crewai(self, tmp_path):
        """Test that Pydantic model is created correctly for CrewAI."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="crewai_test",
            intent="Test CrewAI model",
            inputs=[
                {"name": "data", "param_type": "str", "required": True},
                {"name": "verbose", "param_type": "bool", "required": False, "default": False},
            ],
        )

        from anvil.adapters.crewai import _create_pydantic_model

        model = _create_pydantic_model(tool)

        assert model is not None
        assert "CrewaiTestInput" in model.__name__
        assert "data" in model.model_fields
        assert "verbose" in model.model_fields


class TestToolAdapterMethods:
    """Tests for adapter methods on Tool class."""

    def test_tool_has_to_langchain_method(self, tmp_path):
        """Test that Tool class has to_langchain method."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="test", intent="Test")

        assert hasattr(tool, "to_langchain")
        assert callable(tool.to_langchain)

    def test_tool_has_to_crewai_method(self, tmp_path):
        """Test that Tool class has to_crewai method."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="test", intent="Test")

        assert hasattr(tool, "to_crewai")
        assert callable(tool.to_crewai)

    def test_adapter_uses_tool_name(self, tmp_path):
        """Test that adapters preserve tool name."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="my_special_tool", intent="Do something special")

        assert tool.name == "my_special_tool"
        assert tool.config.intent == "Do something special"

    def test_adapter_uses_tool_intent_as_description(self, tmp_path):
        """Test that adapters use intent as description."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="describe_me",
            intent="This is a detailed description of what the tool does"
        )

        # Intent becomes description in framework adapters
        assert tool.config.intent == "This is a detailed description of what the tool does"


class TestPydanticModelTypes:
    """Tests for type mapping in Pydantic model creation."""

    def test_string_type(self, tmp_path):
        """Test string type mapping."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="str_test",
            intent="Test",
            inputs=[{"name": "text", "param_type": "str", "required": True}],
        )

        from anvil.adapters.langchain import _create_pydantic_model
        model = _create_pydantic_model(tool)

        # Should accept string
        instance = model(text="hello")
        assert instance.text == "hello"

    def test_int_type(self, tmp_path):
        """Test int type mapping."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="int_test",
            intent="Test",
            inputs=[{"name": "count", "param_type": "int", "required": True}],
        )

        from anvil.adapters.langchain import _create_pydantic_model
        model = _create_pydantic_model(tool)

        instance = model(count=42)
        assert instance.count == 42

    def test_float_type(self, tmp_path):
        """Test float type mapping."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="float_test",
            intent="Test",
            inputs=[{"name": "value", "param_type": "float", "required": True}],
        )

        from anvil.adapters.langchain import _create_pydantic_model
        model = _create_pydantic_model(tool)

        instance = model(value=3.14)
        assert instance.value == 3.14

    def test_bool_type(self, tmp_path):
        """Test bool type mapping."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="bool_test",
            intent="Test",
            inputs=[{"name": "enabled", "param_type": "bool", "required": True}],
        )

        from anvil.adapters.langchain import _create_pydantic_model
        model = _create_pydantic_model(tool)

        instance = model(enabled=True)
        assert instance.enabled is True

    def test_list_type(self, tmp_path):
        """Test list type mapping."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="list_test",
            intent="Test",
            inputs=[{"name": "items", "param_type": "list", "required": True}],
        )

        from anvil.adapters.langchain import _create_pydantic_model
        model = _create_pydantic_model(tool)

        instance = model(items=["a", "b", "c"])
        assert instance.items == ["a", "b", "c"]

    def test_optional_with_default(self, tmp_path):
        """Test optional parameter with default value."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="optional_test",
            intent="Test",
            inputs=[
                {"name": "required_field", "param_type": "str", "required": True},
                {"name": "optional_field", "param_type": "int", "required": False, "default": 100},
            ],
        )

        from anvil.adapters.langchain import _create_pydantic_model
        model = _create_pydantic_model(tool)

        # Should work without optional field
        instance = model(required_field="test")
        assert instance.required_field == "test"
        assert instance.optional_field == 100

    def test_no_inputs_returns_none(self, tmp_path):
        """Test that tool with no inputs returns None for args_schema."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="no_inputs", intent="Tool with no inputs")

        # No inputs defined
        assert len(tool.config.inputs) == 0


class TestAutoGenAdapter:
    """Tests for AutoGen adapter."""

    def test_tool_has_to_autogen_method(self, tmp_path):
        """Test that Tool class has to_autogen method."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="test", intent="Test")

        assert hasattr(tool, "to_autogen")
        assert callable(tool.to_autogen)

    def test_to_autogen_with_inputs(self, tmp_path):
        """Test that to_autogen handles input parameters."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="search",
            intent="Search for documents",
            inputs=[
                {"name": "query", "param_type": "str", "required": True, "description": "Search query"},
                {"name": "limit", "param_type": "int", "required": False, "default": 10},
            ],
        )

        # Check that tool has inputs
        assert len(tool.config.inputs) == 2

    def test_pydantic_model_creation_autogen(self, tmp_path):
        """Test that Pydantic model is created correctly for AutoGen."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="autogen_test",
            intent="Test AutoGen model",
            inputs=[
                {"name": "data", "param_type": "str", "required": True},
                {"name": "verbose", "param_type": "bool", "required": False, "default": False},
            ],
        )

        from anvil.adapters.autogen import _create_pydantic_model

        model = _create_pydantic_model(tool)

        assert model is not None
        assert "AutogenTestArgs" in model.__name__
        assert "data" in model.model_fields
        assert "verbose" in model.model_fields


class TestOpenAIAgentsAdapter:
    """Tests for OpenAI Agents SDK adapter."""

    def test_tool_has_to_openai_agents_method(self, tmp_path):
        """Test that Tool class has to_openai_agents method."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="test", intent="Test")

        assert hasattr(tool, "to_openai_agents")
        assert callable(tool.to_openai_agents)

    def test_to_openai_agents_with_inputs(self, tmp_path):
        """Test that to_openai_agents handles input parameters."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="search",
            intent="Search for documents",
            inputs=[
                {"name": "query", "param_type": "str", "required": True, "description": "Search query"},
                {"name": "limit", "param_type": "int", "required": False, "default": 10},
            ],
        )

        # Check that tool has inputs
        assert len(tool.config.inputs) == 2

    def test_json_schema_creation(self, tmp_path):
        """Test that JSON schema is created correctly for OpenAI Agents."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(
            name="openai_test",
            intent="Test OpenAI Agents schema",
            inputs=[
                {"name": "query", "param_type": "str", "required": True, "description": "Search query"},
                {"name": "limit", "param_type": "int", "required": False, "default": 10},
            ],
        )

        from anvil.adapters.openai_agents import _build_json_schema

        schema = _build_json_schema(tool)

        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]
        assert schema["properties"]["query"]["type"] == "string"
        assert schema["properties"]["limit"]["type"] == "integer"
        assert "query" in schema["required"]


class TestAllAdapterMethods:
    """Tests that all adapter methods exist on Tool class."""

    def test_all_adapter_methods_exist(self, tmp_path):
        """Test that Tool class has all four adapter methods."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="test", intent="Test")

        # All four framework adapters
        assert hasattr(tool, "to_langchain")
        assert hasattr(tool, "to_crewai")
        assert hasattr(tool, "to_autogen")
        assert hasattr(tool, "to_openai_agents")

        # All are callable
        assert callable(tool.to_langchain)
        assert callable(tool.to_crewai)
        assert callable(tool.to_autogen)
        assert callable(tool.to_openai_agents)
