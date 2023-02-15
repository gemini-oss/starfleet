"""Starfleet's configuration schema

This defines a basic Marshmallow schema for the Starfleet configuration. This will ensure that the base configuration file
has the correct components on it.

:Module: starfleet.utils.config_schema
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from marshmallow import Schema, fields, INCLUDE, validate


class StarfleetSchema(Schema):
    """This is the main schema for Starfleet itself."""

    # Required Fields:
    deployment_region = fields.String(required=True, data_key="DeploymentRegion")  # This is where all Starfleet resources (SQS, S3, etc.) reside.
    template_bucket = fields.String(required=True, data_key="TemplateBucket")  # This is the name of the S3 bucket that all the templates will reside.
    # This is the SQS queue URL that the Starbase will use for getting the worker/template details so that the worker ship can be tasked properly:
    fanout_queue_url = fields.Url(required=True, schemes={"https"}, data_key="FanOutQueueUrl")

    # This is the name for the account index ship plugin. The default should be used if you are using the AccountIndexGenerator worker ship:
    account_index_ship = fields.String(required=False, data_key="AccountIndexShip", load_default="StarfleetDefaultAccountIndex")

    # Optional fields:
    log_level = fields.String(
        required=False, load_default="INFO", validate=validate.OneOf({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}), data_key="LogLevel"
    )
    third_party_logger_levels = fields.Dict(required=False, data_key="ThirdPartyLoggerLevels")


class BaseConfigurationSchema(Schema):
    """The base configuration Schema for Starfleet"""

    # Required fields:
    starfleet = fields.Nested(StarfleetSchema, required=True, data_key="STARFLEET")

    class Meta:
        """Meta properties on the Schema used by Marshmallow"""

        unknown = INCLUDE  # It's totally OK and normal if we get values that are not in this schema -- we only care that we got the required values
