"""Pytest fixtures for the AWS Config Worker

All the Pytest fixtures unique to the AWS Config worker

:Module: starfleet.tests.starfleet_included_plugins.aws_config.conftest
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument,unused-import,redefined-outer-name
from typing import Any, Dict, Generator

import boto3
import pytest
import yaml
from botocore.client import BaseClient
from moto import mock_config

from tests.account_index.conftest import test_index  # noqa


@pytest.fixture
def aws_config(aws_sts: BaseClient) -> Generator[BaseClient, None, None]:
    """This is a fixture for a Moto wrapped AWS Config mock for the entire unit test. This also imports the STS mock."""
    with mock_config():
        yield boto3.client("config", region_name="us-east-2")  # Assuming that our deployment region for everything is us-east-2.


@pytest.fixture()
def template() -> Dict[str, Any]:
    """Template for describing what the state should be."""
    return yaml.safe_load(
        """
        TemplateName: AWSConfigEnablement
        TemplateDescription: Enabled AWS Config everywhere
        IncludeAccounts:
            AllAccounts: True
        OperateInOrgRoot: True
        IncludeRegions:
            - ALL
        AccountOverrideConfigurations:
            -
                IncludeAccounts:
                    ByIds:
                        - "000000000001"
                IncludeRegions:
                    - us-west-1
                DeliveryChannelDetails:
                    BucketName: bucket-000000000001
                    BucketKeyPrefix: some/prefix/
                    S3DeliveryFrequency: TwentyFour_Hours
                    S3KmsKeyArn: arn:aws:kms:us-west-1:000000000001:key/1234-1445-1919232
                    SnsTopicArn: arn:aws:sns:us-west-1:000000000001:topic/sometopic
                    PreferredName: us-west-1-000000000001
                RecorderConfiguration:
                    PreferredName: us-west-1-000000000001
                    ConfigRoleName: MyConfigRole
                    RecordingEnabled: True
                    RecordingGroup:
                        ResourceTypes:
                            - ALL
                        GlobalsInRegions:
                            - us-west-1
                RetentionPeriodInDays: 30
            -
                IncludeAccounts:
                    ByIds:
                        - "000000000002"
                IncludeRegions:
                    - us-west-1
                DeliveryChannelDetails:
                    BucketName: bucket-000000000002
                    S3DeliveryFrequency: TwentyFour_Hours
                RecorderConfiguration:
                    ConfigRoleName: MyConfigRole
                    RecordingEnabled: True
                    RecordingGroup:
                        ResourceTypes:
                            - AWS::S3::Bucket
                            - AWS::EC2::SecurityGroup
                RetentionPeriodInDays: 2557
        DefaultConfiguration:
            DeliveryChannelDetails:
                BucketName: all-bucket
                S3DeliveryFrequency: TwentyFour_Hours
            RecorderConfiguration:
                ConfigRoleName: MyConfigRole
                RecordingEnabled: True
                RecordingGroup:
                    ResourceTypes:
                        - ALL
                    GlobalsInRegions:
                        - us-east-1
            RetentionPeriodInDays: 2557
    """
    )


@pytest.fixture()
def loaded_template(template: Dict[str, Any]) -> Dict[str, Any]:
    """This is the template loaded through the schema."""
    from starfleet.worker_ships.plugins.aws_config.schemas import AwsConfigWorkerShipPayloadTemplate

    return AwsConfigWorkerShipPayloadTemplate().load(template)
