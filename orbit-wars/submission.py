"""
Orbit Wars Agent — V8 AGGRESSOR
Submit: kaggle competitions submit orbit-wars -f submission.py -m "V8 Aggressor"

Core philosophy:
  - EVERY planet fires EVERY turn if it has ships to spare.
  - Adjacent / co-orbiting planets are the #1 priority — never leave them alone.
  - Comets = 2 ships only, always.
  - Defense is proactive (ETA < 20 ticks), never reactive.
  - Snowball mode: when winning, full-press every surplus planet simultaneously.
  - Pending-incoming accounting: multiple planets can pile on the same hard target.
  - Defend-check radius cut to 40 units so far-away threats don't block aggression.
  - send = max(needed * 1.35, needed + 4) — never lose a capture to production drift.
  - Co-orbit detection: planets orbiting at the same radius AND close in angle get
    an enormous proximity bonus so they are always captured first.
  - Game horizon corrected to 500 turns.
"""

import math

# ─────────────────────────────────────────────────────────────────────────────
# PHYSICS HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def spd(n):
    """Fleet speed from README formula, capped at 6.0."""
    if n <= 1:
        return 1.0
    val = 1.0 + 5.0 * (math.log(max(n, 1)) / math.log(1000)) ** 1.5
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

def orbit_pos(pid, ips, vel, step, tick):
    """Future position of an orbiting planet at turn (step + tick)."""
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
    """Exact target position at tick, handling comets / orbits / static."""
    if tgt['id'] in state['comet_planet_ids']:
        for grp in state.get('comets', []):
            if tgt['id'] in grp['planet_ids']:
                idx = grp['planet_ids'].index(tgt['id'])
                path = grp['paths'][idx]
                p_idx = grp['path_index'] + tick
                if 0 <= p_idx < len(path):
                    return path[p_idx][0], path[p_idx][1]
                return None, None   # expired
    if tgt['id'] in state['moving']:
        return orbit_pos(tgt['id'], ips, vel, step, tick)
    return tgt['x'], tgt['y']

def find_angle(src, tgt, ships, vel, ips, step, state, max_ticks=90):
    """
    Intercept solver: finds launch angle + ETA.
    Tries direct path first; rotates around sun if blocked.
    Returns (angle, eta) or (None, None).
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
        sx = src['x'] + math.cos(base_angle) * (src['r'] + 0.1)
        sy = src['y'] + math.sin(base_angle) * (src['r'] + 0.1)

        if not hits_sun(sx, sy, tx, ty):
            return base_angle, tick

        # Sun evasion sweep
        for off in [0.10, -0.10, 0.20, -0.20, 0.35, -0.35, 0.50, -0.50, 0.65, -0.65]:
            a = base_angle + off
            sx2 = src['x'] + math.cos(a) * (src['r'] + 0.1)
            sy2 = src['y'] + math.sin(a) * (src['r'] + 0.1)
            tx2 = src['x'] + math.cos(a) * dist
            ty2 = src['y'] + math.sin(a) * dist
            if not hits_sun(sx2, sy2, tx2, ty2):
                return a, tick
    return None, None

def is_heading_to(f, p):
    """True if fleet f is flying toward planet p."""
    vx, vy = math.cos(f['angle']), math.sin(f['angle'])
    dx, dy = p['x'] - f['x'], p['y'] - f['y']
    proj = dx * vx + dy * vy
    if proj < 0:
        return False
    px, py = f['x'] + vx * proj, f['y'] + vy * proj
    return math.hypot(px - p['x'], py - p['y']) <= p['r'] + 2.5

# ─────────────────────────────────────────────────────────────────────────────
# CO-ORBIT ADJACENCY  (the key new feature)
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
    ang_tol ~0.40 rad ≈ 23 degrees arc.
    """
    dr = abs(orbital_radius(src) - orbital_radius(tgt))
    if dr > r_tol:
        return False
    ang = angular_separation(src, tgt)
    return ang < ang_tol

# ─────────────────────────────────────────────────────────────────────────────
# SCORING
# ─────────────────────────────────────────────────────────────────────────────

def comet_lifetime(tgt_id, state):
    for grp in state.get('comets', []):
        if tgt_id in grp['planet_ids']:
            idx = grp['planet_ids'].index(tgt_id)
            path = grp['paths'][idx]
            return max(0, len(path) - grp['path_index'])
    return 0

def score_target(src, tgt, eta, is_comet, step, needed, n_mine, state, already_sent=0):
    """
    Economic Value score with:
      - 500-turn horizon (corrected)
      - Co-orbit adjacency mega-bonus
      - Smooth neutral multiplier decay
      - Enemy denial bonus
      - Cluster-choke heuristic (enemy planet closer to us than to their nearest base)
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
    # These are essentially free captures — same ring, just ahead/behind us.
    if is_co_orbit_adjacent(src, tgt):
        score += 4000.0  # dominant priority

    # ── Raw proximity bonus (Euclidean) ─────────────────────────────────────
    if dist < 25.0:
        score += (25.0 - dist) * 60.0   # up to +1500

    # ── Neutral planet bonuses ──────────────────────────────────────────────
    if tgt['owner'] == -1:
        neutral_mult = max(1.0, 2.8 - (step / 400.0) * 1.8)
        score *= neutral_mult
        neutral_bonus = max(5, 250 - 0.6 * step - 25 * n_mine)
        score += neutral_bonus

    # ── Enemy planet bonuses ─────────────────────────────────────────────────
    if tgt['owner'] >= 0:
        # Production denial
        score += tgt['prod'] * 100.0
        # Proximity to us vs enemy cluster (choke detection)
        score += max(0.0, (40.0 - dist) * 35.0)
        # Punish high garrison less (we want to pick cheap targets)
        # already handled by needed penalty below

    # ── Force cost penalty ───────────────────────────────────────────────────
    effective_needed = max(0, needed - already_sent)
    score -= effective_needed * 12.0

    return score

# ─────────────────────────────────────────────────────────────────────────────
# MAIN TACTICAL ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_moves(state, pid):
    planets  = state['planets']
    fleets   = state['fleets']
    ips      = state['ips']
    vel      = state['angular_velocity']
    comets   = state['comet_planet_ids']
    moving   = state['moving']
    step     = state['step']

    mine    = [p for p in planets if p['owner'] == pid]
    targets = [p for p in planets if p['owner'] != pid]

    if not mine:
        return []

    # ── Power state ──────────────────────────────────────────────────────────
    total_ships = sum(p['ships'] for p in planets) + sum(f['ships'] for f in fleets)
    my_ships    = sum(p['ships'] for p in mine) + sum(f['ships'] for f in fleets if f['owner'] == pid)
    snowball    = my_ships >= 0.50 * total_ships and len(mine) >= len(planets) * 0.35

    # ── Track already-committed incoming ships per target ───────────────────
    # (from existing en-route fleets AND moves we add this turn)
    pending = {p['id']: 0.0 for p in targets}
    for f in fleets:
        if f['owner'] != pid:
            continue
        best_id, best_diff = None, 0.30
        for tgt in targets:
            dx, dy = tgt['x'] - f['x'], tgt['y'] - f['y']
            if math.hypot(dx, dy) < 0.5:
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
    # PHASE 1 — PRE-EMPTIVE DEFENSE
    # Trigger if threat ETA < 20 ticks OR garrison will be overrun.
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

        production_turns = int(math.floor(threat_eta))
        garrison = p['ships'] + p['prod'] * production_turns
        safety_need = int(incoming_ships * 1.3 + 6)

        # Pre-emptive trigger: even if garrison is fine, reinforce if threat close
        if garrison >= safety_need and threat_eta >= 20.0:
            continue

        deficit = safety_need - garrison
        if deficit < 3:
            continue

        helpers = sorted(
            [m for m in mine if m['id'] != p['id'] and available[m['id']] > 8],
            key=lambda m: math.hypot(m['x'] - p['x'], m['y'] - p['y'])
        )
        for h in helpers:
            send = min(int(available[h['id']] * 0.65), int(deficit + 4))
            if send < 3:
                continue
            angle, eta = find_angle(h, p, send, vel, ips, step, state)
            if angle is not None:
                moves.append([h['id'], angle, send])
                available[h['id']] -= send
                deficit -= send
                if deficit <= 0:
                    break

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 2 — AGGRESSIVE MULTI-FIRE ATTACK
    # Every planet fires until it runs low.
    # No global turn_targeted set — multiple planets CAN pile on same target.
    # ════════════════════════════════════════════════════════════════════════
    mine_sorted = sorted(mine, key=lambda p: -p['ships'])

    # Per-turn "already assigned this turn" tracking (separate from pending
    # which tracks existing en-route fleets)
    this_turn_sent = {p['id']: 0.0 for p in targets}

    for src in mine_sorted:
        # How many launches can this planet make per turn?
        max_launches = 4 if snowball else 3

        for launch_n in range(max_launches):
            avail = available[src['id']]
            # Minimum ships to keep at home
            keep = 4 if snowball else 10
            if avail <= keep:
                break

            best_score = -float('inf')
            best_tgt   = None
            best_angle = None
            best_send  = 0

            for tgt in targets:
                is_comet = tgt['id'] in comets

                # ── Compute needed ships ─────────────────────────────────
                if is_comet:
                    send = 2
                    needed = 2
                    res = find_angle(src, tgt, send, vel, ips, step, state)
                    if res[0] is None:
                        continue
                    angle, eta = res
                else:
                    # Initial estimate
                    send = min(int(avail - 1), int(tgt['ships']) + 6)
                    angle = None
                    eta   = 0
                    needed = 0

                    for _ in range(3):   # converge send → needed
                        if send < 3:
                            break
                        res = find_angle(src, tgt, send, vel, ips, step, state)
                        if res[0] is None:
                            break
                        angle, eta = res

                        raw_needed = tgt['ships'] + 1
                        if tgt['owner'] >= 0:
                            raw_needed += tgt['prod'] * eta

                        # Subtract what's already on the way (en-route + this turn)
                        committed = pending.get(tgt['id'], 0) + this_turn_sent.get(tgt['id'], 0)
                        needed = max(0, int(math.ceil(raw_needed - committed)))

                        if needed == 0:
                            send = 0
                            break

                        safety = 1.35 if tgt['owner'] >= 0 else 1.10
                        send = min(int(avail - 1), max(int(needed * safety), needed + 4))

                    if send < 3 or angle is None:
                        continue

                    # If fully covered by en-route fleets, skip
                    if needed == 0:
                        continue

                # Reserve check
                dist   = math.hypot(src['x'] - tgt['x'], src['y'] - tgt['y'])
                reserve = 3 if (dist < 25.0 or snowball) else keep
                if avail - send < reserve:
                    continue

                # ── Defend-check (tight 40-unit radius) ─────────────────
                incoming_e = [f for f in fleets
                              if f['owner'] != pid and is_heading_to(f, src)]
                if incoming_e:
                    inc_ships   = sum(f['ships'] for f in incoming_e)
                    cl_f        = min(incoming_e, key=lambda f: math.hypot(src['x'] - f['x'], src['y'] - f['y']))
                    cl_dist     = math.hypot(src['x'] - cl_f['x'], src['y'] - cl_f['y'])
                    if cl_dist <= 40.0:
                        t_eta    = cl_dist / max(spd(cl_f['ships']), 0.1)
                        garrison = avail + src['prod'] * int(math.floor(t_eta))
                        if garrison < inc_ships + 3 + send:
                            continue

                committed = pending.get(tgt['id'], 0) + this_turn_sent.get(tgt['id'], 0)
                sc = score_target(src, tgt, eta, is_comet, step, needed, len(mine), state, committed)

                if sc > best_score:
                    best_score = sc
                    best_tgt   = tgt
                    best_angle = angle
                    best_send  = send

            if best_tgt is None:
                break   # nothing worth launching at from this planet

            moves.append([src['id'], best_angle, best_send])
            available[src['id']] -= best_send
            this_turn_sent[best_tgt['id']] = this_turn_sent.get(best_tgt['id'], 0) + best_send

    return moves

# ─────────────────────────────────────────────────────────────────────────────
# OBSERVATION PARSER
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

# ─────────────────────────────────────────────────────────────────────────────
# KAGGLE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def agent(obs):
    try:
        state = parse_obs(obs)
        pid   = obs.get("player", 0)
        return compute_moves(state, pid)
    except Exception:
        return []