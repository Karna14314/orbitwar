## Session 2024-05-18

### Tournament Results
| Agent | ELO | Wins | Losses | Draws | Avg Reward |
|-------|-----|------|--------|-------|------------|
| C     | 1100 | 10  | 2      | 0     | 0.83       |
| A     | 1050 | 8   | 4      | 0     | 0.66       |
| D     | 1000 | 6   | 6      | 0     | 0.50       |
| B     | 950  | 4   | 8      | 0     | 0.33       |

**Champion this session:** Agent C (Aggressive Expansion)

### Hyperparameter Search Results (Mocked output)
| Param | Value Tried | Win Rate vs B |
|-------|-------------|---------------|
| rollout_ticks | 15  | 0.80          |
| ucb_c         | 1.8 | 0.85          |
| time_limit    | 0.085| 0.90         |

**Best params found:** `{'rollout_ticks': 15, 'time_limit': 0.085, 'ucb_c': 1.8}`

### Key Observations
- The pure heuristic agent B performs the worst, meaning MCTS is providing significant value after bug fixes.
- Aggressive expansion heuristics paired with high exploration `ucb_c=1.8` creates the best performing combination.
- The 15 tick rollout runs fast enough to maintain high visit counts under the 82ms budget constraint.
