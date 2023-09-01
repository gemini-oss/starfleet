"""Starfleet's worker for syncing a GitHub repository contents to S3

This is a worker ship that will periodically verify that a GitHub repository's contents are identical to that
of an S3 bucket. It will add, remove, and update any file in S3 that is not in the corresponding GitHub repo.

This is primarily used for syncing Starfleet templates to S3 for CI/CD, but can be used for any other purpose.

:Module: starfleet.worker_ships.plugins.github_sync.ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=too-many-locals,too-many-statements
import json
import tempfile
from typing import Dict, Any, Optional, TypeVar

import boto3
import click
from click import Context
from marshmallow import fields, validate

from starfleet.utils.logging import LOGGER
from starfleet.utils.niceties import get_all_regions
from starfleet.worker_ships.base_payload_schemas import WorkerShipPayloadBaseTemplate
from starfleet.worker_ships.cli_utils import StarfleetSingleInvokeCommand
from starfleet.worker_ships.lambda_utils import worker_lambda
from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip, AlertPriority
from starfleet.worker_ships.plugins.github_sync.auth import GITHUB_AUTH_MANGER
from starfleet.worker_ships.plugins.github_sync.utils import (
    collect_files_for_diff,
    collect_s3_files_for_diff,
    diff_local_with_s3,
    download_repo,
    extract_repo,
    upload_to_s3,
    delete_from_s3,
)


class GitHubSyncPayloadTemplate(WorkerShipPayloadBaseTemplate):
    """The payload for the GitHubSyncWorker."""

    organization = fields.String(required=True, data_key="Organization")
    repository = fields.String(required=True, data_key="Repository")
    branch_name = fields.String(required=True, data_key="BranchName")
    github_app_id = fields.String(required=True, data_key="GitHubAppId")
    github_installation_id = fields.String(required=True, data_key="GitHubInstallationId")
    bucket_name = fields.String(required=True, data_key="BucketName")
    bucket_region = fields.String(required=True, validate=validate.OneOf(get_all_regions(service="s3")), data_key="BucketRegion")
    extract_zip_contents = fields.Boolean(required=True, data_key="ExtractZipContents")

    # Optionals
    include_repo_paths = fields.List(fields.String, required=False, load_default=[r"^.+$"], data_key="IncludeRepoPaths")  # Default is for all paths
    exclude_repo_paths = fields.List(fields.String, required=False, load_default=[], data_key="ExcludeRepoPaths")
    key_prefix = fields.String(required=False, data_key="KeyPrefix")
    delete_missing_files = fields.Boolean(required=False, load_default=False, data_key="DeleteMissingFiles")


class GitHubSyncWorkerShip(StarfleetWorkerShip):
    """
    This is a worker that will periodically sync the contents of a GitHub repository to S3.

    This will use the Base Configuration template as there isn't really much to configure. This will, however, need to make use of the SecretsManager singleton to
    obtain the GitHub application private key.
    """

    payload_template_class = GitHubSyncPayloadTemplate

    def execute(self, commit: bool = False) -> None:
        """Execute the payload to sync the given repo to S3."""
        # Step 1: Get the required components from the payload:
        organization = self.payload["organization"]
        app_id = self.payload["github_app_id"]
        installation_id = self.payload["github_installation_id"]
        directory = self.payload["dir_path"]
        repo = self.payload["repository"]
        branch = self.payload["branch_name"]

        # Step 2: Download the repo:
        download_repo(organization, app_id, installation_id, repo, branch, directory)  # pylint: disable=too-many-function-args

        # Step 3: If we have it configured to extract the zip contents, then we need to extract the contents:
        if self.payload["extract_zip_contents"]:
            extracted_directory = extract_repo(directory, repo)
            directory += f"/{extracted_directory}"  # Update the path of the files to diff to the extracted path

        # If we are just downloading (CLI) and doing nothing more, then we are done:
        if self.payload.get("download_only"):
            return

        # Step 4: Collect what we have locally and what's in S3:
        include_repo_paths = self.payload["include_repo_paths"]
        exclude_repo_paths = self.payload["exclude_repo_paths"]
        bucket = self.payload["bucket_name"]
        bucket_region = self.payload["bucket_region"]
        key_prefix = self.payload.get("key_prefix")
        local_files = collect_files_for_diff(directory, include_repo_paths, exclude_repo_paths)
        s3_client = boto3.client("s3", region_name=bucket_region)
        s3_files = collect_s3_files_for_diff(bucket, s3_client, key_prefix=key_prefix)

        # Step 5: Perform a diff of what we have locally with what's in S3 - after this, s3_files will contain leftover for deletion if present
        missing_files, different_files = diff_local_with_s3(local_files, s3_files)

        # Step 6: Upload the files that need to be uploaded (if commit):
        upload_files = missing_files + different_files
        delete_files = list(s3_files.keys())
        if commit:
            alert_message = ""
            if upload_files or delete_files:
                alert_message += f"Starfleet's GitHub -> S3 sync job: {self.payload['template_name']} has made the following changes:\n\n"

            if upload_files:
                if missing_files:
                    alert_message += "> *🆕  The following new files were uploaded:*\n>```\n"
                    alert_message += "\n".join([f" - {missing}" for missing in missing_files])
                    alert_message += "\n```\n\n"

                if different_files:
                    alert_message += "> *✨  The following modified files were uploaded:*\n>```\n"
                    alert_message += "\n".join([f" - {different}" for different in different_files])
                    alert_message += "\n```\n\n"

                LOGGER.info(f"[🪣] Uploading {len(upload_files)} file(s) to S3...")
                upload_to_s3(bucket, directory, upload_files, s3_client, key_prefix=key_prefix)
            else:
                LOGGER.info("[🆗] No new or modified files to upload to S3.")

            # Step 7: Delete the excess (if enabled and if commit)
            if self.payload["delete_missing_files"] and delete_files:
                alert_message += "> *🗑  The following files have been deleted:*\n>```\n"
                alert_message += "\n".join([f" - {remove}" for remove in delete_files])
                alert_message += "\n```"

                LOGGER.info(f"[🗑️] Deleting {len(delete_files)} file(s) from S3...")
                delete_from_s3(bucket, delete_files, s3_client, key_prefix=key_prefix)
            else:
                LOGGER.info("[🆗] No files to delete.")

            if alert_message:
                self.send_alert(AlertPriority.IMPORTANT, f"Starfleet GitHub -> S3 Sync Job for {self.payload['template_name']}", alert_message)

        else:
            LOGGER.info("[⏭️] Commit is not enabled so not doing anything.")


@click.group()
@click.pass_context
def sync_github(ctx: Context) -> None:
    """This is the worker ship for syncing a GitHub repo with S3."""
    ctx.obj = GitHubSyncWorkerShip()


@sync_github.command(cls=StarfleetSingleInvokeCommand)
@click.pass_context
def get_installation_token(ctx: Context, **kwargs) -> None:  # noqa # pylint: disable=unused-argument
    """
    This returns the installation token for the given organization, application id, and installation id provided in the payload template.
    This is mostly used for local testing and debugging.
    """
    # Get the app ID and the installation ID out of the payload:
    worker = ctx.obj
    organization = worker.payload["organization"]
    app_id = worker.payload["github_app_id"]
    installation_id = worker.payload["github_installation_id"]

    # Get the token:
    token = GITHUB_AUTH_MANGER.authenticate(organization, app_id, installation_id)
    LOGGER.info(f"[🔑] Starfleet installation token header for organization: {organization}: {token}")


@sync_github.command(cls=StarfleetSingleInvokeCommand)
@click.pass_context
@click.option("--save-dir", type=click.Path(exists=True), required=True, help="A local directory to save the zip in.")
def download(ctx: Context, save_dir: str, **kwargs) -> None:  # noqa # pylint: disable=unused-argument
    """
    This is a helpful debugging command to download the repository. This will extract the contents if the payload specifies the `ExtractZipContents` flag set to `True`.
    You simply provide the payload template and the location for where you want the repo to be downloaded (and optionally extracted),
    and it will be saved to that path as `REPO_NAME.zip` (and extracted as `REPO_NAME-COMMIT-HASH/`).

    The commit flag doesn't do anything for this command.
    """
    # Get the app ID and the installation ID out of the payload:
    worker = ctx.obj

    # Shove the path into the payload:
    worker.payload["dir_path"] = save_dir

    # This command will NOT extract the zip contents or do any additional work:
    worker.payload["download_only"] = True

    # Run it. This will not delete
    worker.execute()

    LOGGER.info("[✅] Done!")


@sync_github.command(cls=StarfleetSingleInvokeCommand)
@click.pass_context
@click.option(
    "--save-dir",
    type=click.Path(exists=True),
    required=False,
    help="An optional local directory to save and retain the contents within. " "If not supplied, then this will create a temporary directory and delete it.",
)
def run(ctx: Context, commit: bool, save_dir: Optional[str] = None, **kwargs) -> None:  # noqa # pylint: disable=unused-argument
    """This will run the syncing of the repository against the payload's specified S3 bucket."""
    if not commit:
        LOGGER.warning("[⚠️] Commit flag is disabled: not writing anything to S3!")

    # If we did not get a save directory provided, then we are going to create a temporary one:
    temp_dir = tempfile.TemporaryDirectory() if not save_dir else None  # pylint: disable=consider-using-with
    working_directory = save_dir or temp_dir.name

    try:
        worker = ctx.obj
        worker.payload["dir_path"] = working_directory
        worker.execute(commit=commit)

    finally:
        if temp_dir:
            temp_dir.cleanup()

    LOGGER.info("[✅] Done!")


GitHubSyncWorkerShipInstance = TypeVar("GitHubSyncWorkerShipInstance", bound=GitHubSyncWorkerShip)


@worker_lambda(GitHubSyncWorkerShip)
def lambda_handler(event: Dict[str, Any], context: object, worker: GitHubSyncWorkerShipInstance, commit: bool) -> None:  # noqa pylint: disable=W0613
    """This is the Lambda entrypoint for the GitHubSyncWorkerShip event from the Starbase."""
    for record in event["Records"]:
        # Load the payload:
        payload = json.loads(record["body"])
        LOGGER.debug(f"[⚙️] Processing Payload: {payload}")
        worker.load_template(payload)

        # Make the temporary directory:
        with tempfile.TemporaryDirectory() as temp_dir_path:
            worker.payload["dir_path"] = temp_dir_path

            # Process it!
            worker.execute(commit=commit)
            LOGGER.info("[✅] Done!")

    LOGGER.info("[🏁] Completed syncing GitHub repository to S3.")
