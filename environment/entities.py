from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Union, List

from django.apps import apps
from environment.models import GCPRegion

PublishedProject = apps.get_model("project", "PublishedProject")


class Region(Enum):
    US_CENTRAL = "us-central1"
    NORTHAMERICA_NORTHEAST = "northamerica-northeast1"
    EUROPE_WEST = "europe-west3"
    AUSTRALIA_SOUTHEAST = "australia-southeast1"


class BucketObjectType(Enum):
    DIRECTORY = "directory"
    FILE = "file"


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
    COLLABORATIVE = "collaborative"

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


class WorkspaceType(Enum):
    SHARED_WORKSPACE = "SharedWorkspace"
    WORKSPACE = "Workspace"
    ENTITY_SCAFFOLDING = "EntityScaffolding"


class WorkflowType(Enum):
    WORKSPACE_CREATION = "workspace_creation"
    WORKSPACE_DELETION = "workspace_deletion"
    SHARED_WORKSPACE_CREATION = "shared_workspace_creation"
    SHARED_WORKSPACE_DELETION = "shared_workspace_deletion"
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
    workspace_id: str

    def display_type(self) -> str:
        action_string = self.type.value.replace("_", " ")
        return action_string.capitalize()


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
    project: Optional[PublishedProject]
    machine_type: Optional[str]
    disk_size: Optional[int]
    gpu_accelerator_type: Optional[str]
    service_account_name: str
    workbench_owner_username: Optional[str]
    service_errors: Optional[List["ServiceError"]] = None

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
    is_owner: bool
    workbenches: Iterable[ResearchEnvironment]
    is_accessible: bool = True
    access_denial_reason: Optional[str] = None
    service_errors: Optional[List["ServiceError"]] = None


@dataclass(frozen=True, eq=True)
class SimplifiedResearchWorkspace:
    gcp_project_id: str
    status: WorkspaceStatus
    owner: str
    region: Optional[Region] = None


@dataclass
class SharedBucket:
    name: str
    is_owner: bool
    is_admin: bool


@dataclass(frozen=True)
class SharedWorkspace:
    gcp_project_id: str
    gcp_billing_id: str
    is_owner: bool
    status: WorkspaceStatus
    buckets: Iterable[SharedBucket]
    is_accessible: bool = True
    access_denial_reason: Optional[str] = None
    service_errors: Optional[List["ServiceError"]] = None


@dataclass
class EntityScaffolding:
    status: Union[WorkspaceStatus, EnvironmentStatus]
    gcp_project_id: str
    region: Optional[Region] = Region.US_CENTRAL
    gcp_billing_id: Optional[str] = None
    is_owner: bool = False
    is_accessible: bool = True
    access_denial_reason: Optional[str] = None
    workbenches: Iterable[ResearchEnvironment] = None
    service_errors: Optional[List["ServiceError"]] = None
    
    def __post_init__(self):
        if self.workbenches is None:
            self.workbenches = []


@dataclass
class ServiceError:
    error_type: str
    message: str
    resource_id: str
    service_name: str
    details: Optional[str] = None
    can_retry: bool = False


@dataclass
class SharedBucketObject:
    type: BucketObjectType
    name: str
    full_path: str
    size: str = None
    modification_time: str = None


@dataclass
class CloudRole:
    full_name: str
    title: str
    description: str

    def __str__(self):
        return self.title


@dataclass
class QuotaInfo:
    metric_name: str
    limit: int
    usage: int
    usage_percentage: float


@dataclass
class DatasetsMonitoringEntry:
    dataset_identifier: str
    instance_type: str
    total_time: str
    user_email: str
