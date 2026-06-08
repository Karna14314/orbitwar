import sys
from kaggle_environments import make

with open("best_agent.txt", "r") as f:
    best_agent = f.read().strip()
champion = "submission.py"

import concurrent.futures

results = {"challenger": 0, "champion": 0, "ties": 0}

def run_champ_match(args):
    i, ba, champ = args
    env = make("orbit_wars", configuration={"seed": 100 + i}, debug=False)
    try:
        env.run([ba, champ])
        final_step = env.steps[-1]
        r0 = final_step[0].reward if final_step[0].reward is not None else 0
        r1 = final_step[1].reward if final_step[1].reward is not None else 0
        return (r0, r1, None)
    except Exception as e:
        return (0, 0, str(e))

tasks = [(i, best_agent, champion) for i in range(9)]

with concurrent.futures.ProcessPoolExecutor() as executor:
    for res in executor.map(run_champ_match, tasks):
        r0, r1, err = res
        if err:
            print(f"  Error: {err}")
            results["champion"] += 1
            continue

        if r0 > r1:
            results["challenger"] += 1
            print("  Challenger won")
        elif r1 > r0:
            results["champion"] += 1
            print("  Champion won")
        else:
            results["ties"] += 1
            print("  Tie")

print("\n--- Final Series Results ---")
print(f"Challenger ({best_agent}): {results['challenger']}")
print(f"Champion ({champion}): {results['champion']}")
print(f"Ties: {results['ties']}")
