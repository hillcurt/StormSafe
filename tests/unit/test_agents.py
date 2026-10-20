"""Acceptance tests for spec 0002: review rules exist and personas stay least-privilege."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / ".claude" / "agents"
AI_REVIEW = ROOT / ".github" / "workflows" / "ai-review.yml"

READ_ONLY_TOOLS = {"Read", "Grep", "Glob"}
PASSES = (
    "spec and plan",
    "acceptance criteria",
    "tests",
    "human-only",
    "adr",
    "security and privacy",
    "scope",
)


def frontmatter(path: Path) -> dict[str, str]:
    """Parse the simple `key: value` frontmatter of a persona file."""
    match = re.match(r"^---\n(.*?)\n---\n", path.read_text(), re.DOTALL)
    assert match, f"{path.name} has no frontmatter"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_review_md_defines_passes_and_severity() -> None:
    text = (ROOT / "REVIEW.md").read_text().lower()
    for item in PASSES:
        assert item in text, f"REVIEW.md does not define the {item!r} pass"
    assert "blocking" in text and "suggestion" in text


def test_reviewer_follows_review_md() -> None:
    body = (AGENTS / "reviewer.md").read_text()
    assert "REVIEW.md" in body
    assert "advisory" in body.lower()
    assert "**Blocking**" in body and "**Suggestions**" in body


def test_reviewer_is_read_only() -> None:
    """Loosening the reviewer's tools must fail CI (ADR 0003: a human-only change)."""
    fields = frontmatter(AGENTS / "reviewer.md")
    assert fields["name"] == "reviewer"
    tools = {t.strip() for t in fields.get("tools", "").split(",") if t.strip()}
    assert tools, "reviewer must declare an explicit tool allowlist"
    assert tools <= READ_ONLY_TOOLS, f"reviewer has non-read-only tools: {tools - READ_ONLY_TOOLS}"


def test_ai_review_workflow_is_bounded_and_pinned() -> None:
    wf = AI_REVIEW.read_text()
    pinned = re.search(r"anthropics/claude-code-action@[0-9a-f]{40}\b", wf)
    assert pinned, "pin the action by commit"
    assert "timeout-minutes:" in wf
    assert "--max-turns 30" in wf
    assert "--model sonnet" in wf
    assert "contents: write" not in wf
    assert "draft == false" in wf
    assert "if: failure()" in wf, "post a note when the review does not finish"


def test_ai_review_notes_a_skipped_review() -> None:
    """A review the action skips (e.g. a PR that changes this workflow) must not pass silently."""
    wf = AI_REVIEW.read_text()
    step = re.search(r"- name: Note a skipped review\n(.*?)(?=\n      - |\Z)", wf, re.DOTALL)
    assert step, "add a step that notes a skipped review"
    assert "if: success()" in step.group(1)
    assert "[ ! -s .review/comment.md ]" in step.group(1)
    assert "gh pr comment" in step.group(1)


def test_workflows_pin_checkout_by_commit() -> None:
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = wf.read_text()
        assert "actions/checkout@v4" not in text, f"{wf.name}: checkout v4 uses deprecated Node 20"
        for ref in re.findall(r"actions/checkout@(\S+)", text):
            assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{wf.name}: pin actions/checkout by commit"


def test_ci_review_runs_the_persona_read_only() -> None:
    """In CI the model runs as the reviewer itself: persona instructions, read-only tools."""
    wf = AI_REVIEW.read_text()
    assert ".claude/agents/reviewer.md" in wf, "the CI prompt must load the persona's instructions"
    assert "Agent(" not in wf, "no delegation step: the model is the reviewer"
    allowed = re.search(r'--allowedTools "([^"]*)"', wf)
    assert allowed, "declare the allowed tools"
    tools = {t.strip() for t in allowed.group(1).split(",") if t.strip()}
    persona = {t.strip() for t in frontmatter(AGENTS / "reviewer.md")["tools"].split(",")}
    assert tools == persona, f"CI tools {tools} must match the persona's {persona}"
    denied = re.search(r'--disallowedTools "([^"]*)"', wf)
    assert denied, "explicitly deny write and shell tools"
    for tool in ("Bash", "Edit", "Write"):
        assert tool in denied.group(1), f"deny {tool}"


def test_ci_review_is_posted_by_the_workflow() -> None:
    """The workflow, not the model, posts the review, and only if it looks like one."""
    wf = AI_REVIEW.read_text()
    assert "steps.review.outputs.execution_file" in wf
    assert "## AI review (advisory)" in wf
    assert 'gh pr comment "$PR" --body-file .review/comment.md' in wf


def test_earlier_findings_must_be_answered() -> None:
    """An AI finding that is neither fixed nor answered resurfaces on the next review."""
    review = (ROOT / "REVIEW.md").read_text().lower()
    assert "earlier findings" in review, "REVIEW.md needs a pass for earlier AI findings"
    template = (ROOT / ".github" / "pull_request_template.md").read_text()
    assert "## Review findings" in template, "the PR template needs a place to answer findings"
    persona = (AGENTS / "reviewer.md").read_text()
    assert ".review/comments.md" in persona, "the reviewer must read earlier PR comments"
    wf = AI_REVIEW.read_text()
    assert "> .review/comments.md" in wf, "the workflow must save PR comments for the reviewer"
