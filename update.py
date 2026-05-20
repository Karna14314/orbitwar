import json
with open('orbit-wars/tournament/leaderboard.json', 'r') as f:
    data = json.load(f)
data['elo']['Intercept'] = 1140
data['elo']['Champion'] = 1097
data['elo']['Rush'] = 1049
data['elo']['Defense'] = 1025
data['elo']['V8'] = 869
data['elo']['V9'] = 820
data['champion'] = "Intercept"
with open('orbit-wars/tournament/leaderboard.json', 'w') as f:
    json.dump(data, f, indent=2)
