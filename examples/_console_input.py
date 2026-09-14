"""Cancellable, serialized terminal input for the interactive examples."""

import asyncio
import queue
import threading


_INPUT_LOCK: asyncio.Lock | None = None
_INPUT_CLOSED = False


def reset_input_state() -> None:
    """Reset process-local state for tests or a fresh interactive workflow."""
    global _INPUT_LOCK, _INPUT_CLOSED
    _INPUT_LOCK = None
    _INPUT_CLOSED = False


def _input_lock() -> asyncio.Lock:
    global _INPUT_LOCK
    if _INPUT_LOCK is None:
        _INPUT_LOCK = asyncio.Lock()
    return _INPUT_LOCK


async def read_answer(prompt: str, *, timeout: float) -> str:
    """Read stdin without blocking the event loop; fail closed after interruption."""
    global _INPUT_CLOSED
    async with _input_lock():
        if _INPUT_CLOSED:
            raise EOFError("Console input is unavailable; restart the example.")

        answers: queue.Queue[str | BaseException] = queue.Queue()

        def read() -> None:
            try:
                answers.put(input(prompt))
            except (EOFError, OSError) as exc:
                answers.put(exc)

        threading.Thread(target=read, daemon=True).start()
        try:
            async with asyncio.timeout(timeout):
                while answers.empty():
                    await asyncio.sleep(0.05)
            answer = answers.get_nowait()
            if isinstance(answer, BaseException):
                raise answer
            return answer.strip()
        except (TimeoutError, EOFError, OSError, asyncio.CancelledError):
            # A blocking stdin read cannot be cancelled safely. Do not start a
            # competing reader in this process after the wait is interrupted.
            _INPUT_CLOSED = True
            raise
