"""Small host-side recorder; a start, completion and result must share an ID."""

from dataclasses import dataclass, field

from copilot.session_events import ToolExecutionCompleteData, ToolExecutionStartData


@dataclass
class ToolTrace:
    started: dict[str, ToolExecutionStartData] = field(default_factory=dict)
    completed: dict[str, ToolExecutionCompleteData] = field(default_factory=dict)

    def record(self, data: object) -> None:
        match data:
            case ToolExecutionStartData(tool_call_id=call_id):
                self.started[call_id] = data
            case ToolExecutionCompleteData(tool_call_id=call_id):
                self.completed[call_id] = data

    def successful_content(self, call_id: str | None) -> str | None:
        completion = self.completed.get(call_id)
        if (
            call_id in self.started
            and completion is not None
            and completion.success
            and completion.error is None
            and completion.result is not None
        ):
            return completion.result.content
        return None
