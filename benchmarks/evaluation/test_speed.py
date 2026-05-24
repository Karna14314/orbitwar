import time
import os
import sys

def load_agent(filepath):
    namespace = {"__file__": os.path.abspath(filepath)}
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()
    exec(code, namespace)
    return namespace["agent"]

def main():
    agent = load_agent("submission_v10.py")
    
    # Mock a large observation with 20 planets and 30 fleets
    planets = []
    # 20 planets: [id, owner, x, y, radius, ships, production]
    for i in range(20):
        owner = 0 if i < 5 else (1 if i < 10 else -1)
        planets.append([i, owner, 20.0 + 5.0 * (i % 5), 20.0 + 5.0 * (i // 5), 3.0, 10.0, 1.0])
        
    fleets = []
    # 30 fleets: [id, owner, x, y, angle, from_planet_id, ships]
    for i in range(30):
        owner = 1 if i % 2 == 0 else 0
        fleets.append([i, owner, 40.0, 40.0, 0.5, i % 20, 15.0])
        
    initial_planets = [p.copy() for p in planets]
    
    obs = {
        "player": 0,
        "step": 100,
        "planets": planets,
        "fleets": fleets,
        "initial_planets": initial_planets,
        "angular_velocity": 0.05,
        "comet_planet_ids": [],
        "comets": []
    }
    
    print("Running agent(obs) on mock observation...")
    start_time = time.perf_counter()
    try:
        moves = agent(obs)
        end_time = time.perf_counter()
        print(f"Success! Generated {len(moves)} moves.")
        print(f"Moves: {moves}")
        print(f"Execution time: {(end_time - start_time) * 1000:.2f} ms")
    except Exception as e:
        print("ERROR occurred:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
