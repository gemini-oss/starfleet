"""Starfleet's configuration schema

This defines a basic Marshmallow schema for the Starfleet configuration. This will ensure that the base configuration file
has the correct components on it.

:Module: starfleet.utils.config_schema
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import boto3
from marshmallow import Schema, fields, INCLUDE, validate

aws_regions = set(boto3.session.Session().get_available_regions("ec2"))


class SecretsManager(Schema):
    """This is a nested schema for AWS Secrets manager which is a pair of the Secrets ID and the region it resides in."""

    secret_id = fields.String(required=True, data_key="SecretId")
    secret_region = fields.String(
        required=True, validate=validate.OneOf(aws_regions), data_key="SecretRegion"
    )  # assuming that the Secrets Manager regions are the same as EC2


class StarfleetSchema(Schema):
    """This is the main schema for Starfleet itself."""

    # Required Fields:
    # This is where all Starfleet resources (SQS, S3, etc.) reside.
    deployment_region = fields.String(required=True, data_key="DeploymentRegion", validate=validate.OneOf(aws_regions))
    template_bucket = fields.String(required=True, data_key="TemplateBucket")  # This is the name of the S3 bucket that all the templates will reside.
    # This is the SQS queue URL that the Starbase will use for getting the worker/template details so that the worker ship can be tasked properly:
    fanout_queue_url = fields.Url(required=True, schemes={"https"}, data_key="FanOutQueueUrl")

    # This is the name for the account index ship plugin. The default should be used if you are using the AccountIndexGeneratorShip worker ship:
    account_index = fields.String(required=False, data_key="AccountIndex", load_default="StarfleetDefaultAccountIndex")

    # Optional fields:
    # This is a field that limits the ACCOUNT_REGION workers such that there are specific regions that can be operated on.
    # If this is set, then you can only run in the regions defined here despite what regions an account has enabled:
    scope_to_regions = fields.List(fields.String(validate=validate.OneOf(aws_regions)), required=False, data_key="ScopeToRegions", load_default=[])
    # ^^ This is useful if you have an SCP that disables regions; this prevents Starfleet to run in regions that are disabled by SCP.

    # Secrets Manager ARN for Starfleet's secrets if required
    secrets_manager = fields.Nested(SecretsManager(), required=False, data_key="SecretsManager")

    # Log Level:
    log_level = fields.String(
        required=False, load_default="INFO", validate=validate.OneOf({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}), data_key="LogLevel"
    )
    # Dictionary to override log levels for 3rd party loggers. This is the name of the log and the level.
    third_party_logger_levels = fields.Dict(required=False, data_key="ThirdPartyLoggerLevels")


class BaseConfigurationSchema(Schema):
    """The base configuration Schema for Starfleet"""

    # Required fields:
    starfleet = fields.Nested(StarfleetSchema, required=True, data_key="STARFLEET")

    class Meta:
        """Meta properties on the Schema used by Marshmallow"""

        unknown = INCLUDE  # It's totally OK and normal if we get values that are not in this schema -- we only care that we got the required values
