# HYPOTHESIS: Defensive Triage to abandon doomed planets surrounded by 3+ enemies
# ROUND: 2 | DATE: 2024-05-26
# BASED ON: champion.py
# CHANGELOG: Implemented triage logic to skip reinforcing planets with 3+ nearby enemies and short ETA
import math

def spd(n):
    if n <= 1: return 1.0
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

def hits_any_planet(x1, y1, x2, y2, src_id, tgt_id, state):
    if hits_sun(x1, y1, x2, y2, margin=0.7): return True
    for p in state['planets']:
        if p['id'] == src_id or p['id'] == tgt_id: continue
        if segment_intersects_circle(x1, y1, x2, y2, p['x'], p['y'], p['r'] + 0.5): return True
    return False

def orbit_pos(pid, ips, vel, step, tick):
    ip = ips.get(pid)
    if not ip: return None, None
    r = math.hypot(ip['x'] - 50, ip['y'] - 50)
    if r < 1.0: return ip['x'], ip['y']
    a0 = math.atan2(ip['y'] - 50, ip['x'] - 50)
    a = a0 + vel * (step + tick)
    return 50 + r * math.cos(a), 50 + r * math.sin(a)

def get_target_pos(tgt, vel, ips, step, tick, state):
    if tgt['id'] in state['comet_planet_ids']:
        for grp in state.get('comets', []):
            if tgt['id'] in grp['planet_ids']:
                idx = grp['planet_ids'].index(tgt['id'])
                path = grp['paths'][idx]
                p_idx = grp['path_index'] + tick
                if 0 <= p_idx < len(path): return path[p_idx][0], path[p_idx][1]
                return None, None
    if tgt['id'] in state['moving']: return orbit_pos(tgt['id'], ips, vel, step, tick)
    return tgt['x'], tgt['y']

def find_angle(src, tgt, ships, vel, ips, step, state, max_ticks=80):
    speed = spd(ships)
    for tick in range(1, max_ticks):
        tx, ty = get_target_pos(tgt, vel, ips, step, tick, state)
        if tx is None: continue
        dist = math.hypot(src['x'] - tx, src['y'] - ty)
        travel_needed = dist - tgt['r'] - src['r'] - 0.1
        if speed * tick < travel_needed: continue
        base_angle = math.atan2(ty - src['y'], tx - src['x'])
        sx = src['x'] + math.cos(base_angle) * (src['r'] + 0.1)
        sy = src['y'] + math.sin(base_angle) * (src['r'] + 0.1)
        if not hits_any_planet(sx, sy, tx, ty, src['id'], tgt['id'], state): return base_angle, tick
        max_off = math.asin(min(0.99, tgt['r'] / max(dist, 1.0)))
        for factor in [0.08, -0.08, 0.25, -0.25, 0.5, -0.5, 0.75, -0.75, 0.95, -0.95]:
            a = base_angle + factor * max_off
            sx2 = src['x'] + math.cos(a) * (src['r'] + 0.1)
            sy2 = src['y'] + math.sin(a) * (src['r'] + 0.1)
            tx2 = src['x'] + math.cos(a) * dist
            ty2 = src['y'] + math.sin(a) * dist
            if not hits_any_planet(sx2, sy2, tx2, ty2, src['id'], tgt['id'], state): return a, tick
    return None, None

def is_heading_to(f, p):
    vx, vy = math.cos(f['angle']), math.sin(f['angle'])
    dx, dy = p['x'] - f['x'], p['y'] - f['y']
    proj = dx * vx + dy * vy
    if proj < 0: return False
    px, py = f['x'] + vx * proj, f['y'] + vy * proj
    return math.hypot(px - p['x'], py - p['y']) <= p['r'] + 2.0

def is_co_orbit_adjacent(src, tgt):
    r1 = math.hypot(src['x'] - 50, src['y'] - 50)
    r2 = math.hypot(tgt['x'] - 50, tgt['y'] - 50)
    if abs(r1 - r2) > 8.0: return False
    a1 = math.atan2(src['y'] - 50, src['x'] - 50)
    a2 = math.atan2(tgt['y'] - 50, tgt['x'] - 50)
    diff = abs(math.atan2(math.sin(a1 - a2), math.cos(a1 - a2)))
    return diff < 0.40

def compute_precise_needed_fast(src, tgt, eta, state, pid):
    tgt_fleets = []
    for f in state['fleets']:
        if is_heading_to(f, tgt):
            d = math.hypot(tgt['x'] - f['x'], tgt['y'] - f['y'])
            f_speed = spd(f['ships'])
            f_eta = max(1, int(math.ceil(d / max(f_speed, 0.1))))
            tgt_fleets.append({'owner': f['owner'], 'ships': f['ships'], 'eta': f_eta})
    tgt_fleets.sort(key=lambda x: x['eta'])
    curr_owner, curr_ships, curr_time, prod = tgt['owner'], tgt['ships'], 0, tgt['prod']
    events_before = [f for f in tgt_fleets if f['eta'] <= eta]
    for f in events_before:
        dt = f['eta'] - curr_time
        if dt > 0:
            if curr_owner >= 0: curr_ships += prod * dt
            curr_time = f['eta']
        if f['owner'] == curr_owner: curr_ships += f['ships']
        else:
            if f['ships'] > curr_ships: curr_owner, curr_ships = f['owner'], f['ships'] - curr_ships
            else: curr_ships -= f['ships']
    dt = eta - curr_time
    if dt > 0 and curr_owner >= 0: curr_ships += prod * dt
    base_needed = 1 if curr_owner == pid else int(curr_ships + 1)
    events_after = [f for f in tgt_fleets if f['eta'] > eta]
    if not events_after: return base_needed
    garrison_after_landing = (curr_ships + base_needed) if curr_owner == pid else (base_needed - curr_ships)
    temp_owner, temp_ships, curr_time, max_deficit = pid, garrison_after_landing, eta, 0
    for f in events_after:
        dt = f['eta'] - curr_time
        if dt > 0:
            temp_ships += prod * dt
            curr_time = f['eta']
        if f['owner'] == temp_owner: temp_ships += f['ships']
        else:
            safety_margin = int(f['ships'] * 1.25 + 3)
            if temp_ships < safety_margin:
                deficit = safety_margin - temp_ships
                max_deficit = max(max_deficit, deficit)
                temp_ships += deficit
            if f['ships'] > temp_ships: temp_owner, temp_ships = f['owner'], f['ships'] - temp_ships
            else: temp_ships -= f['ships']
    return base_needed + max_deficit

def comet_lifetime(tgt_id, state):
    for grp in state.get('comets', []):
        if tgt_id in grp['planet_ids']:
            idx = grp['planet_ids'].index(tgt_id)
            path = grp['paths'][idx]
            return max(0, len(path) - grp['path_index'])
    return 0

def score_target(src, tgt, eta, is_comet, step, needed, mine, planets, pid, state, already_sent=0):
    dist = math.hypot(src['x'] - tgt['x'], src['y'] - tgt['y'])
    ticks_remaining = max(1, 1000 - step - eta)
    if is_comet:
        lifetime = comet_lifetime(tgt['id'], state)
        if lifetime <= eta: return -9999
        return tgt['prod'] * (lifetime - eta) * 3.0 + 500
    ev = tgt['prod'] * ticks_remaining / (1.0 + 0.05 * eta)
    is_moving = tgt['id'] in state['moving']
    if not is_moving:
        anchor_bonus = max(0.0, 40.0 - dist) * 15.0
        ev += anchor_bonus
    min_dist_to_us = min(math.hypot(p['x'] - tgt['x'], p['y'] - tgt['y']) for p in mine)
    if min_dist_to_us < 30.0: ev += (30.0 - min_dist_to_us) * 20.0
    if is_co_orbit_adjacent(src, tgt): ev += 4000.0
    if tgt['owner'] == -1:
        neutral_mult = max(1.0, 2.8 - (step / 400.0) * 1.8)
        ev *= neutral_mult
        ev += max(5.0, 250.0 - 0.6 * step - 25.0 * len(mine))
    enemy_planets = [p for p in planets if p['owner'] >= 0 and p['owner'] != pid]
    if enemy_planets:
        min_dist_to_enemy = min(math.hypot(p['x'] - tgt['x'], p['y'] - tgt['y']) for p in enemy_planets)
        if min_dist_to_enemy < min_dist_to_us - 10.0 and step < 250:
            ev -= (min_dist_to_us - min_dist_to_enemy) * 15.0
    effective_needed = max(0, needed - already_sent)
    return ev - effective_needed * 10.0

def compute_moves(state, pid):
    planets, fleets, ips, vel, comets, step = state['planets'], state['fleets'], state['ips'], state['angular_velocity'], state['comet_planet_ids'], state['step']
    mine, targets = [p for p in planets if p['owner'] == pid], [p for p in planets if p['owner'] != pid]
    if not mine: return []
    total_ships = sum(p['ships'] for p in planets) + sum(f['ships'] for f in fleets)
    my_ships = sum(p['ships'] for p in mine) + sum(f['ships'] for f in fleets if f['owner'] == pid)
    snowball = my_ships >= 0.50 * total_ships and len(mine) >= len(planets) * 0.35
    pending = {p['id']: 0.0 for p in targets}
    for f in fleets:
        if f['owner'] != pid: continue
        best_id, best_diff = None, 0.35
        for tgt in targets:
            dx, dy = tgt['x'] - f['x'], tgt['y'] - f['y']
            if math.hypot(dx, dy) < 1.0: continue
            a_to = math.atan2(dy, dx)
            diff = abs(math.atan2(math.sin(f['angle'] - a_to), math.cos(f['angle'] - a_to)))
            if diff < best_diff: best_diff, best_id = diff, tgt['id']
        if best_id is not None: pending[best_id] = pending.get(best_id, 0) + f['ships']
    available = {p['id']: p['ships'] for p in mine}
    moves = []
    for p in mine:
        enemy_fleets = [(f, math.hypot(p['x'] - f['x'], p['y'] - f['y'])) for f in fleets if f['owner'] != pid and f['owner'] >= 0 and is_heading_to(f, p)]
        if not enemy_fleets: continue
        incoming_ships = sum(f['ships'] for f, _ in enemy_fleets)
        closest_f, closest_dist = min(enemy_fleets, key=lambda x: x[1])
        threat_eta = closest_dist / max(spd(closest_f['ships']), 0.1)
        # CHANGELOG: Threat ETA 35.0
        if threat_eta >= 35.0: continue
        enemy_planets_near = [ep for ep in planets if ep['owner'] != pid and ep['owner'] >= 0 and math.hypot(ep['x'] - p['x'], ep['y'] - p['y']) < 40.0]
        if len(enemy_planets_near) >= 3 and threat_eta < 20.0: continue
        production_turns = int(math.floor(threat_eta))
        garrison = p['ships'] + p['prod'] * production_turns
        safety_need = int(incoming_ships * 1.3 + 5)
        if garrison >= safety_need: continue
        deficit = safety_need - garrison
        if deficit < 3: continue
        helpers = sorted([m for m in mine if m['id'] != p['id'] and available[m['id']] > 5], key=lambda m: math.hypot(m['x'] - p['x'], m['y'] - p['y']))
        for h in helpers:
            send = min(int(available[h['id']] * 0.75), int(deficit + 4))
            if send < 3: continue
            angle, eta = find_angle(h, p, send, vel, ips, step, state)
            if angle is not None and eta < threat_eta:
                moves.append([h['id'], angle, send])
                available[h['id']] -= send
                deficit -= send
                if deficit <= 0: break
    mine_sorted = sorted(mine, key=lambda p: -available[p['id']])
    this_turn_sent = {p['id']: 0.0 for p in targets}
    for src in mine_sorted:
        keep = 1 if (snowball or len(mine) < 3) else 2
        max_launches, launches = 3, 0
        while available[src['id']] > keep and launches < max_launches:
            avail = available[src['id']]
            best_score, best_tgt, best_angle, best_send, best_needed = -float('inf'), None, None, 0, 0
            for tgt in targets:
                is_comet = tgt['id'] in comets
                dist = math.hypot(src['x'] - tgt['x'], src['y'] - tgt['y'])
                incoming_threats = [f for f in fleets if f['owner'] != pid and is_heading_to(f, src)]
                if incoming_threats:
                    closest_threat = min(incoming_threats, key=lambda f: math.hypot(src['x'] - f['x'], src['y'] - f['y']))
                    tdist = math.hypot(src['x'] - closest_threat['x'], src['y'] - closest_threat['y'])
                    if tdist <= 85.0:
                        t_eta = tdist / max(spd(closest_threat['ships']), 0.1)
                        garrison_at_impact = avail + src['prod'] * int(math.floor(t_eta))
                        if garrison_at_impact - 5 < sum(f['ships'] for f in incoming_threats) * 1.25: continue
                reserve = 1 if (snowball or len(mine) < 3) else 2
                max_send = avail - reserve
                if max_send < 2: continue
                if is_comet:
                    send = min(int(max_send), 2)
                    needed = 2
                    res = find_angle(src, tgt, send, vel, ips, step, state)
                    if res[0] is None: continue
                    angle, eta = res
                else:
                    send = min(int(max_send), int(tgt['ships']) + 4)
                    angle, eta, needed = None, 0, 0
                    for _ in range(3):
                        if send < 2: break
                        res = find_angle(src, tgt, send, vel, ips, step, state)
                        if res[0] is None: break
                        angle, eta = res
                        committed = pending.get(tgt['id'], 0) + this_turn_sent.get(tgt['id'], 0)
                        needed = max(0, int(compute_precise_needed_fast(src, tgt, eta, state, pid) - committed))
                        if needed == 0:
                            send = 0
                            break
                        # CHANGELOG: Buffer 1.35
                        send = min(int(max_send), max(int(needed * 1.35), needed + 2))
                    if send < needed or send < 2 or angle is None or needed == 0: continue
                committed = pending.get(tgt['id'], 0) + this_turn_sent.get(tgt['id'], 0)
                sc = score_target(src, tgt, eta, is_comet, step, needed, mine, planets, pid, state, committed)
                if sc > best_score: best_score, best_tgt, best_angle, best_send, best_needed = sc, tgt, angle, send, needed
            if best_tgt is None or best_send < 2: break
            moves.append([src['id'], best_angle, best_send])
            available[src['id']] -= best_send
            this_turn_sent[best_tgt['id']] = this_turn_sent.get(best_tgt['id'], 0) + best_send
            launches += 1
    return moves

def parse_obs(obs):
    raw_planets, raw_fleets, raw_ips = obs.get("planets", []), obs.get("fleets", []), obs.get("initial_planets", [])
    ips = {int(p[0]): {'id': int(p[0]), 'owner': int(p[1]), 'x': float(p[2]), 'y': float(p[3]), 'r': float(p[4]), 'ships': float(p[5]), 'prod': float(p[6])} for p in raw_ips}
    comet_ids, moving = set(obs.get("comet_planet_ids", [])), set()
    for p in raw_planets:
        pid = int(p[0])
        if pid in comet_ids: continue
        if math.hypot(float(p[2]) - 50, float(p[3]) - 50) + float(p[4]) < 50: moving.add(pid)
    planets = [{'id': int(p[0]), 'owner': int(p[1]), 'x': float(p[2]), 'y': float(p[3]), 'r': float(p[4]), 'ships': float(p[5]), 'prod': float(p[6])} for p in raw_planets]
    fleets = [{'id': int(f[0]), 'owner': int(f[1]), 'x': float(f[2]), 'y': float(f[3]), 'angle': float(f[4]), 'from_planet_id': int(f[5]), 'ships': float(f[6])} for f in raw_fleets]
    return {'planets': planets, 'fleets': fleets, 'ips': ips, 'angular_velocity': obs.get("angular_velocity", 0.0), 'step': obs.get("step", 0), 'comet_planet_ids': comet_ids, 'moving': moving, 'comets': obs.get("comets", [])}

def agent(obs):
    try:
        state = parse_obs(obs)
        pid = obs.get("player", 0)
        return compute_moves(state, pid)
    except Exception: return []
