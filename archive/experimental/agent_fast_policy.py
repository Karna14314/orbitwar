import math
import time
import sys
import os
import random

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from _sim import spd, find_angle, obs_to_state, copy_state, is_heading_to, simulate_tick
from experimental.agent_heuristic_current import heuristic_moves

def fast_policy(state, pid):
    """Greedy nearest-target. No angle search loop. Used only inside rollouts."""
    mine = [p for p in state['planets'] if p['owner'] == pid]
    targets = [p for p in state['planets'] if p['owner'] != pid]
    if not mine or not targets: return []
    moves, used_src, used_tgt = [], set(), set()
    for src in sorted(mine, key=lambda p: p['ships'], reverse=True):
        if src['id'] in used_src or src['ships'] < 5: continue
        reachable = [t for t in targets if t['id'] not in used_tgt]
        if not reachable: break
        tgt = min(reachable, key=lambda t: math.hypot(src['x']-t['x'], src['y']-t['y']))
        needed = int(tgt['ships']+1+(tgt['prod']*10 if tgt['owner']>=0 else 0))
        send = min(int(src['ships']-1), needed+3)
        if send < 3: continue
        angle = math.atan2(tgt['y']-src['y'], tgt['x']-src['x'])  # direct, no orbit correction
        moves.append([src['id'], angle, send])
        used_src.add(src['id'])
        used_tgt.add(tgt['id'])
    return moves

def get_winning_force(src, tgt, state):
    angle, ticks = find_angle(src, tgt, src['ships'], state['vel'], state['ips'], state['step'], tgt['id'] in state['moving'])
    if angle is None:
        return 9999
    needed = int(tgt['ships'] + 1 + (tgt['prod'] * ticks if tgt['owner'] >= 0 else 0))
    return needed

def get_candidate_moves(state, pid):
    candidates = []

    mine = [p for p in state['planets'] if p['owner'] == pid]
    targets = [p for p in state['planets'] if p['owner'] != pid]
    enemy = [p for p in state['planets'] if p['owner'] not in (-1, pid)]

    # 1. Base Heuristic
    base_moves = heuristic_moves(state, pid)
    if base_moves: candidates.append(base_moves)

    # 2. Coordinated Attack on highest production enemy
    if enemy and mine:
        best_en = max(enemy, key=lambda p: p['prod'])
        attack_moves = []
        exhausted = set()

        for src in mine:
            if src['id'] in exhausted: continue
            needed = get_winning_force(src, best_en, state)
            if src['ships'] >= needed + 3:
                angle, ticks = find_angle(src, best_en, src['ships'], state['vel'], state['ips'], state['step'], best_en['id'] in state['moving'])
                if angle is not None:
                    attack_moves.append([src['id'], angle, min(int(src['ships']-1), needed+3)])
                    exhausted.add(src['id'])
                    break
        if attack_moves: candidates.append(attack_moves)

    # 3. Econ expansion
    neutrals = [p for p in state['planets'] if p['owner'] == -1]
    if neutrals and mine:
        best_neu = max(neutrals, key=lambda p: p['prod'])
        econ_moves = []
        exhausted = set()
        for src in mine:
            if src['id'] in exhausted: continue
            needed = get_winning_force(src, best_neu, state)
            if src['ships'] >= needed + 3:
                angle, ticks = find_angle(src, best_neu, src['ships'], state['vel'], state['ips'], state['step'], best_neu['id'] in state['moving'])
                if angle is not None:
                    econ_moves.append([src['id'], angle, min(int(src['ships']-1), needed+3)])
                    exhausted.add(src['id'])
                    break
        if econ_moves: candidates.append(econ_moves)

    # 4. Defend
    def_moves = []
    exhausted = set()
    threatened = []
    for p in mine:
        incoming = sum(f['ships'] for f in state['fleets'] if f['owner'] != pid and is_heading_to(f, p))
        if incoming > p['ships']:
            threatened.append((p, incoming - p['ships']))

    for p, deficit in threatened:
        needed = int(deficit + 3)
        helpers = sorted([m for m in mine if m['id'] != p['id'] and m['ships'] > 10], key=lambda m: math.hypot(m['x'] - p['x'], m['y'] - p['y']))
        for h in helpers:
            if h['id'] in exhausted:
                continue
            send = min(int(h['ships'] * 0.5), needed)
            if send >= 3:
                angle, _ = find_angle(h, p, send, state['vel'], state['ips'], state['step'], p['id'] in state['moving'])
                if angle is not None:
                    def_moves.append([h['id'], angle, send])
                    exhausted.add(h['id'])
                    break
    if def_moves: candidates.append(def_moves)

    candidates.append([]) # Pass option

    # Filter unique
    unique = []
    for c in candidates:
        if c not in unique:
            unique.append(c)
    return unique

def evaluate_state(state, pid):
    mine = [p for p in state['planets'] if p['owner'] == pid]
    enemy = [p for p in state['planets'] if p['owner'] not in (pid, -1)]

    if not mine: return -1.0
    if not enemy: return 1.0

    my_prod = sum(p['prod'] for p in mine)
    en_prod = sum(p['prod'] for p in enemy)
    economy_term = (my_prod - en_prod) / max(1.0, my_prod + en_prod)

    my_garrison = sum(p['ships'] for p in mine)
    en_garrison = sum(p['ships'] for p in enemy)

    my_transit = sum(f['ships'] for f in state['fleets'] if f['owner'] == pid)
    en_transit = sum(f['ships'] for f in state['fleets'] if f['owner'] not in (pid, -1))

    my_power = my_garrison + my_transit
    en_power = en_garrison + en_transit
    tactical_term = (my_power - en_power) / max(1.0, my_power + en_power)

    my_center = sum((100.0 - math.hypot(p['x'] - 50, p['y'] - 50)) * p['prod'] for p in mine)
    en_center = sum((100.0 - math.hypot(p['x'] - 50, p['y'] - 50)) * p['prod'] for p in enemy)
    map_control_term = (my_center - en_center) / max(1.0, my_center + en_center)

    my_vulnerability = 0.0
    for p in mine:
        incoming_threat = sum(f['ships'] for f in state['fleets'] if f['owner'] not in (pid, -1) and is_heading_to(f, p))
        if incoming_threat > p['ships'] + p['prod'] * 15.0:
            my_vulnerability += (incoming_threat - p['ships'])

    en_vulnerability = 0.0
    for p in enemy:
        incoming_threat = sum(f['ships'] for f in state['fleets'] if f['owner'] == pid and is_heading_to(f, p))
        if incoming_threat > p['ships'] + p['prod'] * 15.0:
            en_vulnerability += (incoming_threat - p['ships'])

    safety_term = (en_vulnerability - my_vulnerability) / max(1.0, my_power + en_power)

    planet_ratio = (len(mine) - len(enemy)) / max(1, len(mine) + len(enemy))

    return 0.35 * economy_term + 0.25 * tactical_term + 0.15 * map_control_term + 0.15 * safety_term + 0.10 * planet_ratio

class MCTSNode:
    def __init__(self, state, parent=None, move=None):
        self.state = state
        self.parent = parent
        self.move = move
        self.children = []
        self.wins = 0
        self.visits = 0
        self.untried = None

def ucb1(node, parent_visits, c=1.4):
    if node.visits == 0:
        return float('inf')
    return node.wins / node.visits + c * math.sqrt(math.log(parent_visits) / node.visits)

def is_terminal(state):
    if state['step'] >= 500:
        return True
    owners = {p['owner'] for p in state['planets'] if p['owner'] >= 0}
    return len(owners) <= 1

def select_node(root, pid, c=1.4):
    node = root
    while not is_terminal(node.state) and node.untried is not None and len(node.untried) == 0:
        if not node.children:
            break
        parent_visits = node.visits
        node = max(node.children, key=lambda n: ucb1(n, parent_visits, c))
    return node

def get_opponent_move(state, opp_id):
    # Quick random policy for opponents during tree expansion
    return fast_policy(state, opp_id)

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
        all_moves[opp_id] = get_opponent_move(next_state, opp_id)

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
            all_moves[owner] = fast_policy(state, owner)

        simulate_tick(state, all_moves)

    return evaluate_state(state, pid)

def backpropagate(node, reward):
    curr = node
    while curr is not None:
        curr.visits += 1
        curr.wins += reward
        curr = curr.parent

def mcts_search(obs, time_limit=0.075, c=1.4, ticks=20):
    state = obs_to_state(obs)
    pid = obs.get("player", 0)
    root = MCTSNode(state)
    root.untried = get_candidate_moves(state, pid)

    deadline = time.time() + time_limit

    while time.time() < deadline:
        node = select_node(root, pid, c)
        if node.visits > 0 and not is_terminal(node.state):
            node = expand_node(node, pid)
        reward = rollout(node, pid, ticks)
        backpropagate(node, reward)

    if not root.children:
        return heuristic_moves(state, pid)

    best = max(root.children, key=lambda n: n.visits)
    return best.move if best.move is not None else heuristic_moves(state, pid)

def agent(obs):
    try:
        return mcts_search(obs, time_limit=0.075, c=1.4, ticks=20)
    except Exception as e:
        print(f"Agent A Error: {e}")
        try:
            return heuristic_moves(obs_to_state(obs), obs.get("player", 0))
        except:
            return []
