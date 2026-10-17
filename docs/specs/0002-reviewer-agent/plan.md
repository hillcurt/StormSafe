# Plan for spec 0002 — Reviewer agent

**Spec:** `docs/specs/0002-reviewer-agent/spec.md`
**Status:** approved

## Approach
The review rules live in one shared file, `REVIEW.md`. The `reviewer` persona reads it and applies it, with read-only tools only. In CI, a workflow saves the PR diff and description to files, has the main agent hand the review to `reviewer`, and posts the result as one comment. The main agent's only extra permission is `gh pr comment`; the reviewer never gets write access.

## Files
| File | Create / change | Why |
| --- | --- | --- |
| `REVIEW.md` | Create | Review passes and the blocking/suggestion boundary |
| `.claude/agents/reviewer.md` | Create | Persona: `Read`, `Grep`, `Glob` only; model `sonnet`; 30 turns |
| `.github/workflows/ai-review.yml` | Create | Advisory review on each non-draft PR to `trunk` |
| `tests/unit/test_agents.py` | Create | Guards on the persona and workflow |
| `.gitignore` | Change | Ignore `.review/` scratch files |
| `docs/sdlc.md`, `docs/roadmap.md` | Change | Point Track B step 5 at the reviewer; next actions |

## Tests (written first)
1. `REVIEW.md` defines all seven passes and both severities → `test_review_md_defines_passes_and_severity`
2. The persona reads `REVIEW.md`, covers the output format, and says it is advisory → `test_reviewer_follows_review_md`
3. The persona is read-only → `test_reviewer_is_read_only`
4. The workflow is pinned by commit, uses `sonnet`, has `--max-turns 30` and a timeout, skips drafts, and has no `contents: write` → `test_ai_review_workflow_is_bounded_and_pinned`
5. The workflow posts a note when the review fails → covered by test 4

## PR slicing
One PR.

## Risks and open questions
- The workflow can't be exercised until the owner adds `CLAUDE_CODE_OAUTH_TOKEN` and installs the Claude GitHub App. The first real run is the next PR after this one merges.
- Action pinned to the commit of `anthropics/claude-code-action` v1.0.213.
