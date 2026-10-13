# Standard profile

Standard is the default for an explicit invocation. It uses the shared kernel and may
keep a minimal working state: current question, current judgment, active hypotheses,
decision-relevant evidence, most important unknown, and next valuable action.

Create or update a Checkpoint only when the judgment materially changes, the hypothesis set changes, a key hypothesis is eliminated, apparently independent evidence is found not actually independent, counterevidence changes the next action, compression, pause, handoff, or multi-agent synthesis is imminent, or scope, cost, or external side effect materially changes.

Standard must not require a Checkpoint per batch, must not classify every tool call,
must not request epistemic authorization per batch, must not expose state before ordinary
reading, must not require Retro for every terminal, and must not interrupt continuous
research merely to create state.

Ask for explicit control only before irreversible external writes, clearly high-cost work,
material scope expansion, new high-risk or sensitive information, or a point where user
input could materially redirect the research. Do not create a long-lived ledger unless
continuity across compression, handoff, or recovery genuinely needs one minimal checkpoint.
