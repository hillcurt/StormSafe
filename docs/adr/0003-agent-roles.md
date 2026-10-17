# ADR 0003 — Agent roles (subagent personas)

**Status:** accepted
**Date:** 2026-10-17

## Context
Most StormSafe code is written by a coding agent following `CLAUDE.md`. Some checks are better done by a separate agent with a narrow job: an agent reviewing its own work tends to approve it, and a reviewer doesn't need permission to edit anything. Claude Code supports this with subagents defined as Markdown files in `.claude/agents/`, each with its own instructions and tool allowlist.

## Decision
- **Roles are code.** Each persona is a file in `.claude/agents/`, added and changed through a spec and a PR like any other code.
- **A persona must replace a check the owner would otherwise do by hand.** No persona without that.
- **Least privilege.** Each persona lists only the tools it needs. Review personas get no edit, write, or push tools.
- **`CLAUDE.md` always wins.** Personas inherit its guardrails; nothing in a persona file can grant what `CLAUDE.md` reserves for the human.
- **Reviews are advisory.** A persona can comment and recommend; it never approves, merges, or changes a gate. The owner's merge is the decision.
- **No implementer persona.** The main agent following `CLAUDE.md` already fills that role.

**Roster:**

| Persona | Added | Job |
| --- | --- | --- |
| `reviewer` | Spec 0002 | Reviews every PR against its spec, `CLAUDE.md`, and the ADRs; runs in CI on each PR |
| `infra-reviewer` | With the first infrastructure spec | Manifests, Dockerfiles, workflows: pinned versions, secrets, permissions, drift from the infrastructure ADRs |
| `data-auditor` | Phase 2 | Ingestion and labels vs. the data contract: time zones, label windows, leakage at the data level |
| `ml-evaluator` | Phases 3–4 | Time-based splits, leakage, calibration, the recall gate, before Gate 4 sign-off |

## Consequences
- Review findings are on the PR record, which shows the process working.
- CI runs that call a model cost tokens; each persona's workflow caps turns and runtime.
- Changing a persona's tools or permissions is human-only (added to `CLAUDE.md`).

## Alternatives considered
- **One general agent for everything:** it would review its own work.
- **Many personas up front:** coordination overhead before the phases that need them exist.
- **AI review as a required, blocking check:** a model's opinion shouldn't block a merge on its own; revisit once its findings have a track record.
