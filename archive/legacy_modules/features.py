"""
Feature extraction for RL model.
"""

import numpy as np
from typing import List, Dict, Tuple
from orbit_env_utils import (
    Planet, Fleet, distance, get_fleet_speed
)


def extract_global_state_features(obs_dict: Dict, num_planets: int = 16) -> np.ndarray:
    """
    Extract global game state features normalized to [0, 1] or [-1, 1].
    """
    my_planets = obs_dict.get("mine", [])
    enemy_planets = obs_dict.get("enemy", [])
    neutral_planets = obs_dict.get("neutral", [])
    my_fleets = [f for f in obs_dict.get("fleets", []) 
                if f.owner == obs_dict.get("player_id")]
    enemy_fleets = [f for f in obs_dict.get("fleets", []) 
                   if f.owner >= 0 and f.owner != obs_dict.get("player_id")]
    
    my_ships = sum(p.ships for p in my_planets)
    enemy_ships = sum(p.ships for p in enemy_planets)
    my_ships_transit = sum(f.ships for f in my_fleets)
    enemy_ships_transit = sum(f.ships for f in enemy_fleets)
    
    my_production = sum(p.production for p in my_planets)
    enemy_production = sum(p.production for p in enemy_planets)
    
    total_planets = len(my_planets) + len(enemy_planets) + len(neutral_planets)
    
    features = []
    
    max_ships = max(my_ships + enemy_ships + my_ships_transit + enemy_ships_transit, 1)
    features.append((my_ships - enemy_ships) / max_ships)
    features.append((my_ships_transit - enemy_ships_transit) / max_ships)
    
    if total_planets > 0:
        features.append(len(my_planets) / total_planets)
        features.append(len(enemy_planets) / total_planets)
        features.append(len(neutral_planets) / total_planets)
    else:
        features.extend([0, 0, 0])
    
    max_prod = max(my_production + enemy_production, 1)
    features.append((my_production - enemy_production) / max_prod)
    
    if len(my_fleets) + len(enemy_fleets) > 0:
        features.append(len(my_fleets) / (len(my_fleets) + len(enemy_fleets) + 1))
    else:
        features.append(0.0)
    
    return np.array(features, dtype=np.float32)


def extract_candidate_features(candidate: Dict, obs_dict: Dict, 
                               planet_by_id: Dict[int, Planet],
                               fleet_by_id: Dict[int, Fleet]) -> np.ndarray:
    """
    Extract features for a single candidate move.
    """
    features = []
    max_ships = 1000
    max_distance = 200
    max_production = 50
    
    if candidate["type"] == "attack" or candidate["type"] == "reinforce":
        source = planet_by_id[candidate["source_id"]]
        target = planet_by_id[candidate["target_id"]]
        ships = candidate["ships"]
        eta = candidate["eta"]
        
        features.append(ships / max_ships)
        features.append(target.ships / max_ships)
        
        dist = distance(source.x, source.y, target.x, target.y)
        features.append(min(dist / max_distance, 1.0))
        features.append(eta / 60)
        
        features.append(target.production / max_production)
        
        if target.owner == -1:
            owner_feat = [1, 0, 0]
        elif target.owner != obs_dict.get("player_id"):
            owner_feat = [0, 1, 0]
        else:
            owner_feat = [0, 0, 1]
        features.extend(owner_feat)
        
        if target.owner != -1 and eta > 0:
            projected = target.ships + eta * target.production
        else:
            projected = target.ships
        features.append(min(projected / max_ships, 1.0))
        
        features.append(0.0) # vuln placeholder
        
        sun_dist = distance(source.x, source.y, 50, 50)
        features.append(min(sun_dist / max_distance, 1.0))
        
        features.append(1.0 if candidate["type"] == "attack" else 0.0)
        
    else: # coop_attack
        target = planet_by_id[candidate["target_id"]]
        total_ships = candidate["total_ships"]
        num_sources = len(candidate["sources"])
        
        features.append(num_sources / 8)
        features.append(total_ships / max_ships)
        
        distances = []
        for source_info in candidate["sources"]:
            source = planet_by_id[source_info["planet_id"]]
            d = distance(source.x, source.y, target.x, target.y)
            distances.append(d)
        
        avg_dist = np.mean(distances) if distances else 0
        min_dist = np.min(distances) if distances else 0
        features.append(min(avg_dist / max_distance, 1.0))
        features.append(min(min_dist / max_distance, 1.0))
        
        features.append(target.production / max_production)
        
        if target.owner == -1:
            owner_feat = [1, 0, 0]
        elif target.owner != obs_dict.get("player_id"):
            owner_feat = [0, 1, 0]
        else:
            owner_feat = [0, 0, 1]
        features.extend(owner_feat)
        
        features.append(0.0)
    
    # Pad features to exactly CANDIDATE_FEATURE_DIM (16)
    while len(features) < 16:
        features.append(0.0)
    return np.array(features[:16], dtype=np.float32)


def batch_candidate_features(candidates: List[Dict], obs_dict: Dict) -> np.ndarray:
    """
    Extract features for all candidates.
    """
    planet_by_id = {p.id: p for p in obs_dict.get("planets", [])}
    fleet_by_id = {f.id: f for f in obs_dict.get("fleets", [])}
    
    features_list = []
    for candidate in candidates:
        feat = extract_candidate_features(candidate, obs_dict, planet_by_id, fleet_by_id)
        features_list.append(feat)
    
    if not features_list:
        return np.zeros((0, 16), dtype=np.float32)
    
    return np.stack(features_list, axis=0)


GLOBAL_STATE_DIM = 8
CANDIDATE_FEATURE_DIM = 16
