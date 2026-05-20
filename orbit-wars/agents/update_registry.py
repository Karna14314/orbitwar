import json

with open('orbit-wars/agents/experiment_registry.json', 'r') as f:
    registry = json.load(f)

with open('orbit-wars/tournament/exp_tournament_results.json', 'r') as f:
    tourney = json.load(f)

with open('orbit-wars/tournament/challenge_results.json', 'r') as f:
    challenge = json.load(f)

new_entry = {
    "date": "2024-05-20",
    "experimental_agents": {
        "Wave": {
            "strategy": "Concentric Wave Expansion",
            "configs": "Boosts early adjacent neutrals, prioritizes co-orbiting neighbors",
            "outcome_vs_champion": f"Challenged Champion, lost 2-7" if challenge['challenger'] == "Wave" else "Did not reach challenge",
            "failure_reason": "Lost to champion in challenge match" if challenge['challenger'] == "Wave" else None
        },
        "Triage": {
            "strategy": "Defensive Triage",
            "configs": "Abandons planets with 3+ enemy bases nearby and threat ETA < 10, prevents early expansion into contested zones without massive fleet",
            "outcome_vs_champion": f"Challenged Champion, lost 2-7" if challenge['challenger'] == "Triage" else "Did not reach challenge",
            "failure_reason": "Failed to win experimental round robin" if challenge['challenger'] != "Triage" else None
        },
        "Speed": {
            "strategy": "Speed-Scaling Interceptions",
            "configs": "Dynamic safety buffer: max(needed * 1.35, needed + 4)",
            "outcome_vs_champion": f"Challenged Champion, lost 2-7" if challenge['challenger'] == "Speed" else "Did not reach challenge",
            "failure_reason": "Failed to win experimental round robin" if challenge['challenger'] != "Speed" else None
        },
        "Hybrid": {
            "strategy": "Hybrid",
            "configs": "Combined Wave, Triage, and Speed scaling features",
            "outcome_vs_champion": f"Challenged Champion, lost 2-7" if challenge['challenger'] == "Hybrid" else "Did not reach challenge",
            "failure_reason": "Failed to win experimental round robin" if challenge['challenger'] != "Hybrid" else None
        }
    },
    "tournament_winner": tourney['champion'],
    "challenge_winner": challenge['winner']
}

registry.append(new_entry)

with open('orbit-wars/agents/experiment_registry.json', 'w') as f:
    json.dump(registry, f, indent=2)

print("Updated experiment_registry.json")
