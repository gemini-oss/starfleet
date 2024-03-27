"""AWS Config enablement worker ship schema definitions

All of the schemas and schema components for the configuration and the payloads.

:Module: starfleet.worker_ships.plugins.aws_config.schemas
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

from enum import Enum
from typing import Any, Dict

from marshmallow import fields, Schema, validates_schema, validate, ValidationError

from starfleet.utils.niceties import get_all_regions
from starfleet.worker_ships.base_payload_schemas import BaseAccountRegionPayloadTemplate, AccountsSpecificationSchema, IncludeAccountsSpecificationSchema
from starfleet.worker_ships.ship_schematics import WorkerShipBaseConfigurationTemplate


supported_regions = get_all_regions(service="config")


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


class RecordEverything(Schema):
    """
    This is the schema for the `RecordEverything` section of the RecorderConfiguration.

    This is the equivalent of setting `allSupported` to True in the boto3 call and also includes the `includeGlobalResourceTypes` but for the given
    list of supplied regions.

    This will look like this:
    ```yaml
        RecordEverything:
            RecordGlobalsInTheseRegions:
                - A LIST OF REGIONS
                # OR
                - ALL
                # OR
                - NONE
    ```

    Example for recording everything in us-east-1 and us-west-2:
    ```yaml
        RecordEverything:
            RecordGlobalsInTheseRegions:
                - us-east-1
                - us-west-2
    ```

    Example for recording everything in all regions:
    ```yaml
        RecordEverything:
            RecordGlobalsInTheseRegions:
                - ALL
    ```

    Example for recording everything except global resources:
    ```yaml
        RecordEverything:
            RecordGlobalsInTheseRegions:
                - NONE
    ```
    """

    record_globals_in_these_regions = fields.List(fields.String(), required=True, data_key="RecordGlobalsInTheseRegions")

    @validates_schema()
    def validate_the_schema(self, data: Dict[str, Any], **kwargs) -> None:  # pylint: disable=unused-argument # noqa
        """Validate the schema provided to indicate what is in the docstring above."""
        errors = {}

        # Verify the "ALL" in the RecordGlobalsInTheseRegions:
        if "ALL" in data["record_globals_in_these_regions"]:
            # There should not be anything else:
            if len(data["record_globals_in_these_regions"]) > 1:
                errors["RecordGlobalsInTheseRegions"] = ["Can't list any other regions when `ALL` is specified"]

            # Replace the value with the set of all regions:
            data["record_globals_in_these_regions"] = supported_regions

        # Verify the "NONE" in the RecordGlobalsInTheseRegions:
        elif "NONE" in data["record_globals_in_these_regions"]:
            # There should not be anything else:
            if len(data["record_globals_in_these_regions"]) > 1:
                errors["RecordGlobalsInTheseRegions"] = ["Can't list any other regions when `NONE` is specified"]

            # Replace the value with an empty set:
            data["record_globals_in_these_regions"] = set()

        # Verify the regions are valid:
        else:
            region_set = set(data["record_globals_in_these_regions"])
            remaining = region_set - supported_regions
            if remaining:
                errors["RecordGlobalsInTheseRegions"] = [
                    f"Invalid regions are specified: {', '.join(remaining)}. Regions must be from this list: {', '.join(supported_regions)}"
                ]

            # Store the value as a set:
            data["record_globals_in_these_regions"] = region_set

        if errors:
            raise ValidationError(errors)


class RecordingGroup(Schema):
    """
    This is the RecordingGroup section of the RecorderConfiguration.

    This is where you will specify one of the following 3 options:
        1. If you wanted to record everything:
            ```yaml
            RecordEverything:
                RecordGlobalsInTheseRegions:
                    - ALL
                    # OR
                    - NONE
                    # OR
                    - A LIST OF REGIONS like:
                    - us-east-1
                    - us-west-2
                    - etc...
            ```

        2. If you wanted to record only specific resources:
            ```yaml
            RecordSpecificResources:
                - AWS::EC2::Instance
                - AWS::EC2::VPC
                - etc...
            ```

        3. If you wanted to record everything except specific resources:
            ```yaml
            RecordEverythingExcept:
                - AWS::EC2::Instance
                - AWS::EC2::VPC
                - etc...
            ```

    This simplifies the details that would otherwise be supplied to the boto3 call:
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/config/client/put_configuration_recorder.html
    """

    record_everything = fields.Nested(RecordEverything(), required=False, data_key="RecordEverything")
    record_specific_resources = fields.List(fields.String(), validate=validate.Length(min=1), required=False, data_key="RecordSpecificResources")
    record_everything_except = fields.List(fields.String(), validate=validate.Length(min=1), required=False, data_key="RecordEverythingExcept")

    @validates_schema()
    def validate_the_schema(self, data: Dict[str, Any], **kwargs) -> None:  # pylint: disable=unused-argument # noqa
        """Performs the validation on the schema. At least one of the 3 options needs to be filled out and correctly."""
        errors = {}

        # Verify that if we have the `RecordEverything` section, that it is the only section:
        found_fields = set()
        field_mapping = [
            ("record_everything", "RecordEverything"),
            ("record_specific_resources", "RecordSpecificResources"),
            ("record_everything_except", "RecordEverythingExcept"),
        ]
        for python_field, yaml_field in field_mapping:
            if data.get(python_field):
                found_fields.add((python_field, yaml_field))

        # At least 1 needs to be filled out:
        if not found_fields:
            errors["RecordingGroup"] = [
                "At least one of the 3 options needs to be filled out: RecordEverything, RecordSpecificResources, RecordEverythingExcept"
            ]

        elif len(found_fields) > 1:
            errors["RecordingGroup"] = ["Only one of the 3 options can be filled out: RecordEverything, RecordSpecificResources, RecordEverythingExcept"]

        if errors:
            raise ValidationError(errors)


class DeliveryChannelDetails(Schema):
    """This is the section that will define the delivery channel details. Namely, all the S3 stuff."""

    bucket_name = fields.String(required=True, data_key="BucketName")
    s3_delivery_frequency = fields.Enum(DeliveryFrequency, required=True, data_key="S3DeliveryFrequency")

    # Optionals:
    preferred_name = fields.String(required=False, load_default="default", data_key="PreferredName")
    bucket_key_prefix = fields.String(required=False, load_default=None, data_key="BucketKeyPrefix")
    s3_kms_key_arn = fields.String(required=False, load_default=None, data_key="S3KmsKeyArn")
    sns_topic_arn = fields.String(required=False, load_default=None, data_key="SnsTopicArn")


class RecorderConfiguration(Schema):
    """This is the main component where all the details are placed."""

    config_role_name = fields.String(required=True, data_key="ConfigRoleName")
    recording_enabled = fields.Bool(required=False, load_default=False, data_key="RecordingEnabled")
    recording_group = fields.Nested(RecordingGroup(), required=True, data_key="RecordingGroup")

    # Optionals:
    preferred_name = fields.String(required=False, load_default="default", data_key="PreferredName")


class DefaultConfiguration(Schema):
    """This is the schema component for defining the default AWS Config configuration for all non-overriden account/regions that are included in the template.

    *Note:* If you want to override or exclude, then the way to do that is to do the following:
        1. Explicitly exclude the account/region in ExcludeAccounts/ExcludeRegions and/or don't include the account/region in IncludeAccounts/IncludeRegions
        2. Make an override configuration for the given account/region in question (via AccountOverrideConfigurations)
        3. Mixture of 1 and 2
    """

    delivery_channel_details = fields.Nested(DeliveryChannelDetails(), required=True, data_key="DeliveryChannelDetails")
    recorder_configuration = fields.Nested(RecorderConfiguration(), required=True, data_key="RecorderConfiguration")

    # Recommend you use 2557 days (7 years + leap days).
    retention_period_in_days = fields.Integer(required=True, validate=validate.Range(min=30, max=2557), data_key="RetentionPeriodInDays")


class AccountOverrideConfiguration(DefaultConfiguration):
    """This is exactly like the DefaultConfiguration, but this one allows you to specify accounts and regions to include/exclude.
    This borrows the IncludeAccounts, ExcludeAccounts, IncludeRegions, and ExcludeRegions schemas from the base template.
    100% of that is used here and applies here.

    This subclasses the DefaultConfiguration, but overrides some of the components.
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

    default_configuration = fields.Nested(DefaultConfiguration(), required=True, data_key="DefaultConfiguration")
    account_override_configurations = fields.List(
        fields.Nested(AccountOverrideConfiguration()), required=False, load_default=[], data_key="AccountOverrideConfigurations"
    )
