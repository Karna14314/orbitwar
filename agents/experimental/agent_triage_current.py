# HYPOTHESIS: Defensive Triage penalizing scores for doomed targets in contested zones.
# DATE: 2024-05-23
# BASED ON: agents/champion.py
# CHANGELOG: Added contested zone penalty to target scoring.

import math

def spd(n):
    if n <= 1: return 1.0
    return 1.0 + 5.0 * (math.log(n) / math.log(1000)) ** 1.5

def segment_intersects_circle(x1, y1, x2, y2, cx, cy, r):
    vx, vy = x2 - x1, y2 - y1
    len2 = vx*vx + vy*vy
    if len2 == 0: return (x1-cx)**2 + (y1-cy)**2 <= r*r
    t = max(0.0, min(1.0, ((cx-x1)*vx + (cy-y1)*vy) / len2))
    nearest_x, nearest_y = x1 + t*vx, y1 + t*vy
    return (nearest_x-cx)**2 + (nearest_y-cy)**2 <= r*r

def hits_sun(x1, y1, x2, y2, margin=0.6):
    return segment_intersects_circle(x1, y1, x2, y2, 50.0, 50.0, 10.0 + margin)

def future_pos_state_absolute(pid, ips, vel, abs_step):
    ip = ips.get(pid)
    if not ip: return None, None
    r = math.hypot(ip['x'] - 50, ip['y'] - 50)
    if r < 1.0: return ip['x'], ip['y']
    a0 = math.atan2(ip['y'] - 50, ip['x'] - 50)
    a = a0 + vel * abs_step
    return 50 + r * math.cos(a), 50 + r * math.sin(a)

def get_target_pos(src, tgt, vel, ips, step, tick, state=None):
    if state and 'comet_planet_ids' in state and tgt['id'] in state['comet_planet_ids']:
        for group in state.get('comets', []):
            if tgt['id'] in group['planet_ids']:
                idx = group['planet_ids'].index(tgt['id'])
                path = group['paths'][idx]
                p_idx = group['path_index'] + tick
                if 0 <= p_idx < len(path): return path[p_idx][0], path[p_idx][1]
                else: return None, None
    is_moving = False
    if state and 'moving' in state: is_moving = tgt['id'] in state['moving']
    elif tgt['id'] in ips:
        ip = ips[tgt['id']]
        if math.hypot(ip['x'] - 50, ip['y'] - 50) < 45.0: is_moving = True
    if is_moving: return future_pos_state_absolute(tgt['id'], ips, vel, step + tick)
    return tgt['x'], tgt['y']

def find_angle_state(src, tgt, ships, vel, ips, step_or_moving, state=None):
    speed = spd(ships)
    step = state['step'] if state else 0
    is_moving = tgt['id'] in state['moving'] if state else False

    for tick in range(1, 80):
        tx, ty = get_target_pos(src, tgt, vel, ips, step, tick, state)
        if tx is None:
            if is_moving:
                tx, ty = future_pos_state_absolute(tgt['id'], ips, vel, step + tick)
                if tx is None: tx, ty = tgt['x'], tgt['y']
            else: tx, ty = tgt['x'], tgt['y']

        dist = math.hypot(src['x'] - tx, src['y'] - ty)
        dist_to_travel = dist - tgt['r'] - src['r'] - 0.1
        if speed * tick >= dist_to_travel:
            base_angle = math.atan2(ty - src['y'], tx - src['x'])
            x_spawn = src['x'] + math.cos(base_angle) * (src['r'] + 0.1)
            y_spawn = src['y'] + math.sin(base_angle) * (src['r'] + 0.1)
            if not hits_sun(x_spawn, y_spawn, tx, ty, margin=0.6): return base_angle, tick
            for off in [0.08, -0.08, 0.15, -0.15, 0.3, -0.3, 0.45, -0.45]:
                a = base_angle + off
                x_spawn_off = src['x'] + math.cos(a) * (src['r'] + 0.1)
                y_spawn_off = src['y'] + math.sin(a) * (src['r'] + 0.1)
                tx_test = src['x'] + math.cos(a) * dist
                ty_test = src['y'] + math.sin(a) * dist
                if not hits_sun(x_spawn_off, y_spawn_off, tx_test, ty_test, margin=0.6): return a, tick
    return None, None

def is_heading_to(f, p):
    vx, vy = math.cos(f['angle']), math.sin(f['angle'])
    dx, dy = p['x'] - f['x'], p['y'] - f['y']
    proj_len = dx * vx + dy * vy
    if proj_len < 0: return False
    px = f['x'] + vx * proj_len
    py = f['y'] + vy * proj_len
    perp_dist = math.hypot(px - p['x'], py - p['y'])
    return perp_dist <= p['r'] + 2.0

def obs_to_state(obs):
    ips = {}
    for p in obs.get("initial_planets", []):
        ips[p[0]] = {'id': int(p[0]), 'owner': int(p[1]), 'x': float(p[2]), 'y': float(p[3]), 'r': float(p[4]), 'ships': float(p[5]), 'prod': float(p[6])}
    comets = set(obs.get("comet_planet_ids", []))
    moving = set(comets)
    state_planets = []
    for p in obs.get("planets", []):
        ip = ips.get(p[0])
        if ip and (abs(p[2] - ip['x']) > 0.01 or abs(p[3] - ip['y']) > 0.01): moving.add(p[0])
        state_planets.append({'id': int(p[0]), 'owner': int(p[1]), 'x': float(p[2]), 'y': float(p[3]), 'r': float(p[4]), 'ships': float(p[5]), 'prod': float(p[6])})
    state_fleets = [{'id': int(f[0]), 'owner': int(f[1]), 'x': float(f[2]), 'y': float(f[3]), 'angle': float(f[4]), 'from_planet_id': int(f[5]), 'ships': float(f[6])} for f in obs.get("fleets", [])]
    return {
        'planets': state_planets, 'fleets': state_fleets, 'angular_velocity': obs.get("angular_velocity", 0.0),
        'ips': ips, 'step': obs.get("step", 0), 'comet_planet_ids': comets, 'moving': moving, 'comets': obs.get("comets", [])
    }

def heuristic_moves(state, pid):
    moves = []
    mine = [p for p in state['planets'] if p['owner'] == pid]
    targets = [p for p in state['planets'] if p['owner'] != pid]
    if not mine: return []

    avail = {p['id']: p['ships'] for p in mine}

    for src in sorted(mine, key=lambda p: p['ships'], reverse=True):
        if avail[src['id']] < 5: continue
        best_tgt, best_score, best_angle, best_send = None, -float('inf'), None, 0
        for tgt in targets:
            send = min(int(avail[src['id']] - 1), tgt['ships'] + 5)
            if send < 3: continue
            angle, eta = find_angle_state(src, tgt, send, state['angular_velocity'], state['ips'], state['step'], state)
            if angle is None: continue
            needed = tgt['ships'] + 1
            if tgt['owner'] >= 0: needed += tgt['prod'] * eta
            needed = int(math.ceil(needed))
            if avail[src['id']] < needed + 2: continue

            dist_to_us = math.hypot(src['x'] - tgt['x'], src['y'] - tgt['y'])
            enemy_planets = [p for p in state['planets'] if p['owner'] not in (pid, -1)]
            min_dist_to_enemy = min([math.hypot(ep['x'] - tgt['x'], ep['y'] - tgt['y']) for ep in enemy_planets]) if enemy_planets else float('inf')

            # Physics-based scoring - favor moving targets if eta is small
            score = tgt['prod'] * 120 / (eta + 0.5)
            if min_dist_to_enemy < dist_to_us: score /= 2.0
            if tgt['id'] in state['moving']: score *= 2.0
            if tgt['owner'] == -1 and state['step'] < 60: score *= 1.8 # wave expansion integration

            if score > best_score:
                best_score, best_tgt, best_angle, best_send = score, tgt, angle, needed+2
        if best_tgt:
            moves.append([src['id'], best_angle, best_send])
            avail[src['id']] -= best_send
    return moves

def agent(obs):
    try:
        state = obs_to_state(obs)
        return heuristic_moves(state, obs.get("player", 0))
    except:
        return []
