# Claim and evidence model

Use stable identifiers when Full records claims, hypotheses, evidence, or source groups.

- A claim has an `id`, `kind`, and `text`; its kind is one of the five epistemic types.
- A hypothesis has an `id`, `summary`, and `status` such as `active` or `eliminated`.
- Evidence has an `id`, `source`, `source_group`, and `effect` of `support`, `weaken`,
  or `no_effect`.
- An independence group names sources that share an upstream origin. Repeated reporting
  is not independent corroboration.

Do not turn an intake `user_claim` into `verified_fact` without independent grounding.
When evidence changes a conclusion, record the transition and the reason it changed the
action, not a copy of ordinary tool logs.
