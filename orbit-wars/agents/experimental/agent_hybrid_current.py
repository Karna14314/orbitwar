# HYPOTHESIS: Implement an 8-Phase Decision Pipeline (Defense -> Comet Evac -> Expansion -> Coordinated Attack...) prioritizing pure heuristic logic.
# DATE: 2024-05-20
# BASED ON: agent_heuristic_current.py and memory guidelines
# CHANGELOG: Refactored logic to follow the rigid 8-Phase decision pipeline outlined in the guidelines.

import math
import sys
import os

# Add the parent directory to the path so we can import _sim
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from _sim import spd, find_angle, obs_to_state, copy_state, is_heading_to

def get_winning_force(src, tgt, state, is_moving):
    angle, ticks = find_angle(src, tgt, src['ships'], state['vel'], state['ips'], state['step'], is_moving)
    if angle is None:
        return None, None
    needed = int(tgt['ships'] + 1 + (tgt['prod'] * ticks if tgt['owner'] >= 0 else 0))
    return needed, angle

def evaluate_threats(state, pid, p):
    incoming_ships = sum(f['ships'] for f in state['fleets'] if f['owner'] != pid and is_heading_to(f, p))
    if incoming_ships > 0:
        closest_dist = float('inf')
        closest_f = None
        for f in state['fleets']:
            if f['owner'] != pid and is_heading_to(f, p):
                d = math.hypot(p['x']-f['x'], p['y']-f['y'])
                if d < closest_dist:
                    closest_dist = d
                    closest_f = f

        if closest_dist <= 85.0:
            threat_eta = closest_dist / max(spd(closest_f['ships']), 0.1)
            garrison_at_impact = p['ships'] + p['prod'] * threat_eta
            deficit = incoming_ships - garrison_at_impact
            return deficit if deficit > 0 else 0
    return 0

def phase_1_defense(state, pid, mine, used_src):
    moves = []
    threatened = []
    for p in mine:
        deficit = evaluate_threats(state, pid, p)
        if deficit > 0:
            threatened.append((p, deficit))

    for p, deficit in threatened:
        needed = int(deficit + 3)
        helpers = sorted([m for m in mine if m['id'] != p['id'] and m['ships'] > 10], key=lambda m: math.hypot(m['x'] - p['x'], m['y'] - p['y']))
        for h in helpers:
            if h['id'] in used_src: continue

            # Helper can't be threatened itself
            if evaluate_threats(state, pid, h) > 0: continue

            send = min(int(h['ships'] * 0.5), needed)
            if send >= 3:
                angle, _ = find_angle(h, p, send, state['vel'], state['ips'], state['step'], p['id'] in state.get('moving', []))
                if angle is not None:
                    moves.append([h['id'], angle, send])
                    used_src.add(h['id'])
                    needed -= send
                    if needed <= 0: break
    return moves

def phase_2_comet_evac(state, pid, mine, used_src):
    moves = []
    # Simplified evac: if on comet and high amount of ships, send to a safe planet.
    # Often comets get close to sun or boundaries. We just move excess to nearest safe planet.
    comets = [p for p in mine if p['id'] in state.get('moving', [])]
    safe_planets = [p for p in mine if p['id'] not in state.get('moving', [])]

    for c in comets:
        if c['id'] in used_src: continue
        if c['ships'] > 50 and safe_planets: # high threshold to trigger evac
            best_safe = min(safe_planets, key=lambda p: math.hypot(c['x']-p['x'], c['y']-p['y']))
            send = int(c['ships'] - 10)
            if send >= 3:
                angle, _ = find_angle(c, best_safe, send, state['vel'], state['ips'], state['step'], False)
                if angle is not None:
                    moves.append([c['id'], angle, send])
                    used_src.add(c['id'])
    return moves

def phase_3_expansion(state, pid, mine, targets, used_src, pending_targets):
    moves = []
    neutrals = [t for t in targets if t['owner'] == -1]
    mine_sorted = sorted(mine, key=lambda p: p['ships'], reverse=True)

    for src in mine_sorted:
        if src['id'] in used_src: continue
        if src['ships'] < 5: continue
        if evaluate_threats(state, pid, src) > 0: continue

        best_score = -float('inf')
        best_tgt = None
        best_angle = None
        best_needed = 0

        for tgt in neutrals:
            if tgt['id'] in pending_targets: continue

            is_moving = tgt['id'] in state.get('moving', [])
            needed, angle = get_winning_force(src, tgt, state, is_moving)
            if angle is None: continue

            if src['ships'] >= needed + 3:
                dist = math.hypot(src['x']-tgt['x'], src['y']-tgt['y'])
                eta = dist / spd(src['ships'])

                score = tgt['prod'] / (1.0 + 0.05 * eta) - needed * 0.8

                if score > best_score:
                    best_score = score
                    best_tgt = tgt
                    best_angle = angle
                    best_needed = needed

        if best_tgt:
            send = min(int(src['ships'] - 1), best_needed + 3)
            moves.append([src['id'], best_angle, send])
            used_src.add(src['id'])
            pending_targets.add(best_tgt['id'])

    return moves

def phase_4_coordinated_attack(state, pid, mine, targets, used_src, pending_targets):
    moves = []
    enemies = [t for t in targets if t['owner'] >= 0]
    if not enemies: return moves

    best_enemy = max(enemies, key=lambda p: p['prod'])

    for src in mine:
        if src['id'] in used_src: continue
        if src['ships'] < 5: continue
        if evaluate_threats(state, pid, src) > 0: continue

        is_moving = best_enemy['id'] in state.get('moving', [])
        needed, angle = get_winning_force(src, best_enemy, state, is_moving)

        if angle is not None and src['ships'] >= needed + 3:
             send = min(int(src['ships'] - 1), needed + 3)
             moves.append([src['id'], angle, send])
             used_src.add(src['id'])
             pending_targets.add(best_enemy['id'])
             break # One attack per turn on the coordinated target

    return moves

def phase_5_comet_capture(state, pid, mine, targets, used_src, pending_targets):
    moves = []
    enemy_comets = [t for t in targets if t['id'] in state.get('moving', []) and t['owner'] != -1]

    mine_sorted = sorted(mine, key=lambda p: p['ships'], reverse=True)
    for src in mine_sorted:
        if src['id'] in used_src: continue
        if src['ships'] < 5: continue
        if evaluate_threats(state, pid, src) > 0: continue

        for tgt in enemy_comets:
            if tgt['id'] in pending_targets: continue

            needed, angle = get_winning_force(src, tgt, state, True)
            if angle is not None and src['ships'] >= needed + 3:
                send = min(int(src['ships'] - 1), needed + 3)
                moves.append([src['id'], angle, send])
                used_src.add(src['id'])
                pending_targets.add(tgt['id'])
                break
    return moves

def phase_6_consolidation(state, pid, mine, used_src):
    # Move ships from low prod inner planets to high prod/frontline planets if safe
    moves = []
    if len(mine) < 2: return moves

    safe_mine = [p for p in mine if evaluate_threats(state, pid, p) == 0 and p['id'] not in used_src]

    for p in safe_mine:
        if p['prod'] < 3 and p['ships'] > 30:
            frontline = max(mine, key=lambda m: m['prod'])
            if frontline['id'] != p['id']:
                angle, _ = find_angle(p, frontline, int(p['ships'] * 0.8), state['vel'], state['ips'], state['step'], frontline['id'] in state.get('moving', []))
                if angle is not None:
                    send = int(p['ships'] * 0.8)
                    moves.append([p['id'], angle, send])
                    used_src.add(p['id'])
    return moves

def phase_7_idle_deployment(state, pid, mine, targets, used_src, pending_targets):
    # Fallback standard attack for any remaining strong forces
    moves = []
    mine_sorted = sorted(mine, key=lambda p: p['ships'], reverse=True)

    for src in mine_sorted:
        if src['id'] in used_src: continue
        if src['ships'] < 10: continue
        if evaluate_threats(state, pid, src) > 0: continue

        best_score = -float('inf')
        best_tgt = None
        best_angle = None
        best_needed = 0

        for tgt in targets:
            if tgt['id'] in pending_targets: continue

            is_moving = tgt['id'] in state.get('moving', [])
            needed, angle = get_winning_force(src, tgt, state, is_moving)
            if angle is None: continue

            if src['ships'] >= needed + 3:
                dist = math.hypot(src['x']-tgt['x'], src['y']-tgt['y'])
                eta = dist / spd(src['ships'])

                score = tgt['prod'] / (1.0 + 0.05 * eta) - needed * 0.8

                if score > best_score:
                    best_score = score
                    best_tgt = tgt
                    best_angle = angle
                    best_needed = needed

        if best_tgt:
            send = min(int(src['ships'] - 1), best_needed + 3)
            moves.append([src['id'], best_angle, send])
            used_src.add(src['id'])
            pending_targets.add(best_tgt['id'])

    return moves

def phase_8_proactive_reinforcement(state, pid, mine, used_src):
    # Support planets under potential future threat
    moves = []
    frontlines = sorted(mine, key=lambda p: p['x']) # Example placeholder for frontline metric
    backlines = [p for p in mine if p['ships'] > 50 and p['id'] not in used_src]

    for src in backlines:
        if evaluate_threats(state, pid, src) > 0: continue
        for tgt in frontlines:
            if src['id'] != tgt['id']:
                angle, _ = find_angle(src, tgt, int(src['ships'] * 0.5), state['vel'], state['ips'], state['step'], tgt['id'] in state.get('moving', []))
                if angle is not None:
                    send = int(src['ships'] * 0.5)
                    moves.append([src['id'], angle, send])
                    used_src.add(src['id'])
                    break
    return moves

def heuristic_moves(state, pid):
    mine = [p for p in state['planets'] if p['owner'] == pid]
    targets = [p for p in state['planets'] if p['owner'] != pid]

    if not mine:
        return []

    moves = []
    used_src = set()
    pending_targets = set()

    moves.extend(phase_1_defense(state, pid, mine, used_src))
    moves.extend(phase_2_comet_evac(state, pid, mine, used_src))
    moves.extend(phase_3_expansion(state, pid, mine, targets, used_src, pending_targets))
    moves.extend(phase_4_coordinated_attack(state, pid, mine, targets, used_src, pending_targets))
    moves.extend(phase_5_comet_capture(state, pid, mine, targets, used_src, pending_targets))
    moves.extend(phase_6_consolidation(state, pid, mine, used_src))
    moves.extend(phase_7_idle_deployment(state, pid, mine, targets, used_src, pending_targets))
    moves.extend(phase_8_proactive_reinforcement(state, pid, mine, used_src))

    return moves

def agent(obs):
    try:
        state = obs_to_state(obs)
        pid = obs.get("player", 0)
        return heuristic_moves(state, pid)
    except Exception as e:
        print(f"Agent Hybrid Error: {e}")
        return []
