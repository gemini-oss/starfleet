"""AWS Config enablement worker ship schema definitions

All of the schemas and schema components for the configuration and the payloads.

:Module: starfleet.worker_ships.plugins.aws_config.schemas
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from enum import Enum
from typing import Any, Dict

import boto3
from marshmallow import fields, Schema, validates_schema, validate, ValidationError

from starfleet.worker_ships.base_payload_schemas import BaseAccountRegionPayloadTemplate, AccountsSpecificationSchema, IncludeAccountsSpecificationSchema
from starfleet.worker_ships.ship_schematics import WorkerShipBaseConfigurationTemplate


supported_regions = set(boto3.session.Session().get_available_regions("config"))


class AwsConfigWorkerShipConfigurationTemplate(WorkerShipBaseConfigurationTemplate):
    """The configuration for the AwsConfigWorkerShip. The only thing required is the name of the IAM role that this needs to assume to do the work needed."""

    worker_role_to_assume = fields.String(required=True, data_key="WorkerRoleToAssume")
    worker_role_session_name = fields.String(required=False, load_default="StarfleetAwsConfigWorkerShip", data_key="WorkerRoleSessionName")


# pylint: disable=invalid-name
class DeliveryFrequency(Enum):
    """
    AWS Config delivery channel frequency deliveries.

    Defined in: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/config/client/put_delivery_channel.html
    """

    One_Hour = "One_Hour"
    Three_Hours = "Three_Hours"
    Six_Hours = "Six_Hours"
    Twelve_Hours = "Twelve_Hours"
    TwentyFour_Hours = "TwentyFour_Hours"


class RecordingGroup(Schema):
    """
    This is the RecordingGroup section of the RecorderConfiguration.
    This is where you specify the list of resource types or specify that you want all resources.

    Mostly defined in: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/config/client/put_configuration_recorder.html with some ease of use modifications
    """

    resource_types = fields.List(fields.String(), validate=validate.Length(min=1), required=True, data_key="ResourceTypes")
    globals_in_regions = fields.List(fields.String(), required=False, data_key="GlobalsInRegions")

    @validates_schema()
    def validate_the_schema(self, data: Dict[str, Any], **kwargs) -> None:  # pylint: disable=unused-argument # noqa
        """Performs the validation and mutation on the schema. The following is the gist:

        `ResourceTypes` defines the resources to support. This will either be `ALL`, which will set the boto3 `allSupported` flag to True -- OR -- just a list of
        AWS Config supported resources.

        `GlobalsInRegions` is used in *conjunction* with the `allSupported` flag (or setting `ALL` for `ResourceTypes`). This is the boto3 `includeGlobalResourceTypes`
        boolean. *This is only relevant if ALL resources are being recorded.* This contains a list of regions that global resources will be recorded in. Here is what
        this means:
            If you want to record global resources only in us-east-1, but not the other regions, then you would have a YAML that looks like this:

            ```yaml
            ResourceTypes:
              - ALL
            GlobalsInRegions:
              - us-east-1
            ```

            This configuration would set it such that all non-global resources will be recorded. In the above example, us-east-1 would be the only region to *also*
            record global resource types. The in-regin recorders for all the other regions would not capture global resource types.

            This field is a list, so you can add in as many regions to capture global resource types as you want. Note, that we don't support `ALL` here because
            it's unnecessary to record global resources in all the regions since that will also jack up your Config bill.
        """
        errors = {}

        all_resources = False

        # Verify the "ALL" in resource types:
        if "ALL" in data["resource_types"]:
            all_resources = True

            # There should not be anything else:
            if len(data["resource_types"]) > 1:
                errors["IncludeRegions"] = ["Can't specify any other resource types when `ALL` is specified in the list."]

        # We cannot have both specific resources set and the `GlobalsInRegions` field set:
        if not all_resources and data.get("globals_in_regions"):
            errors["GlobalsInRegions"] = ["This field can only be specified with a list of regions if `ResourceTypes` is set to `- ALL`"]

        # If we have all regions set, and we also have global regions defined, then verify that the regions defined are legitimate:
        else:
            region_set = set(data.get("globals_in_regions", []))
            remaining = region_set - supported_regions
            if remaining:
                errors["GlobalsInRegions"] = [
                    f"Invalid regions are specified: {', '.join(remaining)}. Regions must be from this list: {', '.join(supported_regions)}"
                ]

        if errors:
            raise ValidationError(errors)


class DeliveryChannelDetails(Schema):
    """This is the section that will define the delivery channel details. Namely, all the S3 stuff."""

    bucket_name = fields.String(required=True, data_key="BucketName")
    s3_delivery_frequency = fields.Enum(DeliveryFrequency, required=True, data_key="S3DeliveryFrequency")

    # Optionals:
    bucket_key_prefix = fields.String(required=False, load_default=None, data_key="BucketKeyPrefix")
    s3_kms_key_arn = fields.String(required=False, load_default=None, data_key="S3KmsKeyArn")
    sns_topic_arn = fields.String(required=False, load_default=None, data_key="SnsTopicArn")
    preferred_name = fields.String(required=False, load_default=None, data_key="PreferredName")


class RecorderConfiguration(Schema):
    """This is the main component where all the details are placed."""

    config_role_name = fields.String(required=True, data_key="ConfigRoleName")
    recording_enabled = fields.Bool(required=False, load_default=False, data_key="RecordingEnabled")
    recording_group = fields.Nested(RecordingGroup(), required=True, data_key="RecordingGroup")

    # Optionals:
    preferred_name = fields.String(required=False, load_default=None, data_key="PreferredName")


class AllAccountsConfiguration(Schema):
    """This is the schema component for defining the AWS Config configuration all accounts that are included in the template.

    *Note:* If you want to override or exclude, then the way to do that is to do the following:
        1. Explicitly exclude the account/region in ExcludeAccounts/ExcludeRegions and/or don't include the account/region in IncludeAccounts/IncludeRegions
        2. Make an override configuration for the given account/region in question (via AccountOverrideConfigurations)
        3. Mixture of 1 and 2
    """

    delivery_channel_details = fields.Nested(DeliveryChannelDetails(), required=True, data_key="DeliveryChannelDetails")
    recorder_configuration = fields.Nested(RecorderConfiguration(), required=True, data_key="RecorderConfiguration")


class AccountOverrideConfiguration(AllAccountsConfiguration):
    """This is exactly like the AllAccountsRecorderConfiguration, but this one allows you to specify accounts and regions to include/exclude.
    This borrows the IncludeAccounts, ExcludeAccounts, IncludeRegions, and ExcludeRegions schemas from the base template.
    100% of that is used here and applies here.

    This subclasses the AllAccountsRecorderConfiguration, but overrides some of the components.
    """

    include_accounts = fields.Nested(IncludeAccountsSpecificationSchema(), data_key="IncludeAccounts", required=True)
    exclude_accounts = fields.Nested(AccountsSpecificationSchema(), data_key="ExcludeAccounts", load_default={})
    include_regions = fields.List(fields.String(), validate=validate.Length(min=1), data_key="IncludeRegions", required=True)
    exclude_regions = fields.List(fields.String(), data_key="ExcludeRegions", load_default=[])

    @validates_schema()
    def validate_regions(self, data: Dict[str, Any], **kwargs) -> None:  # pylint: disable=unused-argument  # noqa
        """
        This code has largely been copied and pasted from starfleet.worker_ships.base_payload_schemas

        This is going to validate that the regions entered in are legitimate regions that AWS supports. This works by using the boto3 SDK to list out
        all the regions that Config supports. The exception for this is the word "ALL". This is ONLY allowed for include regions!

        **NOTE:** If and when new regions are added, you will need to update the Starfleet dependencies to the latest and greatest boto3 library in order to get that support.
        """
        errors = {}

        # Verify the "ALL" in include regions:
        if "ALL" in data["include_regions"]:
            # There should not be anything else:
            if len(data["include_regions"]) > 1:
                errors["IncludeRegions"] = ["Can't specify any other regions when `ALL` is specified in the list."]

            # If ALL is in there, then we want to replace ALL with all the regions:
            data["include_regions"] = set(supported_regions)

        # If not all regions, then verify that all regions specified are recognized as actual AWS supported regions.
        else:
            region_set = set(data["include_regions"])
            remaining = region_set - supported_regions
            if remaining:
                errors["IncludeRegions"] = [
                    f"Invalid regions are specified: {', '.join(remaining)}. Regions must be from this list: {', '.join(supported_regions)}"
                ]
            else:
                data["include_regions"] = region_set

        if data.get("exclude_regions"):
            region_set = set(data["exclude_regions"])
            remaining = region_set - supported_regions
            if remaining:
                errors["ExcludeRegions"] = [
                    f"Invalid regions are specified: {', '.join(remaining)}. Regions must be from this list: {', '.join(supported_regions)}"
                ]
            else:
                data["exclude_regions"] = region_set

        if errors:
            raise ValidationError(errors)


class AwsConfigWorkerShipPayloadTemplate(BaseAccountRegionPayloadTemplate):
    """
    The payload for the AwsConfigWorkerShip. This will define all the details on where and how to configure AWS Config recorders.
    Much of the configuration details are mapped 1:1 with AWS's SDK and documentation for AWS Config with some deviations for convenience.
    """

    all_accounts_configuration = fields.Nested(AllAccountsConfiguration(), required=True, data_key="AllAccountsConfiguration")
    account_override_configurations = fields.List(
        fields.Nested(AccountOverrideConfiguration()), required=False, load_default=[], data_key="AccountOverrideConfigurations"
    )
