# Spec 0002 — Reviewer agent

**Status:** done
**Phase:** 0

## Goal
A read-only `reviewer` persona (ADR 0003) that reviews each PR against `REVIEW.md`, its spec and plan, `CLAUDE.md`, and the ADRs. It is usable two ways: locally in a Claude Code session before a PR is opened, and automatically on every PR in CI, posting its findings as one PR comment.

## Inputs / outputs
- Creates:
  - `REVIEW.md` at the repo root: the review passes and what counts as **blocking** versus a **suggestion**. One shared definition for humans and agents.
  - `.claude/agents/reviewer.md`: the persona. Its tools are limited to reading and searching the repo; it has no edit, write, shell, or push tools. It reads the PR diff from a file.
  - `.github/workflows/ai-review.yml`: runs the reviewer on PRs to `trunk` using Anthropic's Claude Code GitHub Action (`anthropics/claude-code-action`, pinned by commit), and posts one comment.
- Updates `docs/sdlc.md` (Track B step 5) to point at `REVIEW.md`, the persona, and the workflow.

## Review passes (defined in `REVIEW.md`)
1. **Spec and plan:** the PR names its approved spec; `plan.md` exists and matches what was built, or was updated in the same commit as any departure.
2. **Acceptance criteria:** each is met and encoded by a test or CI check.
3. **Tests:** written first; none deleted, skipped, or loosened.
4. **Human-only areas:** anything from the `CLAUDE.md` "Human only" column is flagged at the top of the PR description.
5. **ADR conflicts:** nothing contradicts an accepted ADR.
6. **Security and privacy:** no secrets, credentials, or site location values (ADR 0004); no committed build artifacts.
7. **Scope:** nothing outside the spec, and nothing from its out-of-scope list.

Output: **blocking** findings (each fails a pass), then **suggestions**, each with a file and line where possible, then a one-line summary. The comment says the review is advisory.

## Acceptance criteria
- [ ] `REVIEW.md` defines the passes above and the blocking/suggestion boundary
- [ ] The persona reads `REVIEW.md` and covers every pass and the output format
- [ ] The persona's frontmatter grants only read-only tools (test, so loosening it fails CI)
- [ ] `ai-review.yml` runs on `pull_request` (opened, synchronize, reopened, ready_for_review) to `trunk`, skips drafts, and posts a single comment
- [ ] The workflow uses least-privilege permissions, an action pinned by commit, model `sonnet`, a 30-turn cap, and a job timeout (test)
- [ ] If the review does not finish, the workflow posts a short note saying so
- [ ] The workflow is not a required status check (advisory, per ADR 0003)

## Out of scope
- `infra-reviewer`, `data-auditor`, `ml-evaluator` (later specs)
- Making the AI review a required or blocking check
- Any automated approval or merge

## Human-only touchpoints
- **Credentials:** the owner installs the Claude GitHub App and adds the `CLAUDE_CODE_OAUTH_TOKEN` secret (from `claude setup-token`). The agent never handles it.
- **The persona's tool list** (ADR 0003).

## Open questions
- None
