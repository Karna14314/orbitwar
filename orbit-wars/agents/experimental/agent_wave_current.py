# HYPOTHESIS: Tests concentric wave expansion. Grabs adjacent neutrals early, prioritizing co-orbiting neighbors.
# DATE: 2024-05-20
# BASED ON: champion.py (Intercept)
# CHANGELOG: Modifies scoring to reward attacks on early game adjacent neutrals and co-orbiting neighbors. Reduces base EV and boosts early neutral / co-orbit value. Checked registry - no duplicate strategy.

import math

# =========================================================
# _SIM.PY HELPER FUNCTIONS (INLINED FOR STANDALONE SAFETY)
# =========================================================

def spd(n):
    if n <= 1: return 1.0
    return 1.0 + 5.0 * (math.log(n) / math.log(1000)) ** 1.5

SUN_X, SUN_Y, SUN_R = 50.0, 50.0, 10.0

def hits_sun(x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    len2 = vx * vx + vy * vy
    if len2 == 0:
        return (x1 - 50) ** 2 + (y1 - 50) ** 2 <= (SUN_R + 0.5) ** 2
    t = max(0.0, min(1.0, ((50 - x1) * vx + (50 - y1) * vy) / len2))
    cx, cy = x1 + t * vx, y1 + t * vy
    return (cx - 50) ** 2 + (cy - 50) ** 2 <= (SUN_R + 0.5) ** 2

def planet_pos_at_step(ip, vel, step):
    r = math.hypot(ip['x'] - 50, ip['y'] - 50)
    if r < 1.0: return ip['x'], ip['y']
    a = math.atan2(ip['y'] - 50, ip['x'] - 50) + vel * step
    return 50 + r * math.cos(a), 50 + r * math.sin(a)

def find_angle(src, tgt, ships, vel, ips, step, is_moving):
    speed = spd(ships)
    for tick in range(1, 80):
        if is_moving:
            tx, ty = planet_pos_at_step(ips[tgt['id']], vel, step + tick)
        else:
            tx, ty = tgt['x'], tgt['y']
        dist = math.hypot(src['x'] - tx, src['y'] - ty)
        if speed * tick >= dist - tgt['r']:
            base_angle = math.atan2(ty - src['y'], tx - src['x'])
            tx_test = src['x'] + math.cos(base_angle) * dist
            ty_test = src['y'] + math.sin(base_angle) * dist
            if not hits_sun(src['x'], src['y'], tx_test, ty_test):
                return base_angle, tick
            for off in [0.08, -0.08, 0.15, -0.15, 0.3, -0.3, 0.45, -0.45, 0.5, -0.5]:
                a = base_angle + off
                tx_test = src['x'] + math.cos(a) * dist
                ty_test = src['y'] + math.sin(a) * dist
                if not hits_sun(src['x'], src['y'], tx_test, ty_test):
                    return a, tick
            return None, None
    return None, None

def is_heading_to(f, p):
    vx = math.cos(f['angle'])
    vy = math.sin(f['angle'])
    dist = math.hypot(p['x'] - f['x'], p['y'] - f['y'])
    tx, ty = f['x'] + vx * dist, f['y'] + vy * dist
    return math.hypot(tx - p['x'], ty - p['y']) <= p['r'] + 2.0

def obs_to_state(obs):
    planets = []
    for p in obs.get('planets', []):
        planets.append({
            'id': p[0], 'owner': p[1], 'x': p[2], 'y': p[3],
            'r': p[4], 'ships': p[5], 'prod': p[6]
        })
    fleets = []
    for f in obs.get('fleets', []):
        fleets.append({
            'id': f[0], 'owner': f[1], 'x': f[2], 'y': f[3],
            'angle': f[4], 'from': f[5], 'ships': f[6]
        })
    ips = {}
    for ip in obs.get('initial_planets', []):
        ips[ip[0]] = {'id': ip[0], 'owner': ip[1], 'x': ip[2], 'y': ip[3],
                      'r': ip[4], 'ships': ip[5], 'prod': ip[6]}
    vel = obs.get('angular_velocity', 0.0)
    step = obs.get('step', 0)
    comet_ids = set(obs.get('comet_planet_ids', []))
    moving = set()
    for p in planets:
        if p['id'] in comet_ids:
            pass
        elif math.hypot(p['x']-50, p['y']-50) + p['r'] < 50:
            moving.add(p['id'])
    return {
        'step': step, 'vel': vel, 'planets': planets,
        'fleets': fleets, 'ips': ips, 'moving': moving, 'comet_planet_ids': comet_ids
    }

# =========================================================
# MAIN AGENT LOGIC
# =========================================================

def heuristic_moves(state, pid, exclude_targets=None):
    if exclude_targets is None:
        exclude_targets = set()

    mine = [p for p in state['planets'] if p['owner'] == pid]
    targets = [p for p in state['planets'] if p['owner'] != pid and p['id'] not in exclude_targets]

    if not mine or not targets:
        return []

    moves = []
    used_src = set()
    pending_targets = set()

    mine_sorted = sorted(mine, key=lambda p: p['ships'], reverse=True)

    for src in mine_sorted:
        if src['id'] in used_src: continue
        if src['ships'] < 5: continue

        best_score = -float('inf')
        best_tgt = None
        best_angle = None
        best_needed = 0

        for tgt in targets:
            if tgt['id'] in pending_targets: continue
            dist = math.hypot(src['x']-tgt['x'], src['y']-tgt['y'])
            is_moving = tgt['id'] in state.get('moving', [])
            angle, ticks = find_angle(src, tgt, src['ships'], state['vel'], state['ips'], state['step'], is_moving)
            if angle is None: continue
            eta = ticks
            needed = int(tgt['ships'] + 1 + (tgt['prod'] * eta if tgt['owner'] >= 0 else 0))

            ticks_remaining = max(1, 1000 - state['step'] - eta)
            ev = tgt['prod'] * ticks_remaining / (1.0 + 0.05 * eta)

            # Wave Expansion Logic: Co-orbiting and early game neutral focus
            # Co-orbiting check: similar distance from sun
            src_r = math.hypot(src['x']-50, src['y']-50)
            tgt_r = math.hypot(tgt['x']-50, tgt['y']-50)
            if abs(src_r - tgt_r) < 10.0:  # Roughly same ring
                ev *= 2.5 # Huge boost to co-orbiting neighbors

            if tgt['owner'] == -1 and state['step'] < 60:
                if dist < 25.0: # immediate adjacent static neutrals
                    ev *= 3.0

            score = ev - needed * 0.8

            if score > best_score:
                best_score = score
                best_tgt = tgt
                best_angle = angle
                best_needed = needed

        if best_tgt and src['ships'] >= best_needed + 3:
            incoming_ships = sum(f['ships'] for f in state['fleets'] if f['owner'] != pid and is_heading_to(f, src))
            if incoming_ships > 0:
                closest_dist = float('inf')
                closest_f = None
                for f in state['fleets']:
                    if f['owner'] != pid and is_heading_to(f, src):
                        d = math.hypot(src['x']-f['x'], src['y']-f['y'])
                        if d < closest_dist:
                            closest_dist = d
                            closest_f = f
                if closest_dist <= 85.0:
                    threat_eta = closest_dist / max(spd(closest_f['ships']), 0.1)
                    garrison_at_impact = src['ships'] + src['prod'] * threat_eta
                    if garrison_at_impact < incoming_ships + 3 + best_needed:
                         continue
            send = min(int(src['ships'] - 1), best_needed + 3)
            moves.append([src['id'], best_angle, send])
            used_src.add(src['id'])
            pending_targets.add(best_tgt['id'])

    return moves

def agent(obs):
    try:
        state = obs_to_state(obs)
        pid = obs.get("player", 0)
        return heuristic_moves(state, pid)
    except Exception as e:
        print(f"Agent Wave Error: {e}")
        return []
