# ADR 0009 — Cloud infrastructure as code

**Status:** accepted
**Date:** 2026-11-07

## Context
ADR 0008 puts StormSafe's data and model artifacts in AWS: a private S3 bucket, IAM identities with scoped access, lifecycle rules, and a budget alert. Resources created by clicking through the console can't be reviewed, can't be rebuilt from scratch, and drift silently. Changes applied from a laptop leave no record of what ran or who approved it. The rest of the project already runs on declarative config in git and reviewed PRs (ADR 0002, ADR 0007).

The owner's rules:
- Anything in AWS is set up through IaC.
- Running `plan` and `apply` is part of the GitHub Actions workflows.

Constraints:
- The repo is public, so its Actions logs are public too. Private values (bucket names, account ID, alert email) and IaC state must never appear in the repo or a log (ADR 0004).
- Credentials are human-only (`CLAUDE.md`).
- No long-lived cloud keys are stored in GitHub.

## Decision
- **Every AWS resource is defined in Terraform** under `infra/aws/`. The only exceptions are the root of trust, which Terraform can't create for itself:
  - the AWS account and its root MFA;
  - the owner's admin identity (an IAM Identity Center user);
  - the cluster user's access key, as below.
- **Two stacks:**
  - `infra/aws/bootstrap/` holds what the workflow needs before it can run, plus its own trust:
    - the state bucket: private, versioned, encrypted, `prevent_destroy`;
    - the GitHub OIDC identity provider;
    - the two workflow roles described below.

    The owner applies it **locally**, once and whenever it changes. Its state is first local, then moved into the state bucket it created (`terraform init -migrate-state`). It stays out of the workflow because a workflow that can edit its own trust policy can grant itself anything.
  - `infra/aws/main/` holds everything in ADR 0008: the data bucket and its settings, the data-access IAM role and user, and the budget alert. **Only the workflow applies it.**
- **Workflow:** `infra.yml`.
  - **On a PR that touches `infra/`:** `fmt -check`, `validate`, and `plan`. It posts a summary of the plan on the PR: counts of resources to add, change, and destroy, and resource addresses, with no attribute values.
  - **On a push to `trunk` that touches `infra/aws/main/`:** a job in the `aws` GitHub environment, which needs the owner's approval, plans again and applies that plan. The PR plan is a preview only; what runs is the plan made against `trunk`, after approval.
  - **Nightly, and on manual dispatch:** `plan -detailed-exitcode` as a drift check. Drift fails the job, and the fix is a PR. A console change is drift.
  - PRs from forks get no OIDC token, and their plan job is skipped.
- **Credentials: GitHub OIDC, no stored keys.** Both roles trust only `token.actions.githubusercontent.com` for this repo:
  - **Plan role:** read-only on the `main` stack's resources. It can read state and write the state lock file. Trusted for PRs from this repo and for the drift check.
  - **Apply role:** what `main` needs to change its resources. Trusted only for jobs in the `aws` environment on `trunk` (`sub` = `repo:hillcurt/StormSafe:environment:aws`).
- **State:** the S3 backend, with `encrypt = true` and native S3 locking (`use_lockfile = true`; no DynamoDB table). State holds names and ARNs, so it stays private like the data.
- **Private values stay out of git and out of logs.**
  - **In the workflow:** the bucket names, account ID, and alert email are GitHub Actions secrets, which GitHub masks wherever they appear in a log. The workflow passes them as `TF_VAR_*` variables and backend config.
  - **Plan output:** the full plan is never printed or uploaded as an artifact; only the summary is.
  - **For the local bootstrap:** the same values live in a git-ignored `terraform.tfvars` and `backend.hcl`. Committed `*.example` files list the keys with blank values, like `.env.example`.
- **No secrets in state.**
  - Terraform creates the cluster's read-only IAM user and its policy. The owner creates that user's access key by hand and puts it in the cluster Secret.
  - The owner's day-to-day data access is an IAM role he assumes through his SSO session, so no long-lived keys sit on the laptop.
- **Pinned:**
  - `required_version` and the AWS provider version are pinned, and `.terraform.lock.hcl` is committed.
  - The `setup-terraform` and AWS credentials actions are pinned by commit.
- **Who does what** (`CLAUDE.md`):
  - The agent writes Terraform and `infra.yml` in PRs.
  - Human-accepted: any new or widened workflow `permissions:` (`infra.yml` needs `id-token: write`), any change to an IAM trust policy, and any change to the workflow roles' permissions.
  - Human-only: approving the `aws` environment (the apply), the local bootstrap apply, any state operation, and the GitHub secrets.
- The data bucket also gets `prevent_destroy`, so a bad plan can't delete the snapshots.

## Consequences
- Every change to AWS is a reviewed PR, a visible plan, an approved apply, and a run log on `trunk`. It can be rebuilt from the repo plus the secrets.
- The drift check catches console changes within a day.
- Approving the `aws` environment is the one manual step per apply, which matches "no auto-merge" (`docs/sdlc.md`).
- **The bootstrap stack is the trust boundary** and is applied by hand. Mistakes there (an over-broad trust condition) give the workflow too much power, so it gets the strictest review. The state bucket must never be deleted; the runbook (Phase 6) covers recovering it.
- Masking depends on GitHub's secret masking. Error messages that contain a value are masked as well, but `infra-reviewer` checks that `infra.yml` never writes plan files, `terraform show` output, or state anywhere public.
- The same OIDC pattern is ready for `train.yml` on hosted runners (ADR 0008).
- `CLAUDE.md` gains a guardrail row for `infra/` and `infra.yml`, and its infra-reviewer rule covers `infra/`. The `infra-reviewer` persona doesn't check Terraform yet; widening its scope is on the roadmap.

## Alternatives considered
- **Console setup ("click-ops"):** rejected by the owner. Unreviewable, can't be rebuilt, and drifts.
- **Plan and apply from the owner's laptop:** no shared record of what ran. Rejected by the owner.
- **Auto-apply on merge without approval:** fastest, but a merged mistake reaches AWS with no last look at the `trunk` plan.
- **Applying the PR's saved plan file after merge:** needs the plan file stored as an artifact, and artifacts on a public repo are downloadable. Planning again on `trunk` is simpler and plans the code that actually merged.
- **Access keys stored as GitHub secrets:** long-lived, broad, and they must be rotated. OIDC gives short-lived credentials scoped by repo and environment.
- **HCP Terraform (Terraform Cloud) or Atlantis:** private plan logs and PR-driven applies. They add an account or a server to run, and move the workflow out of the repo's Actions, where the rest of CI lives.
- **OpenTofu:** an open-source fork of Terraform with the same CLI and language, plus client-side state encryption. A sound choice, and switching later is cheap. Terraform appears in more ML platform job postings, which is what this project is meant to show.
- **CloudFormation or AWS CDK:** no state bucket to manage, since AWS holds the state. AWS-only, and less transferable.
- **Pulumi:** infra in Python, which fits the codebase, but it is less common on platform teams and adds an SDK and a state service.
