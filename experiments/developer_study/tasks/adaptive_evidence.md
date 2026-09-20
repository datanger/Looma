# Developer Study Task A — Adaptive Evidence Workflow

Implement the application specified by
`experiments/workloads/adaptive_evidence/SPEC.md` using the framework assigned
for this session.

## Required behavior

The implementation must:

1. load the supplied scenario;
2. obtain semantic evidence;
3. run deterministic evidence validation;
4. retry up to three rounds when evidence is insufficient;
5. obtain semantic analysis;
6. run deterministic analysis validation;
7. retry up to three rounds when analysis is rejected;
8. write the required final JSON artifact;
9. pass the supplied black-box acceptance tests.

Shared business code, fixtures, validators, and task text may not be modified.

## Allowed work

- framework documentation;
- local IDE/editor;
- normal debugging;
- the same predeclared coding assistant policy for every method condition.

## Completion

Stop the timer when all acceptance tests pass. If the 45-minute cap is reached,
stop and record `tests_passed=false`.

Do not optimize for SLOC during the session; write the implementation you would
normally consider maintainable.
