from collections import namedtuple

from environment.entities import (
    Region,
)

MAX_RUNNING_WORKSPACES = 4

MAX_CPU_USAGE = 32

PERSISTENT_DATA_DISK_NAME = "Persistent data disk 1GB"

ProjectedWorkbenchCost = namedtuple("ProjectedWorkbenchCost", "resource cost")


DATA_STORAGE_PROJECTED_COSTS = {
    Region.US_CENTRAL: ProjectedWorkbenchCost(PERSISTENT_DATA_DISK_NAME, 0.05),
    Region.NORTHAMERICA_NORTHEAST: ProjectedWorkbenchCost(
        PERSISTENT_DATA_DISK_NAME, 0.05
    ),
    Region.EUROPE_WEST: ProjectedWorkbenchCost(PERSISTENT_DATA_DISK_NAME, 0.05),
    Region.AUSTRALIA_SOUTHEAST: ProjectedWorkbenchCost(PERSISTENT_DATA_DISK_NAME, 0.05),
}
