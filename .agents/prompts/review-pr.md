# Prompt: Review a PR

```
Act as .agents/roles/reviewer.md. Review the diff of <branch|PR#> against main.
Report: (1) correctness bugs with file:line and the failure scenario, (2) security findings,
(3) missing tests for stated acceptance criteria, (4) spec drift. Rank by severity.
Skip style issues that the linters catch. Say explicitly if you found nothing in a category.
```
