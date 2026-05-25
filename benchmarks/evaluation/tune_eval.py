"""
Orbit Wars Phase 3 — Evaluation Weights Self-Play Tuning Harness
================================================================
This script automates self-play head-to-head match simulations to optimize the
evaluation function weights for the V5 MCTS agent.

Weights to tune:
  0. prod_horizon      - Current: 25.0 (Horizon multiplier for production capacity)
  1. planet_bonus      - Current: 8.0  (Multiplier for planet ownership)
  2. capture_cost_mult - Current: 0.8  (Cost multiplier for ships spent)
  3. enemy_deny        - Current: 60.0 (Reward multiplier to deny enemy production)
  4. neutral_bonus     - Current: 15.0 (Reward bonus for neutral capture)
  5. comet_penalty     - Current: 40.0 (Penalty for capturing comets)

Usage:
  python tune_eval.py
"""
import math
import time
import random
import copy
from kaggle_environments import make

# ==============================================================================
# CONF-CONFIGURABLE AGENT FACTORY
# ==============================================================================

def make_tuned_agent(weights):
    """
    Returns an agent function configured with the specified weights array:
    weights = [prod_horizon, planet_bonus, capture_cost, enemy_deny, neutral, comet]
    """
    # Unpack weights
    w_prod_horizon      = float(weights[0])
    w_planet_bonus      = float(weights[1])
    w_capture_cost_mult = float(weights[2])
    w_enemy_deny        = float(weights[3])
    w_neutral_bonus     = float(weights[4])
    w_comet_penalty     = float(weights[5])

    # Inner physics and search functions using these configured weights
    def spd(n):
        if n <= 1:
            return 1.0
        return 1.0 + 5.0 * (math.log(n) / math.log(1000)) ** 1.5

    def segment_intersects_circle(x1, y1, x2, y2, cx, cy, r):
        vx, vy = x2 - x1, y2 - y1
        len2 = vx*vx + vy*vy
        if len2 == 0:
            return (x1-cx)**2 + (y1-cy)**2 <= r*r
        t = max(0.0, min(1.0, ((cx-x1)*vx + (cy-y1)*vy) / len2))
        nearest_x, nearest_y = x1 + t*vx, y1 + t*vy
        return (nearest_x-cx)**2 + (nearest_y-cy)**2 <= r*r

    def hits_sun(x1, y1, x2, y2):
        return segment_intersects_circle(x1, y1, x2, y2, 50.0, 50.0, 10.0)

    def future_pos_state(pid, ips, vel, tick):
        ip = ips.get(pid)
        if not ip:
            return None, None
        r = math.hypot(ip['x'] - 50, ip['y'] - 50)
        if r < 1.0:
            return ip['x'], ip['y']
        a0 = math.atan2(ip['y'] - 50, ip['x'] - 50)
        a = a0 + vel * tick
        return 50 + r * math.cos(a), 50 + r * math.sin(a)

    def find_angle_state(src, tgt, ships, vel, ips, is_moving):
        speed = spd(ships)
        for tick in range(1, 80):
            if is_moving:
                tx, ty = future_pos_state(tgt['id'], ips, vel, tick)
                if tx is None:
                    tx, ty = tgt['x'], tgt['y']
            else:
                tx, ty = tgt['x'], tgt['y']
            dist = math.hypot(src['x'] - tx, src['y'] - ty)
            if speed * tick >= dist - tgt['r']:
                if not hits_sun(src['x'], src['y'], tx, ty):
                    return math.atan2(ty - src['y'], tx - src['x']), tick
                else:
                    return None, None
        return None, None

    def score_target_state(src, tgt, eta, is_comet, step, needed):
        ticks_remaining = max(1, 1000 - step - eta)
        ev = tgt['prod'] * ticks_remaining
        capture_cost = needed
        score = ev - capture_cost * w_capture_cost_mult
        if tgt['owner'] >= 0:
            score += tgt['prod'] * w_enemy_deny
        if tgt['owner'] == -1:
            score += w_neutral_bonus
        if is_comet:
            score -= w_comet_penalty
        return score

    def heuristic_moves(state, pid, exclude_targets=None):
        if exclude_targets is None:
            exclude_targets = set()
            
        planets = state['planets']
        fleets = state['fleets']
        ips = state['ips']
        vel = state['angular_velocity']
        comets = state['comet_planet_ids']
        moving = state['moving']
        step = state['step']
        
        mine = [p for p in planets if p['owner'] == pid]
        targets = [p for p in planets if p['owner'] != pid and p['id'] not in exclude_targets]
        
        if not mine:
            return []
            
        pending_targets = set()
        for f in fleets:
            if f['owner'] == pid:
                best_match, best_diff = None, 0.35
                for tgt in targets:
                    dx, dy = tgt['x'] - f['x'], tgt['y'] - f['y']
                    if math.hypot(dx, dy) < 1.0:
                        continue
                    a_to_tgt = math.atan2(dy, dx)
                    diff = abs(math.atan2(math.sin(f['angle'] - a_to_tgt), math.cos(f['angle'] - a_to_tgt)))
                    if diff < best_diff:
                        best_diff, best_match = diff, tgt['id']
                if best_match is not None:
                    pending_targets.add(best_match)

        moves = []
        exhausted = set()
        targeted  = set()
        
        for p in mine:
            incoming_fleets = []
            for f in fleets:
                if f['owner'] == pid or f['owner'] < 0:
                    continue
                dx, dy = p['x'] - f['x'], p['y'] - f['y']
                dist_fp = math.hypot(dx, dy)
                if dist_fp < 1.0 or dist_fp > 50:
                    continue
                angle_to_p = math.atan2(dy, dx)
                angle_diff = abs(math.atan2(math.sin(f['angle'] - angle_to_p), math.cos(f['angle'] - angle_to_p)))
                if angle_diff < 0.26:
                    incoming_fleets.append((f, dist_fp))
                    
            if not incoming_fleets:
                continue
                
            incoming_ships = sum(f['ships'] for f, _ in incoming_fleets)
            closest_f, closest_dist = min(incoming_fleets, key=lambda x: x[1])
            threat_eta = closest_dist / max(spd(closest_f['ships']), 0.1)
            
            garrison_at_impact = p['ships'] + p['prod'] * threat_eta
            if garrison_at_impact >= incoming_ships + 3:
                continue
                
            deficit = incoming_ships - garrison_at_impact + 5
            if deficit < 3:
                continue
            
            helpers = sorted(
                [m for m in mine if m['id'] != p['id'] and m['id'] not in exhausted and m['ships'] > 10],
                key=lambda m: math.hypot(m['x'] - p['x'], m['y'] - p['y'])
            )
            for h in helpers:
                send = min(int(h['ships'] * 0.5), int(deficit))
                if send < 3:
                    continue
                angle, eta = find_angle_state(h, p, send, vel, ips, p['id'] in moving)
                if angle is not None:
                    moves.append([h['id'], angle, send])
                    exhausted.add(h['id'])
                    break
        
        mine_sorted = sorted(mine, key=lambda p: p['ships'], reverse=True)
        attack_options = []
        for src in mine_sorted:
            if src['id'] in exhausted or src['ships'] < 5:
                continue
            for tgt in targets:
                if tgt['id'] in pending_targets:
                    continue
                is_moving_tgt = tgt['id'] in moving
                is_comet = tgt['id'] in comets
                
                est_dist = math.hypot(src['x'] - tgt['x'], src['y'] - tgt['y'])
                est_speed = spd(max(5, int(src['ships'] * 0.5)))
                est_eta = est_dist / max(est_speed, 0.1)
                
                needed = tgt['ships'] + 1
                if tgt['owner'] >= 0:
                    needed += tgt['prod'] * est_eta
                needed = int(math.ceil(needed))
                
                if len(mine) <= 2:
                    max_send = int(src['ships'] - 1)
                elif len(mine) <= 4:
                    max_send = int(src['ships'] * 0.8)
                else:
                    max_send = int(src['ships'] * 0.65)
                
                if max_send < 5:
                    continue
                
                if needed > max_send:
                    continue
                    
                send = max_send
                
                angle, eta = find_angle_state(src, tgt, send, vel, ips, is_moving_tgt)
                if angle is None:
                    continue
                
                sc = score_target_state(src, tgt, eta, is_comet, step, needed)
                attack_options.append((sc, src['id'], tgt['id'], angle, send))
        
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

    def obs_to_state(obs):
        planets = obs.get("planets", [])
        fleets = obs.get("fleets", [])
        initial_planets = obs.get("initial_planets", [])
        
        ips = {}
        for p in initial_planets:
            ips[p[0]] = {
                'id': int(p[0]), 'owner': int(p[1]), 'x': float(p[2]), 'y': float(p[3]),
                'r': float(p[4]), 'ships': float(p[5]), 'prod': float(p[6])
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
                'id': int(p[0]), 'owner': int(p[1]), 'x': float(p[2]), 'y': float(p[3]),
                'r': float(p[4]), 'ships': float(p[5]), 'prod': float(p[6])
            })
            
        state_fleets = []
        next_fleet_id = 0
        for f in fleets:
            state_fleets.append({
                'id': int(f[0]), 'owner': int(f[1]), 'x': float(f[2]), 'y': float(f[3]),
                'angle': float(f[4]), 'from_planet_id': int(f[5]), 'ships': float(f[6])
            })
            if int(f[0]) >= next_fleet_id:
                next_fleet_id = int(f[0]) + 1
                
        return {
            'planets': state_planets, 'fleets': state_fleets,
            'angular_velocity': obs.get("angular_velocity", 0.0), 'ips': ips,
            'step': obs.get("step", 0), 'comet_planet_ids': comets,
            'moving': moving, 'next_fleet_id': next_fleet_id
        }

    def copy_state(state):
        return {
            'planets': [{'id': p['id'], 'owner': p['owner'], 'x': p['x'], 'y': p['y'], 'r': p['r'], 'ships': p['ships'], 'prod': p['prod']} for p in state['planets']],
            'fleets': [{'id': f['id'], 'owner': f['owner'], 'x': f['x'], 'y': f['y'], 'angle': f['angle'], 'ships': f['ships'], 'from_planet_id': f['from_planet_id']} for f in state['fleets']],
            'angular_velocity': state['angular_velocity'], 'ips': state['ips'],
            'step': state['step'], 'comet_planet_ids': state['comet_planet_ids'],
            'moving': state['moving'], 'next_fleet_id': state['next_fleet_id']
        }

    def simulate_tick(state, moves):
        # 1. Fleet launch
        for pid, p_moves in moves.items():
            for src_id, angle, ships in p_moves:
                src = next((p for p in state['planets'] if p['id'] == src_id), None)
                if src and src['owner'] == pid and src['ships'] >= ships:
                    src['ships'] -= ships
                    spawn_dist = src['r'] + 0.1
                    fleet = {
                        'id': state['next_fleet_id'], 'owner': pid,
                        'x': src['x'] + spawn_dist * math.cos(angle), 'y': src['y'] + spawn_dist * math.sin(angle),
                        'angle': angle, 'ships': ships, 'from_planet_id': src_id
                    }
                    state['next_fleet_id'] += 1
                    state['fleets'].append(fleet)

        # 2. Production
        for p in state['planets']:
            if p['owner'] >= 0:
                p['ships'] += p['prod']

        # 3. Fleet movement & Collision
        active_fleets = []
        collisions = {}
        for f in state['fleets']:
            speed = spd(f['ships'])
            dx = speed * math.cos(f['angle'])
            dy = speed * math.sin(f['angle'])
            new_x = f['x'] + dx
            new_y = f['y'] + dy
            
            if hits_sun(f['x'], f['y'], new_x, new_y):
                continue
            if new_x < 0 or new_x > 100 or new_y < 0 or new_y > 100:
                continue
                
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

        # 4. Rotation
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

        # 5. Combat
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
        planets = state['planets']
        targets = sorted([p for p in planets if p['owner'] != pid], key=lambda x: x['prod'], reverse=True)
        candidates = []
        
        moves_0 = heuristic_moves(state, pid)
        candidates.append(moves_0)
        
        for k in range(1, 4):
            if len(targets) >= k:
                excluded = {t['id'] for t in targets[:k]}
                moves_k = heuristic_moves(state, pid, exclude_targets=excluded)
                if moves_k not in candidates:
                    candidates.append(moves_k)
                    
        all_target_ids = {t['id'] for t in targets}
        moves_def = heuristic_moves(state, pid, exclude_targets=all_target_ids)
        if moves_def not in candidates:
            candidates.append(moves_def)
            
        if [] not in candidates:
            candidates.append([])
        return candidates

    def evaluate_state(state, pid):
        mine = [p for p in state['planets'] if p['owner'] == pid]
        enemy = [p for p in state['planets'] if p['owner'] not in (pid, -1)]
        my_fleet_ships = sum(f['ships'] for f in state['fleets'] if f['owner'] == pid)
        en_fleet_ships = sum(f['ships'] for f in state['fleets'] if f['owner'] not in (pid, -1))
        
        my_pow = sum(p['ships'] + p['prod'] * w_prod_horizon for p in mine) + my_fleet_ships
        en_pow = sum(p['ships'] + p['prod'] * w_prod_horizon for p in enemy) + en_fleet_ships
        
        total = max(1.0, my_pow + en_pow)
        planet_bonus = len(mine) * w_planet_bonus
        return (my_pow - en_pow) / total + planet_bonus / 100.0

    def ucb1(node, parent_visits):
        if node.visits == 0:
            return float('inf')
        return node.wins / node.visits + 1.4 * math.sqrt(math.log(parent_visits) / node.visits)

    def select_node(root, pid):
        node = root
        while not is_terminal(node.state) and node.untried is not None and len(node.untried) == 0:
            if not node.children:
                break
            parent_visits = node.visits
            node = max(node.children, key=lambda n: ucb1(n, parent_visits))
        return node

    def expand_node(node, pid):
        if node.untried is None:
            node.untried = get_candidate_moves(node.state, pid)
        if not node.untried:
            return node
            
        move = node.untried.pop()
        next_state = copy_state(node.state)
        
        all_moves = {pid: move}
        opponents = {p['owner'] for p in next_state['planets'] if p['owner'] >= 0 and p['owner'] != pid}
        for opp_id in opponents:
            all_moves[opp_id] = heuristic_moves(next_state, opp_id)
            
        simulate_tick(next_state, all_moves)
        child = MCTSNode(next_state, parent=node, move=move)
        node.children.append(child)
        return child

    def rollout(node, pid, ticks=20):
        state = copy_state(node.state)
        for _ in range(ticks):
            if is_terminal(state):
                break
            all_moves = {}
            owners = {p['owner'] for p in state['planets'] if p['owner'] >= 0}
            for owner in owners:
                all_moves[owner] = heuristic_moves(state, owner)
            simulate_tick(state, all_moves)
        return evaluate_state(state, pid)

    def backpropagate(node, reward):
        curr = node
        while curr is not None:
            curr.visits += 1
            curr.wins += reward
            curr = curr.parent

    def is_terminal(state):
        if state['step'] >= 500:
            return True
        owners = {p['owner'] for p in state['planets'] if p['owner'] >= 0}
        return len(owners) <= 1

    def mcts_search(obs, time_limit=0.082):
        state = obs_to_state(obs)
        pid = obs.get("player", 0)
        root = MCTSNode(state)
        root.untried = get_candidate_moves(state, pid)
        
        deadline = time.time() + time_limit
        while time.time() < deadline:
            node = select_node(root, pid)
            if node.visits > 0 and not is_terminal(node.state):
                node = expand_node(node, pid)
            reward = rollout(node, pid, ticks=20)
            backpropagate(node, reward)
            
        if not root.children:
            return heuristic_moves(state, pid)
        best = max(root.children, key=lambda n: n.visits)
        return best.move if best.move is not None else heuristic_moves(state, pid)

    def agent(obs):
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
# SELF-PLAY TUNING LOOP
# ==============================================================================

def run_self_play_battle(candidate_weights, baseline_weights, n_games=5):
    """
    Run N head-to-head games in orbit_wars. Returns (candidate_wins, baseline_wins).
    """
    candidate_wins = 0
    baseline_wins = 0
    
    agent_cand = make_tuned_agent(candidate_weights)
    agent_base = make_tuned_agent(baseline_weights)
    
    for game_idx in range(n_games):
        env = make("orbit_wars", debug=False)
        
        # Diagonally alternate positions to ensure mirror fairness
        if game_idx % 2 == 0:
            env.run([agent_cand, agent_base])
            reward_cand = env.steps[-1][0].reward
            reward_base = env.steps[-1][1].reward
        else:
            env.run([agent_base, agent_cand])
            reward_base = env.steps[-1][0].reward
            reward_cand = env.steps[-1][1].reward
            
        if reward_cand > reward_base:
            candidate_wins += 1
        elif reward_base > reward_cand:
            baseline_wins += 1
            
    return candidate_wins, baseline_wins

def perturb(weights, scale=0.15):
    """Perturb the current best weights dynamically."""
    new_w = []
    # Index 2 (capture_cost_mult) is bounded [0.1, 2.0]
    # Other indexes are positive rewards/penalties
    for idx, val in enumerate(weights):
        noise = random.normalvariate(0.0, scale) * val
        perturbed = val + noise
        # Apply boundary rules
        if idx == 2:
            perturbed = max(0.1, min(perturbed, 2.0))
        else:
            perturbed = max(0.0, perturbed)
        new_w.append(round(perturbed, 3))
    return new_w

def main():
    print("================================================================")
    print("Starting Orbit Wars Phase 3 Evaluation Weight Self-Play Tuning...")
    print("================================================================")
    
    # Starting baseline weights
    # [prod_horizon, planet_bonus, capture_cost_mult, enemy_deny, neutral_bonus, comet_penalty]
    best_weights = [25.0, 8.0, 0.8, 60.0, 15.0, 40.0]
    print(f"Initial Baseline: {best_weights}\n")
    
    n_trials = 25
    games_per_trial = 4  # Head-to-head simulations per perturbation
    
    for trial in range(1, n_trials + 1):
        print(f"--- Trial {trial}/{n_trials} ---")
        candidate = perturb(best_weights)
        print(f"Candidate: {candidate}")
        
        try:
            cand_wins, base_wins = run_self_play_battle(candidate, best_weights, n_games=games_per_trial)
            print(f"Result: Candidate Wins = {cand_wins} | Baseline Wins = {base_wins}")
            
            # If candidate beats baseline decisively, update baseline
            if cand_wins > base_wins:
                print(f"🏆 NEW BEST WEIGHTS FOUND: {candidate} (decisive win!)")
                best_weights = candidate
            else:
                print(f"❌ Candidate failed to outperform baseline.")
        except Exception as e:
            print(f"⚠️ Simulation error during trial {trial}: {e}")
            
        print(f"Current Best Weights: {best_weights}\n")
        
    print("================================================================")
    print("Tuning Completed!")
    print(f"Optimal Evaluation Weights: {best_weights}")
    print("================================================================")
    print("\nTo use these weights, simply update their values in submission.py:")
    print("  - score_target_state: update capture_cost_mult, enemy_deny, neutral_bonus, comet_penalty")
    print("  - evaluate_state: update prod_horizon, planet_bonus")

if __name__ == "__main__":
    main()
