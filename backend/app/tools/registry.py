from __future__ import annotations

import re
from collections.abc import Iterable

from app.schemas.tool import ToolDefinition
from app.schemas.tool_registry import (
    RegisteredToolInfo,
    ToolRegistrySnapshot,
)
from app.tools.base import BaseTool
from app.tools.exceptions import (
    ToolAlreadyRegisteredError,
    ToolDisabledError,
    ToolNameValidationError,
    ToolNotFoundError,
)
from app.tools.policy import (
    validate_tool_security_policy,
)


_TOOL_NAME_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]{0,63}$"
)


class ToolRegistry:
    """
    Central registry for ORVYN tools.

    Responsibilities:
    - register trusted tool implementations,
    - validate canonical tool names,
    - validate minimum security policy,
    - prevent duplicate registration,
    - enable or disable tools,
    - resolve enabled tools,
    - expose safe machine-readable definitions.

    The registry intentionally does NOT:
    - authorize individual users,
    - grant permissions,
    - approve actions,
    - execute tools.
    """

    def __init__(
        self,
        tools: Iterable[BaseTool] | None = None,
    ) -> None:
        self._tools: dict[
            str,
            BaseTool,
        ] = {}

        self._enabled: dict[
            str,
            bool,
        ] = {}

        if tools is not None:
            for tool in tools:
                self.register(
                    tool
                )

    @staticmethod
    def validate_tool_name(
        name: str,
    ) -> str:
        """
        Validate a canonical ORVYN tool name.
        """

        if not isinstance(
            name,
            str,
        ):
            raise ToolNameValidationError(
                "Tool name must be a string."
            )

        if not _TOOL_NAME_PATTERN.fullmatch(
            name
        ):
            raise ToolNameValidationError(
                (
                    "Tool name must start with a lowercase "
                    "letter and contain only lowercase "
                    "letters, numbers and underscores, "
                    "with a maximum length of 64."
                )
            )

        return name

    def register(
        self,
        tool: BaseTool,
        *,
        enabled: bool = True,
    ) -> None:
        """
        Register a trusted tool implementation.

        Existing tools cannot be silently replaced.
        Tools that understate their risk classification
        are rejected.
        """

        if not isinstance(
            tool,
            BaseTool,
        ):
            raise TypeError(
                (
                    "Only BaseTool instances "
                    "can be registered."
                )
            )

        name = self.validate_tool_name(
            tool.name
        )

        if name in self._tools:
            raise ToolAlreadyRegisteredError(
                (
                    f"Tool '{name}' is "
                    f"already registered."
                )
            )

        tool.get_definition()

        validate_tool_security_policy(
            tool
        )

        self._tools[name] = tool

        self._enabled[name] = bool(
            enabled
        )

    def unregister(
        self,
        name: str,
    ) -> None:
        """
        Remove a tool from the registry.
        """

        name = self.validate_tool_name(
            name
        )

        if name not in self._tools:
            raise ToolNotFoundError(
                (
                    f"Tool '{name}' is "
                    f"not registered."
                )
            )

        del self._tools[name]
        del self._enabled[name]

    def contains(
        self,
        name: str,
    ) -> bool:
        """
        Return whether a valid canonical name is registered.
        """

        try:
            name = self.validate_tool_name(
                name
            )
        except ToolNameValidationError:
            return False

        return name in self._tools

    def is_enabled(
        self,
        name: str,
    ) -> bool:
        """
        Return enabled state of a registered tool.
        """

        name = self.validate_tool_name(
            name
        )

        if name not in self._tools:
            raise ToolNotFoundError(
                (
                    f"Tool '{name}' is "
                    f"not registered."
                )
            )

        return self._enabled[
            name
        ]

    def enable(
        self,
        name: str,
    ) -> None:
        """
        Enable a registered tool.
        """

        name = self.validate_tool_name(
            name
        )

        if name not in self._tools:
            raise ToolNotFoundError(
                (
                    f"Tool '{name}' is "
                    f"not registered."
                )
            )

        self._enabled[name] = True

    def disable(
        self,
        name: str,
    ) -> None:
        """
        Disable a registered tool.
        """

        name = self.validate_tool_name(
            name
        )

        if name not in self._tools:
            raise ToolNotFoundError(
                (
                    f"Tool '{name}' is "
                    f"not registered."
                )
            )

        self._enabled[name] = False

    def get(
        self,
        name: str,
        *,
        require_enabled: bool = True,
    ) -> BaseTool:
        """
        Resolve a registered tool.

        Disabled tools cannot be resolved for execution
        unless internal code explicitly asks to inspect one.
        """

        name = self.validate_tool_name(
            name
        )

        tool = self._tools.get(
            name
        )

        if tool is None:
            raise ToolNotFoundError(
                (
                    f"Tool '{name}' is "
                    f"not registered."
                )
            )

        if (
            require_enabled
            and not self._enabled[
                name
            ]
        ):
            raise ToolDisabledError(
                (
                    f"Tool '{name}' "
                    f"is disabled."
                )
            )

        return tool

    def list_tools(
        self,
        *,
        enabled_only: bool = False,
    ) -> list[BaseTool]:
        """
        Return registered implementations.

        Provider/LLM-facing code should use definitions()
        instead of receiving executable Python objects.
        """

        names = sorted(
            self._tools
        )

        return [
            self._tools[
                name
            ]
            for name in names
            if (
                not enabled_only
                or self._enabled[
                    name
                ]
            )
        ]

    def definitions(
        self,
        *,
        enabled_only: bool = True,
    ) -> list[ToolDefinition]:
        """
        Return machine-readable safe definitions.
        """

        return [
            tool.get_definition()
            for tool
            in self.list_tools(
                enabled_only=enabled_only
            )
        ]

    def snapshot(
        self,
    ) -> ToolRegistrySnapshot:
        """
        Return a safe diagnostic snapshot.
        """

        registered_tools = [
            RegisteredToolInfo(
                definition=(
                    self._tools[
                        name
                    ].get_definition()
                ),
                enabled=(
                    self._enabled[
                        name
                    ]
                ),
            )
            for name
            in sorted(
                self._tools
            )
        ]

        enabled_count = sum(
            1
            for enabled
            in self._enabled.values()
            if enabled
        )

        return ToolRegistrySnapshot(
            tools=registered_tools,
            total=len(
                registered_tools
            ),
            enabled=enabled_count,
            disabled=(
                len(
                    registered_tools
                )
                - enabled_count
            ),
        )

    def __len__(
        self,
    ) -> int:
        return len(
            self._tools
        )