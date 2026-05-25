"""
Orbit Wars Agent — V4 (Proven Heuristic)
Submit this file directly: kaggle competitions submit orbit-wars -f main.py -m "V4 heuristic"

Bugs fixed from V3:
  - Defense was triggering on ALL nearby enemy fleets (d<30), wasting ships
  - Ships needed calculation overestimated by multiplying production*15
  - Was capping at 75% ships, preventing early captures when you only have 10 ships
  - Not tracking already-targeted planets, causing multiple ships to same target
"""
import math

# ==============================================================================
# DATA STRUCTURES (matching README exactly)
# Planet: [id, owner, x, y, radius, ships, production]
# Fleet:  [id, owner, x, y, angle, from_planet_id, ships]
# ==============================================================================

class Planet:
    __slots__ = ['id','owner','x','y','radius','ships','production']
    def __init__(self, pid, owner, x, y, radius, ships, production):
        self.id = int(pid); self.owner = int(owner)
        self.x = float(x); self.y = float(y); self.radius = float(radius)
        self.ships = float(ships); self.production = float(production)

class Fleet:
    __slots__ = ['id','owner','x','y','angle','from_planet_id','ships']
    def __init__(self, fid, owner, x, y, angle, from_planet_id, ships):
        self.id = int(fid); self.owner = int(owner)
        self.x = float(x); self.y = float(y); self.angle = float(angle)
        self.from_planet_id = int(from_planet_id); self.ships = float(ships)

# ==============================================================================
# PHYSICS
# ==============================================================================

SUN_R = 10.0  # Exact from README config table

def spd(n):
    """Fleet speed from README formula."""
    if n <= 1: return 1.0
    return 1.0 + 5.0 * (math.log(n) / math.log(1000)) ** 1.5

def d(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)

def hits_sun(x1, y1, x2, y2):
    """Check if segment (x1,y1)→(x2,y2) intersects sun circle."""
    vx, vy = x2 - x1, y2 - y1
    len2 = vx*vx + vy*vy
    if len2 == 0: return (x1-50)**2 + (y1-50)**2 <= SUN_R*SUN_R
    t = max(0.0, min(1.0, ((50-x1)*vx + (50-y1)*vy) / len2))
    cx, cy = x1 + t*vx, y1 + t*vy
    return (cx-50)**2 + (cy-50)**2 <= (SUN_R + 0.5)**2  # small safety margin

def future_pos(pid, ips, vel, tick):
    """Predict position of orbiting planet at future tick."""
    ip = ips.get(pid)
    if not ip: return None, None
    r = d(ip.x, ip.y, 50, 50)
    if r < 1.0: return ip.x, ip.y
    a0 = math.atan2(ip.y - 50, ip.x - 50)
    a = a0 + vel * tick
    return 50 + r * math.cos(a), 50 + r * math.sin(a)

def find_angle(src, tgt, ships, vel, ips, is_moving):
    """Find launch angle & ETA to intercept target. Returns (angle, eta) or (None, None)."""
    speed = spd(ships)
    for tick in range(1, 80):
        if is_moving:
            tx, ty = future_pos(tgt.id, ips, vel, tick)
            if tx is None: tx, ty = tgt.x, tgt.y
        else:
            tx, ty = tgt.x, tgt.y
        dist = d(src.x, src.y, tx, ty)
        if speed * tick >= dist - tgt.radius:
            if not hits_sun(src.x, src.y, tx, ty):
                return math.atan2(ty - src.y, tx - src.x), tick
            else:
                return None, None  # sun blocks this path
    return None, None

# ==============================================================================
# THREAT DETECTION
# ==============================================================================

def detect_threats(mine, fleets, pid):
    """
    Check which of my planets have enemy fleets heading TOWARDS them.
    Uses fleet angle to verify direction, not just proximity.
    """
    threats = {}  # planet_id -> total incoming ships
    for f in fleets:
        if f.owner == pid or f.owner < 0:
            continue
        # Check if fleet angle points towards any of my planets
        for p in mine:
            dx, dy = p.x - f.x, p.y - f.y
            dist_fp = math.hypot(dx, dy)
            if dist_fp < 1.0 or dist_fp > 50:
                continue
            # Angle from fleet to planet
            angle_to_p = math.atan2(dy, dx)
            # Check if fleet's travel angle is within ~15° of the planet direction
            angle_diff = abs(math.atan2(math.sin(f.angle - angle_to_p), math.cos(f.angle - angle_to_p)))
            if angle_diff < 0.26:  # ~15 degrees
                threats[p.id] = threats.get(p.id, 0) + f.ships
    return threats

# ==============================================================================
# SCORING
# ==============================================================================

def score_target(src, tgt, eta, is_comet):
    """Score a target planet. Higher = better to attack."""
    dist_val = d(src.x, src.y, tgt.x, tgt.y)
    
    # Base: production value vs distance cost
    score = (100 - dist_val) + (15 * tgt.production)
    
    # Enemy planets are worth more (deny their production)
    if tgt.owner >= 0:  # enemy owned
        score += 10 * tgt.production
    
    # Neutral planets are cheap to take
    if tgt.owner == -1:
        score += 20
    
    # Penalize travel time
    score -= 2 * eta
    
    # Comets are temporary — deprioritize
    if is_comet:
        score -= 30
    
    # Penalize ships needed (cheap targets first)
    score -= 0.5 * tgt.ships
    
    return score

# ==============================================================================
# AGENT
# ==============================================================================

def agent(obs):
    try:
        return _agent_logic(obs)
    except Exception:
        return []

def _agent_logic(obs):
    # --- Parse observation ---
    planets = [Planet(*p) for p in obs.get("planets", [])]
    fleets  = [Fleet(*f) for f in obs.get("fleets", [])]
    ips     = {p[0]: Planet(*p) for p in obs.get("initial_planets", [])}
    pid     = obs.get("player", 0)
    vel     = obs.get("angular_velocity", 0.0)
    comets  = set(obs.get("comet_planet_ids", []))
    
    # Detect which planets are currently orbiting
    moving = set(comets)
    for p in planets:
        ip = ips.get(p.id)
        if ip and (abs(p.x - ip.x) > 0.01 or abs(p.y - ip.y) > 0.01):
            moving.add(p.id)
    
    mine    = [p for p in planets if p.owner == pid]
    targets = [p for p in planets if p.owner != pid]
    
    if not mine:
        return []
    
    # --- Track en-route fleets (avoid double-targeting) ---
    en_route = {}  # target_planet_id -> ships already heading there
    for f in fleets:
        if f.owner == pid:
            # We don't know exact target, but we know from_planet
            # Just track that we have ships in transit
            pass
    
    # --- Threat detection ---
    threats = detect_threats(mine, fleets, pid)
    
    moves = []
    exhausted = set()  # planets that have launched this turn
    targeted  = set()  # targets we're already attacking this turn
    
    # === PHASE 1: DEFEND threatened planets ===
    for p_id, incoming_ships in threats.items():
        p = next((x for x in mine if x.id == p_id), None)
        if not p: continue
        
        # Only reinforce if garrison can't hold
        if p.ships >= incoming_ships + 3:
            continue
        
        deficit = incoming_ships - p.ships + 5
        
        # Find closest helper
        helpers = sorted(
            [m for m in mine if m.id != p_id and m.id not in exhausted and m.ships > 10],
            key=lambda m: d(m.x, m.y, p.x, p.y)
        )
        for h in helpers:
            send = min(int(h.ships * 0.5), int(deficit))
            if send < 3: continue
            angle, eta = find_angle(h, p, send, vel, ips, p.id in moving)
            if angle is not None:
                moves.append([h.id, angle, send])
                exhausted.add(h.id)
                break
    
    # === PHASE 2: ATTACK targets ===
    # Sort own planets strongest first
    mine_sorted = sorted(mine, key=lambda p: p.ships, reverse=True)
    
    # Build and score all (source, target) pairs
    attack_options = []
    for src in mine_sorted:
        if src.id in exhausted or src.ships < 5:
            continue
        for tgt in targets:
            is_moving_tgt = tgt.id in moving
            is_comet = tgt.id in comets
            
            # Calculate ships needed to capture
            # For neutrals: just beat garrison
            # For enemies: beat garrison + production during travel
            est_dist = d(src.x, src.y, tgt.x, tgt.y)
            est_speed = spd(max(5, int(src.ships * 0.5)))
            est_eta = est_dist / max(est_speed, 0.1)
            
            needed = tgt.ships + 1
            if tgt.owner >= 0:  # enemy: account for production during travel
                needed += tgt.production * est_eta
            
            needed = int(math.ceil(needed))
            
            # What can we actually send?
            # Early game (few planets): be aggressive, send most ships
            # Late game (many planets): be conservative
            if len(mine) <= 2:
                max_send = int(src.ships - 1)  # keep 1 for ownership
            elif len(mine) <= 4:
                max_send = int(src.ships * 0.8)
            else:
                max_send = int(src.ships * 0.65)
            
            if max_send < 5:
                continue
            
            send = max(5, min(max_send, needed + 3))
            
            # Can we afford it?
            if send > src.ships - 1:
                continue
            
            angle, eta = find_angle(src, tgt, send, vel, ips, is_moving_tgt)
            if angle is None:
                continue
            
            sc = score_target(src, tgt, eta, is_comet)
            attack_options.append((sc, src.id, tgt.id, angle, send))
    
    # Sort by score descending, pick best non-conflicting moves
    attack_options.sort(key=lambda x: x[0], reverse=True)
    
    for sc, src_id, tgt_id, angle, send in attack_options:
        if src_id in exhausted:
            continue
        if tgt_id in targeted:
            continue
        moves.append([src_id, angle, send])
        exhausted.add(src_id)
        targeted.add(tgt_id)
    
    return moves
