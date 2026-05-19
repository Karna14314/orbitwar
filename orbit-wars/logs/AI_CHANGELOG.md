
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

### 2024-05-19 — Session 2

### What Jules tried this session
- Repository Cleanup: Renamed experimental agents to use standard naming format (e.g. `agent_heuristic_current.py`, `agent_mcts_aggressive.py`), removed abandoned agents, and established standard folder limits.
- Fixed Physics: Implemented dynamic anticipation for fleet intercepts matching target moving positions, expanded sun collision check radius slightly for a safety buffer, and implemented multi-angle offset checks for pathfinding around the sun.
- Tweaked Aggressive capture logic: Multiplied Early game EV for unowned/neutral targets by 2.0. Boosted buffer logic when attacking multiples to prevent bleed.
- Held 4-way and 1v1 Tournaments.

### What worked
- The purely heuristic agent improved massively from the neutral evaluation boost, matching the Aggressive MCTS evenly (2 wins each).

### Current champion
- File: `champion_tuned.py` & `agent_heuristic_current.py` tie
- Final submission: `submission.py` combines the MCTS Aggressive logic with the Heuristic updates for Kaggle.
