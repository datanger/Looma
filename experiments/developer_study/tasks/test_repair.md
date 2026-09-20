# Developer Study Task B — Test / Analyze / Repair Loop

Implement a bounded repair workflow using the assigned programming model.

## Functional specification

The application receives a repository path and may perform at most three repair
rounds.

For each round:

1. run the deterministic test command;
2. persist the test result so a resume does not repeat an already completed test
   step unnecessarily;
3. ask the semantic Agent to analyze the failure and return a structured repair
   decision;
4. validate the Agent result;
5. if tests are already acceptable, finish;
6. otherwise apply the proposed patch through the supplied deterministic patch
   helper;
7. continue to the next round.

The final artifact must contain:

- top-level status;
- number of test rounds;
- last test result;
- repair decisions;
- final acceptance result.

The supplied business helpers, schemas, fixtures, and acceptance tests must not
be modified.

## Completion

Stop the timer when all acceptance tests pass or after 45 minutes. Record all
documentation lookups and debug/test iterations using the study form.
