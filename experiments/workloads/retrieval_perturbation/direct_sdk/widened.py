"""Route set the held-out perturbation split turns out to require.

Kept in its own module so the measured development-route file stays exactly the
code an author would have written for the development split; the widening cost is
this file plus the branch in `workflow.py` that consumes it.

The one added route is `list_chunks`: when the corpus is re-keyed or search
returns opaque handles, nothing in the frozen route set can turn a handle into a
chunk id any more.
"""

from __future__ import annotations

from experiments.workloads.retrieval_perturbation.injectors import (
    ACTION_LIST_CHUNKS,
    DEV_ROUTE_SET,
)

WIDENED_ACTIONS = DEV_ROUTE_SET + (ACTION_LIST_CHUNKS,)