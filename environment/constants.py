from collections import namedtuple

from environment.entities import (
    GPUAcceleratorType,
    Region,
)

MAX_RUNNING_WORKSPACES = 4

MAX_CPU_USAGE = 32

PERSISTENT_DATA_DISK_NAME = "Persistent data disk 1GB"

ProjectedWorkbenchCost = namedtuple("ProjectedWorkbenchCost", "resource cost")

GPU_PROJECTED_COSTS = {
    Region.US_CENTRAL: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [GPUAcceleratorType.NVIDIA_TESLA_T4.value, 0.35],
        ]
    ],
    Region.NORTHAMERICA_NORTHEAST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [GPUAcceleratorType.NVIDIA_TESLA_T4.value, 0.35],
        ]
    ],
    Region.EUROPE_WEST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [GPUAcceleratorType.NVIDIA_TESLA_T4.value, 0.41],
        ]
    ],
    Region.AUSTRALIA_SOUTHEAST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [GPUAcceleratorType.NVIDIA_TESLA_T4.value, 0.44],
        ]
    ],
}


DATA_STORAGE_PROJECTED_COSTS = {
    Region.US_CENTRAL: ProjectedWorkbenchCost(PERSISTENT_DATA_DISK_NAME, 0.05),
    Region.NORTHAMERICA_NORTHEAST: ProjectedWorkbenchCost(
        PERSISTENT_DATA_DISK_NAME, 0.05
    ),
    Region.EUROPE_WEST: ProjectedWorkbenchCost(PERSISTENT_DATA_DISK_NAME, 0.05),
    Region.AUSTRALIA_SOUTHEAST: ProjectedWorkbenchCost(PERSISTENT_DATA_DISK_NAME, 0.05),
}
