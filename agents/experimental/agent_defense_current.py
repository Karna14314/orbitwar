# HYPOTHESIS: Defensive clustering and opportunistic expansion.
# DATE: 2024-05-20
# BASED ON: submission_v12.py (Grandmaster)
# CHANGELOG: Initial version, focuses on reinforcing weak planets.

import math
import copy

def spd(n):
    if n <= 1:
        return 1.0
    safe_n = max(float(n), 1.0001)
    val = 1.0 + 5.0 * (math.log(safe_n) / math.log(1000)) ** 1.5
    return min(6.0, val)

def segment_intersects_circle(x1, y1, x2, y2, cx, cy, r):
    vx, vy = x2 - x1, y2 - y1
    len2 = vx * vx + vy * vy
    if len2 == 0:
        return (x1 - cx) ** 2 + (y1 - cy) ** 2 <= r * r
    t = max(0.0, min(1.0, ((cx - x1) * vx + (cy - y1) * vy) / len2))
    nx, ny = x1 + t * vx, y1 + t * vy
    return (nx - cx) ** 2 + (ny - cy) ** 2 <= r * r

def hits_sun(x1, y1, x2, y2, margin=0.7):
    return segment_intersects_circle(x1, y1, x2, y2, 50.0, 50.0, 10.0 + margin)

def get_dist_xy(x1, y1, x2, y2):
    return math.hypot(x1 - x2, y1 - y2)

def agent(obs):
    player = obs.get("player", 0)

    planets = []
    for p in obs.get("planets", []):
        planets.append({"id": p[0], "owner": p[1], "x": p[2], "y": p[3], "radius": p[4], "ships": p[5], "production": p[6]})

    my_planets = [p for p in planets if p['owner'] == player]

    if not my_planets:
        return []

    moves = []

    # 1. Defend weak planets
    weak_planets = [p for p in my_planets if p['ships'] < 10]
    strong_planets = [p for p in my_planets if p['ships'] > 30]

    for sp in strong_planets:
        if weak_planets:
            wp = min(weak_planets, key=lambda x: get_dist_xy(sp['x'], sp['y'], x['x'], x['y']))
            needed = 20 - wp['ships']
            if needed > 0 and sp['ships'] > needed + 10:
                angle = math.atan2(wp['y'] - sp['y'], wp['x'] - sp['x'])
                if not hits_sun(sp['x'], sp['y'], wp['x'], wp['y']):
                    moves.append([sp['id'], angle, needed])
                    sp['ships'] -= needed
                    wp['ships'] += needed

        # 2. Opportunistic expansion
        best_target = None
        best_score = float('inf')
        best_angle = 0
        best_needed = 0

        for tgt in planets:
            if tgt['owner'] == player: continue
            needed = tgt['ships'] + 2
            if sp['ships'] <= needed + 5: continue # Keep a buffer

            dist = get_dist_xy(sp['x'], sp['y'], tgt['x'], tgt['y'])
            if hits_sun(sp['x'], sp['y'], tgt['x'], tgt['y']): continue

            score = dist - (tgt['production'] * 10)
            if score < best_score:
                best_score = score
                best_target = tgt
                best_angle = math.atan2(tgt['y'] - sp['y'], tgt['x'] - sp['x'])
                best_needed = needed

        if best_target:
            moves.append([sp['id'], best_angle, best_needed])
            sp['ships'] -= best_needed

    return moves
