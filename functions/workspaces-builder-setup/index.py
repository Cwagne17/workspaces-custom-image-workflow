import logging
import boto3
import os
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

workspaces_client = boto3.client("workspaces")
ssm_client = boto3.client("")

workspaces_directory_ssm_parameter = "/developer-environment-platform/ds/directory_id"


def get_ssm_parameter(parameter_name):
    """
    Retrieve the value of an SSM parameter.
    """
    ssm_client = boto3.client("")
    try:
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        logger.error(f"Error retrieving SSM parameter {parameter_name}: {e}")
        return None


def lambda_handler(event: dict, context):
    # Custom Workspace Builder Error
    def workspace_error(message):
        logger.error(message)
        return {
            "statusCode": 400,
            "body": message,
        }

    logger.info("Beginning execution of Workspaces_Builder_Setup function.")

    # Create random hash for the automation execution
    execution_suffix = os.urandom(8).hex()
    logger.info(
        f"Execution suffix being used throughout the automation: {execution_suffix}"
    )

    # Retrieve starting parameters from event data
    # If parameter not found, inject default values defined in Lambda function
    directory_id = event.get(
        "DirectoryId",
        os.environ["DirectoryId"],
        get_ssm_parameter(workspaces_directory_ssm_parameter),
    )
    if not directory_id:
        return workspace_error(
            "DirectoryId not found in event, environment variables, or SSM parameter store."
        )

    bundle_id = event.get("BundleId", os.environ["BundleId"])
    if not bundle_id:
        return workspace_error(
            "BundleId not found in event, environment variables, or SSM parameter store."
        )

    # Check that the directory ID is registerd with Workspaces
    try:
        response = workspaces_client.describe_workspace_directories(
            DirectoryIds=[directory_id],
        )
        if not response["Directories"] or len(response["Directories"]) == 0:
            return workspace_error(
                f"Directory ID {directory_id} not found in Workspaces."
            )

        directory_state = response["Directories"][0]["State"]
        if directory_state != "REGISTERED":
            return workspace_error(
                f"Directory ID {directory_id} is not registered with Workspaces: {directory_state}."
            )

        logger.info(
            f"Directory ID {directory_id} is registered with Workspaces: {directory_state}."
        )
        directory_id = response["Directories"][0]["DirectoryId"]
    except Exception as e:
        return workspace_error(f"Error describing workspace directory: {e}")

    # Describe the data access of the directory
    try:
        response = boto3.client("directoryservice").describe_directory_data_access(
            DirectoryId=directory_id,
        )

        # If the directory is not enabled for data access, return an error
        data_access_status = response.get("DataAccessStatus")
        if data_access_status != "Enabled":
            return workspace_error(
                f"Directory ID {directory_id} is not enabled for data access: {data_access_status}"
            )
    except Exception as e:
        return workspace_error(f"Error describing directory data access: {e}")

    # Create workspace
    try:
        response = workspaces_client.create_workspaces(
            Workspaces=[
                {
                    "DirectoryId": directory_id,
                    "UserName": image_builder_user,
                    "BundleId": bundle_id,
                    "UserVolumeEncryptionEnabled": False,
                    "RootVolumeEncryptionEnabled": False,
                    "WorkspaceProperties": {
                        "RunningMode": "AUTO_STOP",
                    },
                    "Tags": [
                        {"Key": "Automated", "Value": "True"},
                    ],
                },
            ]
        )

        logger.info(response)
        image_builder_workspace_id = response["PendingRequests"][0]["WorkspaceId"]

        logger.info(
            "WorkSpace creation in progress for, %s.", image_builder_workspace_id
        )
    except Exception as e:
        logger.error(e)
        logger.info("Unable to deploy WorkSpace for image creation.")
        image_builder_workspace_id = "FAILED"

    # Generate full image name using image name prefix and timestamp
    now = datetime.now()
    dt_string = now.strftime("-%Y-%m-%d-%H-%M")
    ImageName = ImageNamePrefix + dt_string
    BundleName = BundleNamePrefix + dt_string

    return {
        "AutomationParameters": {
            "ImageBuilderUser": ImageBuilderUser,
            "ImageBuilderWorkSpaceId": image_builder_workspace_id,
            "ImageBuilderDirectory": image_builder_directory,
            "ImageBuilderBundleId": image_builder_bundle_id,
            "ImageBuilderProtocol": image_builder_protocol,
            "ImageBuilderRootVolumeSize": image_builder_root_volume_size,
            "ImageBuilderUserVolumeSize": image_builder_user_volume_size,
            "ImageBuilderComputeType": image_builder_compute_type,
            "ImageBuilderSecurityGroup": image_builder_security_group,
            "DeleteBuilder": delete_builder,
            "ImageBuilderAPI": image_builder_api,
            "DisableAPI": disable_api,
            "ImageNamePrefix": ImageNamePrefix,
            "ImageName": ImageName,
            "ImageDescription": ImageDescription,
            "ImageTags": ImageTags,
            "ImageNotificationARN": ImageNotificationARN,
            "ImageBuilderIdArray": {"WorkspaceId": ImageBuilderWorkSpaceId},
            "CreateBundle": CreateBundle,
            "BundleNamePrefix": BundleNamePrefix,
            "BundleName": BundleName,
            "BundleDescription": BundleDescription,
            "BundleComputeType": {"Name": BundleComputeType},
            "BundleRootVolumeSize": {"Capacity": BundleRootVolumeSize},
            "BundleUserVolumeSize": {"Capacity": BundleUserVolumeSize},
            "BundleTags": BundleTags,
            "SoftwareS3Bucket": SoftwareS3Bucket,
            "InstallRoutine": InstallRoutine,
            "SkipWindowsUpdates": SkipWindowsUpdates,
            "PreExistingBuilder": PreExistingBuilder,
        }
    }
