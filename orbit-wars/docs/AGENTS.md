# Orbit Wars Agent Roster

## Champion (current best)
- **File:** agents/champion.py
- **Source:** Agent C (Aggressive Expansion) tuned
- **ELO:** 1100
- **Architecture:** MCTS Action-Generation with fast rollout and aggressive early expansion heuristics
- **Key parameters:** rollout_ticks=15, time_limit=0.085, ucb_c=1.8

## Agent A — Fast MCTS
MCTS with fast_policy rollouts. Uses 20 ticks rollout, ucb_c 1.4. This is a baseline fix.

## Agent B — Fixed Heuristic
Fixed pure heuristic based on V4 without any MCTS. Has all 5 listed bug fixes.

## Agent C — Aggressive Expansion
MCTS with aggressive expansion heuristics for early game neutral capture and higher UCB exploration factor (1.8). Uses faster 15 ticks rollout.

## Agent D — Defensive Turtle
MCTS combined with defensive late-game heuristics, vulnerability penalty, and exploitation-heavy ucb parameter (1.0). Uses longer 25 ticks rollout.
