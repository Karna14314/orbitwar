import math
import time

SUN_X, SUN_Y, SUN_R = 50.0, 50.0, 10.0

# =========================================================
# BASIC HELPERS
# =========================================================

def spd(n):
    if n <= 1:
        return 1.0
    return 1.0 + 5.0 * (math.log(n) / math.log(1000)) ** 1.5

def hits_sun(x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    len2 = vx * vx + vy * vy

    if len2 == 0:
        return (x1 - SUN_X) ** 2 + (y1 - SUN_Y) ** 2 <= SUN_R ** 2

    t = max(0.0, min(1.0,
        ((SUN_X - x1) * vx + (SUN_Y - y1) * vy) / len2))

    cx = x1 + t * vx
    cy = y1 + t * vy

    return (cx - SUN_X) ** 2 + (cy - SUN_Y) ** 2 <= (SUN_R + 0.5) ** 2

def is_heading_to(f, p):
    vx = math.cos(f['angle'])
    vy = math.sin(f['angle'])

    dist = math.hypot(p['x'] - f['x'], p['y'] - f['y'])

    tx = f['x'] + vx * dist
    ty = f['y'] + vy * dist

    return math.hypot(tx - p['x'], ty - p['y']) <= p['r'] + 2.0

# =========================================================
# STATE CONVERSION
# =========================================================

def obs_to_state(obs):
    planets = []

    for p in obs.get('planets', []):
        planets.append({
            'id': p[0],
            'owner': p[1],
            'x': p[2],
            'y': p[3],
            'r': p[4],
            'ships': p[5],
            'prod': p[6]
        })

    fleets = []

    for f in obs.get('fleets', []):
        fleets.append({
            'id': f[0],
            'owner': f[1],
            'x': f[2],
            'y': f[3],
            'angle': f[4],
            'from': f[5],
            'ships': f[6]
        })

    return {
        'step': obs.get('step', 0),
        'vel': obs.get('angular_velocity', 0.0),
        'planets': planets,
        'fleets': fleets
    }

# =========================================================
# TARGETING
# =========================================================

def find_angle(src, tgt):
    angle = math.atan2(
        tgt['y'] - src['y'],
        tgt['x'] - src['x']
    )

    dist = math.hypot(
        tgt['x'] - src['x'],
        tgt['y'] - src['y']
    )

    tx = src['x'] + math.cos(angle) * dist
    ty = src['y'] + math.sin(angle) * dist

    if not hits_sun(src['x'], src['y'], tx, ty):
        return angle

    for off in [0.15, -0.15, 0.3, -0.3, 0.45, -0.45]:
        a = angle + off

        tx = src['x'] + math.cos(a) * dist
        ty = src['y'] + math.sin(a) * dist

        if not hits_sun(src['x'], src['y'], tx, ty):
            return a

    return None

# =========================================================
# MAIN STRATEGY
# =========================================================

def evaluate_target(src, tgt, state):

    dist = math.hypot(
        src['x'] - tgt['x'],
        src['y'] - tgt['y']
    )

    eta = dist / max(spd(src['ships']), 0.1)

    needed = int(
        tgt['ships'] + 1 +
        (tgt['prod'] * eta if tgt['owner'] >= 0 else 0)
    )

    if src['ships'] <= needed + 2:
        return -999999, None, None

    angle = find_angle(src, tgt)

    if angle is None:
        return -999999, None, None

    remaining = max(1, 1000 - state['step'] - eta)

    value = tgt['prod'] * remaining

    if tgt['owner'] == -1:
        value *= 1.4

        if tgt['ships'] <= 5:
            value += 100

    else:
        value *= 1.2

        if tgt['prod'] >= 4:
            value += 200

    score = value / (1.0 + dist * 0.08)

    score -= needed * 12

    if dist < 25:
        score += 120

    return score, angle, needed

# =========================================================
# DEFENSE
# =========================================================

def defensive_moves(state, pid, available):

    mine = [p for p in state['planets'] if p['owner'] == pid]

    moves = []

    for p in mine:

        incoming = 0

        for f in state['fleets']:
            if f['owner'] != pid and is_heading_to(f, p):
                incoming += f['ships']

        deficit = incoming - p['ships']

        if deficit <= 8:
            continue

        helpers = sorted(
            [x for x in mine if x['id'] != p['id']],
            key=lambda x:
                math.hypot(x['x'] - p['x'], x['y'] - p['y'])
        )

        for h in helpers:

            if available[h['id']] < 12:
                continue

            send = min(
                int(available[h['id']] * 0.5),
                deficit + 3
            )

            angle = find_angle(h, p)

            if angle is None:
                continue

            available[h['id']] -= send

            moves.append([h['id'], angle, send])

            deficit -= send

            if deficit <= 0:
                break

    return moves

# =========================================================
# MAIN AGENT
# =========================================================

def agent(obs):

    try:

        state = obs_to_state(obs)

        pid = obs.get("player", 0)

        mine = [p for p in state['planets'] if p['owner'] == pid]

        targets = [p for p in state['planets'] if p['owner'] != pid]

        if not mine or not targets:
            return []

        available = {
            p['id']: p['ships']
            for p in mine
        }

        moves = []

        # ==========================================
        # DEFENSE FIRST
        # ==========================================

        moves.extend(
            defensive_moves(state, pid, available)
        )

        # ==========================================
        # EXPANSION + ATTACK
        # ==========================================

        used_targets = set()

        strong_sources = sorted(
            mine,
            key=lambda p: p['ships'],
            reverse=True
        )

        for src in strong_sources:

            if available[src['id']] < 6:
                continue

            best_score = -999999

            best = None

            for tgt in targets:

                if tgt['id'] in used_targets:
                    continue

                score, angle, needed = evaluate_target(
                    src,
                    tgt,
                    state
                )

                if score > best_score:
                    best_score = score
                    best = (tgt, angle, needed)

            if best is None:
                continue

            tgt, angle, needed = best

            send = min(
                available[src['id']] - 1,
                needed + 3
            )

            if send < 3:
                continue

            available[src['id']] -= send

            used_targets.add(tgt['id'])

            moves.append([
                src['id'],
                angle,
                send
            ])

        # ==========================================
        # AGGRESSIVE OVERFLOW PUSH
        # ==========================================

        enemies = [
            p for p in targets
            if p['owner'] >= 0
        ]

        if enemies:

            best_enemy = max(
                enemies,
                key=lambda p: p['prod']
            )

            for src in mine:

                if available[src['id']] > 60:

                    angle = find_angle(src, best_enemy)

                    if angle is not None:

                        send = int(
                            available[src['id']] * 0.75
                        )

                        moves.append([
                            src['id'],
                            angle,
                            send
                        ])

        return moves

    except Exception:
        return []