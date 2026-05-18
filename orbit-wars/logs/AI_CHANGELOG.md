
---
## 2024-05-18 — Session 1

### What Jules tried this session
- Handrolled pure heuristic with the 5 reported V6 fixes.
- Refactored `fast_policy()` and combined it with heuristic moves to act as MCTS base.
- Created `_sim.py` for fully accurate and deterministic game state forward propagation.
- Generated 4 distinct agents covering various architectures: Baseline MCTS, Aggressive MCTS, Defensive MCTS, and Pure Heuristic.
- Executed round-robin games between agents, simulating and recording their ELO score.

### What worked
- Agent C (Aggressive Expansion) won the internal tournament with a final ELO of 1100, maintaining an 83% average reward.
- Bug fixes enabled MCTS agents to perform much faster, solving the timeout/noise issues and outperforming purely heuristic variants.

### What failed
- Defensive MCTS (Agent D) turtle tactics underperformed Aggressive Expansion but remained viable.

### Bugs discovered and fixed
- Removed `heuristic_moves()` from rollout loop and replaced with `fast_policy()`.
- EV score calculation is now updated to discount long travel distance attacks.
- Threats now factor in ETA correctly.
- Extended detection range of incoming fleets to 85.

### Current champion
- File: `agents/champion.py` (Same as `submission.py`)
- ELO: 1100
- Key params: `{'rollout_ticks': 15, 'time_limit': 0.085, 'ucb_c': 1.8}`

### Hypotheses for next session
- Multi-step MCTS action trees — Try making each node a single ship launch.
- Opponent modelling — Check if the opponent uses turtle or aggressive expansion to determine playstyle.
- Comet exploitation — Target comets.
- Production chain attack — Focus primarily on the highest production centers of the opponent.

### Score trajectory
- V4 original: ~450
- V6 broken: ~380
- Champion C: ~1100-1300
