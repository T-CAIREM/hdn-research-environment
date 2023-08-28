from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Union

from django.apps import apps

PublishedProject = apps.get_model("project", "PublishedProject")


class Region(Enum):
    US_CENTRAL = "us-central1"
    NORTHAMERICA_NORTHEAST = "northamerica-northeast1"
    EUROPE_WEST = "europe-west3"
    AUSTRALIA_SOUTHEAST = "australia-southeast1"


class InstanceType(Enum):
    N1_STANDARD_1 = "n1-standard-1"
    N1_STANDARD_2 = "n1-standard-2"
    N1_STANDARD_4 = "n1-standard-4"
    N1_STANDARD_8 = "n1-standard-8"
    N1_STANDARD_16 = "n1-standard-16"

    def cpus(self):
        INSTANCE_TO_CPU_MAP = {
            InstanceType.N1_STANDARD_1: 1,
            InstanceType.N1_STANDARD_2: 2,
            InstanceType.N1_STANDARD_4: 4,
            InstanceType.N1_STANDARD_8: 8,
            InstanceType.N1_STANDARD_16: 16,
        }

        return INSTANCE_TO_CPU_MAP[self]


class GPUAcceleratorType(Enum):
    NVIDIA_TESLA_T4 = "NVIDIA_TESLA_T4"


class EnvironmentStatus(Enum):
    CREATING = "creating"

    RUNNING = "running"
    STARTING = "starting"

    UPDATING = "updating"

    STOPPED = "stopped"
    STOPPING = "stopping"

    DESTROYING = "destroying"


class EnvironmentType(Enum):
    UNKNOWN = "unknown"
    JUPYTER = "jupyter"
    RSTUDIO = "rstudio"

    @classmethod
    def from_string_or_none(cls, maybe_string: Optional[str]) -> "EnvironmentType":
        if not maybe_string:
            return cls.UNKNOWN
        return cls(maybe_string)


class WorkspaceStatus(Enum):
    CREATED = "created"
    CREATING = "creating"
    DESTROYING = "destroying"


class WorkflowStatus(Enum):
    IN_PROGRESS = "in_progress"
    FAILURE = "failure"
    SUCCESS = "success"


class WorkflowType(Enum):
    WORKSPACE_CREATION = "workspace_creation"
    WORKSPACE_DELETION = "workspace_deletion"

    WORKBENCH_CREATION = "workbench_creation"
    WORKBENCH_DESTROY = "workbench_destroy"
    WORKBENCH_STOP = "workbench_stop"
    WORKBENCH_START = "workbench_start"
    WORKBENCH_UPDATE = "workbench_update"


@dataclass
class Workflow:
    id: str
    type: WorkflowType
    status: WorkflowStatus
    error_information: str

    def display_type(self) -> str:
        entity_type, action_type = self.type.value.split("_")
        return f"{entity_type} {action_type}".capitalize()


@dataclass
class ResearchEnvironment:
    gcp_identifier: str
    dataset_identifier: str
    url: Optional[str]
    workspace_name: str
    status: EnvironmentStatus
    cpu: float
    memory: float
    region: Region
    type: EnvironmentType
    project: PublishedProject
    machine_type: Optional[InstanceType]
    disk_size: Optional[int]
    gpu_accelerator_type: Optional[str]

    @property
    def is_running(self):
        return self.status in [EnvironmentStatus.RUNNING, EnvironmentStatus.UPDATING]

    @property
    def is_paused(self):
        return self.status == EnvironmentStatus.STOPPED

    @property
    def is_in_progress(self):
        return self.status in [
            EnvironmentStatus.CREATING,
            EnvironmentStatus.STARTING,
            EnvironmentStatus.STOPPING,
            EnvironmentStatus.UPDATING,
            EnvironmentStatus.DESTROYING,
        ]

    @property
    def is_active(self):
        return self.is_running or self.is_paused or self.is_in_progress


@dataclass(frozen=True, eq=True)
class ResearchWorkspace:
    region: Region
    gcp_project_id: str
    gcp_billing_id: str
    status: WorkspaceStatus
    workbenches: Iterable[ResearchEnvironment]


@dataclass
class EntityScaffolding:
    status: Union[WorkspaceStatus, EnvironmentStatus]
    gcp_project_id: str
