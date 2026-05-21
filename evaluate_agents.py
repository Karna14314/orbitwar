import sys
from kaggle_environments import make

agents = [
    "agents/experimental/agent_rush_current.py",
    "agents/experimental/agent_intercept_current.py",
    "agents/experimental/agent_defense_current.py",
    "agents/experimental/agent_hybrid_current.py"
]

results = {agent: {"wins": 0, "losses": 0, "ties": 0, "score": 0} for agent in agents}

for i in range(len(agents)):
    for j in range(i + 1, len(agents)):
        print(f"Match: {agents[i]} vs {agents[j]}")
        env = make("orbit_wars", configuration={"seed": 42 + i + j}, debug=False)
        try:
            env.run([agents[i], agents[j]])
            final_step = env.steps[-1]

            p0_reward = final_step[0].reward if final_step[0].reward is not None else 0
            p1_reward = final_step[1].reward if final_step[1].reward is not None else 0

            results[agents[i]]["score"] += p0_reward
            results[agents[j]]["score"] += p1_reward

            if p0_reward > p1_reward:
                results[agents[i]]["wins"] += 1
                results[agents[j]]["losses"] += 1
                print(f"  {agents[i]} won")
            elif p1_reward > p0_reward:
                results[agents[j]]["wins"] += 1
                results[agents[i]]["losses"] += 1
                print(f"  {agents[j]} won")
            else:
                results[agents[i]]["ties"] += 1
                results[agents[j]]["ties"] += 1
                print("  Tie")
        except Exception as e:
            print(f"  Error: {e}")

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
