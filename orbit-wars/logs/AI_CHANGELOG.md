
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

### 2024-05-20 — Session 3

#### Experiments Run
- **agent_rush_current**: Early rush on the nearest neutral/lowest-health post. Result: 2nd place in tournament. Good early momentum but fell short against intercept.
- **agent_intercept_current**: Target coincidentally moving posts (comets) near current trajectory. Result: Won tournament (11W 1L) and won best-of-5 vs Champion (5W 0L). Key observation: Controlling moving planets gives a decisive map control and production advantage.
- **agent_hybrid_current**: 8-Phase Decision Pipeline prioritizing pure heuristic logic. Result: 4th place. Overly complex and performed poorly without specific target prioritization.
- **agent_defense_current**: Reactive retreat/evacuation when outnumbered. Result: 3rd place. Retreating logic saved ships but sacrificed too much ground/production.

#### Failed Combinations (do not retry)
- Strict 8-Phase Decision Pipeline (`agent_hybrid_current`) without explicit comet/rush prioritization fails to gain map control fast enough.
- Evacuation-heavy defense (`agent_defense_current`) cedes too much production to the opponent.

#### Partial Successes (worth hybridizing)
- `agent_rush_current` showed promise for rapid early expansion.
- `agent_intercept_current` maps brilliantly to dynamic comets.

#### Tomorrow's Suggested Direction
Based on today's results, the most promising untried hypothesis is: A hybrid heuristic that combines the early low-health rush of `agent_rush_current` with the mid-game comet-targeting logic of `agent_intercept_current`.

#### Updated Evaluation vs Submissions (V8 / V9)
- Included V8 and V9 submissions in the final mega-tournament to truly establish the hierarchy.
- **Intercept** won the entire tournament with 1140 ELO and 16 Wins.
- The previous champion held its ground fairly well against older variants (1097 ELO) but was consistently outmaneuvered by Intercept's dynamic map control.
- V8 and V9 showed significant degradation in relative performance compared to the current standalone heuristic/MCTS models.
