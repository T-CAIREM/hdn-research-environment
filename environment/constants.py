from collections import namedtuple

from environment.entities import (
    GPUAcceleratorType,
    InstanceType,
    Region,
)

MAX_RUNNING_WORKSPACES = 4

MAX_CPU_USAGE = 32

PERSISTENT_DATA_DISK_NAME = "Persistent data disk 1GB"

ProjectedWorkbenchCost = namedtuple("ProjectedWorkbenchCost", "resource cost")
INSTANCE_PROJECTED_COSTS = {
    Region.US_CENTRAL: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [InstanceType.N1_STANDARD_2.value, 0.09],
            [InstanceType.N1_STANDARD_4.value, 0.19],
            [InstanceType.N1_STANDARD_8.value, 0.38],
            [InstanceType.N1_STANDARD_16.value, 0.76],
        ]
    ],
    Region.NORTHAMERICA_NORTHEAST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [InstanceType.N1_STANDARD_2.value, 0.11],
            [InstanceType.N1_STANDARD_4.value, 0.21],
            [InstanceType.N1_STANDARD_8.value, 0.42],
            [InstanceType.N1_STANDARD_16.value, 0.84],
        ]
    ],
    Region.EUROPE_WEST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [InstanceType.N1_STANDARD_2.value, 0.12],
            [InstanceType.N1_STANDARD_4.value, 0.24],
            [InstanceType.N1_STANDARD_8.value, 0.49],
            [InstanceType.N1_STANDARD_16.value, 0.98],
        ]
    ],
    Region.AUSTRALIA_SOUTHEAST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [InstanceType.N1_STANDARD_2.value, 0.13],
            [InstanceType.N1_STANDARD_4.value, 0.27],
            [InstanceType.N1_STANDARD_8.value, 0.35],
            [InstanceType.N1_STANDARD_16.value, 1.07],
        ]
    ],
}

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

MACHINE_TYPE_SPECIFICATION = {
    InstanceType.N1_STANDARD_2: "2 CPU, 7.5GB RAM",
    InstanceType.N1_STANDARD_4: "4 CPU, 15GB RAM",
    InstanceType.N1_STANDARD_8: "8 CPU, 30GB RAM",
    InstanceType.N1_STANDARD_16: "16 CPU, 60GB RAM",
}
