# REVIEW.md — how StormSafe changes are reviewed

One definition of a good review, shared by the owner and the `reviewer` persona (ADR 0003). Reviews are **advisory**: findings inform the owner's merge, and never approve or block a PR on their own.

StormSafe is a safety system: a missed lightning strike is far worse than an unneeded pool closure. Review with that in mind.

## Passes, in order

1. **Spec and plan.** The PR names its approved spec (`docs/specs/NNNN-*/spec.md`). `plan.md` exists beside it and matches what was built, or was updated in the same commit as any departure. A small fix with no spec is acceptable if the PR says why.
2. **Acceptance criteria.** Each criterion in the spec is met and encoded by a test or CI check. Name any criterion without one.
3. **Tests.** Tests were written before the implementation. No existing test was deleted, skipped, or loosened (removed assertions, widened tolerances, new `skip` or `xfail`).
4. **Human-only areas.** Anything the diff touches from the "Human only" column of `CLAUDE.md` is flagged at the top of the PR description.
5. **ADR conflicts.** Nothing contradicts an accepted ADR. Examples: deploying `latest`, unpinned versions, long-lived branches, a persona gaining write tools.
6. **Security and privacy.** No keys, tokens, passwords, kubeconfigs, or Secret manifests with real values. No site location values (ADR 0004). No `.env` file (`.env.example` is fine). No build artifacts or caches (`.pyc`, `__pycache__/`, `data/`).
7. **Scope.** Nothing outside the spec's scope, and nothing from its out-of-scope list.
8. **Earlier findings.** Every finding from an earlier AI review on this PR is either fixed in the diff or answered, in the PR description's "Review findings" section or a PR comment, with a reason. A finding that is neither is **blocking**: name it and the review it came from. A declined finding with a reason is answered; don't argue it again unless the reason is wrong.

## Severity

- **Blocking:** fails one of the passes above. The PR should not merge until it is fixed or the owner records why not.
- **Suggestion:** an improvement that fails no pass (naming, structure, clearer docs). Optional.
- Not worth raising: style the formatter already enforces, and personal preference.

## Feeding back
When the same finding comes up twice, add the rule to `CLAUDE.md` (or a test or hook) so it stops recurring.
