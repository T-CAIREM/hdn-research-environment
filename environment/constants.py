from environment.entities import (
    InstanceType,
    Region,
)
from collections import namedtuple

MAX_RUNNING_ENVIRONMENTS = 4

MAX_CPU_USAGE = 32

PERSISTENT_DATA_DISK_NAME = "Persistent data disk 1GB"
PERSISTENT_DATA_DISK_TIME_UNIT = "per Month"

T4_TESLA_GPU_NAME = "NVIDIA T4 Tesla"

ProjectedWorkbenchCost = namedtuple(
    "ProjectedWorkbenchCost", "resource cost time_unit", defaults=["per Hour"]
)
PROJECTED_COSTS = {
    Region.US_CENTRAL: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [InstanceType.N1_STANDARD_1.value, 0.05],
            [InstanceType.N1_STANDARD_2.value, 0.09],
            [InstanceType.N1_STANDARD_4.value, 0.19],
            [InstanceType.N1_STANDARD_8.value, 0.38],
            [InstanceType.N1_STANDARD_16.value, 0.76],
            [T4_TESLA_GPU_NAME, 0.35],
            [PERSISTENT_DATA_DISK_NAME, 0.05, PERSISTENT_DATA_DISK_TIME_UNIT],
        ]
    ],
    Region.NORTHAMERICA_NORTHEAST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [InstanceType.N1_STANDARD_1.value, 0.05],
            [InstanceType.N1_STANDARD_2.value, 0.11],
            [InstanceType.N1_STANDARD_4.value, 0.21],
            [InstanceType.N1_STANDARD_8.value, 0.42],
            [InstanceType.N1_STANDARD_16.value, 0.84],
            [T4_TESLA_GPU_NAME, 0.35],
            [PERSISTENT_DATA_DISK_NAME, 0.05, PERSISTENT_DATA_DISK_TIME_UNIT],
        ]
    ],
    Region.EUROPE_WEST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [InstanceType.N1_STANDARD_1.value, 0.06],
            [InstanceType.N1_STANDARD_2.value, 0.12],
            [InstanceType.N1_STANDARD_4.value, 0.24],
            [InstanceType.N1_STANDARD_8.value, 0.49],
            [InstanceType.N1_STANDARD_16.value, 0.98],
            [T4_TESLA_GPU_NAME, 0.41],
            [PERSISTENT_DATA_DISK_NAME, 0.05, PERSISTENT_DATA_DISK_TIME_UNIT],
        ]
    ],
    Region.AUSTRALIA_SOUTHEAST: [
        ProjectedWorkbenchCost(*parameters)
        for parameters in [
            [InstanceType.N1_STANDARD_1.value, 0.07],
            [InstanceType.N1_STANDARD_2.value, 0.13],
            [InstanceType.N1_STANDARD_4.value, 0.27],
            [InstanceType.N1_STANDARD_8.value, 0.35],
            [InstanceType.N1_STANDARD_16.value, 1.07],
            [T4_TESLA_GPU_NAME, 0.44],
            [PERSISTENT_DATA_DISK_NAME, 0.05, PERSISTENT_DATA_DISK_TIME_UNIT],
        ]
    ],
}
