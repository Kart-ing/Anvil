"""Data models for Anvil SDK."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ToolStatus(Enum):
    """Status of a tool in the registry."""
    ACTIVE = "active"
    FAILED = "failed"
    EJECTED = "ejected"  # User took manual control


@dataclass
class InputParam:
    """Definition of a tool input parameter."""
    name: str
    param_type: str = "str"  # "str", "int", "float", "bool", "list"
    required: bool = True
    description: str = ""
    default: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "param_type": self.param_type,
            "required": self.required,
            "description": self.description,
            "default": self.default,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InputParam":
        return cls(
            name=data["name"],
            param_type=data.get("param_type", "str"),
            required=data.get("required", True),
            description=data.get("description", ""),
            default=data.get("default"),
        )


@dataclass
class ToolConfig:
    """Configuration for a tool definition."""
    name: str
    intent: str
    docs_url: str | None = None
    version: str = "1.0"
    inputs: list[InputParam] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "intent": self.intent,
            "docs_url": self.docs_url,
            "version": self.version,
            "inputs": [inp.to_dict() for inp in self.inputs],
        }


@dataclass
class ToolMetadata:
    """Metadata stored in the tool registry."""
    name: str
    intent: str
    docs_url: str | None
    hash: str
    version: str
    status: ToolStatus
    created_at: datetime
    last_generated: datetime
    error_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "intent": self.intent,
            "docs_url": self.docs_url,
            "hash": self.hash,
            "version": self.version,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_generated": self.last_generated.isoformat(),
            "error_count": self.error_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolMetadata":
        return cls(
            name=data["name"],
            intent=data["intent"],
            docs_url=data.get("docs_url"),
            hash=data["hash"],
            version=data["version"],
            status=ToolStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_generated=datetime.fromisoformat(data["last_generated"]),
            error_count=data.get("error_count", 0),
        )


@dataclass
class ToolResult:
    """Result from executing a tool."""
    success: bool
    data: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }


@dataclass
class GeneratedCode:
    """Output from the JIT generator."""
    code: str
    dependencies: list[str] = field(default_factory=list)
