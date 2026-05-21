# HYPOTHESIS: Predict target positions to lead shots, improving capture rate for moving planets and comets.
# DATE: 2024-05-20
# BASED ON: submission_v12.py (Grandmaster)
# CHANGELOG: Initial version, focusing on basic intercept math.

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
    vel = obs.get("angular_velocity", 0)

    planets = []
    for p in obs.get("planets", []):
        planets.append({"id": p[0], "owner": p[1], "x": p[2], "y": p[3], "radius": p[4], "ships": p[5], "production": p[6]})

    my_planets = [p for p in planets if p['owner'] == player]

    if not my_planets:
        return []

    moves = []

    for my_p in my_planets:
        if my_p['ships'] <= 5: continue

        best_target = None
        best_score = float('inf')
        best_angle = 0
        best_needed = 0

        for tgt in planets:
            if tgt['owner'] == player: continue

            needed = tgt['ships'] + 3
            if my_p['ships'] <= needed: continue

            speed = spd(needed)

            # Very basic intercept: assume target rotates by (dist/speed) * vel
            dist_rough = get_dist_xy(my_p['x'], my_p['y'], tgt['x'], tgt['y'])
            ticks_rough = dist_rough / speed

            r = math.hypot(tgt['x'] - 50, tgt['y'] - 50)
            if r < 45.0: # Orbiting
                a0 = math.atan2(tgt['y'] - 50, tgt['x'] - 50)
                a1 = a0 + vel * ticks_rough
                tx = 50 + r * math.cos(a1)
                ty = 50 + r * math.sin(a1)
            else:
                tx, ty = tgt['x'], tgt['y']

            dist_real = get_dist_xy(my_p['x'], my_p['y'], tx, ty)
            angle = math.atan2(ty - my_p['y'], tx - my_p['x'])

            if hits_sun(my_p['x'], my_p['y'], tx, ty):
                continue

            score = dist_real - (tgt['production'] * 5)
            if score < best_score:
                best_score = score
                best_target = tgt
                best_angle = angle
                best_needed = needed

        if best_target:
            moves.append([my_p['id'], best_angle, best_needed])
            my_p['ships'] -= best_needed

    return moves
