import math

# Speed formula (from game README)
def spd(n):
    if n <= 1: return 1.0
    return 1.0 + 5.0 * (math.log(n) / math.log(1000)) ** 1.5

# Sun position and radius
SUN_X, SUN_Y, SUN_R = 50.0, 50.0, 10.0

# Sun collision check (add 0.5 safety margin)
def hits_sun(x1, y1, x2, y2):
    vx, vy = x2-x1, y2-y1
    len2 = vx*vx + vy*vy
    if len2 == 0: return (x1-50)**2+(y1-50)**2 <= SUN_R**2
    t = max(0.0, min(1.0, ((50-x1)*vx+(50-y1)*vy)/len2))
    cx, cy = x1+t*vx, y1+t*vy
    return (cx-50)**2+(cy-50)**2 <= (SUN_R+0.5)**2

# Planet orbit (initial_planets gives t=0 positions)
def planet_pos_at_step(ip, vel, step):
    r = math.hypot(ip['x']-50, ip['y']-50)
    if r < 1.0: return ip['x'], ip['y']
    a = math.atan2(ip['y']-50, ip['x']-50) + vel*step
    return 50+r*math.cos(a), 50+r*math.sin(a)

# Intercept angle search
def find_angle(src, tgt, ships, vel, ips, step, is_moving):
    speed = spd(ships)
    for tick in range(1, 80):
        tx, ty = planet_pos_at_step(ips[tgt['id']], vel, step+tick) \
                 if is_moving else (tgt['x'], tgt['y'])
        if speed*tick >= math.hypot(src['x']-tx, src['y']-ty) - tgt['r']:
            if not hits_sun(src['x'], src['y'], tx, ty):
                return math.atan2(ty-src['y'], tx-src['x']), tick
    return None, None

def segment_intersects_circle(x1, y1, x2, y2, cx, cy, r):
    vx, vy = x2 - x1, y2 - y1
    len2 = vx*vx + vy*vy
    if len2 == 0:
        return (x1 - cx)**2 + (y1 - cy)**2 <= r**2
    t = max(0.0, min(1.0, ((cx - x1)*vx + (cy - y1)*vy) / len2))
    px, py = x1 + t*vx, y1 + t*vy
    return (px - cx)**2 + (py - cy)**2 <= r**2

def copy_state(state):
    return {
        'step': state['step'],
        'vel': state['vel'],
        'planets': [p.copy() for p in state['planets']],
        'fleets': [f.copy() for f in state['fleets']],
        'ips': {k: v.copy() for k, v in state['ips'].items()},
        'moving': set(state['moving']),
        'comet_planet_ids': set(state['comet_planet_ids'])
    }

def obs_to_state(obs):
    # Construct initial dictionary state from observation
    # observation planets: [id, owner, x, y, radius, ships, production]
    # fleets: [id, owner, x, y, angle, from_planet_id, ships]

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

    # Orbiting planets: radius + orbital_radius < 50
    moving = set()
    for p in planets:
        if p['id'] in comet_ids:
            # Comets handled differently, or not orbiting in the same way?
            # Actually, comets are just moving along paths, but for simplicity
            # we might not perfectly simulate comets in MCTS. We just leave them as static or moving.
            # But the requirement says: "planets in state['moving'] rotate by vel*(state['step']+1)"
            # So comets shouldn't be in moving if they don't orbit.
            pass
        elif math.hypot(p['x']-50, p['y']-50) + p['r'] < 50:
            moving.add(p['id'])

    return {
        'step': step,
        'vel': vel,
        'planets': planets,
        'fleets': fleets,
        'ips': ips,
        'moving': moving,
        'comet_planet_ids': comet_ids
    }

def is_heading_to(f, p):
    # Helper logic for threats, since Bug 4 and other logic needs "incoming_ships"
    # Simple check if fleet's trajectory intersects planet's current or future pos
    vx = math.cos(f['angle'])
    vy = math.sin(f['angle'])
    dist = math.hypot(p['x'] - f['x'], p['y'] - f['y'])
    tx, ty = f['x'] + vx * dist, f['y'] + vy * dist
    return math.hypot(tx - p['x'], ty - p['y']) <= p['r'] + 2.0

def simulate_tick(state, dict_moves):
    # dict_moves: {player_id: [[src_id, angle, ships], ...]}

    # 1. Launch fleets
    fleet_id_counter = max([f['id'] for f in state['fleets']] + [0]) + 1

    for pid, moves in dict_moves.items():
        if not moves: continue
        for move in moves:
            src_id, angle, ships = move
            # find source planet
            src_p = None
            for p in state['planets']:
                if p['id'] == src_id:
                    src_p = p
                    break
            if src_p and src_p['owner'] == pid and src_p['ships'] >= ships:
                src_p['ships'] -= ships
                state['fleets'].append({
                    'id': fleet_id_counter,
                    'owner': pid,
                    'x': src_p['x'] + math.cos(angle) * (src_p['r'] + 0.1),
                    'y': src_p['y'] + math.sin(angle) * (src_p['r'] + 0.1),
                    'angle': angle,
                    'from': src_id,
                    'ships': ships
                })
                fleet_id_counter += 1

    # 2. Production
    for p in state['planets']:
        if p['owner'] >= 0:
            p['ships'] += p['prod']

    # 3. Fleet movement
    surviving_fleets = []
    arriving_fleets = {}  # destination_planet_id -> list of fleets

    for f in state['fleets']:
        speed = spd(f['ships'])
        nx = f['x'] + math.cos(f['angle']) * speed
        ny = f['y'] + math.sin(f['angle']) * speed

        # OOB check
        if nx < 0 or nx > 100 or ny < 0 or ny > 100:
            continue

        # Sun collision
        if hits_sun(f['x'], f['y'], nx, ny):
            continue

        # Planet collisions
        hit_p = None
        for p in state['planets']:
            # Cannot hit the planet it just launched from if it's still inside
            if segment_intersects_circle(f['x'], f['y'], nx, ny, p['x'], p['y'], p['r']):
                # If just launched, distance might be very small, but the game engine
                # allows launch out of planet. We'll ignore hit if it's the source
                # and distance is small, but segment_intersects_circle might trigger.
                # Actually, standard game rules say it triggers combat.
                # To be safe, if dist from center is less than radius + speed, it's a hit.
                hit_p = p
                break

        if hit_p:
            if hit_p['id'] not in arriving_fleets:
                arriving_fleets[hit_p['id']] = []
            arriving_fleets[hit_p['id']].append(f)
        else:
            f['x'] = nx
            f['y'] = ny
            surviving_fleets.append(f)

    state['fleets'] = surviving_fleets

    # 4. Planet orbit
    state['step'] += 1
    new_step = state['step']
    for p in state['planets']:
        if p['id'] in state['moving']:
            ip = state['ips'][p['id']]
            nx, ny = planet_pos_at_step(ip, state['vel'], new_step)
            # Sweeping fleets:
            for f in reversed(state['fleets']):
                if math.hypot(nx - f['x'], ny - f['y']) <= p['r']:
                    if p['id'] not in arriving_fleets:
                        arriving_fleets[p['id']] = []
                    arriving_fleets[p['id']].append(f)
                    state['fleets'].remove(f)
            p['x'] = nx
            p['y'] = ny

    # 6. Combat resolution
    for p_id, fleets in arriving_fleets.items():
        p = None
        for planet in state['planets']:
            if planet['id'] == p_id:
                p = planet
                break
        if not p: continue

        owner_ships = {}
        for f in fleets:
            owner_ships[f['owner']] = owner_ships.get(f['owner'], 0) + f['ships']

        # Group attackers
        attackers = [(owner, ships) for owner, ships in owner_ships.items() if owner != p['owner']]

        # Same owner reinforces
        if p['owner'] in owner_ships:
            p['ships'] += owner_ships[p['owner']]

        if attackers:
            attackers.sort(key=lambda x: x[1], reverse=True)
            if len(attackers) >= 2:
                largest = attackers[0]
                second_largest = attackers[1]
                surplus = largest[1] - second_largest[1]
                if surplus > 0:
                    surviving_attacker_owner = largest[0]
                    surviving_attacker_ships = surplus
                else:
                    surviving_attacker_owner = None
                    surviving_attacker_ships = 0
            else:
                surviving_attacker_owner = attackers[0][0]
                surviving_attacker_ships = attackers[0][1]

            if surviving_attacker_ships > 0:
                if surviving_attacker_ships > p['ships']:
                    p['owner'] = surviving_attacker_owner
                    p['ships'] = surviving_attacker_ships - p['ships']
                else:
                    p['ships'] -= surviving_attacker_ships
