# 16 · Skills

[Source](16_skills.py) · [Skill](skills/pr-description/SKILL.md) · [Skills](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/features/skills.md)

A skill is a folder with a `SKILL.md` file: instructions the agent loads when
it needs them. This one writes pull request descriptions in a fixed format.

## Run it

```bash
python examples/16_skills.py
```

## How it works

```python
session = await client.create_session(
    skills={"directories": [str(SKILLS)]},
    tools={"available_tools": ["builtin:skill"]},  # the tool that loads a skill
    events={"on_event": on_event})
```

- `skills.directories` points to `examples/skills`. The runtime finds
  `pr-description/SKILL.md` and shows the model its name and description.
- The model loads a skill's instructions with the built-in `skill` tool, so the
  allow-list includes it.
- The `skill.invoked` event (`SkillInvokedData`) shows which skill ran.

## Output from a live run

````text
[skill] pr-description invoked
## Why
`add()` in `calc.py` subtracted its arguments (`a - b`) instead of adding them.

## What changed
- `add()` in `calc.py` now returns `a + b`.

## How to test
```
pytest -k test_add
```
````

## Try this next

- Add `examples/skills/commit-message/SKILL.md` and ask for a commit message.
