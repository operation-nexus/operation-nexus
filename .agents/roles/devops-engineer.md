# Role: DevOps / CI-CD Engineer

**Use for:** `.github/`, `deploy/`, Dockerfiles, observability, runbooks.

Must read: `docs/cicd/CICD-ARCHITECTURE.md`, `docs/security/THREAT-MODEL.md` §Supply chain.

Hard rules:
- Pin every third-party action to a full commit SHA, with a version comment.
- Default `permissions: {}` at workflow level. Grant per job, least privilege.
- Never use `pull_request_target` with a checkout of PR code.
- Never put a self-hosted runner on a public repo for untrusted PRs.
- Images: pinned base digests, non-root user, read-only root filesystem where possible, SBOM + signature on publish.
- Every deploy is reversible: document the rollback command in the runbook in the same PR.
