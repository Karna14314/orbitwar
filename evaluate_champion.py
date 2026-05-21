import sys
from kaggle_environments import make

best_agent = "agents/experimental/agent_hybrid_current.py"
champion = "agents/champion.py"

results = {"challenger": 0, "champion": 0, "ties": 0}

for i in range(9):
    print(f"Match {i+1}: {best_agent} vs {champion}")
    env = make("orbit_wars", configuration={"seed": 100 + i}, debug=False)
    try:
        env.run([best_agent, champion])
        final_step = env.steps[-1]

        p0_reward = final_step[0].reward if final_step[0].reward is not None else 0
        p1_reward = final_step[1].reward if final_step[1].reward is not None else 0

        if p0_reward > p1_reward:
            results["challenger"] += 1
            print("  Challenger won")
        elif p1_reward > p0_reward:
            results["champion"] += 1
            print("  Champion won")
        else:
            results["ties"] += 1
            print("  Tie")
    except Exception as e:
        print(f"  Error: {e}")
        results["champion"] += 1

print("\n--- Final Series Results ---")
print(f"Challenger ({best_agent}): {results['challenger']}")
print(f"Champion ({champion}): {results['champion']}")
print(f"Ties: {results['ties']}")
