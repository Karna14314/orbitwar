# Agent V14 Evaluation and Tradeoffs

## Tournament Results

A 10-match evaluation tournament was run between the newly proposed `agent_v14.py` and the current repository `champion.py`.

*   **Challenger (agent_v14.py):** 0 wins
*   **Champion (champion.py):** 10 wins
*   **Ties:** 0

The experimental V14 agent severely underperformed the existing champion, failing to secure a single victory.

## Analysis of V14 Code & Potential Tradeoffs

Based on the provided code for V14 and the tournament results, here is an analysis of its design choices and why they likely failed compared to a more optimized champion.

### 1. Gated Spatiotemporal Collision Engine
*   **V14 Approach:** Uses a spatial pre-filter (bounding boxes) and steps by 2 ticks to check for collisions, trying to avoid Time Limit Exceeded (TLE) errors.
*   **Tradeoff:**
    *   *Pros:* Reduced computational overhead, theoretically faster execution.
    *   *Cons:* **Loss of Precision.** By stepping every 2 ticks (`for t in range(1, ticks, 2)`), the agent is blind to collisions that might occur precisely on the skipped even ticks. This likely leads to fleets crashing into planets or other fleets unexpectedly because the evasion algorithm missed the intersection window. In a chaotic environment like Orbit Wars, this loss of fidelity is fatal.

### 2. Compressed Evasion Sweep
*   **V14 Approach:** Limits tactical evasion to just 3 angles: the direct path, and a positive/negative offset based on a single calculated angle `max_offset`.
*   **Tradeoff:**
    *   *Pros:* Very fast to compute.
    *   *Cons:* **Highly Predictable and Brittle.** If all three of these specific paths are blocked (which is common in dense asteroid fields or against clustered enemies), the agent returns `None, None` and fails to launch entirely. A robust agent needs a wider, graded sweep of angles to find a viable path when the primary routes are congested.

### 3. Timeline Emulator & Speed Calculation
*   **V14 Approach:** Uses a logarithmic fleet speed formula and calculates threat ETAs based on an exact integer ceiling of distance over speed.
*   **Tradeoff:**
    *   *Cons:* The game environment might resolve speeds or distances slightly differently than the manual `spd()` function predicts. If the agent under-estimates or over-estimates arrival times by even 1 tick due to rounding errors, its "Safety Buffer" logic fails, leading to lost planets.

### 4. Strategic Phase State Machine
*   **V14 Approach:** Hardcodes threshold values based on turn count (`step < 100` = OPENING) and production ratios (e.g., `< 0.22` = SURVIVAL).
*   **Tradeoff:**
    *   *Pros:* Provides a structured way to change behavior.
    *   *Cons:* **Inflexibility.** The hardcoded `step < 100` might ignore the actual state of the board. If the board is highly dense, the opening phase might end by turn 50. Furthermore, the `execute_strategic_attack` function uses fixed reserve thresholds per phase, which might prevent necessary defensive or opportunistic launches if the agent is stuck in the wrong "phase" based on arbitrary thresholds.

### 5. Multi-Launch Budgeting
*   **V14 Approach:** Allows up to 2 launches per source planet per turn (`launch_registry[sid] >= 2`).
*   **Tradeoff:**
    *   *Pros:* Can dispatch fleets to multiple targets simultaneously.
    *   *Cons:* **Over-extension.** Without perfect pathing and precision ETA calculations (which V14 lacks due to step 1 and 2), launching multiple smaller fleets often results in piecemeal attacks that are easily defended, rather than a single concentrated, overwhelming force.

## Conclusion

The V14 design prioritizes computational speed (stepping every 2 ticks, limiting angle sweeps) at the cost of the absolute precision required to navigate and conquer in Orbit Wars. The 0-10 loss clearly indicates that the tradeoffs made for performance sacrificed too much tactical accuracy. Future iterations must restore precision pathing and a wider evasion search space.
