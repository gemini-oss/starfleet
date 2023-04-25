"""Tests for the GitHub Sync worker itself

Tests out that the worker and CLIs are all working properly.

:Module: starfleet.tests.starfleet_included_plugins.github_sync.test_ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument,too-many-arguments,too-many-locals
import json
import os
from io import BytesIO
from typing import Any, Dict, Set
from unittest import mock

from unittest.mock import MagicMock

import pytest
import yaml
from botocore.client import BaseClient
from click.testing import CliRunner
from tests.starfleet_included_plugins.github_sync.conftest import WrappedTempDir


def test_github_auth_cli(mock_installation_token: MagicMock) -> None:
    """This tests the CLI for getting the GitHub Installation Token back out."""
    from starfleet.worker_ships.plugins.github_sync.ship import sync_github

    with mock.patch("starfleet.worker_ships.plugins.github_sync.ship.LOGGER") as mocked_logger:
        runner = CliRunner()
        payload_file = f"{os.path.dirname(os.path.abspath(__file__))}/test_payload.yaml"
        runner.invoke(sync_github, ["get-installation-token", "--payload", payload_file])  # noqa
        assert (
            mocked_logger.info.call_args.args[0]
            == "[🔑] Starfleet installation token header for organization: fakeorg: {'Authorization': 'Bearer lolsometoken'}"
        )


@pytest.mark.parametrize("commit", [False, True])
def test_download_only_cli(
    commit: bool, mock_installation_token: MagicMock, mock_github: MagicMock, temp_directory: str, aws_s3: BaseClient, random_commit_hash: str
) -> None:
    """This tests the download only CLI"""
    from starfleet.worker_ships.plugins.github_sync.ship import sync_github

    runner = CliRunner()
    payload_file = f"{os.path.dirname(os.path.abspath(__file__))}/test_payload.yaml"
    args = ["download", "--payload", payload_file, "--save-dir", temp_directory]
    result = runner.invoke(sync_github, args)  # noqa

    assert result.exit_code == 0

    # Verify that we did not touch the S3 bucket:
    assert not aws_s3.list_objects_v2(Bucket="some-bucket").get("Contents", [])

    # Grab a list of all the files that are on disk. These should be the same as the files that we have in our unit test directory.
    downloaded_extracted_files = set()
    for root, _, files in os.walk(f"{temp_directory}"):
        for file in files:
            # Strip out the temporary directory path. We should see "/myrepo-COMMIT-HASH/..." in for all the files except the .zip
            downloaded_extracted_files.add(f"{root}/{file}".replace(f"{temp_directory}/", "").replace(f"myrepo-{random_commit_hash}/", ""))

    # Get the list in our unit test files, and begin the comparison:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    local_file_paths = set()
    for root, _, files in os.walk(f"{current_dir}/test_files/"):
        local_file_paths.update({os.path.relpath(os.path.join(root, file), os.path.join(root, "..")).replace("test_files/", "") for file in files})

    # Begin the comparison:
    for file in local_file_paths:
        downloaded_extracted_files.remove(file)

    # The only thing that should remain is the .zip:
    assert downloaded_extracted_files == {"myrepo.zip"}


def confirm_common_things(commit: bool, aws_s3: BaseClient, excess_files: Set[str]) -> bool:
    """This is common code that performs verification for a variety of unit tests for this worker ship."""
    if not commit:
        items = {item["Key"] for item in aws_s3.list_objects_v2(Bucket="some-bucket").get("Contents", [])}
        assert items == excess_files
    else:
        items = {item["Key"] for item in aws_s3.list_objects_v2(Bucket="some-bucket").get("Contents", [])}
        current_dir = os.path.dirname(os.path.abspath(__file__))
        local_file_paths = set()
        for root, _, files in os.walk(f"{current_dir}/test_files/"):
            local_file_paths.update({os.path.relpath(os.path.join(root, file), os.path.join(root, "..")).replace("test_files/", "") for file in files})
        assert local_file_paths == items

    return True


@pytest.mark.parametrize("commit", [False, True])
def test_run_cli_wrapped_dir(commit: bool, aws_s3: BaseClient, mock_installation_token: MagicMock, mock_github: MagicMock, excess_files: Set[str]) -> None:
    """
    This will test the CLI for performing the repo sync operation in but with no supplied download directory. The temporary directory should be created and
    cleaned up properly.
    """
    from starfleet.worker_ships.plugins.github_sync.ship import sync_github

    runner = CliRunner()

    # We are first going to run by not supplying a save directory.  This should automatically clear things up. We are going to mock out and wrap the tempfile package
    # to ensure and assert that it was called properly.
    mocked_temp_dir = WrappedTempDir()
    with mock.patch("starfleet.worker_ships.plugins.github_sync.ship.tempfile.TemporaryDirectory", return_value=mocked_temp_dir):
        payload_file = f"{os.path.dirname(os.path.abspath(__file__))}/test_payload.yaml"

        args = ["run", "--payload", payload_file]
        if commit:
            args.append("--commit")

        result = runner.invoke(sync_github, args)  # noqa

    assert result.exit_code == 0
    assert mocked_temp_dir.cleanup_called
    assert not list(os.walk(f"{mocked_temp_dir.name}"))  # Nothing should return since cleanup was called which deletes this

    assert confirm_common_things(commit, aws_s3, excess_files)


@pytest.mark.parametrize("commit", [False, True])
def test_run_cli_supplied_dir(
    commit: bool,
    aws_s3: BaseClient,
    mock_installation_token: MagicMock,
    mock_github: MagicMock,
    temp_directory: str,
    excess_files: Set[str],
    random_commit_hash: str,
) -> None:
    """
    This will test the CLI for performing the repo sync operation in but with a supplied download directory. The directory should not have contents deleted.
    """
    from starfleet.worker_ships.plugins.github_sync.ship import sync_github

    runner = CliRunner()

    # In this
    payload_file = f"{os.path.dirname(os.path.abspath(__file__))}/test_payload.yaml"
    args = ["run", "--payload", payload_file, "--save-dir", temp_directory]
    if commit:
        args.append("--commit")

    result = runner.invoke(sync_github, args)  # noqa
    assert result.exit_code == 0

    # Grab a list of all the files that are on disk. These should be the same as the files that we have in our unit test directory.
    downloaded_extracted_files = set()
    for root, _, files in os.walk(f"{temp_directory}"):
        for file in files:
            # Strip out the temporary directory path. We should see "/myrepo-COMMIT-HASH/..." in for all the files except the .zip
            downloaded_extracted_files.add(f"{root}/{file}".replace(f"{temp_directory}/", "").replace(f"myrepo-{random_commit_hash}/", ""))

    # Get the list in our unit test files, and begin the comparison:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    local_file_paths = set()
    for root, _, files in os.walk(f"{current_dir}/test_files/"):
        local_file_paths.update({os.path.relpath(os.path.join(root, file), os.path.join(root, "..")).replace("test_files/", "") for file in files})

    # Begin the comparison:
    for file in local_file_paths:
        downloaded_extracted_files.remove(file)

    # The only thing that should remain is the .zip:
    assert downloaded_extracted_files == {"myrepo.zip"}

    # And confirm the rest...
    assert confirm_common_things(commit, aws_s3, excess_files)


@pytest.mark.parametrize("commit", [False, True])
@pytest.mark.parametrize("extract_zip", [False, True])
@pytest.mark.parametrize("delete_missing", [False, True])
def test_lambda(
    commit: bool,
    extract_zip: bool,
    delete_missing: bool,
    aws_s3: BaseClient,
    mock_installation_token: MagicMock,
    mock_github: MagicMock,
    excess_files: Set[str],
    test_configuration: Dict[str, Any],
    zip_repo: BytesIO,
) -> None:
    """This will test out the lambda invocation across a variety of scenarios."""
    from starfleet.worker_ships.plugins.github_sync.ship import lambda_handler

    if commit:
        os.environ["STARFLEET_COMMIT"] = "true"

    # Load the base template:
    payload_file = f"{os.path.dirname(os.path.abspath(__file__))}/test_payload.yaml"
    with open(payload_file, "r", encoding="UTF-8") as file:
        base_payload = yaml.safe_load(file.read())

    # Update the payload with the details:
    base_payload.update({"ExtractZipContents": extract_zip, "DeleteMissingFiles": delete_missing})

    # Run it:
    lambda_handler({"Records": [{"body": json.dumps(base_payload)}]}, object())  # pylint: disable=no-value-for-parameter

    # If we have commit mode, then we should see things in S3:
    if not commit:
        # Then nothing will be deleted or uploaded:
        assert confirm_common_things(False, aws_s3, excess_files)

    if commit:
        # If we are extracting files, and also deleting the excess then this confirmation will look like the others:
        if extract_zip and delete_missing:
            assert confirm_common_things(True, aws_s3, excess_files)

            # Run it again to confirm that we log out that we have nothing to do:
            zip_repo.seek(0)  # Need to reset the zip read for the mocked GitHub API
            with mock.patch("starfleet.worker_ships.plugins.github_sync.ship.LOGGER") as mocked_logger:
                lambda_handler({"Records": [{"body": json.dumps(base_payload)}]}, object())  # pylint: disable=no-value-for-parameter
            found = False
            for call in mocked_logger.info.call_args_list:
                if call[0][0] == "[🆗] No new or modified files to upload to S3.":
                    found = True
                    break
            assert found

        # If we are not extracting the files and not deleting anything:
        elif not extract_zip and not delete_missing:
            items = {item["Key"] for item in aws_s3.list_objects_v2(Bucket="some-bucket").get("Contents", [])}
            excess_files.add("myrepo.zip")
            assert items == excess_files

        # If we are extracting but not deleting:
        elif extract_zip and not delete_missing:
            items = {item["Key"] for item in aws_s3.list_objects_v2(Bucket="some-bucket").get("Contents", [])}
            current_dir = os.path.dirname(os.path.abspath(__file__))
            local_file_paths_with_excess = set()
            for root, _, files in os.walk(f"{current_dir}/test_files/"):
                local_file_paths_with_excess.update(
                    {os.path.relpath(os.path.join(root, file), os.path.join(root, "..")).replace("test_files/", "") for file in files}
                )
            local_file_paths_with_excess.update(excess_files)
            assert items == local_file_paths_with_excess

        # If we are not extracting but deleting:
        elif not extract_zip and delete_missing:
            items = {item["Key"] for item in aws_s3.list_objects_v2(Bucket="some-bucket").get("Contents", [])}
            assert items == {"myrepo.zip"}

    # Clean up the env var:
    os.environ.pop("STARFLEET_COMMIT", None)
