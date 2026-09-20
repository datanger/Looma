# RQ1 — Developer effort and usability study

## Motivation

Static source metrics can show implementation size and framework-specific
surface area, but they do not establish that AEP is faster or easier for humans
to develop with. Any paper claim about **development time** or **usability**
therefore requires a prospective human study.

## Research questions

1. Does AEP reduce time-to-working implementation for equivalent Agent
   applications?
2. Does AEP reduce debugging/documentation effort?
3. Do developers perceive AEP as more usable for these tasks?

## Design

Use a within-subject study with the four primary programming conditions:

- Direct SDK / hand-written loop;
- LangGraph;
- Microsoft Agent Framework;
- Looma / AEP.

A balanced Latin square controls order effects. Each participant receives the
same methods but in a counterbalanced order. Task instances are rotated so that
a participant does not repeatedly solve the exact same scenario under every
method.

The repository provides `make_assignments.py` to generate the schedule.

## Participants

Target at least 16 completed participants if feasible, preferably 20–24, with
documented Python and Agent-development experience. Record experience bands but
do not collect names or employer-identifying information in the research
dataset.

If the work is conducted under an institution/company research process, obtain
the required ethics/privacy approval before collecting participant data.

## Tasks

Two task families are initially specified:

- Task A: Adaptive Evidence Workflow;
- Task B: Test / Analyze / Repair loop.

Each has black-box acceptance tests and a 45-minute cap.

## Environment controls

Freeze:

- hardware class where practical;
- Python version;
- framework versions;
- documentation snapshot/version;
- starting repository commit;
- task instructions;
- available shared helpers;
- coding-assistant policy.

If a coding assistant is allowed, the same assistance policy must be used for
all programming-model conditions and its use must be reported. Otherwise the
study measures "framework + different assistance", which is confounded.

## Primary metrics

Per session:

- elapsed seconds to all acceptance tests passing;
- completion within the time cap;
- implementation SLOC;
- debug/test iterations;
- documentation lookups;
- external-help events;
- framework/runtime errors;
- SUS usability score (10-item System Usability Scale).

SLOC remains a secondary engineering metric; elapsed time is the direct
development-time measure.

## SUS collection

After each method condition, collect the standard 10 SUS responses on the
1–5 agreement scale. `score_session.py` computes the standard 0–100 SUS score.
Do not rewrite the SUS items between conditions.

## Analysis

Use paired participant-level analysis:

- report medians/IQRs for time and counts;
- report completion rate per method;
- report mean/CI for SUS;
- compare Looma with each baseline using paired bootstrap confidence intervals;
- for final paper statistics, add an appropriate paired non-parametric test
  (e.g. Wilcoxon signed-rank) and correct for multiple comparisons.

Order/task effects should also be inspected before interpreting framework
differences.

## Data handling

Use anonymized participant ids only (`P001`, ...). Store one JSON file per
session. Raw free-text notes should be reviewed for accidental personal
information before artifact publication.

## Guard against overclaiming

Until prospective sessions exist, the paper may claim only:

- lower/higher implementation SLOC in the controlled implementations;
- fewer/more framework-specific constructs.

It must **not** claim shorter human development time or better usability from
code metrics alone.
