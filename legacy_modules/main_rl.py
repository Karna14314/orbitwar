"""
Orbit Wars — RL-Enhanced Agent (submission version)
=====================================================
This is the submission main.py that loads trained weights.

Usage:
  tar -czf submission.tar.gz main.py weights.npz
  kaggle competitions submit orbit-wars -f submission.tar.gz -m "RL agent v1"

Falls back to pure heuristic if weights.npz is not found.
"""
import math
import numpy as np
import os

# ==============================================================================
# DATA STRUCTURES
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

SUN_R = 10.0

def spd(n):
    if n <= 1: return 1.0
    return 1.0 + 5.0 * (math.log(n) / math.log(1000)) ** 1.5

def dst(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)

def hits_sun(x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    len2 = vx*vx + vy*vy
    if len2 == 0: return (x1-50)**2 + (y1-50)**2 <= SUN_R*SUN_R
    t = max(0.0, min(1.0, ((50-x1)*vx + (50-y1)*vy) / len2))
    cx, cy = x1 + t*vx, y1 + t*vy
    return (cx-50)**2 + (cy-50)**2 <= (SUN_R + 0.5)**2

def future_pos(pid, ips, vel, tick):
    ip = ips.get(pid)
    if not ip: return None, None
    r = dst(ip.x, ip.y, 50, 50)
    if r < 1.0: return ip.x, ip.y
    a0 = math.atan2(ip.y - 50, ip.x - 50)
    a = a0 + vel * tick
    return 50 + r * math.cos(a), 50 + r * math.sin(a)

def find_angle(src, tgt, ships, vel, ips, is_moving):
    speed = spd(ships)
    for tick in range(1, 80):
        if is_moving:
            tx, ty = future_pos(tgt.id, ips, vel, tick)
            if tx is None: tx, ty = tgt.x, tgt.y
        else:
            tx, ty = tgt.x, tgt.y
        dd = dst(src.x, src.y, tx, ty)
        if speed * tick >= dd - tgt.radius:
            if not hits_sun(src.x, src.y, tx, ty):
                return math.atan2(ty - src.y, tx - src.x), tick
    return None, None

# ==============================================================================
# FEATURES (must match train_rl.py exactly)
# ==============================================================================

GLOBAL_DIM = 8
CAND_DIM = 12
FEATURE_DIM = GLOBAL_DIM + CAND_DIM

def extract_global(state):
    mine = state["mine"]; targets = state["targets"]
    my_ships = sum(p.ships for p in mine)
    enemy_ships = sum(p.ships for p in targets if p.owner >= 0)
    neutral_ships = sum(p.ships for p in targets if p.owner == -1)
    my_fleets = sum(f.ships for f in state["fleets"] if f.owner == state["pid"])
    enemy_fleets = sum(f.ships for f in state["fleets"] if f.owner >= 0 and f.owner != state["pid"])
    total = max(1.0, my_ships + enemy_ships + neutral_ships)
    my_prod = sum(p.production for p in mine)
    enemy_prod = sum(p.production for p in targets if p.owner >= 0)
    return np.array([
        my_ships / total, len(mine) / max(1, len(state["planets"])),
        my_prod / max(1, my_prod + enemy_prod),
        my_fleets / max(1, my_fleets + enemy_fleets),
        enemy_ships / total, neutral_ships / total,
        len(state["comets"]) / 10.0, state["vel"] * 20,
    ], dtype=np.float32)

def extract_candidate(cand, state):
    src, tgt = cand["src"], cand["tgt"]
    distance_val = dst(src.x, src.y, tgt.x, tgt.y)
    return np.array([
        cand["ships"] / max(1, src.ships), cand["ships"] / 500.0,
        tgt.ships / 500.0, distance_val / 141.0, cand["eta"] / 80.0,
        tgt.production / 5.0, 1.0 if tgt.owner == -1 else 0.0,
        1.0 if tgt.owner >= 0 else 0.0, 1.0 if cand["is_comet"] else 0.0,
        src.ships / 500.0, src.production / 5.0,
        dst(tgt.x, tgt.y, 50, 50) / 70.0,
    ], dtype=np.float32)

# ==============================================================================
# MODEL
# ==============================================================================

class NumpyMLP:
    def __init__(self):
        self.weights = []
        self.biases = []
    
    def load(self, path):
        data = np.load(path)
        self.weights = []; self.biases = []
        i = 0
        while f"W{i}" in data:
            self.weights.append(data[f"W{i}"])
            self.biases.append(data[f"b{i}"])
            i += 1
    
    def forward(self, X):
        h = X
        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            h = h @ W + b
            if i < len(self.weights) - 1:
                h = np.maximum(0, h)
        return h.flatten()

# ==============================================================================
# HEURISTIC FALLBACK
# ==============================================================================

def heuristic_score(src, tgt, eta, is_comet):
    d_val = dst(src.x, src.y, tgt.x, tgt.y)
    score = (100 - d_val) + (15 * tgt.production) - (2 * eta) - (0.5 * tgt.ships)
    if tgt.owner >= 0: score += 10 * tgt.production
    if tgt.owner == -1: score += 20
    if is_comet: score -= 30
    return score

def detect_threats(mine, fleets, pid):
    threats = {}
    for f in fleets:
        if f.owner == pid or f.owner < 0: continue
        for p in mine:
            dx, dy = p.x - f.x, p.y - f.y
            dist_fp = math.hypot(dx, dy)
            if dist_fp < 1.0 or dist_fp > 50: continue
            angle_to_p = math.atan2(dy, dx)
            angle_diff = abs(math.atan2(math.sin(f.angle - angle_to_p), math.cos(f.angle - angle_to_p)))
            if angle_diff < 0.26:
                threats[p.id] = threats.get(p.id, 0) + f.ships
    return threats

# ==============================================================================
# AGENT
# ==============================================================================

# Try loading RL model
_model = None
_weights_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights.npz")
if os.path.exists(_weights_path):
    _model = NumpyMLP()
    _model.load(_weights_path)

def agent(obs):
    try:
        return _agent_logic(obs)
    except Exception:
        return []

def _agent_logic(obs):
    planets = [Planet(*p) for p in obs.get("planets", [])]
    fleets  = [Fleet(*f) for f in obs.get("fleets", [])]
    ips     = {p[0]: Planet(*p) for p in obs.get("initial_planets", [])}
    pid     = obs.get("player", 0)
    vel     = obs.get("angular_velocity", 0.0)
    comets  = set(obs.get("comet_planet_ids", []))
    moving  = set(comets)
    for p in planets:
        ip = ips.get(p.id)
        if ip and (abs(p.x - ip.x) > 0.01 or abs(p.y - ip.y) > 0.01):
            moving.add(p.id)
    
    state = {
        "planets": planets, "fleets": fleets, "ips": ips,
        "pid": pid, "vel": vel, "comets": comets, "moving": moving,
        "mine": [p for p in planets if p.owner == pid],
        "targets": [p for p in planets if p.owner != pid],
    }
    mine = state["mine"]
    targets = state["targets"]
    
    if not mine: return []
    
    # Defense
    threats = detect_threats(mine, fleets, pid)
    moves = []
    exhausted = set()
    
    for p_id, incoming in threats.items():
        p = next((x for x in mine if x.id == p_id), None)
        if not p or p.ships >= incoming + 3: continue
        deficit = incoming - p.ships + 5
        helpers = sorted([m for m in mine if m.id != p_id and m.id not in exhausted and m.ships > 10],
                         key=lambda m: dst(m.x, m.y, p.x, p.y))
        for h in helpers:
            send = min(int(h.ships * 0.5), int(deficit))
            if send < 3: continue
            a, _ = find_angle(h, p, send, vel, ips, p.id in moving)
            if a is not None:
                moves.append([h.id, a, send])
                exhausted.add(h.id)
                break
    
    # Generate candidates
    candidates = []
    for src in mine:
        if src.id in exhausted or src.ships < 5: continue
        for tgt in targets:
            is_mov = tgt.id in moving
            est_d = dst(src.x, src.y, tgt.x, tgt.y)
            est_eta = est_d / max(spd(max(5, int(src.ships * 0.5))), 0.1)
            needed = tgt.ships + 1
            if tgt.owner >= 0: needed += tgt.production * est_eta
            needed = int(math.ceil(needed))
            
            if len(mine) <= 2: max_send = int(src.ships - 1)
            elif len(mine) <= 4: max_send = int(src.ships * 0.8)
            else: max_send = int(src.ships * 0.65)
            
            send = max(5, min(max_send, needed + 3))
            if send > src.ships - 1 or send < 5: continue
            
            a, eta = find_angle(src, tgt, send, vel, ips, is_mov)
            if a is None: continue
            
            candidates.append({
                "src_id": src.id, "tgt_id": tgt.id,
                "angle": a, "ships": send, "eta": eta,
                "src": src, "tgt": tgt,
                "is_comet": tgt.id in comets,
            })
    
    if not candidates: return moves
    
    # Score candidates
    if _model is not None:
        # RL model scoring
        glob = extract_global(state)
        feat_rows = [np.concatenate([glob, extract_candidate(c, state)]) for c in candidates]
        features = np.stack(feat_rows)
        scores = _model.forward(features)
    else:
        # Heuristic fallback
        scores = np.array([heuristic_score(c["src"], c["tgt"], c["eta"], c["is_comet"]) 
                           for c in candidates])
    
    order = np.argsort(-scores)
    used_src = set(exhausted)
    used_tgt = set()
    
    for idx in order:
        c = candidates[idx]
        if c["src_id"] not in used_src and c["tgt_id"] not in used_tgt:
            moves.append([c["src_id"], c["angle"], c["ships"]])
            used_src.add(c["src_id"])
            used_tgt.add(c["tgt_id"])
    
    return moves
