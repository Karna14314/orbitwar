"""
Round-robin tournament. Each pair of agents plays N_GAMES games.
Player assignments alternate (each agent plays both sides equally).
Records win/loss/draw and average reward.
"""
from kaggle_environments import make
import json, time, importlib.util, os

# Set working directory to project root so we can find agents/ folder
os.chdir(os.path.join(os.path.dirname(__file__), '..'))

AGENTS = {
    'Champion': 'submission.py',
    'V8': '../submission_v8.py',
    'V9': '../submission_v9.py',
    'Rush': 'agents/experimental/agent_rush_current.py',
    'Intercept': 'agents/experimental/agent_intercept_current.py',
    'Defense': 'agents/experimental/agent_defense_current.py',
}
N_GAMES = 4          # games per matchup pair
ELO_K   = 32          # ELO K-factor

def load_agent(path):
    spec = importlib.util.spec_from_file_location("agent_mod", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent

def expected_score(ra, rb):
    return 1.0 / (1.0 + 10**((rb-ra)/400))

def update_elo(ra, rb, score_a):
    ea = expected_score(ra, rb)
    return ra + ELO_K*(score_a - ea), rb + ELO_K*((1-score_a) - (1-ea))

def run_game(agent_a, agent_b):
    env = make('orbit_wars', debug=False)
    env.run([agent_a, agent_b])
    r0 = env.steps[-1][0].reward or 0
    r1 = env.steps[-1][1].reward or 0
    if r0 > r1:   return 1.0, r0, r1   # A wins
    if r0 < r1:   return 0.0, r0, r1   # B wins
    return 0.5, r0, r1                  # draw

def run_tournament():
    names  = list(AGENTS.keys())
    agents = {n: load_agent(p) for n, p in AGENTS.items()}
    elo    = {n: 1000 for n in names}
    record = {n: {'wins':0,'losses':0,'draws':0,'reward':0.0} for n in names}

    pairs = [(a,b) for i,a in enumerate(names) for b in names[i+1:]]
    for a_name, b_name in pairs:
        print(f"\n{'='*50}")
        print(f"  {a_name} vs {b_name}  ({N_GAMES} games)")
        print(f"{'='*50}")
        for g in range(N_GAMES):
            # Alternate who plays first (eliminates first-mover advantage bias)
            if g % 2 == 0:
                score, r0, r1 = run_game(agents[a_name], agents[b_name])
                elo[a_name], elo[b_name] = update_elo(elo[a_name], elo[b_name], score)
                record[a_name]['reward'] += r0
                record[b_name]['reward'] += r1
            else:
                score, r0, r1 = run_game(agents[b_name], agents[a_name])
                score = 1.0 - score  # flip for A's perspective
                elo[a_name], elo[b_name] = update_elo(elo[a_name], elo[b_name], score)
                record[a_name]['reward'] += r1
                record[b_name]['reward'] += r0
            # Record win/loss/draw
            if score == 1.0:   record[a_name]['wins']+=1;   record[b_name]['losses']+=1
            elif score == 0.0: record[b_name]['wins']+=1;   record[a_name]['losses']+=1
            else:              record[a_name]['draws']+=1;  record[b_name]['draws']+=1
            print(f"  Game {g+1:02d}: A_reward={r0:.0f} B_reward={r1:.0f} "
                  f"ELO: {a_name}={elo[a_name]:.0f} {b_name}={elo[b_name]:.0f}")

    # Normalize rewards by games played
    games_per_agent = N_GAMES * (len(names)-1)
    for n in names:
        record[n]['avg_reward'] = record[n]['reward'] / games_per_agent

    results = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M'),
        'n_games_per_pair': N_GAMES,
        'elo': elo,
        'record': record,
        'champion': max(elo, key=elo.get)
    }

    os.makedirs('tournament', exist_ok=True)
    with open('tournament/leaderboard.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*50}")
    print("FINAL ELO STANDINGS")
    for n, e in sorted(elo.items(), key=lambda x: -x[1]):
        r = record[n]
        print(f"  {n}: ELO={e:.0f}  W={r['wins']} L={r['losses']} "
              f"D={r['draws']}  AvgReward={r['avg_reward']:.0f}")
    print(f"\n  CHAMPION: {results['champion']}")
    print(f"{'='*50}")
    return results

if __name__ == '__main__':
    results = run_tournament()
