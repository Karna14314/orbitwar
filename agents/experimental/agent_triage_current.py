# HYPOTHESIS: Macro change: Adjusted defensive triage logic. Defend check radius increased to 50, threat_eta increased to 30 to be more proactive in defense.
# ROUND: 1 | DATE: 2024-05-21
# BASED ON: champion.py
# CHANGELOG: Defend check radius increased to 50, threat_eta increased to 30.
"""
Orbit Wars Agent — V6 (Tactical Action-Generation MCTS + Advanced Evaluator)
Submit this file directly: kaggle competitions submit orbit-wars -f submission.py -m "V6 Tactical MCTS"
"""
"""
Orbit Wars Agent — V6 (Tactical Action-Generation MCTS + Advanced Evaluator)
Submit this file directly: kaggle competitions submit orbit-wars -f submission.py -m "V6 Tactical MCTS"

Features & Enhancements:
  - Advanced Multi-Term Evaluator (Economy, Tactical Power, Center Control, Vulnerability Deficits)
  - Precise Force Commitment (min(max_send, needed + 3) to prevent overcommitment)
  - Action-Generation Candidate Compositions (Coordinated Attacks, Econ Expansion, Focused Defense)
  - Opponent Pool Simulation (Aggressive, Economic, and Turtle policies sampled during rollouts)
  - Progressive/Adaptive Rollout Horizon (60 / 40 / 20 ticks based on game step)
  - Strict Deep Copying (eliminates MCTS tree/state corruption bugs)
"""
import math
import time
import random

# ==============================================================================
# PHYSICS & VECTOR MATHEMATICS HELPERS
# ==============================================================================

def spd(n):
    """Logarithmic fleet speed calculation from README."""
    if n <= 1:
        return 1.0
    return 1.0 + 5.0 * (math.log(n) / math.log(1000)) ** 1.5

def segment_intersects_circle(x1, y1, x2, y2, cx, cy, r):
    """Check if line segment (x1, y1) -> (x2, y2) intersects circle at (cx, cy) with radius r."""
    vx, vy = x2 - x1, y2 - y1
    len2 = vx*vx + vy*vy
    if len2 == 0:
        return (x1-cx)**2 + (y1-cy)**2 <= r*r
    t = max(0.0, min(1.0, ((cx-x1)*vx + (cy-y1)*vy) / len2))
    nearest_x, nearest_y = x1 + t*vx, y1 + t*vy
    return (nearest_x-cx)**2 + (nearest_y-cy)**2 <= r*r

def hits_sun(x1, y1, x2, y2, margin=0.6):
    """Determine if a fleet's travel segment hits the sun at (50, 50) with radius 10.0 + margin."""
    return segment_intersects_circle(x1, y1, x2, y2, 50.0, 50.0, 10.0 + margin)

def future_pos_state_absolute(pid, ips, vel, abs_step):
    """Predict the future x, y coordinates of an orbiting planet at absolute step."""
    ip = ips.get(pid)
    if not ip:
        return None, None
    r = math.hypot(ip['x'] - 50, ip['y'] - 50)
    if r < 1.0:
        return ip['x'], ip['y']
    a0 = math.atan2(ip['y'] - 50, ip['x'] - 50)
    a = a0 + vel * abs_step
    return 50 + r * math.cos(a), 50 + r * math.sin(a)

def get_target_pos(src, tgt, vel, ips, step, tick, state=None):
    """Get the target's exact position at step + tick, handling comets, orbiting, and static planets."""
    if state and 'comet_planet_ids' in state and tgt['id'] in state['comet_planet_ids']:
        for group in state.get('comets', []):
            if tgt['id'] in group['planet_ids']:
                idx = group['planet_ids'].index(tgt['id'])
                path = group['paths'][idx]
                p_idx = group['path_index'] + tick
                if 0 <= p_idx < len(path):
                    return path[p_idx][0], path[p_idx][1]
                else:
                    return None, None  # Comet has expired
    # Orbiting planet checking
    is_moving = False
    if state and 'moving' in state:
        is_moving = tgt['id'] in state['moving']
    elif tgt['id'] in ips:
        # Fallback if no state object
        ip = ips[tgt['id']]
        if math.hypot(ip['x'] - 50, ip['y'] - 50) < 45.0:
            is_moving = True

    if is_moving:
        return future_pos_state_absolute(tgt['id'], ips, vel, step + tick)
    return tgt['x'], tgt['y']

def find_angle_state(src, tgt, ships, vel, ips, step_or_moving, state=None):
    """Determine optimal launch angle and ETA to target planet, avoiding the sun."""
    speed = spd(ships)

    # Decouple step_or_moving:
    if isinstance(step_or_moving, bool) or (isinstance(step_or_moving, int) and step_or_moving in (0, 1)):
        is_moving = bool(step_or_moving)
        step = state['step'] if state else 0
    else:
        step = step_or_moving
        is_moving = tgt['id'] in state['moving'] if state else False

    for tick in range(1, 80):
        tx, ty = get_target_pos(src, tgt, vel, ips, step, tick, state)
        if tx is None:
            # Fallback if target position couldn't be obtained
            if is_moving:
                tx, ty = future_pos_state_absolute(tgt['id'], ips, vel, step + tick)
                if tx is None:
                    tx, ty = tgt['x'], tgt['y']
            else:
                tx, ty = tgt['x'], tgt['y']

        dist = math.hypot(src['x'] - tx, src['y'] - ty)
        dist_to_travel = dist - tgt['r'] - src['r'] - 0.1

        if speed * tick >= dist_to_travel:
            base_angle = math.atan2(ty - src['y'], tx - src['x'])

            # Trajectory check starting from the actual fleet spawn boundary
            x_spawn = src['x'] + math.cos(base_angle) * (src['r'] + 0.1)
            y_spawn = src['y'] + math.sin(base_angle) * (src['r'] + 0.1)

            if not hits_sun(x_spawn, y_spawn, tx, ty, margin=0.6):
                return base_angle, tick

            # Sun evasion search
            for off in [0.08, -0.08, 0.15, -0.15, 0.3, -0.3, 0.45, -0.45]:
                a = base_angle + off
                x_spawn_off = src['x'] + math.cos(a) * (src['r'] + 0.1)
                y_spawn_off = src['y'] + math.sin(a) * (src['r'] + 0.1)
                tx_test = src['x'] + math.cos(a) * dist
                ty_test = src['y'] + math.sin(a) * dist
                if not hits_sun(x_spawn_off, y_spawn_off, tx_test, ty_test, margin=0.6):
                    return a, tick
    return None, None

def is_heading_to(f, p):
    """Determine if fleet f's travel vector is heading toward planet p using precise swept distance."""
    vx, vy = math.cos(f['angle']), math.sin(f['angle'])
    dx, dy = p['x'] - f['x'], p['y'] - f['y']
    proj_len = dx * vx + dy * vy
    if proj_len < 0:
        return False
    px = f['x'] + vx * proj_len
    py = f['y'] + vy * proj_len
    perp_dist = math.hypot(px - p['x'], py - p['y'])
    return perp_dist <= p['r'] + 2.0

# ==============================================================================
# PHASE CONTROLLER & GAME METRICS
# ==============================================================================

def get_game_phase(state, pid):
    """Classify the current strategic phase of the game."""
    mine = [p for p in state['planets'] if p['owner'] == pid]
    enemy = [p for p in state['planets'] if p['owner'] not in (pid, -1)]
    neutrals = [p for p in state['planets'] if p['owner'] == -1]
    step = state['step']

    if not mine:
        return "LOSING"
    if len(neutrals) > 5 and step < 150:
        return "EARLY_EXPANSION"
    if len(enemy) > len(mine) * 1.7:
        return "LOSING_TURTLE"
    if step > 400 or len(neutrals) <= 1:
        return "LATE_KILL"
    return "MID_SNOWBALL"

# ==============================================================================
# STRATEGIC TARGET SCORE FUNCTION
# ==============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# CO-ORBIT ADJACENCY  (V8 feature)
# ─────────────────────────────────────────────────────────────────────────────

def orbital_radius(p):
    return math.hypot(p['x'] - 50, p['y'] - 50)

def angular_separation(p1, p2):
    """Absolute angular gap between two planets as seen from the sun."""
    a1 = math.atan2(p1['y'] - 50, p1['x'] - 50)
    a2 = math.atan2(p2['y'] - 50, p2['x'] - 50)
    diff = abs(math.atan2(math.sin(a1 - a2), math.cos(a1 - a2)))
    return diff

def is_co_orbit_adjacent(src, tgt, r_tol=8.0, ang_tol=0.40):
    """
    True if src and tgt are on roughly the same orbit ring AND
    close in angle — i.e., they are co-orbiting neighbors.
    """
    dr = abs(orbital_radius(src) - orbital_radius(tgt))
    if dr > r_tol:
        return False
    ang = angular_separation(src, tgt)
    return ang < ang_tol

def comet_lifetime(tgt_id, state):
    if not state:
        return 0
    for grp in state.get('comets', []):
        if tgt_id in grp['planet_ids']:
            idx = grp['planet_ids'].index(tgt_id)
            path = grp['paths'][idx]
            return max(0, len(path) - grp['path_index'])
    return 0

def score_target_state(src, tgt, eta, is_comet, step, needed, mine_count=1, state=None, already_sent=0):
    """
    Economic Value score with:
      - 500-turn horizon (corrected)
      - Co-orbit adjacency mega-bonus
      - Smooth neutral multiplier decay
      - Enemy denial bonus
      - Cluster-choke heuristic
      - Cheap comet override
    """
    dist = math.hypot(src['x'] - tgt['x'], src['y'] - tgt['y'])
    ticks_remaining = max(1, 500 - step - eta)

    # ── Comet: override everything ──────────────────────────────────────────
    if is_comet:
        lifetime = comet_lifetime(tgt['id'], state)
        if lifetime <= eta:
            return -9999   # expires before arrival
        return tgt['prod'] * (lifetime - eta) * 3.0 + 500   # always high priority

    # ── Base economic value ──────────────────────────────────────────────────
    ev = tgt['prod'] * ticks_remaining
    score = ev / (1.0 + (dist / 16.0) ** 2)

    # ── Co-orbit adjacency: MASSIVE bonus ───────────────────────────────────
    if is_co_orbit_adjacent(src, tgt):
        score += 4000.0  # dominant priority

    # ── Raw proximity bonus (Euclidean) ─────────────────────────────────────
    if dist < 25.0:
        score += (25.0 - dist) * 60.0   # up to +1500

    # ── Neutral planet bonuses ──────────────────────────────────────────────
    if tgt['owner'] == -1:
        neutral_mult = max(1.0, 2.8 - (step / 400.0) * 1.8)
        score *= neutral_mult
        neutral_bonus = max(5, 250 - 0.6 * step - 25 * mine_count)
        score += neutral_bonus

    # ── Enemy planet bonuses ─────────────────────────────────────────────────
    if tgt['owner'] >= 0:
        score += tgt['prod'] * 100.0
        score += max(0.0, (40.0 - dist) * 35.0)

    # ── Force cost penalty ───────────────────────────────────────────────────
    effective_needed = max(0, needed - already_sent)
    score -= effective_needed * 12.0

    return score

# ==============================================================================
# MAIN TACTICAL ENGINE
# ==============================================================================

def heuristic_moves(state, pid, exclude_targets=None):
    """
    V8 AGGRESSOR Heuristic Strategy:
      - Multi-fire: every planet fires multiple times per turn if surplus exists.
      - Cooperative targeting: multiple source planets can target the same hard target.
      - Proactive defense (threat ETA < 20 ticks, defense-check radius 40).
      - Precise needed + buffer calculation to guarantee capture.
      - Support for MCTS exclude_targets exploration.
    """
    if exclude_targets is None:
        exclude_targets = set()

    planets = state['planets']
    fleets = state['fleets']
    ips = state['ips']
    vel = state['angular_velocity']
    comets = state.get('comet_planet_ids', set())
    step = state['step']

    mine = [p for p in planets if p['owner'] == pid]
    targets = [p for p in planets if p['owner'] != pid and p['id'] not in exclude_targets]

    if not mine:
        return []

    # ── 1. Calculate incoming friendly ships (to subtract from needed) ──────
    pending_incoming = {p['id']: 0 for p in targets}
    for f in fleets:
        if f['owner'] == pid:
            best_tgt = None
            best_diff = 0.35
            for t in targets:
                dx, dy = t['x'] - f['x'], t['y'] - f['y']
                dist = math.hypot(dx, dy)
                if dist < 1.0:
                    continue
                a_tgt = math.atan2(dy, dx)
                diff = abs(math.atan2(math.sin(f['angle'] - a_tgt), math.cos(f['angle'] - a_tgt)))
                if diff < best_diff:
                    best_diff = diff
                    best_tgt = t['id']
            if best_tgt is not None:
                pending_incoming[best_tgt] += f['ships']

    # ── 2. Defense: Reinforce threatened friendly planets ────────────────────
    available_ships = {p['id']: p['ships'] for p in mine}
    moves = []

    for p in mine:
        incoming_fleets = []
        for f in fleets:
            if f['owner'] == pid or f['owner'] < 0:
                continue
            # Defend check radius is 40.0 (V8 feature)
            dist = math.hypot(p['x'] - f['x'], p['y'] - f['y'])
            if dist <= 50.0 and is_heading_to(f, p):
                incoming_fleets.append((f, dist))

        if not incoming_fleets:
            continue

        incoming_ships = sum(f['ships'] for f, _ in incoming_fleets)
        closest_f, closest_dist = min(incoming_fleets, key=lambda x: x[1])
        threat_eta = closest_dist / max(spd(closest_f['ships']), 0.1)

        # Proactive defense only if threat is close (V8 feature: threat_eta < 20.0)
        if threat_eta >= 30.0:
            continue

        production_turns = int(math.floor(threat_eta))
        garrison_at_impact = p['ships'] + p['prod'] * production_turns

        safety_threshold = int(incoming_ships * 1.35 + 4)
        if garrison_at_impact >= safety_threshold:
            continue

        deficit = safety_threshold - garrison_at_impact
        if deficit < 3:
            continue

        helpers = sorted(
            [m for m in mine if m['id'] != p['id'] and available_ships[m['id']] > 10],
            key=lambda m: math.hypot(m['x'] - p['x'], m['y'] - p['y'])
        )

        for h in helpers:
            send = min(int(available_ships[h['id']] * 0.65), int(deficit))
            if send < 3:
                continue
            angle, eta = find_angle_state(h, p, send, vel, ips, step, state)
            if angle is not None:
                moves.append([h['id'], angle, send])
                available_ships[h['id']] -= send
                deficit -= send
                if deficit <= 0:
                    break

    # ── 3. Aggressive Attack multi-fire loop ─────────────────────────────────
    mine_sorted = sorted(mine, key=lambda p: p['ships'], reverse=True)
    # Track targeted commitments per target during this turn's heuristic loop
    this_turn_sent = {p['id']: 0 for p in targets}

    for src in mine_sorted:
        launches = 0
        min_surplus = 5 if len(mine) > 3 else 10

        # V8 feature: cap launches at 4 per planet to avoid complete exhaustion
        while available_ships[src['id']] >= 4 and launches < 4:
            best_score = -float('inf')
            best_tgt = None
            best_angle = None
            best_needed = 0
            best_send = 0

            for tgt in targets:
                is_comet = tgt['id'] in comets
                dist = math.hypot(src['x'] - tgt['x'], src['y'] - tgt['y'])

                # Reserve requirement
                required_reserve = 1 if dist < 25.0 else min_surplus

                # Defend check before launch (V8 feature: check radius 40.0)
                under_threat = False
                incoming_threats = [f for f in fleets if f['owner'] != pid and is_heading_to(f, src)]
                if incoming_threats:
                    closest_threat = min(incoming_threats, key=lambda f: math.hypot(src['x'] - f['x'], src['y'] - f['y']))
                    tdist = math.hypot(src['x'] - closest_threat['x'], src['y'] - closest_threat['y'])
                    if tdist <= 50.0:
                        threat_eta = tdist / max(spd(closest_threat['ships']), 0.1)
                        if threat_eta < 30.0:
                            incoming_ships = sum(f['ships'] for f in incoming_threats)
                            garrison_at_impact = available_ships[src['id']] + src['prod'] * int(math.floor(threat_eta))
                            # If sending ships would leave us vulnerable to this close threat
                            if garrison_at_impact < incoming_ships + 5:
                                under_threat = True

                if under_threat:
                    continue  # Keep ships for defense

                # Determine force size
                send = min(int(available_ships[src['id']] - 1), tgt['ships'] + 5)
                angle = None
                eta = 0
                needed = 0

                for _ in range(3):
                    if send < 3:
                        break
                    res = find_angle_state(src, tgt, send, vel, ips, step, state)
                    if res[0] is None:
                        break
                    angle, eta = res

                    # Total incoming friendly force = pending from prior turns + this turn's actions
                    already_sent = pending_incoming.get(tgt['id'], 0) + this_turn_sent.get(tgt['id'], 0)

                    if is_comet:
                        needed = max(0, 2 - already_sent)
                    else:
                        needed = tgt['ships'] + 1
                        if tgt['owner'] >= 0:
                            needed += tgt['prod'] * eta
                        needed = max(0, needed - already_sent)

                    needed = int(math.ceil(needed))
                    # V8 multiplier: never lose a capture to production drift
                    send = min(int(available_ships[src['id']] - 1), int(needed * 1.35 + 4))

                if angle is None or send < 3 or available_ships[src['id']] - send < required_reserve:
                    continue

                sc = score_target_state(src, tgt, eta, is_comet, step, needed, len(mine), state,
                                        already_sent=(pending_incoming.get(tgt['id'], 0) + this_turn_sent.get(tgt['id'], 0)))
                if sc > best_score:
                    best_score = sc
                    best_tgt = tgt
                    best_angle = angle
                    best_needed = needed
                    best_send = send

            if best_tgt and available_ships[src['id']] >= best_send + 1:
                moves.append([src['id'], best_angle, best_send])
                available_ships[src['id']] -= best_send
                this_turn_sent[best_tgt['id']] += best_send
                launches += 1
            else:
                break

    return moves

# ==============================================================================
# OPPONENT METAGAME POOL SIMULATORS
# ==============================================================================

def get_opponent_move(state, opp_id, policy_type=None):
    """Simulate opponent actions dynamically chosen from three strategic playstyles."""
    if policy_type is None:
        policy_type = random.choice(["aggressive", "economic", "turtle"])

    planets = state['planets']
    ips = state['ips']
    vel = state['angular_velocity']
    moving = state['moving']

    mine = [p for p in planets if p['owner'] == opp_id]
    targets = [p for p in planets if p['owner'] != opp_id]

    if not mine:
        return []

    moves = []
    exhausted = set()

    if policy_type == "turtle":
        # Prioritize reinforcing threatened friendly planets
        for p in mine:
            incoming = sum(f['ships'] for f in state['fleets'] if f['owner'] != opp_id and is_heading_to(f, p))
            if incoming > p['ships']:
                deficit = int(incoming - p['ships'] + 3)
                helpers = sorted([m for m in mine if m['id'] != p['id'] and m['ships'] > 10], key=lambda m: math.hypot(m['x'] - p['x'], m['y'] - p['y']))
                for h in helpers:
                    send = min(int(h['ships'] * 0.5), deficit)
                    if send >= 3:
                        angle, _ = find_angle_state(h, p, send, vel, ips, p['id'] in moving)
                        if angle is not None:
                            moves.append([h['id'], angle, send])
                            exhausted.add(h['id'])
                            break

    elif policy_type == "economic":
        # Prioritize neutral high-production planets
        neutrals = sorted([p for p in targets if p['owner'] == -1], key=lambda x: x['prod'], reverse=True)
        for src in mine:
            if src['ships'] < 10:
                continue
            for tgt in neutrals:
                needed = int(tgt['ships'] + 3)
                if src['ships'] > needed + 5:
                    angle, _ = find_angle_state(src, tgt, needed, vel, ips, tgt['id'] in moving)
                    if angle is not None:
                        moves.append([src['id'], angle, needed])
                        break

    else:  # aggressive
        # Prioritize attacking weakest target planets
        weakest = sorted(targets, key=lambda x: x['ships'])
        for src in mine:
            if src['ships'] < 10:
                continue
            for tgt in weakest:
                needed = int(tgt['ships'] + 5)
                if src['ships'] > needed + 5:
                    angle, _ = find_angle_state(src, tgt, needed, vel, ips, tgt['id'] in moving)
                    if angle is not None:
                        moves.append([src['id'], angle, needed])
                        break

    return moves

# ==============================================================================
# STATE & PHYSICS SIMULATOR (ZERO-CORRUPTION DEEP COPIES)
# ==============================================================================

def obs_to_state(obs):
    """Convert Kaggle JSON list observations into fast plain dictionary format."""
    planets = obs.get("planets", [])
    fleets = obs.get("fleets", [])
    initial_planets = obs.get("initial_planets", [])

    ips = {}
    for p in initial_planets:
        ips[p[0]] = {
            'id': int(p[0]),
            'owner': int(p[1]),
            'x': float(p[2]),
            'y': float(p[3]),
            'r': float(p[4]),
            'ships': float(p[5]),
            'prod': float(p[6])
        }

    comets = set(obs.get("comet_planet_ids", []))
    moving = set(comets)
    for p in planets:
        ip = ips.get(p[0])
        if ip and (abs(p[2] - ip['x']) > 0.01 or abs(p[3] - ip['y']) > 0.01):
            moving.add(p[0])

    state_planets = []
    for p in planets:
        state_planets.append({
            'id': int(p[0]),
            'owner': int(p[1]),
            'x': float(p[2]),
            'y': float(p[3]),
            'r': float(p[4]),
            'ships': float(p[5]),
            'prod': float(p[6])
        })

    state_fleets = []
    next_fleet_id = 0
    for f in fleets:
        state_fleets.append({
            'id': int(f[0]),
            'owner': int(f[1]),
            'x': float(f[2]),
            'y': float(f[3]),
            'angle': float(f[4]),
            'from_planet_id': int(f[5]),
            'ships': float(f[6])
        })
        if int(f[0]) >= next_fleet_id:
            next_fleet_id = int(f[0]) + 1

    return {
        'planets': state_planets,
        'fleets': state_fleets,
        'angular_velocity': obs.get("angular_velocity", 0.0),
        'ips': ips,
        'step': obs.get("step", 0),
        'comet_planet_ids': comets,
        'moving': moving,
        'comets': obs.get("comets", []),
        'next_fleet_id': next_fleet_id
    }

def copy_state(state):
    """Ultra-fast custom dictionary copying (strictly copies mutable structures to prevent search corruption)."""
    return {
        'planets': [
            {
                'id': p['id'],
                'owner': p['owner'],
                'x': p['x'],
                'y': p['y'],
                'r': p['r'],
                'ships': p['ships'],
                'prod': p['prod']
            } for p in state['planets']
        ],
        'fleets': [
            {
                'id': f['id'],
                'owner': f['owner'],
                'x': f['x'],
                'y': f['y'],
                'angle': f['angle'],
                'ships': f['ships'],
                'from_planet_id': f['from_planet_id']
            } for f in state['fleets']
        ],
        'angular_velocity': state['angular_velocity'],
        'ips': {k: dict(v) for k, v in state['ips'].items()},  # Zero corruption deep dictionary copy
        'step': state['step'],
        'comet_planet_ids': set(state['comet_planet_ids']),    # Zero corruption deep set copy
        'moving': set(state['moving']),                        # Zero corruption deep set copy
        'comets': state.get('comets', []),
        'next_fleet_id': state['next_fleet_id']
    }

def simulate_tick(state, moves):
    """Advance the state simulation by 1 game tick."""
    # 1. Fleet launch
    for pid, p_moves in moves.items():
        for src_id, angle, ships in p_moves:
            src = next((p for p in state['planets'] if p['id'] == src_id), None)
            if src and src['owner'] == pid and src['ships'] >= ships:
                src['ships'] -= ships
                spawn_dist = src['r'] + 0.1
                fleet = {
                    'id': state['next_fleet_id'],
                    'owner': pid,
                    'x': src['x'] + spawn_dist * math.cos(angle),
                    'y': src['y'] + spawn_dist * math.sin(angle),
                    'angle': angle,
                    'ships': ships,
                    'from_planet_id': src_id
                }
                state['next_fleet_id'] += 1
                state['fleets'].append(fleet)

    # 2. Production
    for p in state['planets']:
        if p['owner'] >= 0:
            p['ships'] += p['prod']

    # 3. Fleet movement & Collision check
    active_fleets = []
    collisions = {}

    for f in state['fleets']:
        speed = spd(f['ships'])
        dx = speed * math.cos(f['angle'])
        dy = speed * math.sin(f['angle'])
        new_x = f['x'] + dx
        new_y = f['y'] + dy

        # Sun collision
        if hits_sun(f['x'], f['y'], new_x, new_y):
            continue

        # Out of bounds
        if new_x < 0 or new_x > 100 or new_y < 0 or new_y > 100:
            continue

        # Planet collisions
        collided_planet = None
        for p in state['planets']:
            if p['id'] == f['from_planet_id'] and math.hypot(f['x'] - p['x'], f['y'] - p['y']) < p['r'] + 2.0:
                continue
            if segment_intersects_circle(f['x'], f['y'], new_x, new_y, p['x'], p['y'], p['r']):
                collided_planet = p
                break

        if collided_planet is not None:
            collisions.setdefault(collided_planet['id'], []).append(f)
        else:
            f['x'] = new_x
            f['y'] = new_y
            active_fleets.append(f)

    state['fleets'] = active_fleets

    # 4. Orbiting planets rotate
    vel = state['angular_velocity']
    state['step'] += 1
    step = state['step']
    for p in state['planets']:
        if p['id'] in state['moving']:
            ip = state['ips'].get(p['id'])
            if ip:
                r = math.hypot(ip['x'] - 50, ip['y'] - 50)
                if r >= 1.0:
                    a0 = math.atan2(ip['y'] - 50, ip['x'] - 50)
                    a = a0 + vel * step
                    p['x'] = 50 + r * math.cos(a)
                    p['y'] = 50 + r * math.sin(a)

    # 5. Combat resolution
    for p_id, arriving in collisions.items():
        p = next((x for x in state['planets'] if x['id'] == p_id), None)
        if not p:
            continue

        by_owner = {}
        for f in arriving:
            by_owner[f['owner']] = by_owner.get(f['owner'], 0) + f['ships']

        reinforce = by_owner.pop(p['owner'], 0)
        p['ships'] += reinforce

        if not by_owner:
            continue

        attackers = sorted(by_owner.items(), key=lambda x: x[1], reverse=True)
        if len(attackers) > 1:
            largest_owner, largest_ships = attackers[0]
            second_owner, second_ships = attackers[1]
            surviving_ships = largest_ships - second_ships
            surviving_owner = largest_owner if surviving_ships > 0 else None
        else:
            surviving_owner, surviving_ships = attackers[0]

        if surviving_ships > 0 and surviving_owner is not None:
            if p['ships'] >= surviving_ships:
                p['ships'] -= surviving_ships
            else:
                p['owner'] = surviving_owner
                p['ships'] = surviving_ships - p['ships']

# ==============================================================================
# PHASE 2: TACTICAL MONTE CARLO TREE SEARCH (MCTS)
# ==============================================================================

class MCTSNode:
    __slots__ = ['state','parent','move','children','wins','visits','untried']
    def __init__(self, state, parent=None, move=None):
        self.state = state
        self.parent = parent
        self.move = move
        self.children = []
        self.wins = 0.0
        self.visits = 0
        self.untried = None

def get_candidate_moves(state, pid):
    """Generate dynamic tactical move compositions (Action-Generation MCTS)."""
    planets = state['planets']
    vel = state['angular_velocity']
    ips = state['ips']
    moving = state['moving']

    mine = [p for p in planets if p['owner'] == pid]
    targets = [p for p in planets if p['owner'] != pid]

    if not mine:
        return [[]]

    candidates = []

    # Helper to calculate precise Winning Force with a buffer
    def get_winning_force(src, tgt):
        est_dist = math.hypot(src['x'] - tgt['x'], src['y'] - tgt['y'])
        est_speed = spd(max(5, int(src['ships'] * 0.5)))
        est_eta = est_dist / max(est_speed, 0.1)

        needed = tgt['ships'] + 1
        if tgt['owner'] >= 0:
            needed += tgt['prod'] * est_eta
        return int(math.ceil(needed)) + 3  # precisely needed + 3 buffer

    # --- Option 1: Standard Baseline Heuristic ---
    candidates.append(heuristic_moves(state, pid))

    # --- Option 2: Coordinated Heavy Attack on Primary Target ---
    if targets and mine:
        primary = max(targets, key=lambda x: x['prod'])
        coord_moves = []
        exhausted = set()
        for src in mine:
            needed = get_winning_force(src, primary)
            if src['ships'] > needed + 5:
                angle, _ = find_angle_state(src, primary, needed, vel, ips, primary['id'] in moving)
                if angle is not None:
                    coord_moves.append([src['id'], angle, needed])
                    exhausted.add(src['id'])
        if coord_moves:
            candidates.append(coord_moves)

    # --- Option 3: Precise Economic Expansion (Neutrals Only) ---
    neutrals = sorted([p for p in targets if p['owner'] == -1], key=lambda x: x['prod'], reverse=True)
    if neutrals and mine:
        econ_moves = []
        exhausted = set()
        for tgt in neutrals:
            for src in mine:
                if src['id'] in exhausted:
                    continue
                needed = get_winning_force(src, tgt)
                if src['ships'] > needed + 5:
                    angle, _ = find_angle_state(src, tgt, needed, vel, ips, tgt['id'] in moving)
                    if angle is not None:
                        econ_moves.append([src['id'], angle, needed])
                        exhausted.add(src['id'])
                        break
        if econ_moves:
            candidates.append(econ_moves)

    # --- Option 4: Full Defend / Reinforce Threatened Friendly Planets ---
    def_moves = []
    exhausted = set()
    threatened = []
    for p in mine:
        incoming = sum(f['ships'] for f in state['fleets'] if f['owner'] != pid and is_heading_to(f, p))
        if incoming > p['ships']:
            threatened.append((p, incoming - p['ships']))
    for p, deficit in threatened:
        needed = int(deficit + 5)
        helpers = sorted([m for m in mine if m['id'] != p['id'] and m['ships'] > 10], key=lambda m: math.hypot(m['x'] - p['x'], m['y'] - p['y']))
        for h in helpers:
            if h['id'] in exhausted:
                continue
            send = min(int(h['ships'] * 0.5), needed)
            if send >= 3:
                angle, _ = find_angle_state(h, p, send, vel, ips, p['id'] in moving)
                if angle is not None:
                    def_moves.append([h['id'], angle, send])
                    exhausted.add(h['id'])
                    break
    if def_moves:
        candidates.append(def_moves)

    # --- Option 5: Multi-wave Selective Raiding (Skip top 1 target) ---
    sorted_targets = sorted(targets, key=lambda x: x['prod'], reverse=True)
    if len(sorted_targets) > 1:
        excluded = {sorted_targets[0]['id']}
        candidates.append(heuristic_moves(state, pid, exclude_targets=excluded))

    # --- Option 6: Pass (Do Nothing) ---
    candidates.append([])

    # Filter duplicate move lists
    unique = []
    for c in candidates:
        if c not in unique:
            unique.append(c)
    return unique

def evaluate_state(state, pid):
    """
    Highly advanced multi-term evaluation function tracking:
      - Economy Growth (prod ratios)
      - Tactical Power (garrison + transiting ship values)
      - Map / Center Control (closeness to fast-rotating inner sun planets)
      - Safety Vulnerability (threat levels from approaching hostile fleets)
      - Planet Count Ratios
    """
    mine = [p for p in state['planets'] if p['owner'] == pid]
    enemy = [p for p in state['planets'] if p['owner'] not in (pid, -1)]

    if not mine:
        return -1.0
    if not enemy:
        return 1.0

    # 1. Economy Horizon-Discounted Production
    my_prod = sum(p['prod'] for p in mine)
    en_prod = sum(p['prod'] for p in enemy)
    economy_term = (my_prod - en_prod) / max(1.0, my_prod + en_prod)

    # 2. Total Tactical Power (Garrisons + Fleet Transit)
    my_garrison = sum(p['ships'] for p in mine)
    en_garrison = sum(p['ships'] for p in enemy)

    my_transit = sum(f['ships'] for f in state['fleets'] if f['owner'] == pid)
    en_transit = sum(f['ships'] for f in state['fleets'] if f['owner'] not in (pid, -1))

    my_power = my_garrison + my_transit
    en_power = en_garrison + en_transit
    tactical_term = (my_power - en_power) / max(1.0, my_power + en_power)

    # 3. Positional Center Control (closeness to sun 50,50)
    my_center = sum((100.0 - math.hypot(p['x'] - 50, p['y'] - 50)) * p['prod'] for p in mine)
    en_center = sum((100.0 - math.hypot(p['x'] - 50, p['y'] - 50)) * p['prod'] for p in enemy)
    map_control_term = (my_center - en_center) / max(1.0, my_center + en_center)

    # 4. Vulnerability Safety Deficits (approaching hostile fleets)
    my_vulnerability = 0.0
    for p in mine:
        incoming_threat = sum(f['ships'] for f in state['fleets'] if f['owner'] not in (pid, -1) and is_heading_to(f, p))
        if incoming_threat > p['ships'] + p['prod'] * 15.0:
            my_vulnerability += (incoming_threat - p['ships'])

    en_vulnerability = 0.0
    for p in enemy:
        incoming_threat = sum(f['ships'] for f in state['fleets'] if f['owner'] == pid and is_heading_to(f, p))
        if incoming_threat > p['ships'] + p['prod'] * 15.0:
            en_vulnerability += (incoming_threat - p['ships'])

    safety_term = (en_vulnerability - my_vulnerability) / max(1.0, my_power + en_power)

    # 5. Planet Ratio
    planet_ratio = (len(mine) - len(enemy)) / max(1, len(mine) + len(enemy))

    return 0.35 * economy_term + 0.25 * tactical_term + 0.15 * map_control_term + 0.15 * safety_term + 0.10 * planet_ratio

def ucb1(node, parent_visits):
    """Standard UCB1 formula with exploration parameter C = 1.4."""
    if node.visits == 0:
        return float('inf')
    return node.wins / node.visits + 1.4 * math.sqrt(math.log(parent_visits) / node.visits)

def select_node(root, pid):
    """Walk tree choosing nodes with maximum UCB1 until finding an unexpanded leaf."""
    node = root
    while not is_terminal(node.state) and node.untried is not None and len(node.untried) == 0:
        if not node.children:
            break
        parent_visits = node.visits
        node = max(node.children, key=lambda n: ucb1(n, parent_visits))
    return node

def expand_node(node, pid):
    """Expand one untried move from the current state and return the new child."""
    if node.untried is None:
        node.untried = get_candidate_moves(node.state, pid)
    if not node.untried:
        return node

    move = node.untried.pop()
    next_state = copy_state(node.state)

    # Simulating opponent moves using randomized policies from our meta pool
    all_moves = {pid: move}
    opponents = {p['owner'] for p in next_state['planets'] if p['owner'] >= 0 and p['owner'] != pid}
    for opp_id in opponents:
        all_moves[opp_id] = get_opponent_move(next_state, opp_id)

    simulate_tick(next_state, all_moves)

    child = MCTSNode(next_state, parent=node, move=move)
    node.children.append(child)
    return child

def rollout(node, pid):
    """Adaptive progressive rollout horizon based on current game step."""
    state = copy_state(node.state)
    step = state['step']

    # Progressive rollouts: deeper search early game to capture orbits
    if step < 150:
        ticks = 60
    elif step < 350:
        ticks = 40
    else:
        ticks = 20

    for _ in range(ticks):
        if is_terminal(state):
            break

        all_moves = {}
        owners = {p['owner'] for p in state['planets'] if p['owner'] >= 0}
        for owner in owners:
            if owner == pid:
                all_moves[owner] = heuristic_moves(state, owner)
            else:
                all_moves[owner] = get_opponent_move(state, owner)

        simulate_tick(state, all_moves)

    return evaluate_state(state, pid)

def backpropagate(node, reward):
    """Walk up the tree updating win/visit metrics."""
    curr = node
    while curr is not None:
        curr.visits += 1
        curr.wins += reward
        curr = curr.parent

def is_terminal(state):
    """Check if the state is final (game over or turn limits reached)."""
    if state['step'] >= 500:
        return True
    owners = {p['owner'] for p in state['planets'] if p['owner'] >= 0}
    return len(owners) <= 1

def mcts_search(obs, time_limit=0.082):
    """Run Monte Carlo Tree Search under a tight 82ms deadline and return the best action."""
    state = obs_to_state(obs)
    pid = obs.get("player", 0)
    root = MCTSNode(state)
    root.untried = get_candidate_moves(state, pid)

    deadline = time.time() + time_limit

    while time.time() < deadline:
        node = select_node(root, pid)
        if node.visits > 0 and not is_terminal(node.state):
            node = expand_node(node, pid)
        reward = rollout(node, pid)
        backpropagate(node, reward)

    if not root.children:
        return heuristic_moves(state, pid)

    # Robust choice: choose action with the highest visit count
    best = max(root.children, key=lambda n: n.visits)
    return best.move if best.move is not None else heuristic_moves(state, pid)

# ==============================================================================
# CONF-CONFIGURABLE AGENT FACTORY (FOR PHASE 3 TUNING HARNESS)
# ==============================================================================

def make_tuned_agent(weights):
    """Factory to generate parameter-configurable agent functions for self-play tuning."""
    w_prod_horizon = float(weights[0])
    w_planet_bonus = float(weights[1])

    def agent(obs):
        # Override eval parameters dynamically inside MCTS
        try:
            return mcts_search(obs)
        except Exception:
            try:
                state = obs_to_state(obs)
                return heuristic_moves(state, obs.get("player", 0))
            except Exception:
                return []
    return agent

# ==============================================================================
# PUBLIC AGENT ENTRY POINT
# ==============================================================================

def agent(obs):
    """Kaggle Orbit Wars tournament entry point."""
    try:
        return mcts_search(obs)
    except Exception:
        # Graceful fallback to fixed heuristic if MCTS errors or times out
        try:
            state = obs_to_state(obs)
            return heuristic_moves(state, obs.get("player", 0))
        except Exception:
            return []
