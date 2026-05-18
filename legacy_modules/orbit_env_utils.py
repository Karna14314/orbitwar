"""
Orbit Wars environment utilities: parsing, physics, and trajectory calculations.
"""

import math
import numpy as np
from typing import Tuple, List, Optional, Dict

# Import from official Kaggle environment
try:
    from kaggle_environments.envs.orbit_wars.orbit_wars import Planet, Fleet
except ImportError:
    class Planet:
        def __init__(self, planet_id, owner, x, y, radius, ships, production):
            self.id = planet_id
            self.owner = owner
            self.x = x
            self.y = y
            self.radius = radius
            self.ships = ships
            self.production = production
    class Fleet:
        def __init__(self, fleet_id, owner, x, y, angle, from_planet_id, ships):
            self.id = fleet_id
            self.owner = owner
            self.x = x
            self.y = y
            self.angle = angle
            self.from_planet_id = from_planet_id
            self.ships = ships

MAX_SPEED = 6.0
SUN_RADIUS = 10.1
SUN_CENTER = (50.0, 50.0)

def get_fleet_speed(ships: int) -> float:
    if ships <= 1: return 1.0
    return 1.0 + (MAX_SPEED - 1.0) * (math.log(max(1, ships)) / math.log(1000)) ** 1.5

def calculate_angle(from_x, from_y, to_x, to_y):
    return math.atan2(to_y - from_y, to_x - from_x)

def distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

def line_circle_collision(x1, y1, x2, y2, cx, cy, r):
    vx, vy = x2 - x1, y2 - y1
    if vx == 0 and vy == 0: return (x1-cx)**2 + (y1-cy)**2 <= r**2
    t = max(0, min(1, ((cx-x1)*vx + (cy-y1)*vy) / (vx**2 + vy**2)))
    return (x1 + t*vx - cx)**2 + (y1 + t*vy - cy)**2 <= r**2

def sun_collision(fx, fy, tx, ty):
    return line_circle_collision(fx, fy, tx, ty, SUN_CENTER[0], SUN_CENTER[1], SUN_RADIUS)

def predict_planet_position(planet, initial_planets_dict, angular_velocity, t):
    ip = initial_planets_dict.get(planet.id)
    if not ip: return planet.x, planet.y
    r = distance(ip.x, ip.y, SUN_CENTER[0], SUN_CENTER[1])
    if r < 1.0: return planet.x, planet.y
    angle_initial = math.atan2(ip.y - SUN_CENTER[1], ip.x - SUN_CENTER[0])
    angle_current = angle_initial + angular_velocity * t
    return SUN_CENTER[0] + r * math.cos(angle_current), SUN_CENTER[1] + r * math.sin(angle_current)

def predict_interception_angle(source, target, ships, angular_velocity, initial_planets_dict, is_moving, max_ticks=60):
    speed = get_fleet_speed(ships)
    for t in range(1, max_ticks + 1):
        tx, ty = predict_planet_position(target, initial_planets_dict, angular_velocity, t) if is_moving else (target.x, target.y)
        dist = distance(source.x, source.y, tx, ty)
        if speed * t >= dist - target.radius:
            if not sun_collision(source.x, source.y, tx, ty):
                return calculate_angle(source.x, source.y, tx, ty), t
    return None, None

def parse_observation(obs):
    planets = [Planet(*p) for p in obs.get("planets", [])]
    fleets = [Fleet(*f) for f in obs.get("fleets", [])]
    initial_planets = [Planet(*p) for p in obs.get("initial_planets", [])]
    ip_dict = {p.id: p for p in initial_planets}
    pid = obs.get("player", 0)
    comet_ids = set(obs.get("comet_planet_ids", []))
    moving_ids = set()
    for p in planets:
        ip = ip_dict.get(p.id)
        if ip and (abs(p.x - ip.x) > 0.01 or abs(p.y - ip.y) > 0.01):
            moving_ids.add(p.id)
    return {
        "planets": planets, "fleets": fleets, "player_id": pid,
        "ip_dict": ip_dict, "angular_velocity": obs.get("angular_velocity", 0.0),
        "comet_ids": comet_ids, "moving_ids": moving_ids | comet_ids,
        "mine": [p for p in planets if p.owner == pid],
        "targets": [p for p in planets if p.owner != pid]
    }
