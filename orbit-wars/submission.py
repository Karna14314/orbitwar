import math
import time
import sys
import os

sys.path.append(os.path.dirname(__file__))

# Sim basics
def spd(n):
    if n <= 1: return 1.0
    return 1.0 + 5.0 * (math.log(n) / math.log(1000)) ** 1.5

SUN_X, SUN_Y, SUN_R = 50.0, 50.0, 10.0

def hits_sun(x1, y1, x2, y2):
    vx, vy = x2-x1, y2-y1
    len2 = vx*vx + vy*vy
    if len2 == 0: return (x1-50)**2+(y1-50)**2 <= SUN_R**2
    t = max(0.0, min(1.0, ((50-x1)*vx+(50-y1)*vy)/len2))
    cx, cy = x1+t*vx, y1+t*vy
    return (cx-50)**2+(cy-50)**2 <= (SUN_R+0.5)**2

def planet_pos_at_step(ip, vel, step):
    r = math.hypot(ip['x']-50, ip['y']-50)
    if r < 1.0: return ip['x'], ip['y']
    a = math.atan2(ip['y']-50, ip['x']-50) + vel*step
    return 50+r*math.cos(a), 50+r*math.sin(a)

def segment_intersects_circle(x1, y1, x2, y2, cx, cy, r):
    vx, vy = x2 - x1, y2 - y1
    len2 = vx*vx + vy*vy
    if len2 == 0: return (x1 - cx)**2 + (y1 - cy)**2 <= r**2
    t = max(0.0, min(1.0, ((cx - x1)*vx + (cy - y1)*vy) / len2))
    px, py = x1 + t*vx, y1 + t*vy
    return (px - cx)**2 + (py - cy)**2 <= r**2

def is_heading_to(f, p):
    vx = math.cos(f['angle'])
    vy = math.sin(f['angle'])
    dist = math.hypot(p['x'] - f['x'], p['y'] - f['y'])
    tx, ty = f['x'] + vx * dist, f['y'] + vy * dist
    return math.hypot(tx - p['x'], ty - p['y']) <= p['r'] + 2.0

def obs_to_state(obs):
    planets = []
    for p in obs.get('planets', []):
        planets.append({'id': p[0], 'owner': p[1], 'x': p[2], 'y': p[3], 'r': p[4], 'ships': p[5], 'prod': p[6]})
    fleets = []
    for f in obs.get('fleets', []):
        fleets.append({'id': f[0], 'owner': f[1], 'x': f[2], 'y': f[3], 'angle': f[4], 'from': f[5], 'ships': f[6]})
    ips = {}
    for ip in obs.get('initial_planets', []):
        ips[ip[0]] = {'id': ip[0], 'owner': ip[1], 'x': ip[2], 'y': ip[3], 'r': ip[4], 'ships': ip[5], 'prod': ip[6]}
    vel = obs.get('angular_velocity', 0.0)
    step = obs.get('step', 0)
    comet_ids = set(obs.get('comet_planet_ids', []))
    moving = set()
    for p in planets:
        if p['id'] not in comet_ids and math.hypot(p['x']-50, p['y']-50) + p['r'] < 50:
            moving.add(p['id'])
    return {'step': step, 'vel': vel, 'planets': planets, 'fleets': fleets, 'ips': ips, 'moving': moving, 'comet_planet_ids': comet_ids}

def find_angle_with_avoidance(src, tgt, ships, vel, ips, step, is_moving, max_ticks=80):
    speed = spd(ships)
    for tick in range(1, max_ticks):
        tx, ty = planet_pos_at_step(ips[tgt['id']], vel, step+tick) if is_moving else (tgt['x'], tgt['y'])
        dist = math.hypot(src['x']-tx, src['y']-ty)
        if speed*tick >= dist - tgt['r']:
            base_angle = math.atan2(ty-src['y'], tx-src['x'])
            if not hits_sun(src['x'], src['y'], tx, ty):
                return base_angle, tick
            else:
                for offset in [0.08, -0.08, 0.15, -0.15, 0.25, -0.25, 0.35, -0.35, 0.5, -0.5]:
                    test_angle = base_angle + offset
                    nx = src['x'] + math.cos(test_angle) * dist
                    ny = src['y'] + math.sin(test_angle) * dist
                    if not hits_sun(src['x'], src['y'], nx, ny):
                        return test_angle, int(tick * 1.1)
    return None, None

def comet_departure_ticks(p, step):
    # Very rough estimation of comet departure. A comet is assumed to just fly straight out of bounds.
    # The prompt mentions "Uses comet path progress to estimate departure; skips captures within 30 ticks of departure".
    # For now, let's just use a simplistic heuristic or ignore capturing if we think it's too close to edge.
    if p['x'] < 10 or p['x'] > 90 or p['y'] < 10 or p['y'] > 90:
        return 20 # likely departing soon
    return 100

def agent_v7_logic(state, pid):
    mine = [p for p in state['planets'] if p['owner'] == pid]
    enemy = [p for p in state['planets'] if p['owner'] not in (-1, pid)]
    neutrals = [p for p in state['planets'] if p['owner'] == -1]

    available_ships = {p['id']: p['ships'] for p in mine}
    moves = []

    def issue_order(src_id, angle, ships):
        if available_ships[src_id] >= ships and ships > 0:
            available_ships[src_id] -= ships
            moves.append([src_id, angle, ships])
            return True
        return False

    # Pre-calculate threats
    threats = {p['id']: 0 for p in mine}
    friendly_incoming = {p['id']: 0 for p in mine}
    for f in state['fleets']:
        for p in mine:
            if is_heading_to(f, p):
                if f['owner'] not in (pid, -1): threats[p['id']] += f['ships']
                elif f['owner'] == pid: friendly_incoming[p['id']] += f['ships']

    # Phase 1: Defense
    for p in sorted(mine, key=lambda x: x['prod'], reverse=True): # Value-Based Defense Triage
        deficit = threats[p['id']] - (available_ships[p['id']] + friendly_incoming[p['id']])
        if deficit > 0:
            value = p['prod'] * (1000 - state['step'])
            if deficit > value * 0.6: # Won't defend if deficit > 60% of planet's remaining value
                continue

            # Request help
            for helper in sorted(mine, key=lambda x: math.hypot(x['x']-p['x'], x['y']-p['y'])):
                if helper['id'] == p['id'] or available_ships[helper['id']] < 5: continue
                if deficit <= 0: break

                can_send = int(available_ships[helper['id']] * 0.8)
                angle, ticks = find_angle_with_avoidance(helper, p, can_send, state['vel'], state['ips'], state['step'], p['id'] in state['moving'])
                if angle is not None:
                    send = min(can_send, int(deficit + 1))
                    if issue_order(helper['id'], angle, send):
                        deficit -= send

    # Phase 2: Comet Evacuation
    for p in mine:
        if p['id'] in state['comet_planet_ids'] and comet_departure_ticks(p, state['step']) < 30:
            # Evacuate to nearest safe friendly planet
            safe_friends = [f for f in mine if f['id'] != p['id'] and f['id'] not in state['comet_planet_ids']]
            if safe_friends and available_ships[p['id']] > 0:
                best_dest = min(safe_friends, key=lambda x: math.hypot(p['x']-x['x'], p['y']-x['y']))
                angle, ticks = find_angle_with_avoidance(p, best_dest, available_ships[p['id']], state['vel'], state['ips'], state['step'], best_dest['id'] in state['moving'])
                if angle is not None:
                    issue_order(p['id'], angle, int(available_ships[p['id']]))

    # Phase 3: Expansion (Easy Capture) & Coordinated Attack
    # We use the unified scoring formula
    targets = neutrals + enemy

    # Track used sources to prevent single planet sending multiple fleets in one tick if not necessary,
    # though `available_ships` naturally limits this.
    for src in mine:
        if available_ships[src['id']] < 5: continue

        best_score = -float('inf')
        best_tgt = None
        best_angle = None
        best_send = 0

        for tgt in targets:
            if tgt['id'] in state['comet_planet_ids'] and comet_departure_ticks(tgt, state['step']) < 30:
                continue # Skip near-departure comet captures

            angle, ticks = find_angle_with_avoidance(src, tgt, available_ships[src['id']], state['vel'], state['ips'], state['step'], tgt['id'] in state['moving'])
            if angle is None: continue

            eta = ticks
            dist = eta * spd(available_ships[src['id']])
            cost = tgt['ships'] + 1 + (tgt['prod'] * eta if tgt['owner'] >= 0 else 0)

            if available_ships[src['id']] < cost + 3: continue

            remaining_ticks = max(1, 1000 - state['step'] - eta)
            score = (tgt['prod'] * remaining_ticks) / (1.0 + 0.08 * eta)
            score -= cost * 0.4

            # Neutral bonus
            if tgt['owner'] == -1:
                score += 40 # 20-60
                if tgt['ships'] <= 3: score += 40
                elif tgt['ships'] <= 7: score += 25
            else:
                # Enemy denial
                if tgt['prod'] >= 4:
                    score += 30
                score += tgt['prod'] * 45

            # Efficiency bonus
            efficiency = tgt['prod'] / (dist * 0.1 + cost * 0.05 + 1.0)
            score += efficiency * 20

            # Comet penalty
            if tgt['id'] in state['comet_planet_ids']:
                score -= 100 # 60-140

            # Distance bonus
            score += max(0, 15 - dist * 0.1)

            if score > best_score:
                best_score = score
                best_tgt = tgt
                best_angle = angle
                best_send = int(cost + 3)

        if best_tgt and best_score > 0:
            issue_order(src['id'], best_angle, best_send)

    # Phase 4: Coordinated Multi-Source Attacks
    if enemy:
        # Re-evaluate top 4 enemies for coordinated attack
        top_enemies = sorted(enemy, key=lambda e: e['prod'], reverse=True)[:4]
        for tgt in top_enemies:
            attackers = []
            total_force = 0
            for src in mine:
                if available_ships[src['id']] > 10:
                    send = int(available_ships[src['id']] * 0.55)
                    angle, ticks = find_angle_with_avoidance(src, tgt, send, state['vel'], state['ips'], state['step'], tgt['id'] in state['moving'])
                    if angle is not None:
                        attackers.append((src['id'], angle, send, ticks))
                        total_force += send
            if not attackers: continue
            avg_eta = sum(t for _, _, _, t in attackers) / len(attackers)
            needed = tgt['ships'] + tgt['prod'] * avg_eta + 5

            if total_force > needed:
                for src_id, angle, send, _ in attackers:
                    issue_order(src_id, angle, send)

    # Phase 6: Consolidation
    for src in mine:
        if 10 < available_ships[src['id']] < 50:
            closest_f = None
            closest_dist = float('inf')
            for f in mine:
                if f['id'] == src['id']: continue
                d = math.hypot(src['x']-f['x'], src['y']-f['y'])
                if d < closest_dist and d < 30:
                    closest_dist = d
                    closest_f = f
            if closest_f:
                angle, ticks = find_angle_with_avoidance(src, closest_f, available_ships[src['id']]-1, state['vel'], state['ips'], state['step'], closest_f['id'] in state['moving'])
                if angle is not None:
                    issue_order(src['id'], angle, int(available_ships[src['id']]-1))

    # Phase 7: Idle Ship Deployment
    for src in mine:
        if available_ships[src['id']] > 50:
            nearest_enemy = None
            nearest_dist = float('inf')
            for e in enemy:
                d = math.hypot(src['x']-e['x'], src['y']-e['y'])
                if d < nearest_dist:
                    nearest_dist = d
                    nearest_enemy = e
            if nearest_enemy:
                angle, ticks = find_angle_with_avoidance(src, nearest_enemy, int(available_ships[src['id']]*0.8), state['vel'], state['ips'], state['step'], nearest_enemy['id'] in state['moving'])
                if angle is not None:
                    issue_order(src['id'], angle, int(available_ships[src['id']]*0.8))

    # Phase 8: Proactive Reinforcement
    for src in mine:
        if available_ships[src['id']] > 20:
            high_prod_low_garrison = [p for p in mine if p['id'] != src['id'] and p['prod'] >= 4 and p['ships'] < 20]
            if high_prod_low_garrison:
                target = min(high_prod_low_garrison, key=lambda x: math.hypot(src['x']-x['x'], src['y']-x['y']))
                angle, ticks = find_angle_with_avoidance(src, target, 10, state['vel'], state['ips'], state['step'], target['id'] in state['moving'])
                if angle is not None:
                    issue_order(src['id'], angle, 10)

    return moves

def agent(obs):
    try:
        state = obs_to_state(obs)
        pid = obs.get("player", 0)
        return agent_v7_logic(state, pid)
    except Exception as e:
        print(f"Agent V7 Error: {e}")
        return []
