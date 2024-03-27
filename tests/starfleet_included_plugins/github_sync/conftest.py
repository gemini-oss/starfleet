"""Pytest fixtures for the GitHub Sync worker ship

All the Pytest fixtures unique to the GitHub Sync worker

:Module: starfleet.tests.starfleet_included_plugins.github_sync.conftest
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

# pylint: disable=unused-argument,unused-import,redefined-outer-name
import base64
from io import BytesIO
import os
from datetime import datetime, timedelta
import tempfile
import random
import string
from typing import Any, Dict, Generator, Optional, Set
from unittest import mock
from unittest.mock import MagicMock
from zipfile import ZipFile

import boto3
import pytest
import yaml
from botocore.client import BaseClient
from moto import mock_s3

# NOTE: This is only for unit testing. This key is not used anywhere.
# This is a P Key that is only used for unit testing (not used anywhere else), and it's base64'd so that code scanning tools won't flip a table:
TEST_BASE64_GITHUB_KEY = (
    "LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQpNSUlFcEFJQkFBS0NBUUVBcE5rc1c0NGRHNGp2bEtqUmVYVFprdi81SHBDWG1ZcnV3c0dSVm5SSWdvb"
    "FVPdWd0CjdKUnJKYk5nbUhRTG8ycm9ka1puSHBwTWE2aEgwM0ZpUG1kY1hTZ1Zwc3JISzRhZUYyaTAya3A1N3F0b1FpZEcKU2VPbGZ5b3doUGVoaWU1ZWZGbm"
    "c0YlV2REZraU9qenFBRi9DMkl6Qkp2YzdydVU2Rzkycm9PT2ZBSnZ0Qnpyagp6dGNvVzVFTWxCbkxjOEpKVUpzZmdyY1Q5TzFraEpwOEpUSmtSTC9yMlJzVm0"
    "5K2N1Qjlhbm5yYXk2RkJsT3RlCmlIU2cvU3MwS2t1eUVrc2xSSU9BRWhNNzNYTmE1WEplVmRVSE9GaWh1Sm5jRTd0UDRoVFAwMW5KSWpDeGdKUkcKNXVndFBF"
    "eFRTYS9wUHB1WWkwcFRvWEczU3MvWmVhbTA4TWN4UXdJREFRQUJBb0lCQVFDSkVaOGxmWlJNV2Q5RQpEOThsaTNpQ0YxOHYvL0JlRmp5VEtkcE1OYUk1RURFK"
    "1RlSXByZnN0dk9vYnVab1h4b1FHSEdJUCt5S0IvY25EClVhcnIwb3ZsVmJnekdMYmxSU2pjdEE1MDE2cHRQbzhST3BEaVRXeEZ3WEhZamdMK3FucGNFV3ZBb1"
    "NPK3M3cVgKRENGU01FM1dPNnM3V0NXRE5rekw4TlNOa2RhYTdMWkwzUlI5bG52WkFZSXIxakxVWElsVkx3SjNoelowMzlHbQpqR3NaY05wQVpadmhrNEVyZGF"
    "KV1pYa3VwaHRRZW9UcVJyaDBWQ2M2VmlqTzNTYXdFd1IwQmtUQVdNUjBHZWFUCmZLVnRhd2x6Y3huaFBXdFpIRUVQYnhnMGhUa0U0N1VDaUtOaERMbkk4aWtF"
    "K0wzbmF2MEh1WWZvTVFzL0wrOXYKRGxVWkt3WjVBb0dCQU5EcEdvTk9TQS9oZlZpRmp6aWU4RTZSSFlOWnBBSThPbGQ4akdpZHdxNXN2RmVZalFOQwpTTGtCb"
    "UFrTERpY2I3ZkRuVzJzSEh3ZUo4KzBkekpVWkJoTHo5RFY2V0EwdjJ6ZC9ORVF4a2pza1poTldFcHRZClhuajloWGNrYnRISkhscTdjVnVNTENUc0hYdEJFYW"
    "gra1NwL1hNYVlzZWwyK0FQZEwvbk9HMG1sQW9HQkFNb0IKaFAwNmo2U3B3MSs3dzNBYlhJZXFnMTNUcTBlWWxXZXQ4ZmRMcmcvSWNpcEx4RlZDK1pHZUwyb1p"
    "IQ21BUU1CaQphczFHSEVPa09nN1g5eUdjQTUrUWxWYXNOT2pIaGxieWRCK0VBOW50K2hOdVhaSWRicUpUU0dwT2hVZFhxS3V2CjhqQmZQVDlscGRFdS92eXAy"
    "QW5pa3liaXFmcjkxMDRxNHlRQ0JvckhBb0dBU0dPTmlWUTF5akx6VVJvdWo0c2IKYjgzKzhRVzl1L3lNcHNZRWpUZWxQdlYwcWRHMWd4eVR3RytaOUFBOXJqV"
    "1NWSGlHaCthV3pQRHpjZ1Z5WDNPbApWQ251UkIyWnB6QWZBUEwxOUc5TTRXdHlaMTdhNGJOVVFRNXdFZUd3K01aODJ5bTZWT09VWkZMZ3dGWEN2YVRsCnZsa1"
    "ZsOGRQVnJ1Zm93OGcwYW1tY1BVQ2dZRUFvY3pYeGJEN1R5dis1cFpSYzJFbkd5OVRxM3FZYlc5azlEZWEKWUxiSWc3SE01OTNxTTFUQzY0VWxlemtEbXFZMHR"
    "5UGRZZkF2UVdxd2FpVkh1QzdycEFvOTQ3OXBYYTQ3QnplSwpGWmc3TVhwdzNOR0F0MEZGMVZVWjRyUmtBb0hQQXoyWm9tOFdjc29ySjhNWjBDMEdjdHg5ZXg4"
    "QWdaNkNyd1NoCkRMMW1tZzhDZ1lBSWdub2lZUEd2R3Vid2hUeTlWTTJ6aTJLS1ljTjBmRzRxak1acnllNi9aQllRa1VPQnpvTE8KVjA2NnhWTEJ5ZWFjeVBNR"
    "Gx2OVN5cGdIWlI3RGs0eDlxa1R0S3UxWVpBWGtDRmFtTWJacFV6Q3pFSVpuVStoQgp4MUtYWmZ2VWxzc1ZuNHBVUzYzaUJyODBCSDdPdkZ0dlNjeWVlYUk4cT"
    "lyRzc1SWdBYWlOZ2c9PQotLS0tLUVORCBSU0EgUFJJVkFURSBLRVktLS0tLQo= "
)

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEApNksW44dG4jvlKjReXTZ
kv/5HpCXmYruwsGRVnRIgolUOugt7JRrJbNgmHQLo2rodkZnHppMa6hH03FiPmdc
XSgVpsrHK4aeF2i02kp57qtoQidGSeOlfyowhPehie5efFng4bUvDFkiOjzqAF/C
2IzBJvc7ruU6G92roOOfAJvtBzrjztcoW5EMlBnLc8JJUJsfgrcT9O1khJp8JTJk
RL/r2RsVm9+cuB9annray6FBlOteiHSg/Ss0KkuyEkslRIOAEhM73XNa5XJeVdUH
OFihuJncE7tP4hTP01nJIjCxgJRG5ugtPExTSa/pPpuYi0pToXG3Ss/Zeam08Mcx
QwIDAQAB
-----END PUBLIC KEY-----
"""


class WrappedTempDir(tempfile.TemporaryDirectory):
    """This is a wrapped TemporaryDirectory that we can confirm that it was called properly in our tests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cleanup_called = False

    def cleanup(self) -> None:
        """This is the wrapped cleanup call that just calls the superclass but also sets our called flag."""
        self.cleanup_called = True
        super().cleanup()


@pytest.fixture
def testing_github_key() -> str:
    """This is a test GitHub API key."""
    return base64.b64decode(TEST_BASE64_GITHUB_KEY).decode("utf-8")


@pytest.fixture
def unit_test_secrets(base_secrets: Dict[str, Any], testing_github_key: str) -> Dict[str, Any]:
    """This mocks out secrets manager to contain what we need to contain for this unit test."""
    base_secrets.update({"GitHubSyncWorker": {"fakeorg": testing_github_key}})
    return base_secrets


@pytest.fixture
def mock_installation_token(unit_test_secrets: Dict[str, Any]) -> Generator[MagicMock, None, None]:
    """This mocks out the GitHub endpoint to return the installation token."""

    class MockedResult:
        """Mocked result class to be returned from mocking requests.post()"""

        status_code = 201

        def json(self) -> Dict[str, Any]:
            """Mocked out the JSON function to return a fake token back out."""
            # Make expiration 1 hour from now:
            time_stamp = (datetime.utcnow().replace(tzinfo=None, microsecond=0) + timedelta(minutes=60)).isoformat() + "Z"
            return {"expires_at": time_stamp, "token": "lolsometoken"}

    mocked_requests = MagicMock()
    mocked_requests.post.return_value = MockedResult()

    with mock.patch("starfleet.worker_ships.plugins.github_sync.auth.requests", mocked_requests):
        yield mocked_requests


@pytest.fixture
def random_commit_hash() -> str:
    """
    This is supposed to be a random string that is added after the extracted directory name. This is not really a commit hash, it's just 32 random characters.
    This is a separate fixture to simply other tests to locate where the files are on disk.
    """
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=32))


@pytest.fixture
def zip_repo(random_commit_hash: str) -> BytesIO:
    """
    This is a fixture that will take our `test_files` directory, and make a zip in memory. The resultant zip will save files to a directory that is the name of the
    repo with a random string that would be the hash of the commit.

    For the purposes of testing, we are calling this repo: "myrepo".
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ram_zip = BytesIO()  # This is the main file object in RAM that will contain the zip.
    with ZipFile(ram_zip, "w") as zipped:
        for root, _, files in os.walk(f"{current_dir}/test_files"):
            for file in files:
                # https://stackoverflow.com/questions/1855095/how-to-create-a-zip-archive-of-a-directory
                # Note: this is going to put things in the zip within `myrepo-COMMIT-HASH/...` and this is because GitHub embeds all the files in a parent directory
                # that is named after the repo and the commit hash
                zipped.write(
                    os.path.join(root, file),
                    arcname=os.path.relpath(os.path.join(root, file), os.path.join(root, current_dir)).replace("test_files/", f"myrepo-{random_commit_hash}/"),
                )

    # Reset the read pointer to reopen the file for use:
    ram_zip.seek(0)

    yield ram_zip
    ram_zip.close()


class GitHubResult:
    """Mock GitHub response class."""

    def __init__(self, status_code: int, text: Optional[str] = None, content: Optional[bytes] = None):
        self.status_code = status_code
        self.text = text if text else content.decode("ISO-8859-1")
        self.content = content if content else text.encode("UTF-8")


@pytest.fixture
def mock_github(zip_repo: BytesIO) -> Generator[MagicMock, None, None]:
    """This mocks out the GitHub download API."""

    class MockedGitHubApi:
        """Class that mocks the requests call to GitHub."""

        def get(self, *args, **kwargs) -> GitHubResult:
            """This will return the object to download -- or a 404 if we intentionally pass in the 404 path for testing."""

            if "badrepo" in args[0]:
                return GitHubResult(
                    404, text='{"message":"Not Found","documentation_url":"https://docs.github.com/rest/reference/repos#download-a-repository-archive"}'
                )

            return GitHubResult(200, content=zip_repo.read())

    with mock.patch("starfleet.worker_ships.plugins.github_sync.utils.requests", MockedGitHubApi()) as mocked_requests:
        yield mocked_requests


@pytest.fixture
def temp_directory() -> str:
    """This will create a temporary directory that gets deleted after the test is over."""
    with tempfile.TemporaryDirectory() as temp_dir_path:
        yield temp_dir_path


@pytest.fixture
def downloaded_repo(temp_directory: str, mock_github: MagicMock, mock_installation_token: MagicMock) -> None:
    """This will set up the downloaded repo. This just calls the existing code to download and save the repo."""
    from starfleet.worker_ships.plugins.github_sync.utils import download_repo

    download_repo("fakeorg", "1234567", "987654", "myrepo", "main", temp_directory)  # pylint: disable=too-many-function-args


@pytest.fixture
def aws_s3(aws_credentials: None) -> Generator[BaseClient, None, None]:
    """This is a fixture for a Moto wrapped AWS S3 mock for the entire unit test."""
    with mock_s3():
        client = boto3.client("s3", region_name="us-east-2")  # Assuming that our deployment region for everything is us-east-2.

        # Make the bucket:
        client.create_bucket(CreateBucketConfiguration={"LocationConstraint": "us-east-2"}, Bucket="some-bucket")

        yield client


@pytest.fixture
def local_diffed_files() -> Dict[str, Any]:
    """This returns the dictionary from `collect_files_for_diff` based on the directory tree structure of the test extracted repo."""
    from starfleet.worker_ships.plugins.github_sync.utils import collect_files_for_diff

    include_repo_paths = [r"^.+$"]
    dir_path = f"{os.path.dirname(os.path.abspath(__file__))}/test_files"
    return collect_files_for_diff(dir_path, include_repo_paths, [])


@pytest.fixture
def excess_files(aws_s3: BaseClient) -> Set[str]:
    """This places excess files in our bucket for the purposes of testing deletions. This returns the set of the prefixes for them."""
    items = set()
    for item in range(0, 10):
        items.add(f"some/path/{item}")
        aws_s3.put_object(Bucket="some-bucket", Key=f"some/path/{item}", Body=f"{item}")

    return items


@pytest.fixture
def github_sync_payload() -> Dict[str, Any]:
    """This is the base test payload loaded from disk."""
    payload_file = f"{os.path.dirname(os.path.abspath(__file__))}/test_payload.yaml"
    with open(payload_file, "r", encoding="UTF-8") as file:
        payload = yaml.safe_load(file.read())

    return payload


@pytest.fixture
def mock_github_sync_secrets(base_secrets: Dict[str, Any]) -> Dict[str, Any]:
    """Injects the GitHubSync secrets into the secrets dictionary."""
    base_secrets["GitHubSyncWorker"] = {"fakeorg": "pewpewpew"}
    return base_secrets
