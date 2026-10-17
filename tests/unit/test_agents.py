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
    assert re.search(r"anthropics/claude-code-action@[0-9a-f]{40}\b", wf), "pin the action by commit"
    assert "timeout-minutes:" in wf
    assert "--max-turns 30" in wf
    assert "--model sonnet" in wf
    assert "contents: write" not in wf
    assert "draft == false" in wf
    assert "if: failure()" in wf, "post a note when the review does not finish"
