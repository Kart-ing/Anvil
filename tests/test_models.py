"""Tests for Anvil data models."""

from datetime import datetime

from anvil.models import (
    GeneratedCode,
    ToolConfig,
    ToolMetadata,
    ToolResult,
    ToolStatus,
)


class TestToolConfig:
    def test_create_with_required_fields(self):
        config = ToolConfig(
            name="search_notion",
            intent="Search Notion workspace",
        )
        assert config.name == "search_notion"
        assert config.intent == "Search Notion workspace"
        assert config.docs_url is None
        assert config.version == "1.0"

    def test_create_with_all_fields(self):
        config = ToolConfig(
            name="search_notion",
            intent="Search Notion workspace",
            docs_url="https://developers.notion.com",
            version="2.0",
        )
        assert config.docs_url == "https://developers.notion.com"
        assert config.version == "2.0"

    def test_to_dict(self):
        config = ToolConfig(
            name="test",
            intent="Test intent",
            docs_url="https://example.com",
        )
        d = config.to_dict()
        assert d["name"] == "test"
        assert d["intent"] == "Test intent"
        assert d["docs_url"] == "https://example.com"
        assert d["version"] == "1.0"


class TestToolMetadata:
    def test_create_metadata(self):
        now = datetime.now()
        metadata = ToolMetadata(
            name="test_tool",
            intent="Test intent",
            docs_url="https://example.com",
            hash="abc12345",
            version="1.0",
            status=ToolStatus.ACTIVE,
            created_at=now,
            last_generated=now,
        )
        assert metadata.name == "test_tool"
        assert metadata.status == ToolStatus.ACTIVE
        assert metadata.error_count == 0

    def test_to_dict_and_from_dict(self):
        now = datetime.now()
        original = ToolMetadata(
            name="test_tool",
            intent="Test intent",
            docs_url="https://example.com",
            hash="abc12345",
            version="1.0",
            status=ToolStatus.ACTIVE,
            created_at=now,
            last_generated=now,
            error_count=2,
        )

        d = original.to_dict()
        restored = ToolMetadata.from_dict(d)

        assert restored.name == original.name
        assert restored.intent == original.intent
        assert restored.hash == original.hash
        assert restored.status == original.status
        assert restored.error_count == original.error_count


class TestToolResult:
    def test_success_result(self):
        result = ToolResult(success=True, data={"items": [1, 2, 3]})
        assert result.success is True
        assert result.data == {"items": [1, 2, 3]}
        assert result.error is None

    def test_error_result(self):
        result = ToolResult(success=False, error="API rate limited")
        assert result.success is False
        assert result.data is None
        assert result.error == "API rate limited"

    def test_to_dict(self):
        result = ToolResult(success=True, data="test")
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"] == "test"
        assert d["error"] is None


class TestGeneratedCode:
    def test_create_with_defaults(self):
        gen = GeneratedCode(code="def run(): pass")
        assert gen.code == "def run(): pass"
        assert gen.dependencies == []

    def test_create_with_dependencies(self):
        gen = GeneratedCode(
            code="import requests\ndef run(): pass",
            dependencies=["requests"],
        )
        assert gen.dependencies == ["requests"]
