# HYPOTHESIS: Target coincidentally moving posts near current trajectory. Prioritizes moving planets (comets) that are closer.
# DATE: 2024-05-20
# BASED ON: agent_heuristic_current.py
# CHANGELOG: Modifies scoring to reward attacks on comets (moving planets).

import math
import sys
import os

# Add the parent directory to the path so we can import _sim
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from _sim import spd, find_angle, obs_to_state, copy_state, is_heading_to

def heuristic_moves(state, pid, exclude_targets=None):
    """
    Intercept heuristic. Gives priority to capturing comets (moving planets).
    """
    if exclude_targets is None:
        exclude_targets = set()

    mine = [p for p in state['planets'] if p['owner'] == pid]
    targets = [p for p in state['planets'] if p['owner'] != pid and p['id'] not in exclude_targets]

    if not mine or not targets:
        return []

    moves = []
    used_src = set()
    pending_targets = set()

    # Sort mine by ships (largest first)
    mine_sorted = sorted(mine, key=lambda p: p['ships'], reverse=True)

    for src in mine_sorted:
        if src['id'] in used_src: continue
        if src['ships'] < 5: continue

        best_score = -float('inf')
        best_tgt = None
        best_angle = None
        best_needed = 0

        for tgt in targets:
            # Skip pending targets
            if tgt['id'] in pending_targets: continue

            dist = math.hypot(src['x']-tgt['x'], src['y']-tgt['y'])

            is_moving = tgt['id'] in state.get('moving', [])

            # Find angle using _sim find_angle
            angle, ticks = find_angle(src, tgt, src['ships'], state['vel'], state['ips'], state['step'], is_moving)

            if angle is None: continue

            eta = ticks

            # Ships needed accounting for production
            needed = int(tgt['ships'] + 1 + (tgt['prod'] * eta if tgt['owner'] >= 0 else 0))

            # Base EV based on production and remaining time
            ticks_remaining = max(1, 1000 - state['step'] - eta)
            ev = tgt['prod'] * ticks_remaining / (1.0 + 0.05 * eta)  # discount by travel time

            if is_moving:
                ev *= 1.5 # Boost moving targets

            # Massive priority to early game neutral targets
            if tgt['owner'] == -1 and state['step'] < 200:
                ev *= 2.0

            score = ev - needed * 0.8

            if score > best_score:
                best_score = score
                best_tgt = tgt
                best_angle = angle
                best_needed = needed

        if best_tgt and src['ships'] >= best_needed + 3:

            # Defense ignores production during threat ETA
            # Before committing, make sure we have enough to defend incoming threats
            incoming_ships = sum(f['ships'] for f in state['fleets'] if f['owner'] != pid and is_heading_to(f, src))

            if incoming_ships > 0:
                # Find closest incoming fleet for threat ETA
                closest_dist = float('inf')
                closest_f = None
                for f in state['fleets']:
                    if f['owner'] != pid and is_heading_to(f, src):
                        d = math.hypot(src['x']-f['x'], src['y']-f['y'])
                        if d < closest_dist:
                            closest_dist = d
                            closest_f = f

                if closest_dist <= 85.0:
                    threat_eta = closest_dist / max(spd(closest_f['ships']), 0.1)
                    garrison_at_impact = src['ships'] + src['prod'] * threat_eta

                    if garrison_at_impact < incoming_ships + 3 + best_needed:
                         continue # Cannot safely send this attack

            # Can send
            send = min(int(src['ships'] - 1), best_needed + 3)
            moves.append([src['id'], best_angle, send])
            used_src.add(src['id'])
            pending_targets.add(best_tgt['id'])

    return moves

def agent(obs):
    try:
        state = obs_to_state(obs)
        pid = obs.get("player", 0)
        return heuristic_moves(state, pid)
    except Exception as e:
        print(f"Agent Intercept Error: {e}")
        return []
