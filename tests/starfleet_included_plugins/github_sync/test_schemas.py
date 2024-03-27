"""Tests for the GitHub Sync worker's schemas

Tests out the schemas for configuration and payload to make sure they are correct.

:Module: starfleet.tests.starfleet_included_plugins.github_sync.test_schemas
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

import pytest
import yaml
from marshmallow import ValidationError


def test_payload_template() -> None:
    """This tests that the GitHubSyncPayloadTemplate schema has proper validation logic."""
    from starfleet.worker_ships.plugins.github_sync.ship import GitHubSyncPayloadTemplate

    # Good:
    payload = """
        TemplateName: SyncRepo
        TemplateDescription: Syncs a repo on GitHub with S3
        Organization: gemini-oss
        Repository: starfleet
        BranchName: main
        GitHubAppId: "0123456"
        GitHubInstallationId: "0123456"
        BucketName: some-bucket
        BucketRegion: us-east-2
        KeyPrefix: Some/Path
        ExtractZipContents: True
        IncludeRepoPaths:
            - "starfleet/*"
        ExcludeRepoPaths:
            - "*.toml"
        DeleteMissingFiles: True
    """
    assert GitHubSyncPayloadTemplate().load(yaml.safe_load(payload)) == {
        "extract_zip_contents": True,
        "bucket_region": "us-east-2",
        "key_prefix": "Some/Path",
        "template_name": "SyncRepo",
        "organization": "gemini-oss",
        "bucket_name": "some-bucket",
        "exclude_repo_paths": ["*.toml"],
        "github_app_id": "0123456",
        "delete_missing_files": True,
        "github_installation_id": "0123456",
        "repository": "starfleet",
        "branch_name": "main",
        "template_description": "Syncs a repo on GitHub with S3",
        "include_repo_paths": ["starfleet/*"],
    }

    # Test the region validator:
    bad_region = yaml.safe_load(payload)
    bad_region["BucketRegion"] = "pewpewpew"
    with pytest.raises(ValidationError) as exc:
        GitHubSyncPayloadTemplate().load(bad_region)
    assert exc.value.messages_dict["BucketRegion"][0].startswith("Must be one of: ")
