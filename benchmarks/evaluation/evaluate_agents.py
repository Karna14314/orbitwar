import sys
from kaggle_environments import make

agents = [
    "agents/experimental/agent_wave_current.py",
    "agents/experimental/agent_speed_current.py",
    "agents/experimental/agent_triage_current.py",
    "agents/experimental/agent_hybrid_current.py"
]

import concurrent.futures

results = {agent: {"wins": 0, "losses": 0, "ties": 0, "score": 0} for agent in agents}

def run_match(args):
    i, j, match_idx, a1, a2 = args
    env = make("orbit_wars", configuration={"seed": 42 + i + j + match_idx * 100}, debug=False)
    try:
        env.run([a1, a2])
        final_step = env.steps[-1]
        r0 = final_step[0].reward if final_step[0].reward is not None else 0
        r1 = final_step[1].reward if final_step[1].reward is not None else 0
        return (a1, a2, r0, r1, None)
    except Exception as e:
        return (a1, a2, 0, 0, str(e))

tasks = []
for i in range(len(agents)):
    for j in range(i + 1, len(agents)):
        for match_idx in range(10):
            tasks.append((i, j, match_idx, agents[i], agents[j]))

with concurrent.futures.ProcessPoolExecutor() as executor:
    for res in executor.map(run_match, tasks):
        a1, a2, r0, r1, err = res
        if err:
            print(f"  Error: {err}")
            continue

        results[a1]["score"] += r0
        results[a2]["score"] += r1

        if r0 > r1:
            results[a1]["wins"] += 1
            results[a2]["losses"] += 1
            print(f"  {a1} won")
        elif r1 > r0:
            results[a2]["wins"] += 1
            results[a1]["losses"] += 1
            print(f"  {a2} won")
        else:
            results[a1]["ties"] += 1
            results[a2]["ties"] += 1
            print("  Tie")

print("\n--- Results ---")
best_agent = None
best_wins = -1

for agent, stats in results.items():
    print(f"{agent}: Wins: {stats['wins']}, Losses: {stats['losses']}, Ties: {stats['ties']}, Score: {stats['score']}")
    if stats['wins'] > best_wins:
        best_wins = stats['wins']
        best_agent = agent

print(f"\nBest agent: {best_agent}")
with open("best_agent.txt", "w") as f:
    f.write(best_agent)
