# Architecture

## 1. Physics Model
- **Speed Formula**: Speed scales with ship count logarithmically: `1.0 + 5.0 * (log(n) / log(1000))^1.5`. Single ships move at 1.0, larger fleets faster.
- **Sun Collision**: The sun is located at `(50, 50)` with a radius of `10.0`. Fleet trajectories passing within `SUN_R` (plus a small safety margin) are destroyed. Segment-to-circle intersection is used for validation.
- **Planet Orbiting**: Inner planets revolve around the sun based on their initial distance and position. At any tick `step`, the coordinates can be predicted with `atan2` calculations: `angle = initial_angle + velocity * step`.

## 2. Observation Format
- `planets`: Array of all planets `[id, owner, x, y, radius, ships, production]`.
- `fleets`: Array of in-transit fleets `[id, owner, x, y, angle, from_planet_id, ships]`.
- `player`: Agent's player ID (0-3).
- `angular_velocity`: Velocity parameter for rotating inner planets.
- `initial_planets`: Planet coordinates and stats at `step=0`, necessary for predicting planetary orbital paths.
- `comet_planet_ids`: Array of planet IDs that act as comets.
- `step`: Current game turn (0 to 500).

## 3. Simulator Design
Simulator strictly executes mechanics in this order:
1. **Launch Fleets**: Create new fleet objects for issued commands and subtract source ships.
2. **Production**: Add production per tick to garrisoned ships BEFORE any movements happen.
3. **Fleet Movement**: Fleets advance according to `speed(ships)`. Check for Out of Bounds, Sun Collision, and Planet segment collision.
4. **Planet Orbit**: Orbiting inner planets move. Check if planets "sweep" across fleets.
5. **Tick Update**: Game step is incremented.
6. **Combat Resolution (AFTER Movement)**: Arriving fleets reinforce or attack. Group attacks by owner, largest surplus conquers and remaining attackers act as garrison.

## 4. MCTS Design
- **UCB1**: Uses an exploration vs exploitation node selection formula `(wins/visits) + c * sqrt(ln(parent_visits)/visits)`. Constant varies per agent variant (e.g. 1.0, 1.4, 1.8).
- **Candidate Generation**: Atomic actions grouped into mutually exclusive tactical strategies (e.g., precise expansion, coordinated attacks, focus defend).
- **Rollout**: A heavily optimized `fast_policy` acts as an O(N^2) nearest-neighbor attack script during the depth rollout.
- **Backpropagation**: Rolls `wins`/eval scores back up the MCTS tree nodes.

## 5. Heuristic Baseline
The baseline agent evaluates options via:
- **EV Scoring Formula**: Captures the worth of an assault: `EV = tgt_prod * ticks_remaining / (1.0 + 0.05 * eta)`. Subtracts estimated `capture_cost` for the final target value.
- **Pending Targets Skipping**: An ongoing attack list bypasses multiple fleets targeting the same objective.
- **Defense Gate**: Checks for ETA-adjusted incoming hostiles. Fleets won't launch if their origin planet faces an imminent deadly threat before `threat_eta` resolves.

## 6. Performance Budget
- **Budget**: Maximum ~82ms per turn before timeouts.
- **Optimization Strategy**: Rollout tick loop size is lowered to 15-25 (from 60) and manual deepcopies via dictionary comprehensions are implemented to maintain O(50+) rollouts target.

## 7. Known Failure Modes
- **Early Far-Planet Obsession**: EV was originally not discounting long travel times, fixed via the `0.05 * eta` discount factor.
- **Defense Blindspot Range**: Previously set to `<60`, extending to `85` ensures high-velocity, distant fleets are correctly anticipated.
- **Overcommitting**: A maximum buffer margin (`needed + 3`) is enforced to save backline defenses from easy counter-raids.
