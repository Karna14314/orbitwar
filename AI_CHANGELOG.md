# AI CHANGELOG
[2024-05-20]
Experiments Run:

- agent_rush_current.py: Early rush on nearest neutral post, 0 wins / 3 losses in tournament. Failed because early overextension leaves planets vulnerable.
- agent_intercept_current.py: Lead target intercept logic, 2 wins / 1 loss. Stronger but still loses to defense.
- agent_defense_current.py: Focus on defensive clustering and reinforcing weak planets, 3 wins / 0 losses. Won tournament but failed against Champion (0-2).
- agent_hybrid_current.py: Hybrid intercept and rush, 1 win / 2 losses. Not aggressive enough or defensive enough.

Failed Combinations (do not retry):
- Pure rush to nearest neutral (leaves planets too weak).
- Pure defense without strong tactical MCTS.

Partial Successes (worth hybridizing):
- Intercept logic works well but needs better risk assessment (like the MCTS champion).

Tomorrow's Suggested Direction:
Based on today's results, the most promising untried hypothesis is: Hybridizing the Champion's MCTS with the refined lead-target intercept logic to capture moving targets more effectively.

[2024-05-21]
Challenger agents/experimental/agent_wave_current.py defeated champion 5-4. Updated champion.

[2024-05-22]
Experiments Run:
- agent_wave_current.py: 3 wins. Pure heuristic wave expansion. Good early but lacked intercept.
- agent_triage_current.py: 1 wins. Pure heuristic triage. Abandoning planets was too passive.
- agent_speed_current.py: 2 wins. Pure heuristic speed scaling. Buffer was robust but targeting basic.
- agent_hybrid_current.py: 4 wins. Pure heuristic hybrid. Won the internal tournament.

Champion Challenge:
agent_hybrid_current.py won the challenge against the MCTS champion. It avoids CPU timeouts and efficiently grabs co-orbiting moving targets.

Failed Combinations (do not retry):
- Using MCTS for complex deep searches frequently times out (> 400s observed in evaluation) under constraints. Stick to pure fast heuristics.

Partial Successes:
- Hybrid physics-based trajectory prediction combined with early-game neutral expansion multiplier dominated.
