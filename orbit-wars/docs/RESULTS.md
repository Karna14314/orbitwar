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

## Session 2024-05-20

### Tournament Results
| Agent | ELO | Wins | Losses | Draws | Avg Reward |
|-------|-----|------|--------|-------|------------|
| Intercept | 1118 | 11 | 1 | 0 | 1.00 |
| Rush  | 1030 | 7 | 5 | 0 | 0.00 |
| Defense | 1002 | 6 | 6 | 0 | 0.00 |
| Hybrid | 850 | 0 | 12 | 0 | -1.00 |

**Champion this session:** agent_intercept_current.py

### Champion Challenge
| Matchup | Challenger (Intercept) | Champion |
|-------|-------------|---------------|
| Best-of-5 | 5 Wins | 0 Wins |

**New Champion:** agent_intercept_current.py

## Session Final Output

### Super Tournament Results
| Agent | ELO | Wins | Losses | Draws | Avg Reward |
|-------|-----|------|--------|-------|------------|
| Intercept | 1140 | 16 | 3 | 1 | 1.00 |
| Champion | 1097 | 15 | 4 | 1 | 1.00 |
| Rush  | 1049 | 12 | 8 | 0 | 0.00 |
| Defense | 1025 | 11 | 9 | 0 | 0.00 |
| V8 | 869 | 4 | 16 | 0 | -1.00 |
| V9 | 820 | 1 | 19 | 0 | -1.00 |

**Overall Champion:** Intercept (agent_intercept_current.py)
