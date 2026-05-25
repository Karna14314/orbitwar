import os
import sys
import traceback
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
    
    print("Running match with debug=True...")
    env = make("orbit_wars", debug=True)
    env.run([v10, intercept])
    
    print("\nMatch finished!")
    for i, step in enumerate(env.steps):
        # Print status of players if there's an error
        for p_idx, p_step in enumerate(step):
            if p_step.status == "ERROR":
                print(f"Error at step {i} for Player {p_idx}: status={p_step.status}, reward={p_step.reward}")
                print("Logs:", p_step.observation)
                
    # Print final rewards
    final = env.steps[-1]
    print(f"Final Rewards: Player 0: {final[0].reward}, Player 1: {final[1].reward}")
    print(f"Final Status: Player 0: {final[0].status}, Player 1: {final[1].status}")

if __name__ == "__main__":
    main()
