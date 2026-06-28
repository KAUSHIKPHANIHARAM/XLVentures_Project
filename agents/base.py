"""
agents/base.py

BaseAgent — abstract base class for all platform agents.

Every agent in the platform inherits from this class. It handles all
boilerplate: LLM creation, tool binding, the ReAct execution loop,
error wrapping, and WorkflowState updates.

Subclasses only need to override:
    - _build_prompt(): construct the messages list for this agent's role
    - _parse_output(): extract structured data from the LLM response

Design:
    - invoke(state) is the LangGraph node entry point.
    - Uses LangChain's tool-calling API (bind_tools + tool_calls loop).
    - Max iterations guard prevents infinite tool loops.
    - All LLM calls go through utils.retry for transience resilience.
    - Produces an AgentOutput that is stored in WorkflowState.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from agents.llm_factory import get_llm
from config.schemas import AgentConfig, LLMConfig
from schemas.agent import AgentOutput, AgentStatus, WorkflowState
from utils.datetime_utils import utc_now_iso
from utils.json_utils import safe_json_dumps
from utils.logging import get_logger
from utils.retry import retry_llm_call

logger = get_logger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all platform agents.

    Args:
        config:     AgentConfig loaded from YAML.
        llm_config: Effective LLM config (platform default or agent override).
        tools:      List of LangChain Tool objects bound to this agent.
        domain:     Domain name this agent belongs to.
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_config: LLMConfig,
        tools: list[Any],
        domain: str,
    ) -> None:
        self.config = config
        self.llm_config = llm_config
        self.tools = tools
        self.domain = domain
        self.name = config.name
        self.role = config.role
        self._logger = get_logger(f"agents.{config.name}")

        # Bind tools to LLM if any tools are configured
        base_llm = get_llm(llm_config)
        self._llm = base_llm.bind_tools(tools) if tools else base_llm
        self._logger.debug(
            "Agent '%s' initialised with %d tool(s).", self.name, len(tools)
        )

    def invoke(self, state: WorkflowState) -> dict[str, Any]:
        """
        LangGraph node entry point.

        Executes the agent against the current workflow state and returns
        a dict of state updates to merge into WorkflowState.

        Args:
            state: Current WorkflowState from the LangGraph graph.

        Returns:
            Dict of state keys to update.
        """
        self._logger.info(
            "Agent '%s' invoked. Query: '%.60s...'",
            self.name,
            state.get("user_query", ""),
        )

        try:
            output = self._run(state)
        except Exception as exc:
            self._logger.error("Agent '%s' failed: %s", self.name, exc, exc_info=True)
            output = AgentOutput(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                response=f"Agent '{self.name}' encountered an error: {exc}",
                error=str(exc),
            )

        # Merge this agent's output into the shared agent_outputs dict
        existing_outputs: dict[str, AgentOutput] = state.get("agent_outputs", {})
        existing_outputs[self.name] = output

        trace: list[dict] = state.get("execution_trace", [])
        trace.append({
            "agent": self.name,
            "status": output.status.value,
            "timestamp": utc_now_iso(),
            "tools_called": output.tool_calls_made,
        })

        total_tool_calls = state.get("total_tool_calls", 0) + len(output.tool_calls_made)

        updates: dict[str, Any] = {
            "agent_outputs": existing_outputs,
            "execution_trace": trace,
            "total_tool_calls": total_tool_calls,
        }

        # Let subclasses add domain-specific state keys
        updates.update(self._state_updates(output, state))
        return updates

    def _run(self, state: WorkflowState) -> AgentOutput:
        """
        Core execution loop: build prompt → call LLM → execute tools → respond.
        """
        messages = self._build_prompt(state)
        tool_calls_made: list[str] = []
        retrieved_data: list[dict[str, Any]] = list(state.get("retrieved_data", []))

        for iteration in range(self.config.max_iterations):
            ai_message: AIMessage = self._call_llm(messages)
            messages.append(ai_message)

            # No tool calls → final response
            if not ai_message.tool_calls:
                response_text = (
                    ai_message.content
                    if isinstance(ai_message.content, str)
                    else str(ai_message.content)
                )
                return self._build_output(
                    response=response_text,
                    tool_calls_made=tool_calls_made,
                    retrieved_data=retrieved_data,
                    state=state,
                )

            # Execute each tool call
            for tool_call in ai_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
                tool_call_id = tool_call.get("id", tool_name)

                self._logger.debug(
                    "Calling tool '%s' with args: %s", tool_name, tool_args
                )
                tool_calls_made.append(tool_name)

                result_content = self._execute_tool(tool_name, tool_args)

                # Collect structured data if tool returned a dict/list
                if isinstance(result_content, (dict, list)):
                    retrieved_data.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result_content,
                    })

                messages.append(ToolMessage(
                    content=safe_json_dumps(result_content)
                    if not isinstance(result_content, str)
                    else result_content,
                    tool_call_id=tool_call_id,
                ))

        # Max iterations reached — return what we have
        self._logger.warning(
            "Agent '%s' reached max iterations (%d).", self.name, self.config.max_iterations
        )
        last_content = messages[-1].content if messages else "Max iterations reached."
        return self._build_output(
            response=str(last_content),
            tool_calls_made=tool_calls_made,
            retrieved_data=retrieved_data,
            state=state,
        )

    @retry_llm_call(max_attempts=3)
    def _call_llm(self, messages: list[BaseMessage]) -> AIMessage:
        """Invoke the LLM with retry on transient errors."""
        result = self._llm.invoke(messages)
        return result  # type: ignore[return-value]

    def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> Any:
        """Find and execute a tool by name. Returns the tool's output."""
        for tool in self.tools:
            if tool.name == tool_name:
                try:
                    return tool.invoke(args)
                except Exception as exc:
                    self._logger.error(
                        "Tool '%s' raised error: %s", tool_name, exc
                    )
                    return {"error": str(exc), "tool": tool_name}
        return {"error": f"Tool '{tool_name}' not found in agent's tool list."}

    # ------------------------------------------------------------------
    # Abstract methods — subclasses must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _build_prompt(self, state: WorkflowState) -> list[BaseMessage]:
        """
        Build the message list to send to the LLM.

        Subclasses compose the system prompt, context from state,
        knowledge chunks, retrieved data, and the user query here.
        """

    # ------------------------------------------------------------------
    # Overridable hooks — subclasses may override for custom behaviour
    # ------------------------------------------------------------------

    def _parse_output(self, response: str) -> dict[str, Any]:
        """Parse structured data from the LLM's text response. Optional."""
        return {}

    def _state_updates(
        self, output: AgentOutput, state: WorkflowState
    ) -> dict[str, Any]:
        """
        Additional WorkflowState keys to update after this agent runs.

        Base implementation returns empty dict. Subclasses (e.g. RouterAgent)
        override to write routing decisions or retrieved data to state.
        """
        return {}

    def _build_output(
        self,
        response: str,
        tool_calls_made: list[str],
        retrieved_data: list[dict[str, Any]],
        state: WorkflowState,
    ) -> AgentOutput:
        """Assemble an AgentOutput from the raw LLM response."""
        return AgentOutput(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            response=response,
            tool_calls_made=tool_calls_made,
            retrieved_data=retrieved_data,
        )

    # ------------------------------------------------------------------
    # Shared prompt helpers (used by all subclasses)
    # ------------------------------------------------------------------

    def _system_message(self, extra_context: str = "") -> SystemMessage:
        """Build the system message from the YAML system_prompt."""
        content = self.config.system_prompt
        if extra_context:
            content = f"{content}\n\n{extra_context}"
        return SystemMessage(content=content)

    def _knowledge_context_block(self, state: WorkflowState) -> str:
        """Format knowledge chunks from state into an injectable block."""
        chunks: list[str] = state.get("knowledge_chunks", [])
        if not chunks:
            return ""
        lines = ["--- Relevant Knowledge ---"]
        for i, chunk in enumerate(chunks[:3], 1):
            lines.append(f"[{i}] {chunk[:400]}")
        lines.append("--- End Knowledge ---")
        return "\n".join(lines)

    def _data_context_block(self, state: WorkflowState) -> str:
        """Format retrieved_data from state into a compact context block."""
        data: list[dict] = state.get("retrieved_data", [])
        if not data:
            return ""
        lines = ["--- Retrieved Data ---"]
        for item in data[:3]:
            lines.append(safe_json_dumps(item, indent=None)[:500])
        lines.append("--- End Data ---")
        return "\n".join(lines)
