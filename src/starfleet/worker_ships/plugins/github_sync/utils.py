"""Logic for the GitHubSyncWorker

Logic and utilities for the GitHubSyncWorker is here.

:Module: starfleet.worker_ships.plugins.github_sync.utils
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

import hashlib
import os
import re
from typing import Dict, List, Optional, Any, Tuple
from zipfile import ZipFile

import requests
from botocore.client import BaseClient
from cloudaux.aws.decorators import paginated

from starfleet.utils.logging import LOGGER
from starfleet.worker_ships.plugins.github_sync.auth import github_auth


# Copied from https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types, this may be out of date:
MIME_TYPE_REFERENCE = {
    "aac": "audio/aac",
    "abw": "application/x-abiword",
    "arc": "application/x-freearc",
    "avif": "image/avif",
    "avi": "video/x-msvideo",
    "azw": "application/vnd.amazon.ebook",
    "bin": "application/octet-stream",
    "bmp": "image/bmp",
    "bz": "application/x-bzip",
    "bz2": "application/x-bzip2",
    "cda": "application/x-cdf",
    "csh": "application/x-csh",
    "css": "text/css",
    "csv": "text/csv",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "eot": "application/vnd.ms-fontobject",
    "epub": "application/epub+zip",
    "gz": "application/gzip",
    "gif": "image/gif",
    "htm": "text/html",
    "html": "text/html",
    "ico": "image/vnd.microsoft.icon",
    "ics": "text/calendar",
    "jar": "application/java-archive",
    "jpeg, .jpg": "image/jpeg",
    "js": "text/javascript",
    "json": "application/json",
    "jsonld": "application/ld+json",
    "mid:": "audio/midi",
    "midi": "audio/x-midi",
    "mjs": "text/javascript",
    "mp3": "audio/mpeg",
    "mp4": "video/mp4",
    "mpeg": "video/mpeg",
    "mpkg": "application/vnd.apple.installer+xml",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "odt": "application/vnd.oasis.opendocument.text",
    "oga": "audio/ogg",
    "ogv": "video/ogg",
    "ogx": "application/ogg",
    "opus": "audio/opus",
    "otf": "font/otf",
    "png": "image/png",
    "pdf": "application/pdf",
    "php": "application/x-httpd-php",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "rar": "application/vnd.rar",
    "rtf": "application/rtf",
    "sh": "application/x-sh",
    "svg": "image/svg+xml",
    "tar": "application/x-tar",
    "tif, .tiff": "image/tiff",
    "ts": "video/mp2t",
    "ttf": "font/ttf",
    "txt": "text/plain",
    "vsd": "application/vnd.visio",
    "wav": "audio/wav",
    "weba": "audio/webm",
    "webm": "video/webm",
    "webp": "image/webp",
    "woff": "font/woff",
    "woff2": "font/woff2",
    "xhtml": "application/xhtml+xml",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xml": "application/xml",
    "xul": "application/vnd.mozilla.xul+xml",
    "zip": "application/zip",
    "3gp": "video/3gpp",
    "3g2": "video/3gpp2",
    "7z": "application/x-7z-compressed",
    "yml": "application/yaml",
    "yaml": "application/yaml",
}


class InvalidResponseFromGitHubError(Exception):
    """Raised if we get an invalid response from GitHub."""


class EmptyZipFileError(Exception):
    """This is raised if the zip file is empty."""


@github_auth
def download_repo(organization: str, repo: str, branch: str, save_dir: str, github_headers: Dict[str, str] = None) -> None:
    """
    This downloads the repo's zip file from the proper location.

    Follows GitHub's API: https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28#download-a-repository-archive-zip--code-samples
    """
    LOGGER.info(f"[⬇️] Downloading zip for repo/branch: {repo}/{branch} from the {organization} organization...")
    github_headers.update({"X-GitHub-Api-Version": "2022-11-28", "Accept": "application/vnd.github+json"})

    # Add more headers per their docs:
    response = requests.get(f"https://api.github.com/repos/{organization}/{repo}/zipball/{branch}", headers=github_headers, timeout=20, allow_redirects=True)
    if response.status_code != 200:
        LOGGER.error(f"[⛔] Invalid response from GitHub: {response.status_code}/{response.text}")
        raise InvalidResponseFromGitHubError(response.status_code, response.text)

    # Save the file:
    LOGGER.info("[💾] Saving the repo...")
    path = f"{save_dir}/{repo}.zip"
    with open(path, "wb") as file:
        file.write(response.content)


def extract_repo(dir_path: str, repo_name: str) -> str:
    """This will extract the repo contents to disk. This will also return the name for the extracted directory."""
    LOGGER.info("[🪛] Extracting the repo's contents to disk...")

    with ZipFile(f"{dir_path}/{repo_name}.zip", "r") as zipped:
        # Extract what the parent folder name will be:
        if not zipped.filelist:
            LOGGER.error("[⁉️] Why is the zip file empty? Cannot continue!")
            raise EmptyZipFileError()

        extracted_directory = zipped.filelist[0].filename.split("/")[0]
        zipped.extractall(f"{dir_path}/")

    return extracted_directory


def match_path(file_path: str, regex_list: List[str]) -> bool:
    """This is a utility function that will work with the Include/Exclude paths. This will ensure that we only compare the files that need to be compared with S3."""
    for regex_str in regex_list:
        if re.search(regex_str, file_path):
            return True

    return False


def generate_s3_hash(file_path: str) -> str:
    """Generates the S3 e-tag hash of the file. This determines if the file is the same as the file that is existing in S3 or not."""
    # See https://zihao.me/post/calculating-etag-for-aws-s3-objects/ for details: -- using 4 MB chunks for checksum.
    value_md5 = hashlib.md5(usedforsecurity=False)
    with open(file_path, "rb") as file:
        for data in iter(lambda: file.read(4096), b""):
            value_md5.update(data)

    return value_md5.hexdigest()


def collect_files_for_diff(dir_path: str, include_paths: List[str], exclude_paths: List[str]) -> Dict[str, str]:
    """
    This is going to collect a list of all files downloaded (or extracted) and it will:
        1. Verify that the file in question is included and not excluded
        2. Generate a list of the S3-style checksums for the files that need to be diffed with what's on S3
    """
    verify_files = {}

    for root, _, files in os.walk(dir_path):
        for file in files:
            file_path = os.path.relpath(os.path.join(root, file), dir_path)

            # Is this explicitly ignored?
            if match_path(file_path, exclude_paths):
                LOGGER.debug(f"[⏭️] Skipping {file_path} -- it is explicitly ignored.")
                continue

            if match_path(file_path, include_paths):
                LOGGER.debug(f"[➕] Including file: {file_path}")
                verify_files[file_path] = generate_s3_hash(os.path.join(root, file))

    return verify_files


@paginated("Contents", request_pagination_marker="ContinuationToken", response_pagination_marker="NextContinuationToken")
def list_objects_v2(client: BaseClient, **kwargs) -> Dict[str, Any]:
    """List all objects in the bucket -- calls are wrapped by CloudAux"""
    result = client.list_objects_v2(**kwargs)
    if not result.get("Contents"):
        result["Contents"] = []

    return result


def collect_s3_files_for_diff(bucket: str, s3_client: BaseClient, key_prefix: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    This is going to collect a list of all files in the S3 location and:
        1. List all the files in S3 at the key prefix location (or the base)
        2. Create a dictionary of the object prefix and the corresponding S3 list object

    ## Note: S3 should store a 1-1 mapping of what is in the repo
    """
    key_prefix = key_prefix or ""
    s3_files: Dict[str, Any] = {}

    s3_args = {"Bucket": bucket}
    if key_prefix:
        s3_args["Prefix"] = key_prefix

    LOGGER.debug(f"[📡] Fetching object list from S3: {bucket} at prefix: {key_prefix or 'root of bucket'}.")
    objects = list_objects_v2(s3_client, **s3_args)
    for s3_obj in objects:
        # Need to strip out the key_prefix so that it maps 1:1 with what's locally on disk:
        s3_files[s3_obj["Key"][len(key_prefix) :]] = s3_obj

    LOGGER.debug(f"[🧮] Found a total of {len(s3_files)} in the bucket.")
    return s3_files


def get_content_type(filename: str) -> str:
    """
    Gets the content type to set for the object in S3.

    ## NOTE: For performance reasons, we are going to split the filename on dots, and check if that is in the mime type reference above.

    If we are unable to find it in our mapping, then just return binary/octet-stream
    """
    extension = filename.split(".")[-1:][0]
    return MIME_TYPE_REFERENCE.get(extension, "binary/octet-stream")


def upload_to_s3(bucket: str, dir_path: str, files_to_upload: List[str], s3_client: BaseClient, key_prefix: Optional[str] = None) -> None:
    """This will upload the files in question to S3. This will upload all objects with the `bucket-owner-full-control` canned ACL."""
    key_prefix = key_prefix or ""

    for file in files_to_upload:
        prefix = key_prefix + file
        with open(f"{dir_path}/{file}", "rb") as file_body:
            LOGGER.debug(f"[⬆️] Uploading object: {file} to bucket/prefix: {bucket}/{prefix}...")
            s3_client.put_object(Bucket=bucket, Key=prefix, ContentType=get_content_type(file), Body=file_body, ACL="bucket-owner-full-control")


def diff_local_with_s3(local_files: Dict[str, str], s3_files: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    This is going to perform a diff of the local files with what's in S3. This will return a tuple with a list of file paths:
        1. The first is the list of local files that are new
        2. The second is the list of local files that are different and need to be uploaded as well

    This function will update the vale of S3 files. The files remaining in the S3 files dictionary are the files that should be
    removed if enabled.
    """
    missing_files = []
    different_files = []

    for file, checksum in local_files.items():
        # Does this file exist in S3? Does the checksum match?
        if s3_files.get(file):
            if checksum != s3_files[file]["ETag"][1:-1]:
                different_files.append(file)
                LOGGER.debug(f"[🕵️] File: {file} is different than what's in S3.")

            else:
                LOGGER.debug(f"[👍] File: {file} is the same as what's in S3.")

            # The file is accounted for:
            s3_files.pop(file)

        else:
            missing_files.append(file)
            LOGGER.debug(f"[🤷] File: {file} is missing in S3.")

    if s3_files:
        for file in s3_files.keys():
            LOGGER.debug(f"[👾] File: {file} is in S3 but not in the repo.")

    LOGGER.info(f"[🆕] There are {len(missing_files)} missing file(s) in the bucket.")
    LOGGER.info(f"[📝] There are {len(different_files)} outdated file(s) in the bucket.")
    LOGGER.info(f"[👾] There are {len(s3_files)} excess file(s) on the bucket.")

    return missing_files, different_files


def delete_from_s3(bucket: str, files_to_delete: List[str], s3_client: BaseClient, key_prefix: Optional[str] = None) -> None:
    """This will delete the excess files from the bucket if present."""
    key_prefix = key_prefix or ""

    batches = []
    current_batch = []
    # Batch it all:
    for file in files_to_delete:
        prefix = key_prefix + file
        if len(current_batch) == 1000:
            batches.append(current_batch)
            current_batch = []

        LOGGER.debug(f"[🔫] Queueing object for deletion: {prefix} in {bucket}...")
        current_batch.append({"Key": prefix})

    batches.append(current_batch)

    # Delete them:
    for index, batch in enumerate(batches, start=1):
        LOGGER.debug(f"[🎆] Deleting batch: {index}...")
        s3_client.delete_objects(Bucket=bucket, Delete={"Objects": batch})
