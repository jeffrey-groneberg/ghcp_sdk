# `.copilot/` — project-level Copilot CLI configuration

This folder bundles **reusable skills** with the repo so anyone working on
`ghcp_sdk` can install them locally for their own [GitHub Copilot CLI][cli]
sessions. They are mirrored from the maintainer's user-level
`~/.copilot/skills/` directory and are the same skills that were used to
build the workshop deck under `docs/` and the example walkthroughs under
`examples/`.

[cli]: https://docs.github.com/copilot/copilot-in-the-cli

## Skills included (`./skills/`)

| Skill              | What it does                                                                                                       |
| ------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `frontend-slides`  | Build zero-dependency, animation-rich HTML presentations. Used to author `docs/index.html` in this repo.           |
| `doc-coauthoring`  | Structured workflow for co-authoring documentation (proposals, specs, decision docs).                              |
| `excalidraw`       | Generate hand-drawn Excalidraw JSON diagrams (architecture, flow, sequence).                                       |

Each skill has its own `SKILL.md` describing the workflow it provides.
`frontend-slides` also ships its own `LICENSE` (MIT) and supporting
`scripts/` for deploy + PDF export.

## Install locally so Copilot CLI picks them up

Copilot CLI auto-discovers skills from `~/.copilot/skills/`. To make these
project-local skills available globally, mirror them into your user folder:

**PowerShell (Windows):**

```powershell
robocopy .\.copilot\skills $HOME\.copilot\skills /MIR /XD plugins
```

**Bash (macOS / Linux):**

```bash
mkdir -p ~/.copilot/skills
cp -R .copilot/skills/. ~/.copilot/skills/
```

No restart required — Copilot CLI re-scans on each invocation.

## Why ship skills in the repo?

- **Reproducibility** — anyone can rebuild the deck or the walkthroughs the
  same way the maintainer did, without hunting for which skill was used.
- **Onboarding** — new contributors get the same Copilot tooling as the
  maintainer with a single copy command.
- **Versioning** — the skill behaviour for this repo is pinned at the
  commit you check out, so changes upstream don't silently change how
  Copilot helps here.

## Provenance

Skills were copied from `C:\Users\Inkvi\.copilot\skills` (the maintainer's
user-level Copilot configuration) on 2026-05-26. The Claude-plugin stub
files under `plugins/` were skipped because they're relative-path pointers
that only resolve inside their original layout.
