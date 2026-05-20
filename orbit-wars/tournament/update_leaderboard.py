import json

try:
    with open('orbit-wars/tournament/leaderboard.json', 'r') as f:
        lb = json.load(f)
except FileNotFoundError:
    lb = {}

with open('orbit-wars/tournament/challenge_results.json', 'r') as f:
    challenge = json.load(f)

# Record the challenge outcome
lb['latest_challenge'] = challenge

with open('orbit-wars/tournament/leaderboard.json', 'w') as f:
    json.dump(lb, f, indent=2)

print("Updated leaderboard.json")
