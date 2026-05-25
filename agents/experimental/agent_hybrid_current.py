# HYPOTHESIS: Adjust EV additive value
# ROUND: 1 | DATE: 2024-05-25
# BASED ON: champion.py
# CHANGELOG: Adjust EV additive value
import math

# ─────────────────────────────────────────────────────────────────────────────
# GAME PHYSICS & UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def spd(n):
    """Logarithmic fleet speed formula from Orbit Wars rules."""
    if n <= 1:
        return 1.0
    safe_n = max(float(n), 1.0001)
    val = 1.0 + 5.0 * (math.log(safe_n) / math.log(1000)) ** 1.5
    return min(6.0, val)

def segment_intersects_circle(x1, y1, x2, y2, cx, cy, r):
    """Checks if a 2D line segment between (x1, y1) and (x2, y2) intersects a circle."""
    vx, vy = x2 - x1, y2 - y1
    len2 = vx * vx + vy * vy
    if len2 == 0:
        return (x1 - cx) ** 2 + (y1 - cy) ** 2 <= r * r
    t = max(0.0, min(1.0, ((cx - x1) * vx + (cy - y1) * vy) / len2))
    nx, ny = x1 + t * vx, y1 + t * vy
    return (nx - cx) ** 2 + (ny - cy) ** 2 <= r * r

def hits_sun(x1, y1, x2, y2, margin=0.7):
    """Checks if the trajectory hits the central sun (50, 50) with a safety margin."""
    return segment_intersects_circle(x1, y1, x2, y2, 50.0, 50.0, 10.0 + margin)

def hits_any_planet(x1, y1, x2, y2, src_id, tgt_id, state):
    """Checks if the trajectory hits the sun or any intermediate planet."""
    if hits_sun(x1, y1, x2, y2, margin=0.7):
        return True

    # Check other planets
    for p in state['planets']:
        if p['id'] == src_id or p['id'] == tgt_id:
            continue
        # Use current position of the intermediate planet as an approximation
        if segment_intersects_circle(x1, y1, x2, y2, p['x'], p['y'], p['r'] + 0.5):
            return True
    return False

def orbit_pos(pid, ips, vel, step, tick):
    """Predicts the position of an orbital planet at turn (step + tick)."""
    ip = ips.get(pid)
    if not ip:
        return None, None
    r = math.hypot(ip['x'] - 50, ip['y'] - 50)
    if r < 1.0:
        return ip['x'], ip['y']
    a0 = math.atan2(ip['y'] - 50, ip['x'] - 50)
    a = a0 + vel * (step + tick)
    return 50 + r * math.cos(a), 50 + r * math.sin(a)

def get_target_pos(tgt, vel, ips, step, tick, state):
    """Computes exact coordinate lookahead for all target types."""
    if tgt['id'] in state['comet_planet_ids']:
        for grp in state.get('comets', []):
            if tgt['id'] in grp['planet_ids']:
                idx = grp['planet_ids'].index(tgt['id'])
                path = grp['paths'][idx]
                p_idx = grp['path_index'] + tick
                if 0 <= p_idx < len(path):
                    return path[p_idx][0], path[p_idx][1]
                return None, None
    if tgt['id'] in state['moving']:
        return orbit_pos(tgt['id'], ips, vel, step, tick)
    return tgt['x'], tgt['y']

def find_angle(src, tgt, ships, vel, ips, step, state, max_ticks=80):
    """
    Trajectory solver that dynamically sweeps safe offset angles.
    Guarantees the offset vector will intersect the target planet's circle.
    """
    speed = spd(ships)
    for tick in range(1, max_ticks):
        tx, ty = get_target_pos(tgt, vel, ips, step, tick, state)
        if tx is None:
            continue

        dist = math.hypot(src['x'] - tx, src['y'] - ty)
        travel_needed = dist - tgt['r'] - src['r'] - 0.1
        if speed * tick < travel_needed:
            continue

        base_angle = math.atan2(ty - src['y'], tx - src['x'])
        # Start exactly at planet surface boundary to avoid self-collision
        sx = src['x'] + math.cos(base_angle) * (src['r'] + 0.1)
        sy = src['y'] + math.sin(base_angle) * (src['r'] + 0.1)

        # Check direct line
        if not hits_any_planet(sx, sy, tx, ty, src['id'], tgt['id'], state):
            return base_angle, tick

        # Dynamic evasion offset sweep
        max_off = math.asin(min(0.99, tgt['r'] / max(dist, 1.0)))
        for factor in [0.08, -0.08, 0.25, -0.25, 0.5, -0.5, 0.75, -0.75, 0.95, -0.95]:
            a = base_angle + factor * max_off
            sx2 = src['x'] + math.cos(a) * (src['r'] + 0.1)
            sy2 = src['y'] + math.sin(a) * (src['r'] + 0.1)
            tx2 = src['x'] + math.cos(a) * dist
            ty2 = src['y'] + math.sin(a) * dist

            if not hits_any_planet(sx2, sy2, tx2, ty2, src['id'], tgt['id'], state):
                return a, tick

    return None, None

def is_heading_to(f, p):
    """Checks if a fleet's heading vector passes through a planet's radius + threshold."""
    vx, vy = math.cos(f['angle']), math.sin(f['angle'])
    dx, dy = p['x'] - f['x'], p['y'] - f['y']
    proj = dx * vx + dy * vy
    if proj < 0:
        return False
    px, py = f['x'] + vx * proj, f['y'] + vy * proj
    return math.hypot(px - p['x'], py - p['y']) <= p['r'] + 2.0

# ─────────────────────────────────────────────────────────────────────────────
# STRATEGIC CO-ORBIT & ALGEBRAIC TIMELINE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def is_co_orbit_adjacent(src, tgt):
    r1 = math.hypot(src['x'] - 50, src['y'] - 50)
    r2 = math.hypot(tgt['x'] - 50, tgt['y'] - 50)
    if abs(r1 - r2) > 8.0:
        return False
    a1 = math.atan2(src['y'] - 50, src['x'] - 50)
    a2 = math.atan2(tgt['y'] - 50, tgt['x'] - 50)
    diff = abs(math.atan2(math.sin(a1 - a2), math.cos(a1 - a2)))
    return diff < 0.40

def compute_precise_needed_fast(src, tgt, eta, state, pid):
    """
    Event-driven algebraic timeline analyzer.
    Runs in O(F) where F is the number of fleets, avoiding slow nested simulation loops.
    """
    tgt_fleets = []
    for f in state['fleets']:
        if is_heading_to(f, tgt):
            d = math.hypot(tgt['x'] - f['x'], tgt['y'] - f['y'])
            f_speed = spd(f['ships'])
            f_eta = max(1, int(math.ceil(d / max(f_speed, 0.1))))
            tgt_fleets.append({
                'owner': f['owner'],
                'ships': f['ships'],
                'eta': f_eta
            })

    # Sort en-route fleets chronologically
    tgt_fleets.sort(key=lambda x: x['eta'])

    curr_owner = tgt['owner']
    curr_ships = tgt['ships']
    curr_time = 0
    prod = tgt['prod']

    events_before = [f for f in tgt_fleets if f['eta'] <= eta]

    # Simulate arrivals chronologically before our fleet lands
    for f in events_before:
        dt = f['eta'] - curr_time
        if dt > 0:
            if curr_owner >= 0:
                curr_ships += prod * dt
            curr_time = f['eta']

        if f['owner'] == curr_owner:
            curr_ships += f['ships']
        else:
            if f['ships'] > curr_ships:
                curr_owner = f['owner']
                curr_ships = f['ships'] - curr_ships
            else:
                curr_ships -= f['ships']

    # Advance remaining turns to our arrival
    dt = eta - curr_time
    if dt > 0 and curr_owner >= 0:
        curr_ships += prod * dt

    # Standard baseline needed to capture/reinforce
    if curr_owner == pid:
        base_needed = 1
    else:
        base_needed = int(curr_ships + 1)

    # Analyze en-route hostile arrivals AFTER our arrival
    events_after = [f for f in tgt_fleets if f['eta'] > eta]
    if not events_after:
        return base_needed

    # Determine the maximum safety deficit caused by subsequent hostile arrivals
    garrison_after_landing = (curr_ships + base_needed) if curr_owner == pid else (base_needed - curr_ships)
    temp_owner = pid
    temp_ships = garrison_after_landing
    curr_time = eta
    max_deficit = 0

    for f in events_after:
        dt = f['eta'] - curr_time
        if dt > 0:
            temp_ships += prod * dt
            curr_time = f['eta']

        if f['owner'] == temp_owner:
            temp_ships += f['ships']
        else:
            safety_margin = int(f['ships'] * 1.25 + 3)
            if temp_ships < safety_margin:
                deficit = safety_margin - temp_ships
                max_deficit = max(max_deficit, deficit)
                temp_ships += deficit # Assume we sent this to survive

            if f['ships'] > temp_ships:
                temp_owner = f['owner']
                temp_ships = f['ships'] - temp_ships
            else:
                temp_ships -= f['ships']

    return base_needed + max_deficit

# ─────────────────────────────────────────────────────────────────────────────
# TARGET EVALUATION & SCORING
# ─────────────────────────────────────────────────────────────────────────────

def comet_lifetime(tgt_id, state):
    for grp in state.get('comets', []):
        if tgt_id in grp['planet_ids']:
            idx = grp['planet_ids'].index(tgt_id)
            path = grp['paths'][idx]
            return max(0, len(path) - grp['path_index'])
    return 0

def score_target(src, tgt, eta, is_comet, step, needed, mine, planets, pid, state, already_sent=0):
    dist = math.hypot(src['x'] - tgt['x'], src['y'] - tgt['y'])

    # CORRECT step horizon (1000 steps instead of 500)
    ticks_remaining = max(1, 1000 - step - eta)

    # Comet scoring
    if is_comet:
        lifetime = comet_lifetime(tgt['id'], state)
        if lifetime <= eta:
            return -9999
        return tgt['prod'] * (lifetime - eta) * 3.0 + 500

    # Base Economic ROI
    ev = tgt['prod'] * ticks_remaining / (1.0 + 0.05 * eta)

    # Static planet anchoring bonus
    is_moving = tgt['id'] in state['moving']
    if not is_moving:
        anchor_bonus = max(0.0, 40.0 - dist) * 15.0
        ev += anchor_bonus

    # Proximity/influence reinforcement bonus
    min_dist_to_us = min(math.hypot(p['x'] - tgt['x'], p['y'] - tgt['y']) for p in mine)
    if min_dist_to_us < 30.0:
        ev += (30.0 - min_dist_to_us) * 20.0

    # Co-orbit Ring adjacency bonus
    if is_co_orbit_adjacent(src, tgt):
        ev += 4000.0

    # Aggressive neutral expansion early-game bonuses
    if tgt['owner'] == -1:
        neutral_mult = max(1.0, 2.8 - (step / 400.0) * 1.8)
        ev *= neutral_mult
        ev += max(10.0, 300.0 - 0.5 * step - 20.0 * len(mine))

    # Over-extension early-game penalties
    enemy_planets = [p for p in planets if p['owner'] >= 0 and p['owner'] != pid]
    if enemy_planets:
        min_dist_to_enemy = min(math.hypot(p['x'] - tgt['x'], p['y'] - tgt['y']) for p in enemy_planets)
        if min_dist_to_enemy < min_dist_to_us - 10.0 and step < 250:
            ev -= (min_dist_to_us - min_dist_to_enemy) * 15.0

    effective_needed = max(0, needed - already_sent)
    return ev - effective_needed * 10.0

# ─────────────────────────────────────────────────────────────────────────────
# TACTICAL ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_moves(state, pid):
    planets  = state['planets']
    fleets   = state['fleets']
    ips      = state['ips']
    vel      = state['angular_velocity']
    comets   = state['comet_planet_ids']
    step     = state['step']

    mine    = [p for p in planets if p['owner'] == pid]
    targets = [p for p in planets if p['owner'] != pid]

    if not mine:
        return []

    total_ships = sum(p['ships'] for p in planets) + sum(f['ships'] for f in fleets)
    my_ships    = sum(p['ships'] for p in mine) + sum(f['ships'] for f in fleets if f['owner'] == pid)
    snowball    = my_ships >= 0.50 * total_ships and len(mine) >= len(planets) * 0.35

    # Group friendly en-route fleet forces by their targets
    pending = {p['id']: 0.0 for p in targets}
    for f in fleets:
        if f['owner'] != pid:
            continue
        best_id, best_diff = None, 0.35
        for tgt in targets:
            dx, dy = tgt['x'] - f['x'], tgt['y'] - f['y']
            if math.hypot(dx, dy) < 1.0:
                continue
            a_to = math.atan2(dy, dx)
            diff = abs(math.atan2(math.sin(f['angle'] - a_to), math.cos(f['angle'] - a_to)))
            if diff < best_diff:
                best_diff, best_id = diff, tgt['id']
        if best_id is not None:
            pending[best_id] = pending.get(best_id, 0) + f['ships']

    available = {p['id']: p['ships'] for p in mine}
    moves = []

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 1 — DYNAMIC DEFENSE & REINFORCEMENTS
    # ════════════════════════════════════════════════════════════════════════
    for p in mine:
        enemy_fleets = [(f, math.hypot(p['x'] - f['x'], p['y'] - f['y']))
                        for f in fleets
                        if f['owner'] != pid and f['owner'] >= 0 and is_heading_to(f, p)]
        if not enemy_fleets:
            continue

        incoming_ships = sum(f['ships'] for f, _ in enemy_fleets)
        closest_f, closest_dist = min(enemy_fleets, key=lambda x: x[1])
        threat_eta = closest_dist / max(spd(closest_f['ships']), 0.1)

        if threat_eta >= 25.0:
            continue

        production_turns = int(math.floor(threat_eta))
        garrison = p['ships'] + p['prod'] * production_turns
        safety_need = int(incoming_ships * 1.3 + 5)

        if garrison >= safety_need:
            continue

        deficit = safety_need - garrison
        if deficit < 3:
            continue

        # Sort helpers by proximity to target
        helpers = sorted(
            [m for m in mine if m['id'] != p['id'] and available[m['id']] > 5],
            key=lambda m: math.hypot(m['x'] - p['x'], m['y'] - p['y'])
        )
        for h in helpers:
            send = min(int(available[h['id']] * 0.75), int(deficit + 4))
            if send < 3:
                continue
            angle, eta = find_angle(h, p, send, vel, ips, step, state)

            # CRITICAL CHECK: Reinforcement MUST arrive strictly before threat
            if angle is not None and eta < threat_eta:
                moves.append([h['id'], angle, send])
                available[h['id']] -= send
                deficit -= send
                if deficit <= 0:
                    break

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 2 — LAUNCH ATTACKS & EXPANSION
    # ════════════════════════════════════════════════════════════════════════
    mine_sorted = sorted(mine, key=lambda p: -available[p['id']])
    this_turn_sent = {p['id']: 0.0 for p in targets}

    for src in mine_sorted:
        # Secure minimal reserve for extreme early expansion
        keep = 1 if (snowball or len(mine) < 3) else 2
        max_launches = 3
        launches = 0

        while available[src['id']] > keep and launches < max_launches:
            avail = available[src['id']]
            best_score = -float('inf')
            best_tgt   = None
            best_angle = None
            best_send  = 0
            best_needed = 0

            for tgt in targets:
                is_comet = tgt['id'] in comets
                dist = math.hypot(src['x'] - tgt['x'], src['y'] - tgt['y'])

                # ── Defensive Bunkering Check ────────────────────────────────
                incoming_threats = [f for f in fleets if f['owner'] != pid and is_heading_to(f, src)]
                if incoming_threats:
                    closest_threat = min(incoming_threats, key=lambda f: math.hypot(src['x'] - f['x'], src['y'] - f['y']))
                    tdist = math.hypot(src['x'] - closest_threat['x'], src['y'] - closest_threat['y'])
                    if tdist <= 85.0:
                        t_eta = tdist / max(spd(closest_threat['ships']), 0.1)
                        garrison_at_impact = avail + src['prod'] * int(math.floor(t_eta))
                        total_threat_ships = sum(f['ships'] for f in incoming_threats)
                        if garrison_at_impact - 5 < total_threat_ships * 1.25:
                            continue

                reserve = 1 if (snowball or len(mine) < 3) else 2
                max_send = avail - reserve
                if max_send < 2:
                    continue

                if is_comet:
                    send = min(int(max_send), 2)
                    needed = 2
                    res = find_angle(src, tgt, send, vel, ips, step, state)
                    if res[0] is None:
                        continue
                    angle, eta = res
                else:
                    send = min(int(max_send), int(tgt['ships']) + 4)
                    angle = None
                    eta = 0
                    needed = 0

                    for _ in range(3):
                        if send < 2:
                            break
                        res = find_angle(src, tgt, send, vel, ips, step, state)
                        if res[0] is None:
                            break
                        angle, eta = res

                        committed = pending.get(tgt['id'], 0) + this_turn_sent.get(tgt['id'], 0)

                        # Use lightning-fast event-driven bidding engine
                        needed = compute_precise_needed_fast(src, tgt, eta, state, pid)
                        needed = max(0, int(needed - committed))

                        if needed == 0:
                            send = 0
                            break

                        send = min(int(max_send), max(int(needed * 1.15), needed + 2))

                    if send < needed or send < 2 or angle is None or needed == 0:
                        continue

                committed = pending.get(tgt['id'], 0) + this_turn_sent.get(tgt['id'], 0)
                sc = score_target(src, tgt, eta, is_comet, step, needed, mine, planets, pid, state, committed)

                if sc > best_score:
                    best_score = sc
                    best_tgt   = tgt
                    best_angle = angle
                    best_send  = send
                    best_needed = needed

            # Allow small micro-attacks (send >= 2) early on
            if best_tgt is None or best_send < 2:
                break

            moves.append([src['id'], best_angle, best_send])
            available[src['id']] -= best_send
            this_turn_sent[best_tgt['id']] = this_turn_sent.get(best_tgt['id'], 0) + best_send
            launches += 1

    return moves

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def parse_obs(obs):
    raw_planets  = obs.get("planets", [])
    raw_fleets   = obs.get("fleets", [])
    raw_ips      = obs.get("initial_planets", [])

    ips = {}
    for p in raw_ips:
        ips[int(p[0])] = {
            'id': int(p[0]), 'owner': int(p[1]),
            'x': float(p[2]), 'y': float(p[3]),
            'r': float(p[4]), 'ships': float(p[5]), 'prod': float(p[6])
        }

    comet_ids = set(obs.get("comet_planet_ids", []))
    moving    = set()
    for p in raw_planets:
        pid = int(p[0])
        if pid in comet_ids:
            continue
        if math.hypot(float(p[2]) - 50, float(p[3]) - 50) + float(p[4]) < 50:
            moving.add(pid)

    planets = [{
        'id': int(p[0]), 'owner': int(p[1]),
        'x': float(p[2]), 'y': float(p[3]),
        'r': float(p[4]), 'ships': float(p[5]), 'prod': float(p[6])
    } for p in raw_planets]

    fleets = [{
        'id': int(f[0]), 'owner': int(f[1]),
        'x': float(f[2]), 'y': float(f[3]),
        'angle': float(f[4]), 'from_planet_id': int(f[5]), 'ships': float(f[6])
    } for f in raw_fleets]

    return {
        'planets': planets, 'fleets': fleets, 'ips': ips,
        'angular_velocity': obs.get("angular_velocity", 0.0),
        'step': obs.get("step", 0),
        'comet_planet_ids': comet_ids,
        'moving': moving,
        'comets': obs.get("comets", [])
    }

def agent(obs):
    try:
        state = parse_obs(obs)
        pid   = obs.get("player", 0)
        return compute_moves(state, pid)
    except Exception:
        return []
