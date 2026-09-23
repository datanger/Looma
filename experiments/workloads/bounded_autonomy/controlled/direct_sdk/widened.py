"""Route set that the held-out perturbation split turns out to require.

Kept in its own module so that the measured development-route file stays exactly the code
an author would have written for the development split; the widening cost is this file
plus the branch that consumes it.
"""

from __future__ import annotations

from experiments.workloads.bounded_autonomy.controlled.protocol import ACTION_LIST, ACTION_READ


# A discovery branch: enumerate the environment instead of only reading declared
# candidates, then read whatever the catalog shows as relevant.
WIDENED_ACTIONS = (ACTION_READ, ACTION_LIST)