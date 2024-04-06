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
            [InstanceType.N2_STANDARD_2.value, 0.10],
            [InstanceType.N2_STANDARD_4.value, 0.20],
            [InstanceType.N2_STANDARD_8.value, 0.39],
            [InstanceType.N2_STANDARD_16.value, 0.78],
        ]
    ],
    Region.NORTHAMERICA_NORTHEAST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [InstanceType.N1_STANDARD_2.value, 0.11],
            [InstanceType.N1_STANDARD_4.value, 0.21],
            [InstanceType.N1_STANDARD_8.value, 0.42],
            [InstanceType.N1_STANDARD_16.value, 0.84],
            [InstanceType.N2_STANDARD_2.value, 0.10],
            [InstanceType.N2_STANDARD_4.value, 0.21],
            [InstanceType.N2_STANDARD_8.value, 0.43],
            [InstanceType.N2_STANDARD_16.value, 0.85],
        ]
    ],
    Region.EUROPE_WEST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [InstanceType.N1_STANDARD_2.value, 0.12],
            [InstanceType.N1_STANDARD_4.value, 0.24],
            [InstanceType.N1_STANDARD_8.value, 0.49],
            [InstanceType.N1_STANDARD_16.value, 0.98],
            [InstanceType.N2_STANDARD_2.value, 0.11],
            [InstanceType.N2_STANDARD_4.value, 0.21],
            [InstanceType.N2_STANDARD_8.value, 0.43],
            [InstanceType.N2_STANDARD_16.value, 0.85],
        ]
    ],
    Region.AUSTRALIA_SOUTHEAST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [InstanceType.N1_STANDARD_2.value, 0.13],
            [InstanceType.N1_STANDARD_4.value, 0.27],
            [InstanceType.N1_STANDARD_8.value, 0.35],
            [InstanceType.N1_STANDARD_16.value, 1.07],
            [InstanceType.N2_STANDARD_2.value, 0.14],
            [InstanceType.N2_STANDARD_4.value, 0.28],
            [InstanceType.N2_STANDARD_8.value, 0.55],
            [InstanceType.N2_STANDARD_16.value, 1.10],
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
    InstanceType.N1_STANDARD_2: "N1, 2 CPU, 7.5GB RAM",
    InstanceType.N1_STANDARD_4: "N1, 4 CPU, 15GB RAM",
    InstanceType.N1_STANDARD_8: "N1, 8 CPU, 30GB RAM",
    InstanceType.N1_STANDARD_16: "N1, 16 CPU, 60GB RAM",
    InstanceType.N2_STANDARD_2: "N2, 2 CPU, 8GB RAM",
    InstanceType.N2_STANDARD_4: "N2, 4 CPU, 16GB RAM",
    InstanceType.N2_STANDARD_8: "N2, 8 CPU, 32GB RAM",
    InstanceType.N2_STANDARD_16: "N2, 16 CPU, 64GB RAM",
}
