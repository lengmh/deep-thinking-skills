# Full profile

```json
{
  "contract": "deep-thinking-profile-v1",
  "profile": "full",
  "research_run": "required",
  "checkpoint": "material_transition",
  "typed_terminal": "required",
  "retro": "trigger_only",
  "state_tool": "required"
}
```

Full is selected only by an explicit `$deep-thinking full` invocation. It uses the
shared kernel and records a separate, recoverable Research Run. Its center is epistemic
state, not a tool log.

Record the research question, decision goal, Research Mandate, claims, hypotheses,
evidence, independence groups, current judgment, Material Epistemic Transition,
Checkpoints, terminal record, and an applicable Restart Condition. A transition is a
real change in what is known or what should happen next; splitting one read into several
tool calls does not create more obligations.

Use `tools/research_state.py` only for Full. It supports `init`, `checkpoint`,
`finalize`, `resume`, and `validate`; use `--state-dir` for tests or an isolated run.
Each Research Run has a single writer. Concurrent writes fail immediately with
`research run is busy`; they do not wait, retry, or overwrite another update. A process
killed while writing may leave `.<run-id>.lock`; remove it manually only after confirming
that no writer is active. The tool never creates a global active mode.

Terminal values are `answered`, `conditionally_answered`, `unresolved_evidence_limit`,
`blocked_access`, `stopped_budget`, and `invalidated_question`. An unresolved terminal
needs a structured Restart Condition with an event type, subject, and observable condition.
Free-form promises such as “get more information” are not Restart Conditions.

The current state schema is version 3. The current CLI rejects version 1 and 2 state rather
than guessing a migration; replay historical runs with their captured package. Every v3
run records local Full activation provenance: profile, invocation ID, and an activation
time equal to run creation. This is state provenance, not authenticated host-selection proof.

Full uses a bounded Research Mandate instead of batch authorization. Reconfirm only when
scope, cost, external side effect, high-risk information, or the research objective
materially changes. A Retro is exceptional: use it only for a major reversal, user-found
error, invalidated source, serious evaluator disagreement, protocol exception, abnormal
stop, high-impact error, or a method worth preserving.
