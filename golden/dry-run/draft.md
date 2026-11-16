# Draft: does a noise floor bound what a leaderboard can claim

> Gate label, not a paper. A row under the ACCEPT heading is a claim whose recorded gate decision is ACCEPT. Dry-run evidence is a fixture of synthetic votes. Nothing in this file is a research finding or a live-model result.

## Claims the gate marked ACCEPT

### A noise floor computed over five independent label producers bounds what a leaderboard leader can claim

- Verdict: `READABLE`
- Leader: `strong` at `0.9475`
- Noise floor: `0.9155` (loo)
- Margin over floor: `+0.0320`
- Minimum detectable effect: `0.0312` (`binomial_approx`)
- Threshold applied: `0.0312`
- Generators: `5` over `400` items

### A five-producer floor separates a strong system but not a weak one

- Verdict: `READABLE`
- Leader: `strong` at `0.9275`
- Noise floor: `0.8850` (loo)
- Margin over floor: `+0.0425`
- Minimum detectable effect: `0.0363` (`binomial_approx`)
- Threshold applied: `0.0363`
- Generators: `5` over `400` items

## Unresolved claims (tested, not separable)

_These were run and the gate did not mark them ACCEPT. They stay in the draft so the refusal is visible. They are gate outcomes on the recorded evidence, not scientific findings._

- **Swapping the arithmetic mean for the median changes the leader when producers disagree at the margin** `MARGINAL`  
  margin +0.0285 is inside the resolution bound 0.0357
