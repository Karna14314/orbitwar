import os
import sys
import time
from kaggle_environments import make

def load_agent(filepath):
    namespace = {"__file__": os.path.abspath(filepath)}
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()
    exec(code, namespace)
    return namespace["agent"]

def main():
    print("Loading agents...")
    v10 = load_agent("submission_v10.py")
    intercept = load_agent("submission_intercept.py")
    
    n_games = 10
    v10_wins = 0
    intercept_wins = 0
    draws = 0
    
    print(f"Starting benchmark: submission_v10.py vs submission_intercept.py for {n_games} games...")
    
    for i in range(n_games):
        env = make("orbit_wars", debug=False)
        # Alternate who is Player 0 (index 0) and Player 1 (index 1)
        if i % 2 == 0:
            env.run([v10, intercept])
            reward_v10 = env.steps[-1][0].reward
            reward_intercept = env.steps[-1][1].reward
            v10_role = "P0"
            intercept_role = "P1"
        else:
            env.run([intercept, v10])
            reward_intercept = env.steps[-1][0].reward
            reward_v10 = env.steps[-1][1].reward
            v10_role = "P1"
            intercept_role = "P0"
            
        if reward_v10 > reward_intercept:
            v10_wins += 1
            result = "v10 WON"
        elif reward_intercept > reward_v10:
            intercept_wins += 1
            result = "intercept WON"
        else:
            draws += 1
            result = "DRAW"
            
        print(f"Game {i+1:2d}: v10={reward_v10:.1f} ({v10_role}) | intercept={reward_intercept:.1f} ({intercept_role}) -> {result}")

    print("\nBenchmark Complete!")
    print(f"submission_v10.py Wins: {v10_wins}")
    print(f"submission_intercept.py Wins: {intercept_wins}")
    print(f"Draws: {draws}")

if __name__ == "__main__":
    main()
