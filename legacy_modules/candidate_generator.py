"""
Candidate move generator using heuristic rules.
"""

import math
from typing import List, Tuple, Optional, Dict
from orbit_env_utils import (
    Planet, Fleet, get_fleet_speed, predict_interception_angle,
    predict_total_ships_needed, distance, calculate_angle
)


MIN_SHIPS_ATTACK = 5
MIN_SHIPS_COOP_ATTACK = 20
MAX_COOP_SOURCES = 8
FORMULA_DIST = 100
FORMULA_PROD_MULT = 15
FORMULA_ENEMY_BONUS_MULT = 10
FORMULA_TOTAL_SHIPS_PERCENT = 0.7


def score_target(source: Planet, target: Planet, ships: int, 
                 eta: float) -> float:
    """Heuristic score for attacking a target."""
    dist = distance(source.x, source.y, target.x, target.y)
    
    enemy_produced = 0
    enemy_bonus = 0
    if target.owner != -1:
        enemy_produced = eta * target.production
        enemy_bonus = target.production
    
    total_ships = ships + 1 + enemy_produced
    
    return (
        (FORMULA_DIST - dist)
        + (FORMULA_PROD_MULT * target.production)
        + (FORMULA_ENEMY_BONUS_MULT * enemy_bonus)
        - (FORMULA_TOTAL_SHIPS_PERCENT * total_ships)
        - (2 * eta)
    )


def get_ranked_targets(source: Planet, targets: List[Planet],
                       excluded_ids: set, comet_ids: set) -> List[Tuple[Planet, float]]:
    """Get targets ranked by heuristic score."""
    scored = []
    
    for target in targets:
        if target.id in excluded_ids or target.id in comet_ids:
            continue
        
        dist = distance(source.x, source.y, target.x, target.y)
        fleet_speed = get_fleet_speed(MIN_SHIPS_ATTACK)
        eta = dist / fleet_speed
        
        score = score_target(source, target, MIN_SHIPS_ATTACK, eta)
        scored.append((target, score))
    
    return sorted(scored, key=lambda x: x[1], reverse=True)


def get_closest_sources(target: Planet, sources: List[Planet],
                        excluded_ids: set) -> List[Tuple[Planet, float]]:
    """Get source planets closest to target."""
    distances = []
    for source in sources:
        if source.id in excluded_ids:
            continue
        dist = distance(source.x, source.y, target.x, target.y)
        distances.append((source, dist))
    
    return sorted(distances, key=lambda x: x[1])


def generate_attack_candidates(my_planets: List[Planet], 
                               target_planets: List[Planet],
                               excluded_ids: set,
                               comet_ids: set,
                               angular_velocity: float,
                               under_attack: Dict) -> List[Dict]:
    """
    Generate single-source attack candidates.
    """
    candidates = []
    
    for source in sorted(my_planets, key=lambda p: p.ships, reverse=True):
        if source.id in excluded_ids or source.ships < MIN_SHIPS_ATTACK:
            continue
        
        available = source.ships
        if source.id in under_attack:
            threat = sum(att["fleet"].ships 
                        for att in under_attack[source.id]["fleets"])
            available = max(0, source.ships - threat)
        
        if available < MIN_SHIPS_ATTACK:
            continue
        
        targets = get_ranked_targets(source, target_planets, excluded_ids, comet_ids)
        
        for target, _ in targets[:5]:
            is_moving = getattr(target, '_is_moving', False)
            angle, eta = predict_interception_angle(
                source, target, MIN_SHIPS_ATTACK, angular_velocity, {}, is_moving
            )
            
            if angle is None:
                continue
            
            total_ships, final_angle, final_eta = predict_total_ships_needed(
                source, target, MIN_SHIPS_ATTACK, angular_velocity, available, is_moving
            )
            
            if total_ships is None or total_ships > available:
                continue
            
            score = score_target(source, target, total_ships, final_eta)
            
            candidates.append({
                "type": "attack",
                "source_id": source.id,
                "target_id": target.id,
                "ships": int(total_ships),
                "angle": float(final_angle),
                "eta": int(final_eta),
                "score": float(score),
            })
    
    return sorted(candidates, key=lambda c: c["score"], reverse=True)


def generate_reinforcement_candidates(my_planets: List[Planet],
                                      under_attack: Dict,
                                      excluded_ids: set,
                                      angular_velocity: float) -> List[Dict]:
    """
    Generate reinforcement candidates for planets under attack.
    """
    candidates = []
    
    for target_id, attack_info in under_attack.items():
        target = attack_info["planet"]
        incoming_fleets = sorted(attack_info["fleets"], 
                                key=lambda f: f["arrive_tick"])
        
        if not incoming_fleets:
            continue
        
        incoming_ships = sum(f["fleet"].ships for f in incoming_fleets)
        reinforcement_needed = max(MIN_SHIPS_ATTACK, incoming_ships + 1)
        
        sources = get_closest_sources(target, my_planets, 
                                      excluded_ids | {target_id})
        
        for source, _ in sources:
            available = source.ships
            
            if available < MIN_SHIPS_ATTACK:
                continue
            
            ships_to_send = min(available, reinforcement_needed)
            
            is_moving = getattr(target, '_is_moving', False)
            angle, eta = predict_interception_angle(
                source, target, ships_to_send, angular_velocity, {}, is_moving
            )
            
            if angle is None:
                continue
            
            if eta > incoming_fleets[0]["arrive_tick"]:
                continue
            
            candidates.append({
                "type": "reinforce",
                "source_id": source.id,
                "target_id": target.id,
                "ships": int(ships_to_send),
                "angle": float(angle),
                "eta": int(eta),
            })
    
    return candidates


def generate_cooperative_attack_candidates(my_planets: List[Planet],
                                          target_planets: List[Planet],
                                          excluded_ids: set,
                                          comet_ids: set,
                                          angular_velocity: float,
                                          under_attack: Dict) -> List[Dict]:
    """
    Generate cooperative attack candidates.
    """
    candidates = []
    
    for target in target_planets:
        if target.id in comet_ids or target.ships < MIN_SHIPS_COOP_ATTACK:
            continue
        
        sources = get_closest_sources(target, my_planets, excluded_ids | {target.id})
        
        if not sources:
            continue
        
        total = 0
        source_info = []
        angles = []
        min_eta = float('inf')
        
        for source, _ in sources:
            if len(source_info) >= MAX_COOP_SOURCES:
                break
            
            if source.id in excluded_ids or source.ships < MIN_SHIPS_ATTACK:
                continue
            
            available = source.ships
            if source.id in under_attack:
                threat = sum(att["fleet"].ships 
                            for att in under_attack[source.id]["fleets"])
                available = max(0, available - threat)
            
            if available < MIN_SHIPS_ATTACK:
                continue
            
            is_moving = getattr(target, '_is_moving', False)
            angle, eta = predict_interception_angle(
                source, target, available, angular_velocity, {}, is_moving
            )
            
            if angle is None:
                continue
            
            source_info.append({
                "planet_id": source.id,
                "ships": int(available),
            })
            angles.append(float(angle))
            total += available
            min_eta = min(min_eta, eta)
        
        if len(source_info) >= 2 and total >= target.ships + 1:
            candidates.append({
                "type": "coop_attack",
                "sources": source_info,
                "target_id": target.id,
                "angles": angles,
                "eta": int(min_eta),
                "total_ships": total,
            })
    
    return candidates


def generate_all_candidates(my_planets: List[Planet],
                           target_planets: List[Planet],
                           angular_velocity: float,
                           under_attack: Dict,
                           comet_ids: set,
                           excluded_ids: Optional[set] = None) -> List[Dict]:
    """Generate all candidate moves."""
    if excluded_ids is None:
        excluded_ids = set()
    
    candidates = []
    candidates.extend(generate_attack_candidates(
        my_planets, target_planets, excluded_ids, comet_ids, angular_velocity, under_attack
    ))
    candidates.extend(generate_reinforcement_candidates(
        my_planets, under_attack, excluded_ids, angular_velocity
    ))
    candidates.extend(generate_cooperative_attack_candidates(
        my_planets, target_planets, excluded_ids, comet_ids, angular_velocity, under_attack
    ))
    
    return candidates
