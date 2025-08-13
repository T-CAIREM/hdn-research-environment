"""
API Response Types for Research Environment API.

This module defines the exact structure of API responses to ensure type safety
and prevent confusion from passing around untyped response.json() dictionaries.
"""

from typing import List, Optional, Union, TypedDict
from typing_extensions import NotRequired


class BillingInfo(TypedDict):
    """Billing information for a workspace."""
    billing_enabled: bool
    billing_account_id: Optional[str]


class ServiceErrorResponse(TypedDict):
    """Service error information from API responses."""
    error_type: str  # billing_disabled, api_not_enabled, permission_denied, quota_exceeded, not_found, unknown
    message: str
    resource_id: str
    service_name: str
    details: NotRequired[Optional[str]]
    can_retry: bool


class WorkbenchResponse(TypedDict):
    """Individual workbench from API response."""
    gcp_identifier: str
    status: str  # running, stopped, creating, destroying, etc.
    dataset_identifier: str
    workbench_type: str  # jupyter, rstudio, collaborative
    cpu: int
    memory: float
    disk_size: int
    machine_type: str
    url: str
    zone: str
    sharing_bucket_identifiers: List[str]
    collaborators: Optional[List[str]]
    service_account_name: str
    workbench_owner_username: Optional[str]
    service_errors: NotRequired[List[ServiceErrorResponse]]


class WorkspaceResponse(TypedDict):
    """Individual workspace from API response."""
    gcp_project_id: str
    billing_info: BillingInfo
    region: str
    status: str  # created, creating, destroying
    is_owner: bool
    workbenches: List[WorkbenchResponse]
    service_errors: List[ServiceErrorResponse]


class ScaffoldingResponse(TypedDict):
    """Scaffolding/workflow entity from API response."""
    id: str
    gcp_project_id: str
    status: str


class WorkspaceListResponse(TypedDict):
    """Response from GET /api/workspaces endpoint."""
    workspaces: List[WorkspaceResponse]
    scaffolding: NotRequired[List[ScaffoldingResponse]]


class SingleWorkspaceResponse(TypedDict):
    """Response from GET /api/workspaces/{id} endpoint."""
    workspace: WorkspaceResponse


class SharedBucketResponse(TypedDict):
    """Individual shared bucket from API response."""
    bucket_name: str
    is_owner: NotRequired[bool]  # Added for compatibility with existing code
    is_admin: NotRequired[bool]  # Added for compatibility with existing code


class SharedWorkspaceResponse(TypedDict):
    """Individual shared workspace from API response."""
    gcp_project_id: str
    is_owner: bool
    billing_info: BillingInfo
    status: str  # created, creating, destroying
    buckets: List[SharedBucketResponse]
    service_errors: List[ServiceErrorResponse]


class SharedWorkspaceListResponse(TypedDict):
    """Response from GET /api/shared-workspaces endpoint."""
    shared_workspaces: List[SharedWorkspaceResponse]


class SingleSharedWorkspaceResponse(TypedDict):
    """Response from GET /api/shared-workspaces/{id} endpoint."""
    shared_workspace: SharedWorkspaceResponse


# Union types for different API response patterns
APIWorkspaceData = Union[WorkspaceListResponse, SingleWorkspaceResponse]
APISharedWorkspaceData = Union[SharedWorkspaceListResponse, SingleSharedWorkspaceResponse]

# Type aliases for commonly used response data
RawWorkspacesData = List[WorkspaceResponse]
RawSharedWorkspacesData = List[SharedWorkspaceResponse]
RawWorkbenchesData = List[WorkbenchResponse]
RawServiceErrorsData = List[ServiceErrorResponse]