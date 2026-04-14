"""Test utilities for LXA tests.

Provides a RecordingTestLLM class that extends OpenHands SDK's TestLLM
to record all calls for assertion in tests.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from openhands.sdk.llm.llm_response import LLMResponse
from openhands.sdk.llm.message import Message
from openhands.sdk.llm.streaming import TokenCallbackType
from openhands.sdk.testing import TestLLM
from pydantic import ConfigDict, PrivateAttr

if TYPE_CHECKING:
    from openhands.sdk.tool.tool import ToolDefinition


@dataclass
class LLMCall:
    """Record of a single call to the LLM."""

    messages: list[Message]
    """The messages passed to the LLM."""

    tools: Sequence[ToolDefinition] | None
    """The tools available for this call."""

    kwargs: dict[str, Any]
    """Any additional kwargs passed."""

    response: LLMResponse | None = None
    """The response returned (None if an exception was raised)."""

    exception: Exception | None = None
    """The exception raised (None if successful)."""


class RecordingTestLLM(TestLLM):
    """Extension of TestLLM that records all calls for test assertions.

    This allows tests to:
    1. Provide scripted responses via TestLLM
    2. Assert on the prompts/messages sent to the LLM
    3. Verify tool availability at each call

    Example:
        >>> from openhands.sdk.llm import Message, TextContent, MessageToolCall
        >>> from tests.testing import RecordingTestLLM
        >>>
        >>> # Create a recording LLM with scripted responses
        >>> llm = RecordingTestLLM.from_messages([
        ...     Message(
        ...         role="assistant",
        ...         content=[TextContent(text="I'll create the file for you.")],
        ...         tool_calls=[MessageToolCall(
        ...             id="call_1",
        ...             name="file_editor",
        ...             arguments='{"command":"create","path":"hello.txt","content":"Hello!"}',
        ...             origin="completion",
        ...         )],
        ...     ),
        ...     Message(role="assistant", content=[TextContent(text="Done! Created hello.txt")]),
        ... ])
        >>>
        >>> # Use llm in your code...
        >>> # After running, check the calls:
        >>> assert len(llm.recorded_calls) == 2
        >>> assert "create" in llm.recorded_calls[0].messages[0].content[0].text
    """

    # Prevent pytest from collecting this class as a test
    __test__: ClassVar[bool] = False

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    _recorded_calls: list[LLMCall] = PrivateAttr(default_factory=list)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._recorded_calls = []

    @classmethod
    def from_messages(
        cls,
        messages: list[Message | Exception],
        *,
        model: str = "test-model",
        usage_id: str = "test-llm",
        **kwargs: Any,
    ) -> RecordingTestLLM:
        """Create a RecordingTestLLM with scripted responses.

        Args:
            messages: List of Message or Exception objects to return in order.
            model: Model name (default: "test-model")
            usage_id: Usage ID for metrics (default: "test-llm")
            **kwargs: Additional arguments passed to TestLLM.

        Returns:
            A RecordingTestLLM configured with the scripted responses.
        """
        return cls(
            model=model,
            usage_id=usage_id,
            scripted_responses=messages,
            **kwargs,
        )

    @property
    def recorded_calls(self) -> list[LLMCall]:
        """Return the list of recorded calls."""
        return self._recorded_calls

    def completion(
        self,
        messages: list[Message],
        tools: Sequence[ToolDefinition] | None = None,
        _return_metrics: bool = False,
        add_security_risk_prediction: bool = False,
        on_token: TokenCallbackType | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Record the call and delegate to parent TestLLM."""
        call = LLMCall(
            messages=list(messages),
            tools=tools,
            kwargs=dict(kwargs),
        )

        try:
            response = super().completion(
                messages,
                tools,
                _return_metrics=_return_metrics,
                add_security_risk_prediction=add_security_risk_prediction,
                on_token=on_token,
                **kwargs,
            )
            call.response = response
            self._recorded_calls.append(call)
            return response
        except Exception as e:
            call.exception = e
            self._recorded_calls.append(call)
            raise

    def get_last_user_message(self) -> str | None:
        """Helper to get the last user message text from the most recent call."""
        if not self._recorded_calls:
            return None

        last_call = self._recorded_calls[-1]
        for msg in reversed(last_call.messages):
            if msg.role == "user":
                from openhands.sdk.llm.message import TextContent

                for content in msg.content:
                    if isinstance(content, TextContent):
                        return content.text
        return None

    def assert_task_was_received(self, task_fragment: str) -> None:
        """Assert that the task fragment appears in one of the user messages."""
        for call in self._recorded_calls:
            for msg in call.messages:
                if msg.role == "user":
                    from openhands.sdk.llm.message import TextContent

                    for content in msg.content:
                        if isinstance(content, TextContent) and task_fragment in content.text:
                            return
        raise AssertionError(
            f"Task fragment '{task_fragment}' not found in any user messages. "
            f"Calls: {len(self._recorded_calls)}"
        )
