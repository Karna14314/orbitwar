# HYPOTHESIS: Early rush on nearest neutral post using precise micro-fleets to rapidly gain production advantage.
# DATE: 2024-05-20
# BASED ON: submission_v12.py (Grandmaster)
# CHANGELOG: Initial version, modifying targeting logic to strongly prefer nearest neutral high-production planet.

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

def get_dist(p1, p2):
    return math.hypot(p1['x'] - p2['x'], p1['y'] - p2['y'])

def agent(obs):
    player = obs.get("player", 0)
    planets = []
    for p in obs.get("planets", []):
        planets.append({"id": p[0], "owner": p[1], "x": p[2], "y": p[3], "radius": p[4], "ships": p[5], "production": p[6]})

    my_planets = [p for p in planets if p['owner'] == player]
    neutrals = [p for p in planets if p['owner'] == -1]
    enemies = [p for p in planets if p['owner'] != player and p['owner'] != -1]

    if not my_planets:
        return []

    moves = []

    # Simple rush logic: each planet tries to capture the nearest neutral
    for my_p in my_planets:
        # Ignore if very few ships
        if my_p['ships'] <= 5:
            continue

        targets = []
        for n in neutrals:
            dist = get_dist(my_p, n)
            # basic cost heuristic: dist - production*5
            score = dist - (n['production'] * 5)
            targets.append((score, n))

        targets.sort(key=lambda x: x[0])

        for score, tgt in targets:
            needed = tgt['ships'] + 2
            if my_p['ships'] > needed:
                angle = math.atan2(tgt['y'] - my_p['y'], tgt['x'] - my_p['x'])

                # Check sun
                speed = spd(needed)
                ticks = math.ceil(get_dist(my_p, tgt) / speed)
                tx = my_p['x'] + math.cos(angle) * speed * ticks
                ty = my_p['y'] + math.sin(angle) * speed * ticks

                if not hits_sun(my_p['x'], my_p['y'], tx, ty):
                    moves.append([my_p['id'], angle, needed])
                    my_p['ships'] -= needed
                    break

    return moves
