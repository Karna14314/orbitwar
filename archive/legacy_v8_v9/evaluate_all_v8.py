import sys
import os
import time
import math
from kaggle_environments import make

sys.path.append(os.path.abspath("."))
sys.path.append(os.path.abspath("orbit-wars"))

def load_agent(filepath):
    namespace = {"__file__": os.path.abspath(filepath)}
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()
    exec(code, namespace)
    return namespace["agent"]

print("Loading agents...")
v8_agent = load_agent("submission_v8.py")
mcts_hybrid = load_agent("submission.py")
champion = load_agent("orbit-wars/agents/champion.py")
champion_tuned = load_agent("archive/experimental/champion_tuned.py")

def run_match(agent_a, agent_b, name_a, name_b, n_games=6):
    print(f"\n=============================================================")
    print(f"MATCH: {name_a} vs {name_b} ({n_games} Games)")
    print(f"=============================================================")
    wins_a = 0
    wins_b = 0
    draws = 0
    scores_a = []
    scores_b = []
    
    for i in range(n_games):
        env = make("orbit_wars", debug=False)
        if i % 2 == 0:
            env.run([agent_a, agent_b])
            reward_a = env.steps[-1][0].reward
            reward_b = env.steps[-1][1].reward
        else:
            env.run([agent_b, agent_a])
            reward_b = env.steps[-1][0].reward
            reward_a = env.steps[-1][1].reward
            
        scores_a.append(reward_a)
        scores_b.append(reward_b)
        
        if reward_a > reward_b:
            wins_a += 1
            print(f"  Game {i+1}: {name_a} WON ({reward_a:.1f} vs {reward_b:.1f})")
        elif reward_b > reward_a:
            wins_b += 1
            print(f"  Game {i+1}: {name_b} WON ({reward_b:.1f} vs {reward_a:.1f})")
        else:
            draws += 1
            print(f"  Game {i+1}: DRAW ({reward_a:.1f} vs {reward_b:.1f})")
            
    avg_a = sum(scores_a) / len(scores_a)
    avg_b = sum(scores_b) / len(scores_b)
    print(f"--- Results: {wins_a} Wins for {name_a}, {wins_b} Wins for {name_b}, {draws} Draws")
    print(f"--- Avg Scores: {name_a} = {avg_a:.1f} | {name_b} = {avg_b:.1f}")
    return wins_a, wins_b, draws

if __name__ == "__main__":
    # Run matches
    run_match(v8_agent, mcts_hybrid, "V8 Aggressor", "Hybrid MCTS", n_games=6)
    run_match(v8_agent, champion, "V8 Aggressor", "Champion MCTS", n_games=6)
    run_match(v8_agent, champion_tuned, "V8 Aggressor", "Champion Tuned MCTS", n_games=6)
