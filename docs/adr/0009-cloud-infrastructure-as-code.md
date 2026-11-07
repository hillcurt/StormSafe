# ADR 0009 — Cloud infrastructure as code

**Status:** accepted
**Date:** 2026-11-07

## Context
ADR 0008 puts StormSafe's data and model artifacts in AWS: a private S3 bucket, IAM identities with scoped access, lifecycle rules, and a budget alert. Resources created by clicking through the console can't be reviewed, can't be rebuilt from scratch, and drift silently. The rest of the project already runs on declarative config in git: the `kind` cluster config and the Argo CD manifests (ADR 0007). The owner's rule is that anything in AWS is set up through IaC.

Constraints:
- The repo is public, so private values (bucket names, account ID, alert email) and IaC state stay out of it (ADR 0004).
- Applying changes and handling credentials are human-only (`CLAUDE.md`).
- CI holds no cloud credentials (ADR 0007, ADR 0008).

## Decision
- **Every AWS resource is defined in Terraform** under `infra/aws/`. The only exceptions are the root of trust, which Terraform can't create for itself:
  - the AWS account and its root MFA;
  - the owner's admin identity (an IAM Identity Center user), which runs Terraform;
  - access keys, as below.
- **Two stacks:**
  - `infra/aws/bootstrap/` creates the state bucket: private, versioned, encrypted, with `prevent_destroy`. It is first applied with local state, then moved into the bucket it created (`terraform init -migrate-state`).
  - `infra/aws/main/` holds everything in ADR 0008: the data bucket and its settings, IAM roles, users and policies, and the budget alert.
- **State:** the S3 backend, with `encrypt = true` and native S3 locking (`use_lockfile = true`; no DynamoDB table). State holds names and ARNs, so it stays private like the data.
- **Private values stay out of git.** The bucket names, account ID, and alert email go in a git-ignored `terraform.tfvars` and `backend.hcl` (partial backend config). Committed `*.example` files list the keys with blank values, like `.env.example`.
- **No secrets in state.**
  - Terraform creates the cluster's read-only IAM user and its policy. The owner creates that user's access key by hand and puts it in the cluster Secret, so the key never lands in Terraform state.
  - The owner's day-to-day data access is an IAM role he assumes through his SSO session, so no long-lived keys sit on the laptop.
- **Pinned and checked:** `required_version` and the AWS provider version are pinned, and `.terraform.lock.hcl` is committed. `ci.yml` runs `terraform fmt -check` and `terraform validate` (`-backend=false`). Neither needs credentials.
- **Who does what:** the agent writes Terraform in PRs. The owner runs `plan` and `apply` and handles state and credentials. Before merging, the owner posts the plan's summary line (counts only, no values) on the PR. A console change is drift: the fix is a code change, or reverting the console change.
- The data bucket also gets `prevent_destroy`, so a bad plan can't delete the snapshots.

## Consequences
- AWS setup is reviewable in PRs and rebuildable from the repo plus the private tfvars.
- New tool and state to manage. The state bucket is the one thing that must never be deleted. The runbook (Phase 6) covers recovering it and moving state.
- `CLAUDE.md` gains a guardrail row for `infra/`, and its infra-reviewer rule covers `infra/`. The `infra-reviewer` persona doesn't check Terraform yet; widening its scope is on the roadmap.
- A `terraform plan` in CI would need credentials. It waits for a GitHub OIDC role, decided in the same later spec as `train.yml` on hosted runners (ADR 0008).

## Alternatives considered
- **Console setup ("click-ops"):** rejected by the owner. Unreviewable, can't be rebuilt, and drifts.
- **OpenTofu:** an open-source fork of Terraform with the same CLI and language, plus client-side state encryption. A sound choice, and switching later is cheap. Terraform appears in more ML platform job postings, which is what this project is meant to show.
- **CloudFormation or AWS CDK:** no state bucket to manage, since AWS holds the state. AWS-only, and less transferable.
- **Pulumi:** infra in Python, which fits the codebase, but it is less common on platform teams and adds an SDK and a state service.
- **One stack, with state in a hand-made bucket:** simpler, but it breaks "everything in AWS through IaC" for the most important bucket.
