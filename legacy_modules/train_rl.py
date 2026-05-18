"""
Orbit Wars — RL Training Script
================================
Run on Kaggle GPU or locally to train a policy ranker model.

Workflow:
  1. Heuristic agent generates candidate moves
  2. Model learns to rank candidates by playing games
  3. Weights saved to weights.npz
  4. Bundle: tar -czf submission.tar.gz main.py weights.npz
  5. Submit: kaggle competitions submit orbit-wars -f submission.tar.gz -m "RL v1"

Weight persistence across sessions:
  - Save weights to a Kaggle Dataset after each training session
  - Next session loads from the dataset and continues training
"""

import math
import numpy as np
import os
import json
import time
from collections import deque

# ============================================================================
# 1. DATA STRUCTURES (same as main.py)
# ============================================================================

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

def dist(x1, y1, x2, y2):
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
    r = dist(ip.x, ip.y, 50, 50)
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
        dd = dist(src.x, src.y, tx, ty)
        if speed * tick >= dd - tgt.radius:
            if not hits_sun(src.x, src.y, tx, ty):
                return math.atan2(ty - src.y, tx - src.x), tick
    return None, None

# ============================================================================
# 2. CANDIDATE GENERATOR
# ============================================================================

def parse_obs(obs):
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
    return {
        "planets": planets, "fleets": fleets, "ips": ips,
        "pid": pid, "vel": vel, "comets": comets, "moving": moving,
        "mine": [p for p in planets if p.owner == pid],
        "targets": [p for p in planets if p.owner != pid],
    }

def generate_candidates(state):
    """Generate all legal candidate moves with features."""
    mine = state["mine"]
    targets = state["targets"]
    ips, vel = state["ips"], state["vel"]
    moving, comets = state["moving"], state["comets"]
    
    candidates = []
    for src in mine:
        if src.ships < 5: continue
        for tgt in targets:
            is_mov = tgt.id in moving
            
            # Estimate ships needed
            est_d = dist(src.x, src.y, tgt.x, tgt.y)
            est_eta = est_d / max(spd(max(5, int(src.ships * 0.5))), 0.1)
            needed = tgt.ships + 1
            if tgt.owner >= 0:
                needed += tgt.production * est_eta
            needed = int(math.ceil(needed))
            
            max_send = int(src.ships - 1)
            send = max(5, min(max_send, needed + 3))
            if send > src.ships - 1 or send < 5:
                continue
            
            angle, eta = find_angle(src, tgt, send, vel, ips, is_mov)
            if angle is None:
                continue
            
            candidates.append({
                "src_id": src.id, "tgt_id": tgt.id,
                "angle": angle, "ships": send, "eta": eta,
                "src": src, "tgt": tgt,
                "is_comet": tgt.id in comets,
            })
    return candidates

# ============================================================================
# 3. FEATURE EXTRACTION (for RL model)
# ============================================================================

GLOBAL_DIM = 8
CAND_DIM = 12
FEATURE_DIM = GLOBAL_DIM + CAND_DIM  # 20

def extract_global(state):
    """8-dim global game state features."""
    mine = state["mine"]
    targets = state["targets"]
    planets = state["planets"]
    fleets = state["fleets"]
    pid = state["pid"]
    
    my_ships = sum(p.ships for p in mine)
    enemy_ships = sum(p.ships for p in targets if p.owner >= 0)
    neutral_ships = sum(p.ships for p in targets if p.owner == -1)
    my_fleets = sum(f.ships for f in fleets if f.owner == pid)
    enemy_fleets = sum(f.ships for f in fleets if f.owner >= 0 and f.owner != pid)
    
    total = max(1.0, my_ships + enemy_ships + neutral_ships)
    my_prod = sum(p.production for p in mine)
    enemy_prod = sum(p.production for p in targets if p.owner >= 0)
    
    return np.array([
        my_ships / total,                             # 0: ship ratio
        len(mine) / max(1, len(planets)),             # 1: planet control
        my_prod / max(1, my_prod + enemy_prod),       # 2: production share
        my_fleets / max(1, my_fleets + enemy_fleets), # 3: fleet share
        enemy_ships / total,                          # 4: enemy strength
        neutral_ships / total,                        # 5: neutral available
        len(state["comets"]) / 10.0,                  # 6: comet count
        state["vel"] * 20,                            # 7: angular velocity
    ], dtype=np.float32)

def extract_candidate(cand, state):
    """12-dim candidate move features."""
    src, tgt = cand["src"], cand["tgt"]
    
    distance_val = dist(src.x, src.y, tgt.x, tgt.y)
    
    return np.array([
        cand["ships"] / max(1, src.ships),       # 0: fraction of source used
        cand["ships"] / 500.0,                   # 1: absolute ships (normalized)
        tgt.ships / 500.0,                       # 2: target garrison
        distance_val / 141.0,                    # 3: distance (normalized by diagonal)
        cand["eta"] / 80.0,                      # 4: ETA
        tgt.production / 5.0,                    # 5: target production value
        1.0 if tgt.owner == -1 else 0.0,         # 6: is neutral
        1.0 if tgt.owner >= 0 else 0.0,          # 7: is enemy
        1.0 if cand["is_comet"] else 0.0,        # 8: is comet
        src.ships / 500.0,                       # 9: source strength
        src.production / 5.0,                    # 10: source production
        dist(tgt.x, tgt.y, 50, 50) / 70.0,      # 11: target distance from sun
    ], dtype=np.float32)

def build_feature_matrix(candidates, state):
    """Build (N, 20) feature matrix for N candidates."""
    if not candidates:
        return np.zeros((0, FEATURE_DIM), dtype=np.float32)
    
    glob = extract_global(state)
    rows = []
    for c in candidates:
        cand_feat = extract_candidate(c, state)
        rows.append(np.concatenate([glob, cand_feat]))
    return np.stack(rows)

# ============================================================================
# 4. NUMPY-ONLY MLP MODEL
# ============================================================================

class NumpyMLP:
    """Lightweight MLP with numpy only. No PyTorch needed at inference."""
    
    def __init__(self, layer_sizes=None):
        if layer_sizes is None:
            layer_sizes = [FEATURE_DIM, 64, 32, 1]
        self.weights = []
        self.biases = []
        for i in range(len(layer_sizes) - 1):
            # Xavier initialization
            scale = np.sqrt(2.0 / layer_sizes[i])
            W = np.random.randn(layer_sizes[i], layer_sizes[i+1]).astype(np.float32) * scale
            b = np.zeros(layer_sizes[i+1], dtype=np.float32)
            self.weights.append(W)
            self.biases.append(b)
    
    def forward(self, X):
        """Forward pass. X shape: (N, feature_dim). Returns (N,) scores."""
        h = X
        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            h = h @ W + b
            if i < len(self.weights) - 1:  # ReLU on all but last
                h = np.maximum(0, h)
        return h.flatten()
    
    def save(self, path):
        data = {}
        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            data[f"W{i}"] = W
            data[f"b{i}"] = b
        np.savez(path, **data)
        print(f"Saved model weights to {path}")
    
    def load(self, path):
        data = np.load(path)
        self.weights = []
        self.biases = []
        i = 0
        while f"W{i}" in data:
            self.weights.append(data[f"W{i}"])
            self.biases.append(data[f"b{i}"])
            i += 1
        print(f"Loaded model with {i} layers from {path}")

# ============================================================================
# 5. TRAINING VIA REINFORCE (Policy Gradient)
# ============================================================================

class RLTrainer:
    """
    REINFORCE trainer that learns from self-play episodes.
    
    The model scores candidate moves. We sample from the softmax distribution
    over candidates, play the game, and update weights based on the reward.
    """
    
    def __init__(self, model, lr=1e-3):
        self.model = model
        self.lr = lr
        self.episode_buffer = []  # list of (features, action_idx, reward)
    
    def select_action(self, features, temperature=1.0):
        """Select action using softmax over model scores."""
        scores = self.model.forward(features)
        # Softmax with temperature
        scores = scores / max(temperature, 0.01)
        scores = scores - scores.max()  # numerical stability
        probs = np.exp(scores) / np.sum(np.exp(scores))
        action = np.random.choice(len(probs), p=probs)
        return action, probs
    
    def store_transition(self, features, action_idx, probs):
        """Store a transition for later update."""
        self.episode_buffer.append({
            "features": features.copy(),
            "action": action_idx,
            "probs": probs.copy(),
        })
    
    def update(self, reward):
        """
        REINFORCE update after episode ends.
        
        For each stored transition:
          ∇J = reward * ∇log(π(a|s))
        
        We compute this numerically (finite differences) since we're using numpy.
        """
        if not self.episode_buffer:
            return 0.0
        
        total_loss = 0.0
        eps = 1e-4
        
        for transition in self.episode_buffer:
            features = transition["features"]
            action = transition["action"]
            
            # Compute gradient via finite differences for each weight
            for layer_idx in range(len(self.model.weights)):
                W = self.model.weights[layer_idx]
                b = self.model.biases[layer_idx]
                
                # Weight gradient (sample a few elements for speed)
                n_samples = min(50, W.size)
                indices = np.random.choice(W.size, n_samples, replace=False)
                
                for idx in indices:
                    i, j = np.unravel_index(idx, W.shape)
                    
                    # +eps
                    W[i, j] += eps
                    scores_plus = self.model.forward(features)
                    log_prob_plus = scores_plus[action] - np.log(np.sum(np.exp(scores_plus - scores_plus.max())))
                    
                    # -eps
                    W[i, j] -= 2 * eps
                    scores_minus = self.model.forward(features)
                    log_prob_minus = scores_minus[action] - np.log(np.sum(np.exp(scores_minus - scores_minus.max())))
                    
                    # restore
                    W[i, j] += eps
                    
                    grad = (log_prob_plus - log_prob_minus) / (2 * eps)
                    W[i, j] += self.lr * reward * grad
                
                # Bias gradient
                for j in range(min(10, len(b))):
                    b[j] += eps
                    scores_plus = self.model.forward(features)
                    log_prob_plus = scores_plus[action] - np.log(np.sum(np.exp(scores_plus - scores_plus.max())))
                    
                    b[j] -= 2 * eps
                    scores_minus = self.model.forward(features)
                    log_prob_minus = scores_minus[action] - np.log(np.sum(np.exp(scores_minus - scores_minus.max())))
                    
                    b[j] += eps
                    
                    grad = (log_prob_plus - log_prob_minus) / (2 * eps)
                    b[j] += self.lr * reward * grad
        
        n = len(self.episode_buffer)
        self.episode_buffer = []
        return n

# ============================================================================
# 6. RL AGENT (uses model for inference)
# ============================================================================

def make_rl_agent(model):
    """Create an agent function that uses the RL model for candidate ranking."""
    
    def rl_agent(obs):
        try:
            state = parse_obs(obs)
            if not state["mine"]:
                return []
            
            candidates = generate_candidates(state)
            if not candidates:
                return []
            
            features = build_feature_matrix(candidates, state)
            scores = model.forward(features)
            
            # Greedy selection: pick best non-conflicting moves
            order = np.argsort(-scores)
            
            moves = []
            used_src = set()
            used_tgt = set()
            
            for idx in order:
                c = candidates[idx]
                if c["src_id"] not in used_src and c["tgt_id"] not in used_tgt:
                    moves.append([c["src_id"], c["angle"], c["ships"]])
                    used_src.add(c["src_id"])
                    used_tgt.add(c["tgt_id"])
            
            return moves
        except Exception:
            return []
    
    return rl_agent

# ============================================================================
# 7. TRAINING LOOP (call from notebook)
# ============================================================================

def train_loop(n_episodes=100, lr=1e-3, weights_path=None, save_path="weights.npz"):
    """
    Main training loop. Call from notebook or command line.
    
    Args:
        n_episodes: Number of episodes to train
        lr: Learning rate
        weights_path: Path to load previous weights (for continued training)
        save_path: Path to save final weights
    """
    try:
        from kaggle_environments import make
    except ImportError:
        print("Install kaggle-environments: pip install 'kaggle-environments>=1.28.0'")
        return
    
    # Initialize model
    model = NumpyMLP()
    if weights_path and os.path.exists(weights_path):
        model.load(weights_path)
        print(f"Resumed from {weights_path}")
    
    trainer = RLTrainer(model, lr=lr)
    
    # Metrics
    rewards_history = []
    
    for ep in range(n_episodes):
        env = make("orbit_wars", debug=False)
        
        # Create agent that records transitions
        episode_data = []
        
        def training_agent(obs):
            try:
                state = parse_obs(obs)
                if not state["mine"]:
                    return []
                
                candidates = generate_candidates(state)
                if not candidates:
                    return []
                
                features = build_feature_matrix(candidates, state)
                action_idx, probs = trainer.select_action(features, temperature=1.0)
                
                trainer.store_transition(features, action_idx, probs)
                
                # Execute selected candidate
                c = candidates[action_idx]
                
                # Also pick other non-conflicting moves greedily
                scores = model.forward(features)
                order = np.argsort(-scores)
                moves = [[c["src_id"], c["angle"], c["ships"]]]
                used_src = {c["src_id"]}
                used_tgt = {c["tgt_id"]}
                
                for idx in order:
                    cc = candidates[idx]
                    if cc["src_id"] not in used_src and cc["tgt_id"] not in used_tgt:
                        moves.append([cc["src_id"], cc["angle"], cc["ships"]])
                        used_src.add(cc["src_id"])
                        used_tgt.add(cc["tgt_id"])
                
                return moves
            except Exception:
                return []
        
        # Play vs random
        env.run([training_agent, "random"])
        
        # Get reward
        final = env.steps[-1]
        my_reward = final[0].reward if final[0].reward else 0
        opp_reward = final[1].reward if final[1].reward else 0
        
        # Shaped reward: win/loss + ship advantage
        if my_reward > opp_reward:
            reward = 1.0 + (my_reward - opp_reward) / 1000.0
        elif my_reward < opp_reward:
            reward = -1.0 + (my_reward - opp_reward) / 1000.0
        else:
            reward = 0.0
        
        # Update weights
        n_transitions = trainer.update(reward)
        rewards_history.append(my_reward)
        
        if (ep + 1) % 10 == 0:
            avg = np.mean(rewards_history[-10:])
            print(f"Episode {ep+1}/{n_episodes} | Reward: {my_reward:.0f} | "
                  f"Avg(10): {avg:.0f} | Transitions: {n_transitions}")
        
        # Save checkpoint every 25 episodes
        if (ep + 1) % 25 == 0:
            model.save(save_path)
    
    # Final save
    model.save(save_path)
    print(f"\nTraining complete. Final avg reward: {np.mean(rewards_history[-20:]):.0f}")
    print(f"Weights saved to: {save_path}")
    return model, rewards_history

# ============================================================================
# 8. COMMAND LINE ENTRY
# ============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Orbit Wars RL Training")
    parser.add_argument("--episodes", type=int, default=100, help="Number of episodes")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--load", type=str, default=None, help="Path to load weights")
    parser.add_argument("--save", type=str, default="weights.npz", help="Path to save weights")
    args = parser.parse_args()
    
    train_loop(
        n_episodes=args.episodes,
        lr=args.lr,
        weights_path=args.load,
        save_path=args.save,
    )
