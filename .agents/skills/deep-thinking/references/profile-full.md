# Full profile

Full is selected only by an explicit `$deep-thinking full` invocation. It uses the
shared kernel and records a separate, recoverable Research Run. Its center is epistemic
state, not a tool log.

Record the research question, decision goal, Research Mandate, claims, hypotheses,
evidence, independence groups, current judgment, Material Epistemic Transition,
Checkpoints, terminal record, and an applicable Restart Condition. A transition is a
real change in what is known or what should happen next; splitting one read into several
tool calls does not create more obligations.

Use `tools/research_state.py` only for Full. It supports `init`, `checkpoint`,
`finalize`, and `resume`; use `--state-dir` for tests or an isolated run. It never
creates a global active mode.

Terminal values are `answered`, `conditionally_answered`, `unresolved_evidence_limit`,
`blocked_access`, `stopped_budget`, and `invalidated_question`. An unresolved terminal
needs a concrete event-based Restart Condition, not “get more information”.

Full uses a bounded Research Mandate instead of batch authorization. Reconfirm only when
scope, cost, external side effect, high-risk information, or the research objective
materially changes. A Retro is exceptional: use it only for a major reversal, user-found
error, invalidated source, serious evaluator disagreement, protocol exception, abnormal
stop, high-impact error, or a method worth preserving.
