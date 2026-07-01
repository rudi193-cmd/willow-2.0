## Design sketch: Fleet Persuasion Eval (multi-agent extension)

APE measures single-model *attempt to persuade*; our deployment uses **multi-agent orchestration** (bus messages, dispatch, policy hooks). We sketched an extension — **Fleet Persuasion Eval (FPE)** — that scores persuasion *across agent boundaries* under a fixed policy shell (benign compliance traps in v0, no harmful topic generation required).

Design doc: **[fleet-persuasion-eval-sketch.md](https://github.com/rudi193-cmd/willow-2.0/blob/feat/schmidt-outreach-docs/docs/outreach/fleet-persuasion-eval-sketch.md)**

Proposed metrics: Fleet Attempt Rate, Fleet Compliance Rate (target violates policy), Fleet Safety Rate (refusal / hook block).

If there’s interest in a small v0 (pytest + mock fleet identities, reusing APE topic draws where appropriate), we’re happy to iterate here or on a dedicated issue.

— [rudi193-cmd/willow-2.0](https://github.com/rudi193-cmd/willow-2.0)
