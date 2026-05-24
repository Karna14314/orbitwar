import sys
import os
import random
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from kaggle_environments import make

agents = [
    "champion_tuned.agent",
    "experimental.agent_heuristic_current.agent"
]

def load_agent(name):
    module_path = ".".join(name.split(".")[:-1])
    func_name = name.split(".")[-1]
    mod = __import__(module_path, fromlist=[func_name])
    return getattr(mod, func_name)

agent_funcs = [load_agent(n) for n in agents]

print("Running tournament with agents:")
for name in agents:
    print(f" - {name}")

num_matches = 2
scores = {i: 0 for i in range(len(agents))}

for match in range(num_matches):
    print(f"\nMatch {match+1}/{num_matches}...")
    env = make("orbit_wars", debug=False)

    # Shuffle seats for fairness
    seats = list(range(2))
    random.shuffle(seats)
    match_agents = [agent_funcs[seats.index(i)] for i in range(2)]

    env.run(match_agents)
    final_state = env.steps[-1]

    # Determine winner
    max_reward = -float('inf')
    winners = []
    for i, s in enumerate(final_state):
        if s.reward is not None and s.reward > max_reward:
            max_reward = s.reward
            winners = [i]
        elif s.reward == max_reward:
            winners.append(i)

    print(f"Match results (rewards): {[s.reward for s in final_state]}")
    for w in winners:
        original_agent_idx = seats[w]
        scores[original_agent_idx] += 1
        print(f"Winner: {agents[original_agent_idx]}")

print("\n--- FINAL TOURNAMENT RESULTS ---")
for i, name in enumerate(agents):
    print(f"{name}: {scores[i]} wins")
