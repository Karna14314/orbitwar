# =========================================================
# Orbit Wars Kaggle Submission
# Reliable Heuristic + Accurate Intercepts
# Focus:
# - Nearby neutral snowball
# - Safe sun avoidance
# - Moving target interception
# - Low timeout risk
# - Kaggle standalone compatible
# =========================================================

import math

SUN_X = 50.0
SUN_Y = 50.0
SUN_R = 10.5

# =========================================================
# SPEED
# =========================================================

def spd(n):
    if n <= 1:
        return 1.0
    return 1.0 + 5.0 * (math.log(n) / math.log(1000)) ** 1.5

# =========================================================
# SUN COLLISION
# =========================================================

def hits_sun(x1, y1, x2, y2):

    vx = x2 - x1
    vy = y2 - y1

    len2 = vx * vx + vy * vy

    if len2 == 0:
        return (x1 - SUN_X) ** 2 + (y1 - SUN_Y) ** 2 <= SUN_R ** 2

    t = max(
        0.0,
        min(
            1.0,
            ((SUN_X - x1) * vx + (SUN_Y - y1) * vy) / len2
        )
    )

    cx = x1 + t * vx
    cy = y1 + t * vy

    return (cx - SUN_X) ** 2 + (cy - SUN_Y) ** 2 <= SUN_R ** 2

# =========================================================
# PLANET POSITION PREDICTION
# =========================================================

def future_planet_position(ip, angular_velocity, step):

    r = math.hypot(ip['x'] - 50, ip['y'] - 50)

    if r < 1.0:
        return ip['x'], ip['y']

    angle0 = math.atan2(ip['y'] - 50, ip['x'] - 50)

    angle = angle0 + angular_velocity * step

    return (
        50 + r * math.cos(angle),
        50 + r * math.sin(angle)
    )

# =========================================================
# STATE
# =========================================================

def obs_to_state(obs):

    planets = []

    for p in obs.get("planets", []):
        planets.append({
            "id": p[0],
            "owner": p[1],
            "x": p[2],
            "y": p[3],
            "r": p[4],
            "ships": p[5],
            "prod": p[6]
        })

    fleets = []

    for f in obs.get("fleets", []):
        fleets.append({
            "id": f[0],
            "owner": f[1],
            "x": f[2],
            "y": f[3],
            "angle": f[4],
            "from": f[5],
            "ships": f[6]
        })

    ips = {}

    for p in obs.get("initial_planets", []):
        ips[p[0]] = {
            "id": p[0],
            "owner": p[1],
            "x": p[2],
            "y": p[3],
            "r": p[4],
            "ships": p[5],
            "prod": p[6]
        }

    return {
        "step": obs.get("step", 0),
        "angular_velocity": obs.get("angular_velocity", 0.0),
        "planets": planets,
        "fleets": fleets,
        "ips": ips
    }

# =========================================================
# INTERCEPT SOLVER
# =========================================================

def find_intercept_angle(src, tgt, ships, state):

    speed = spd(ships)

    ips = state["ips"]

    angular_velocity = state["angular_velocity"]

    step_now = state["step"]

    best = None

    # progressive ETA search
    for tick in range(1, 85):

        # future moving target position
        if tgt["id"] in ips:

            tx, ty = future_planet_position(
                ips[tgt["id"]],
                angular_velocity,
                step_now + tick
            )

        else:
            tx, ty = tgt["x"], tgt["y"]

        dx = tx - src["x"]
        dy = ty - src["y"]

        dist = math.hypot(dx, dy)

        arrival_dist = speed * tick

        # interception possible
        if arrival_dist >= dist - tgt["r"]:

            base_angle = math.atan2(dy, dx)

            # robust angular sweep
            offsets = [
                0,
                0.08, -0.08,
                0.16, -0.16,
                0.24, -0.24,
                0.35, -0.35,
                0.50, -0.50,
                0.70, -0.70
            ]

            for off in offsets:

                angle = base_angle + off

                ex = src["x"] + math.cos(angle) * dist
                ey = src["y"] + math.sin(angle) * dist

                # sun safety
                if hits_sun(src["x"], src["y"], ex, ey):
                    continue

                # final intercept validation
                pred_x = src["x"] + math.cos(angle) * arrival_dist
                pred_y = src["y"] + math.sin(angle) * arrival_dist

                final_dist = math.hypot(
                    pred_x - tx,
                    pred_y - ty
                )

                if final_dist <= tgt["r"] + 2.0:

                    best = (angle, tick)

                    return best

    return None, None

# =========================================================
# THREAT CHECK
# =========================================================

def incoming_enemy_strength(state, pid, planet):

    total = 0

    for f in state["fleets"]:

        if f["owner"] == pid:
            continue

        dx = planet["x"] - f["x"]
        dy = planet["y"] - f["y"]

        angle = math.atan2(dy, dx)

        diff = abs(angle - f["angle"])

        if diff < 0.35:
            total += f["ships"]

    return total

# =========================================================
# TARGET EVALUATION
# =========================================================

def evaluate_target(src, tgt, state, pid, my_planets_count):

    dist = math.hypot(
        tgt["x"] - src["x"],
        tgt["y"] - src["y"]
    )

    angle, eta = find_intercept_angle(
        src,
        tgt,
        src["ships"],
        state
    )

    if angle is None:
        return -999999, None, None

    needed = int(
        tgt["ships"] + 1 +
        (
            tgt["prod"] * eta
            if tgt["owner"] >= 0
            else 0
        )
    )

    if src["ships"] <= needed + 2:
        return -999999, None, None

    remaining_ticks = max(
        1,
        1000 - state["step"] - eta
    )

    score = 0

    # =====================================================
    # EARLY NEUTRAL EXPANSION
    # =====================================================

    if tgt["owner"] == -1:

        score += tgt["prod"] * remaining_ticks * 0.9

        # VERY IMPORTANT FIX
        # prioritize nearby cheap neutrals

        if dist < 25:
            score += 250

        if tgt["ships"] <= 5:
            score += 180

        if tgt["prod"] >= 2:
            score += 120

        if state["step"] < 200 and my_planets_count < 5:
            score *= 1.8

        score -= dist * 4.0

    else:

        # enemy targets
        score += tgt["prod"] * remaining_ticks * 0.7

        if tgt["prod"] >= 4:
            score += 180

        score -= dist * 5.5

    # efficiency
    score -= needed * 10

    # ETA penalty
    score /= (1 + eta * 0.12)

    return score, angle, needed

# =========================================================
# MAIN AGENT
# =========================================================

def agent(obs):

    try:

        state = obs_to_state(obs)

        pid = obs.get("player", 0)

        planets = state["planets"]

        mine = [
            p for p in planets
            if p["owner"] == pid
        ]

        targets = [
            p for p in planets
            if p["owner"] != pid
        ]

        if not mine or not targets:
            return []

        my_planets_count = len(mine)

        moves = []

        used_targets = set()

        # strongest planets first
        mine_sorted = sorted(
            mine,
            key=lambda p: p["ships"],
            reverse=True
        )

        for src in mine_sorted:

            if src["ships"] < 6:
                continue

            # defensive reserve
            incoming = incoming_enemy_strength(
                state,
                pid,
                src
            )

            safe_ships = src["ships"] - incoming

            if safe_ships < 6:
                continue

            best_score = -999999

            best_target = None
            best_angle = None
            best_needed = None

            for tgt in targets:

                if tgt["id"] in used_targets:
                    continue

                score, angle, needed = evaluate_target(
                    src,
                    tgt,
                    state,
                    pid,
                    my_planets_count
                )

                if score > best_score:

                    best_score = score

                    best_target = tgt

                    best_angle = angle

                    best_needed = needed

            if best_target is None:
                continue

            send = min(
                src["ships"] - 1,
                best_needed + 3
            )

            if send < 3:
                continue

            moves.append([
                src["id"],
                best_angle,
                int(send)
            ])

            used_targets.add(best_target["id"])

        return moves

    except Exception:
        return []