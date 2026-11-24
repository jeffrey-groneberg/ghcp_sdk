# 15 · Cost

Deck slide 30 · [Source](15_cost.py) · [Session limits](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/features/session-limits.md) · [Usage and billing](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/features/usage-and-billing.md)

Cap what a session may spend, and watch its cost per model call and in total.

## Run it

```bash
python examples/15_cost.py
```

## How it works

```python
session = await client.create_session(
    tools={"available_tools": []},
    execution={"limits": {"max_ai_credits": 30}},  # soft cap; the runtime's minimum is 30
    events={"on_event": on_event})
...
metrics = await session.rpc.usage.get_metrics()
```

- `max_ai_credits` is a soft cap: the runtime checks it after each model call,
  so one answer can go past it before the next call is blocked. Runtime 1.0.114
  rejects caps below 30 ("Minimum session limit is 30 AI credits").
- Every model call emits an `assistant.usage` event (`AssistantUsageData`) with
  its model and tokens. It's delivered live and not replayed on resume.
- `session.rpc.usage.get_metrics()` returns the session's totals, including
  `total_nano_aiu`. Like the SDK docs, the example divides it by 1e9 to show
  AI credits; GitHub's billing is authoritative. One GitHub AI Credit is $0.01.
- `max_ai_credits` (`SessionLimitsConfig`) and the `UsageApi` group
  (`session.rpc.usage`) are experimental in SDK 2.0.1.

## Output from a live run

```text
[assistant.usage] claude-sonnet-5.5: 4480 tokens in, 64 out, AI credits: 0.82236
Capping an agent's spending prevents runaway loops, bugs, or misjudged tasks from racking up unbounded costs, keeping usage predictable and limiting the damage from mistakes.
session total: 0.8224 AI credits (complete), premium request cost: 1.0
```

## Try this next

- Decide in code what happens when the cap is reached: register interest in
  `session_limits_exhausted.requested` with
  `session.rpc.event_log.register_interest` and answer through
  `session.rpc.ui.handle_pending_session_limits_exhausted`, as the session
  limits guide describes.
