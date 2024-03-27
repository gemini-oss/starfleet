"""Tests for the GitHubSyncerWorker backend logic

This tests the backend logic that the worker relies upon.

:Module: starfleet.tests.starfleet_included_plugins.github_sync.test_utils
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

# pylint: disable=unused-argument
import os
from typing import Any, Dict, Set
from unittest import mock
from zipfile import ZipFile

import pytest
from botocore.client import BaseClient


def test_download_repo(downloaded_repo: None, temp_directory: str) -> None:
    """This tests that we are able to download and save the repo to disk. The successful code is run in the `downloaded_repo` fixture."""
    from starfleet.worker_ships.plugins.github_sync.utils import download_repo, InvalidResponseFromGitHubError

    # Open the file and verify that it's correct (created by fixture):
    with ZipFile(f"{temp_directory}/myrepo.zip", "r") as file:
        assert len(file.filelist) == 4  # If you add more files to `test_files/` then you need to update this number

    # With a repo that doesn't exist:
    with pytest.raises(InvalidResponseFromGitHubError):
        download_repo("fakeorg", "1234567", "987654", "badrepo", "main", temp_directory)  # pylint: disable=too-many-function-args


def test_extract_repo(downloaded_repo: None, temp_directory: str) -> None:
    """This tests that we can properly extract the downloaded repo."""
    from starfleet.worker_ships.plugins.github_sync.utils import extract_repo

    extracted_dir = extract_repo(temp_directory, "myrepo")

    # Verify everything is correct by walking the OS path and verifying that it's the same as the path that we have in the test directory. First get what's in our test dir:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    local_file_paths = set()
    for root, _, files in os.walk(f"{current_dir}/test_files/"):
        local_file_paths.update({os.path.relpath(os.path.join(root, file), os.path.join(root, "..")).replace("test_files/", "") for file in files})
    assert local_file_paths

    # Next get what's in our extracted path:
    target_file_paths = set()
    for root, _, files in os.walk(f"{temp_directory}/{extracted_dir}"):
        target_file_paths.update({os.path.relpath(os.path.join(root, file), os.path.join(root, "..")).replace(f"{extracted_dir}/", "") for file in files})

    # All file paths should be the same:
    assert target_file_paths == local_file_paths


def test_extract_empty_repo(temp_directory: str, random_commit_hash: str) -> None:
    """This is going to test that we properly raise an Exception if we have an empty zip file."""
    from starfleet.worker_ships.plugins.github_sync.utils import extract_repo, EmptyZipFileError

    # Create an empty zip file:
    with ZipFile(f"{temp_directory}/myrepo.zip", "w"):
        pass

    with pytest.raises(EmptyZipFileError):
        extract_repo(temp_directory, "myrepo")


def test_match_path() -> None:
    """Tests the regex matching logic for path matching."""
    from starfleet.worker_ships.plugins.github_sync.utils import match_path

    regex_strings = [r"^.+\.yaml$", r"^some/path/that/ends/in/.+\.json$", "exact-match.zip"]

    assert not match_path("some/file/that/ends/in/filename.txt", regex_strings)
    assert match_path("some/file/that/ends/in.yaml", regex_strings)
    assert match_path("some/path/that/ends/in/something.json", regex_strings)
    assert not match_path("some.json", regex_strings)
    assert match_path("exact-match.zip", regex_strings)

    # Now verify all paths -- this is the default regex string used in the schema (or it should be anyway):
    regex_strings = [r"^.+$"]
    assert match_path("anything /goes/here.yaml.json.txt.zip", regex_strings)


def test_generate_s3_hash(temp_directory: str) -> None:
    """Tests that we get a proper MD5 checksum for a files. This will check the MD5 checksum for the test_files/file_two.yaml file."""
    from starfleet.worker_ships.plugins.github_sync.utils import generate_s3_hash

    file_path = f"{os.path.dirname(os.path.abspath(__file__))}/test_files/file_two.yaml"

    # NOTE: If you change this file, you need to re-run `md5sum file_two.yaml` to get this value:
    file_md5 = "fbe749e86ade4493006d621f099d8005"
    assert generate_s3_hash(file_path) == file_md5

    # Test the 4MB looping part by creating an empty 8MB temporary file, and then verifying the checksum for it:
    empty_file_md5 = "96995b58d4cbf6aaa9041b4f00c7f6ae"  # Created an emtpy file with `dd if=/dev/zero of=./emptyfile bs=4M count=2 && md5sum ./emptyfile`
    with open(f"{temp_directory}/emptyfile", "wb") as file:
        eight_mb = bytes([0] * 1024 * 1024 * 8)
        file.write(eight_mb)

    assert generate_s3_hash(f"{temp_directory}/emptyfile") == empty_file_md5


def test_collect_files_for_diff(local_diffed_files: Dict[str, Any]) -> None:
    """This is going to go through the local files and build the checksum report. This also tests out the fixture that runs the function."""
    from starfleet.worker_ships.plugins.github_sync.utils import collect_files_for_diff

    assert len(local_diffed_files) == 4  # NOTE: If you add more files to the `test_files` dir you need to update this number.
    # NOTE: If you change this file, you need to re-run `md5sum file_two.yaml` to get this value.
    assert local_diffed_files["file_two.yaml"] == "fbe749e86ade4493006d621f099d8005"

    # Now, let's test the exclusion logic:
    # Exclude all .txt and .json files:
    dir_path = f"{os.path.dirname(os.path.abspath(__file__))}/test_files"
    exclude_repo_paths = [r"^.+\.json$", r"^.+\.txt$"]
    files = collect_files_for_diff(dir_path, [r"^.+$"], exclude_repo_paths)
    assert len(files) == 2  # NOTE: If you add more files to the `test_files` dir you may need to update this number.
    for file in files:
        assert file.endswith(".yaml")


def test_collect_s3_files_for_diff(aws_s3: BaseClient) -> None:
    """This will test the collection of data from S3."""
    from starfleet.worker_ships.plugins.github_sync.utils import collect_s3_files_for_diff

    # With no files in there:
    assert not collect_s3_files_for_diff("some-bucket", aws_s3)

    # Put some fake files on the bucket first:
    object_map = {"file1": "file1", "file2": "file2", "some/path/file3": "file3", "some/path/with/more/nested/file4": "file4"}
    for key, value in object_map.items():
        aws_s3.put_object(Bucket="some-bucket", Key=key, Body=value)
    s3_files = collect_s3_files_for_diff("some-bucket", aws_s3)
    assert len(s3_files) == len(object_map)

    # with a `some/path` base prefix:
    s3_files = collect_s3_files_for_diff("some-bucket", aws_s3, key_prefix="some/path/")
    assert len(s3_files) == 2
    assert "file3" in s3_files
    assert "with/more/nested/file4" in s3_files


def test_get_content_type() -> None:
    """Quickly test the content-type fetching."""
    from starfleet.worker_ships.plugins.github_sync.utils import get_content_type

    # Some we know of:
    assert get_content_type("myfile.json") == "application/json"
    assert get_content_type("python/is/better/than.js") == "text/javascript"
    assert get_content_type("this/path.has.multiple.yaml.dots.yaml") == "application/yaml"

    # We don't know:
    assert get_content_type("some_random_file.pewpewpew") == "binary/octet-stream"


def test_upload_to_s3(aws_s3: BaseClient, local_diffed_files: Dict[str, Any]) -> None:
    """Tests uploading local files to the S3 bucket."""
    from starfleet.worker_ships.plugins.github_sync.utils import get_content_type, upload_to_s3

    dir_path = f"{os.path.dirname(os.path.abspath(__file__))}/test_files"
    upload_to_s3("some-bucket", dir_path, list(local_diffed_files.keys()), aws_s3)

    # Check that they are there:
    results = aws_s3.list_objects_v2(Bucket="some-bucket")
    assert len(results["Contents"]) == len(local_diffed_files)
    for result in results["Contents"]:
        assert result["Key"] in local_diffed_files
        assert aws_s3.head_object(Bucket="some-bucket", Key=result["Key"])["ContentType"] == get_content_type(result["Key"])

    # With a different prefix:
    upload_to_s3("some-bucket", dir_path, list(local_diffed_files.keys()), aws_s3, key_prefix="a/different/prefix/")
    results = aws_s3.list_objects_v2(Bucket="some-bucket", Prefix="a/different/prefix/")
    for result in results["Contents"]:
        assert result["Key"].split("a/different/prefix/")[1] in local_diffed_files
        assert aws_s3.head_object(Bucket="some-bucket", Key=result["Key"])["ContentType"] == get_content_type(result["Key"])


def test_diff_local_with_s3(aws_s3: BaseClient, local_diffed_files: Dict[str, Any]) -> None:
    """This will test the diffing logic."""
    from starfleet.worker_ships.plugins.github_sync.utils import collect_s3_files_for_diff, diff_local_with_s3, upload_to_s3

    # Run for the first time with nothing in the S3 bucket - which would be {} for the s3 files:
    missing_files, different_files = diff_local_with_s3(local_diffed_files, {})
    assert not different_files
    assert sorted(missing_files) == sorted(local_diffed_files.keys())

    # Upload the files to S3:
    dir_path = f"{os.path.dirname(os.path.abspath(__file__))}/test_files"
    upload_to_s3("some-bucket", dir_path, list(local_diffed_files.keys()), aws_s3)
    s3_files = collect_s3_files_for_diff("some-bucket", aws_s3)

    # Compare - nothing should be different:
    assert diff_local_with_s3(local_diffed_files, s3_files) == ([], [])
    assert not s3_files

    # Throw an extra file in there and mutate another one:
    aws_s3.put_object(Bucket="some-bucket", Key="some-extra-file", Body="some-extra-file")
    aws_s3.put_object(Bucket="some-bucket", Key="file_two.yaml", Body="old contents")
    s3_files = collect_s3_files_for_diff("some-bucket", aws_s3)
    assert diff_local_with_s3(local_diffed_files, s3_files) == ([], ["file_two.yaml"])
    assert len(s3_files) == 1
    assert "some-extra-file" in s3_files


def test_delete_from_s3(aws_s3: BaseClient, excess_files: Set[str]) -> None:
    """This tests that our logic for s3 item deletion is correct. This needs to ensure that we batch properly."""
    from starfleet.worker_ships.plugins.github_sync.utils import delete_from_s3

    # Add a lot more objects to the bucket so that we have 2010 additional objects in there at a different prefix:
    for item in range(0, 2000):
        excess_files.add(f"some/other/path/{item}")
        aws_s3.put_object(Bucket="some-bucket", Key=f"some/other/path/{item}", Body=f"{item}")

    # Add 5 objects in a prefix that is also unique (this will test the key prefix logic)
    unique_files = []
    for item in range(0, 5):
        excess_files.add(f"some/unique/path/{item}")
        unique_files.append(f"{item}")
        aws_s3.put_object(Bucket="some-bucket", Key=f"some/unique/path/{item}", Body=f"{item}")

    # Delete from the "unique" path:
    delete_from_s3("some-bucket", unique_files, aws_s3, key_prefix="some/unique/path/")

    # Verify that nothing is in the unique path:
    assert not aws_s3.list_objects_v2(Bucket="some-bucket", Prefix="some/unique").get("Contents")

    # Verify that the other objects are OK:
    assert aws_s3.list_objects_v2(Bucket="some-bucket").get("Contents")

    # Delete all the objects (tests out the batching):
    with mock.patch("starfleet.worker_ships.plugins.github_sync.utils.LOGGER") as mocked_logger:
        delete_from_s3("some-bucket", list(excess_files), aws_s3)

    # Nothing should be left:
    assert not aws_s3.list_objects_v2(Bucket="some-bucket").get("Contents")

    # Verify that we batched (3 batches: 1000/batch, and 10 + 2000 ==> 2010 items, so 3 batches):
    last_calls = mocked_logger.debug.call_args_list[-3:]
    assert len(last_calls) == 3
    for index, call in enumerate(last_calls, start=1):
        assert call[0][0] == f"[🎆] Deleting batch: {index}..."
