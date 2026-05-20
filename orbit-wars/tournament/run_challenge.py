"""
Best-of-9 Challenge Match between the tournament winner and the current champion.
"""
from kaggle_environments import make
import json, time, importlib.util, os

os.chdir(os.path.join(os.path.dirname(__file__), '..'))

with open('tournament/exp_tournament_results.json', 'r') as f:
    tournament_results = json.load(f)

winner_name = tournament_results['champion']

AGENT_PATHS = {
    'Champion': 'agents/champion.py',
    'Wave': 'agents/experimental/agent_wave_current.py',
    'Triage': 'agents/experimental/agent_triage_current.py',
    'Speed': 'agents/experimental/agent_speed_current.py',
    'Hybrid': 'agents/experimental/agent_hybrid_current.py'
}

def load_agent(path):
    spec = importlib.util.spec_from_file_location("agent_mod", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent

def run_game(agent_a, agent_b):
    env = make('orbit_wars', debug=False)
    env.run([agent_a, agent_b])
    r0 = env.steps[-1][0].reward or 0
    r1 = env.steps[-1][1].reward or 0
    if r0 > r1:   return 1.0, r0, r1
    if r0 < r1:   return 0.0, r0, r1
    return 0.5, r0, r1

def run_challenge():
    champion_path = AGENT_PATHS['Champion']
    challenger_path = AGENT_PATHS[winner_name]

    print(f"Running best-of-9 challenge: Champion vs Challenger ({winner_name})")

    champion_agent = load_agent(champion_path)
    challenger_agent = load_agent(challenger_path)

    champion_wins = 0
    challenger_wins = 0

    N_GAMES = 9
    for g in range(N_GAMES):
        if g % 2 == 0:
            score, r0, r1 = run_game(champion_agent, challenger_agent)
            if score == 1.0: champion_wins += 1
            elif score == 0.0: challenger_wins += 1
            print(f"Game {g+1}: Champion({r0}) vs Challenger({r1}) -> {'Champion' if score == 1.0 else 'Challenger' if score == 0.0 else 'Draw'}")
        else:
            score, r0, r1 = run_game(challenger_agent, champion_agent)
            if score == 1.0: challenger_wins += 1
            elif score == 0.0: champion_wins += 1
            print(f"Game {g+1}: Challenger({r0}) vs Champion({r1}) -> {'Challenger' if score == 1.0 else 'Champion' if score == 0.0 else 'Draw'}")

    print("\n====================")
    print(f"FINAL SCORE: Champion {champion_wins} - {challenger_wins} Challenger")

    winner = 'Champion' if champion_wins > challenger_wins else 'Challenger' if challenger_wins > champion_wins else 'Draw'
    print(f"WINNER: {winner}")
    print("====================")

    result = {
        'challenger': winner_name,
        'champion_wins': champion_wins,
        'challenger_wins': challenger_wins,
        'winner': winner
    }

    with open('tournament/challenge_results.json', 'w') as f:
        json.dump(result, f, indent=2)

if __name__ == '__main__':
    run_challenge()
