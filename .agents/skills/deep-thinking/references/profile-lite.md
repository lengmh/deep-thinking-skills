# Lite profile

```json
{
  "contract": "deep-thinking-profile-v1",
  "profile": "lite",
  "research_run": "forbidden",
  "checkpoint": "forbidden",
  "typed_terminal": "forbidden",
  "retro": "forbidden",
  "state_tool": "forbidden"
}
```

Lite is prompt-only. Use the shared epistemic kernel, challenge the key assumption,
consider the strongest alternative, and give a clear judgment with a reversal condition.

Lite must not create persistent state, a research state machine, public pre-tool state,
or a fixed output template. It must not require tool-call classification or batch
authorization. It must not require Checkpoints, typed terminals, or Restart Conditions.
It must not require Retro. It must not refuse a solvable task because process records are
absent.

Keep this profile brief. It loads no Standard or Full governance material.
