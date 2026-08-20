import asyncio

import pytest

from backend.application.chat_runs.service import ChatRunService


async def _collect(stream):
    return [item async for item in stream]


class RuntimeGateway:
    def __init__(self):
        self.stream_kwargs = None
        self.resume_kwargs = None

    async def _events(self, event):
        yield event

    def stream(self, message, **kwargs):
        self.stream_kwargs = {"message": message, **kwargs}
        return self._events({"kind": "answer", "text": "hello"})

    async def claim_approval(self, **kwargs):
        return ("workflow", "lease")

    def resume(self, **kwargs):
        self.resume_kwargs = kwargs
        return self._events({"kind": "answer", "text": "created"})


def test_chat_run_service_delegates_immutable_turn_settings() -> None:
    gateway = RuntimeGateway()
    service = ChatRunService(gateway)

    events = asyncio.run(_collect(service.stream(
        "hello",
        thread_id="thread-1",
        thinking=True,
        effort="high",
        web_search_enabled=False,
    )))

    assert events == [{"kind": "answer", "text": "hello"}]
    assert gateway.stream_kwargs == {
        "message": "hello",
        "thread_id": "thread-1",
        "thinking": True,
        "effort": "high",
        "web_search_enabled": False,
    }


def test_chat_run_service_rejects_empty_other_feedback_before_runtime() -> None:
    service = ChatRunService(RuntimeGateway())

    with pytest.raises(ValueError, match="non-empty feedback"):
        service.resume(
            thread_id="thread-1",
            interrupt_id="approval-1",
            decision="other",
            message="  ",
            claim=("workflow", "lease"),
        )


def test_chat_run_service_passes_claim_to_resume_gateway() -> None:
    gateway = RuntimeGateway()
    service = ChatRunService(gateway)

    events = asyncio.run(_collect(service.resume(
        thread_id="thread-1",
        interrupt_id="approval-1",
        decision="approve",
        claim=("workflow", "lease"),
    )))

    assert events[0]["text"] == "created"
    assert gateway.resume_kwargs["claim"] == ("workflow", "lease")
