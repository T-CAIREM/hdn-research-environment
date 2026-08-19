class IdentityProvisioningFailed(Exception):
    pass


class StopEnvironmentFailed(Exception):
    pass


class StartEnvironmentFailed(Exception):
    pass


class DeleteEnvironmentFailed(Exception):
    pass


class ChangeEnvironmentInstanceTypeFailed(Exception):
    pass


class EnvironmentCreationFailed(Exception):
    pass


class BillingVerificationFailed(Exception):
    pass


class BillingSharingFailed(Exception):
    pass


class BillingAccessRevokationFailed(Exception):
    pass


class GetAvailableEnvironmentsFailed(Exception):
    pass


class GetUserInfoFailed(Exception):
    pass


class GetWorkspaceDetailsFailed(Exception):
    pass


class GetBillingAccountsListFailed(Exception):
    pass


class GetWorkspacesListFailed(Exception):
    pass


class CreateWorkspaceFailed(Exception):
    pass


class DeleteWorkspaceFailed(Exception):
    pass


class CreateSharedBucketFailed(Exception):
    pass


class DeleteSharedBucketFailed(Exception):
    pass


class BucketSharingFailed(Exception):
    pass


class BucketAccessRevokationFailed(Exception):
    pass


class GetWorkflowFailed(Exception):
    pass


class GenerateSignedUrlFailed(Exception):
    pass


class GetSharedBucketContentFailed(Exception):
    pass


class CreateSharedBucketDirectoryFailed(Exception):
    pass


class DeleteSharedBucketContentFailed(Exception):
    pass


class InvitedUserIsAccountOwner(Exception):
    pass


class CreateCloudGroupFailed(Exception):
    pass


class DeleteCloudGroupFailed(Exception):
    pass


class ListGroupRolesFailed(Exception):
    pass


class GetGroupIAMRolesFailed(Exception):
    pass


class AddRolesToCloudGroupFailed(Exception):
    pass


class RemoveRolesFromCloudGroupFailed(Exception):
    pass


class GetGroupsIAMRolesFailed(Exception):
    pass


class GetMonitoringDatasetsFailed(Exception):
    pass


class UpdateWorkspaceBillingAccountFailed(Exception):
    pass


class RemoveWorkbenchCollaboratorFailed(Exception):
    pass


class AddWorkbenchCollaboratorFailed(Exception):
    pass


class RenewEnvironmentCertificateFailed(Exception):
    pass


class PublishedProjectAccessFailed(Exception):
    pass


class GetSimplifiedWorkspaceFailed(Exception):
    pass


class GetSharedBucketFailed(Exception):
    pass


class GetSimplifiedWorkspaceFailed(Exception):
    pass


class GetSharedBucketFailed(Exception):
    pass


class InvalidApiResponse(Exception):
    """An API response that cannot be used as the expected success payload.

    Raised by ``environment.utilities.validated_json`` when a response has an
    error status or a body of the wrong shape; converted into the operation's
    domain exception by ``environment.decorators.handle_api_error``.
    """

    def __init__(self, response, reason: str):
        self.response = response
        self.reason = reason
        super().__init__(reason)
