"""Pytest fixtures for the IAM worker ships

All the Pytest fixtures unique to the AWS IAM workers

:Module: starfleet.tests.starfleet_included_plugins.iam.conftest
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument,unused-import,redefined-outer-name
import os
from typing import Any, Dict, Generator

import boto3
import pytest
import yaml
from botocore.client import BaseClient
from moto import mock_iam

from tests.account_index.conftest import test_index  # noqa


@pytest.fixture
def aws_iam(aws_credentials: None) -> Generator[BaseClient, None, None]:
    """This is a fixture for a Moto wrapped AWS IAM mock for the entire unit test."""
    os.environ["MOTO_ACCOUNT_ID"] = "000000000001"

    with mock_iam():
        yield boto3.client("iam", region_name="us-east-1")

    del os.environ["MOTO_ACCOUNT_ID"]


@pytest.fixture
def test_role(aws_iam: BaseClient, aws_sts: BaseClient) -> None:
    """This is a sample IAM role that is used for testing."""
    aws_iam.create_role(
        RoleName="StarfleetIambicTesting",
        AssumeRolePolicyDocument='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}',
        Description="This is a test role",
    )


@pytest.fixture()
def template() -> Dict[str, Any]:
    """Template for describing what the test role should be"""
    return yaml.safe_load(
        """
        TemplateName: TestingTemplate
        TemplateDescription: This is a test template IAM Role
        IncludeAccounts:
            AllAccounts: True
        OperateInOrgRoot: True
        IambicVariables:
          - Key: some_key
            Value: some_value
          - Key: some_other_key
            Value: some_other_value
        IambicRoleTemplate:
          properties:
            description: 'Starfleet iambic test role with variable {{ var.some_key }}'
            assume_role_policy_document:
              statement:
                - action: sts:AssumeRole
                  effect: Allow
                  principal:
                    service: ec2.amazonaws.com
              version: '2012-10-17'
            managed_policies:
              - policy_arn: arn:aws:iam::aws:policy/ReadOnlyAccess
            inline_policies:
              - policy_name: 'SomePolicyIn-{{ var.account_name }}'
                StarfleetIncludeAccounts:
                  ByOrgUnits:
                    - SomeNestedOU
                StarfleetExcludeAccounts:
                  ByNames:
                    - Account 10
                statement:
                  - effect: Deny
                    action: s3:*
                    resource: '*'
                version: '2012-10-17'
            role_name: StarfleetIambicTesting
            tags:
              - key: owner
                value: pewpewpew
              - key: some_other_key
                value: '{{ var.some_other_key }}'
    """
    )
