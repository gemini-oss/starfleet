"""Starfleet's worker ship definitions

This defines the base classes and components for all of Starfleet's "worker plugins". The worker plugins are plugins
that are loaded on start-up, and do the actual given task in Starfleet.

All ship plugins *must* implement the components defined here. Documentation for this follows. Also very helpful
to see existing ship plugins to get ideas on how to make your own.

:Module: starfleet.worker_ships.ship_schematics
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from enum import Enum
from typing import Any, Dict, Type, TypeVar

from marshmallow import Schema, fields, INCLUDE, post_load, ValidationError

from starfleet.worker_ships.base_payload_schemas import WorkerShipPayloadBaseTemplate


class InvocationSources(Enum):
    """This is an Enum that defines the type of invocation for a given Starfleet worker. This defines the
    allowable sources that can invoke the worker. This is used by the Starbase to determine if a given
    worker should be tasked.

    These also correspond to a configuration that each worker is required to have.
    """

    S3 = "S3"  # This doesn't require any additional configuration (already part of the base worker configuration template)
    SQS = "SQS"  # This doesn't require any additional configuration (already part of the base worker configuration template)

    # This is a EventBridge Events rule. If specified, you will need to provide more configuration details in EventBridgeTimedEventFrequency
    EVENTBRIDGE_TIMED_EVENT = "EVENTBRIDGE_TIMED_EVENT"


class FanOutStrategy(Enum):
    """This is an Enum that informs the Starbase on how to divvy out the workload."""

    SINGLE_INVOCATION = "SINGLE_INVOCATION"  # This means that there is 1 Lambda function required to complete the task.
    ACCOUNT = "ACCOUNT"  # This means that there should be 1 Lambda function for each account to complete the task.
    ACCOUNT_REGION = "ACCOUNT_REGION"  # This means that there is 1 Lambda function for each account AND enabled region pair to complete the task.


class EventBridgeFrequency(Enum):
    """These are the valid values for EventBridge Event timed invocation frequencies."""

    THIRTY_MIN = "THIRTY_MIN"  # Every 30 min / half-hourly
    HOURLY = "HOURLY"  # Every 60 min / hourly
    SIX_HOURLY = "SIX_HOURLY"  # Every 6 hours
    TWELVE_HOURLY = "TWELVE_HOURLY"  # Every 12 hours / half-daily
    DAILY = "DAILY"  # Once a day / every 24 hours


class WorkerShipBaseConfigurationTemplate(Schema):
    """This is the base worker ship configuration template schema that illustrates how the worker should be configured.
    This is _only_ used for validation purposes. The worker configuration will live with the global configuration and should
    be referenced by the STARFLEET_CONFIGURATION instance in starfleet.utils.configuration.

    Note: All configuration file YAMLs should be written in UpperCamelCase, but programmatically referenced in the Python Marshmallow
    object in snake_case.
    """

    # All ships must define an `Enabled = True` for the plugin to be used:
    enabled = fields.Bool(required=True, data_key="Enabled")

    # All ships must define an S3 template path, which includes the S3 bucket that contains the template, and the prefix for where the templates live:
    template_prefix = fields.String(required=True, data_key="TemplatePrefix")
    # ^^ the template prefix will list out object names with that prefix. Any YAML file (*.yaml) in that prefix is used.
    # If this is the direct template itself (ending in .yaml), then no search in S3 is needed. If it's not, then the Starbase will list all objects under that prefix
    # to obtain all the YAML templates. Be mindful of quantity of objects since that will slow things down (this should be good for < 1000 objects per single-digit workers).

    # This is the SQS queue URL that will be used to invoke this function. This is used by the Starbase to know where to message the ship invocation action:
    invocation_queue_url = fields.Url(required=True, schemes={"https"}, data_key="InvocationQueueUrl")

    # This is the invocation sources. This needs to be specified.
    invocation_sources = fields.List(fields.Enum(InvocationSources), required=True, data_key="InvocationSources")

    # If a EventBridgeTimed event is specified, then you need to add details on the invocation frequency (this manually configured below):
    eventbridge_timed_frequency = fields.Enum(EventBridgeFrequency, required=False, data_key="EventBridgeTimedFrequency")

    # This is an (Optional) SNS topic ARN that gets Starbase to invoke this Lambda function. The purpose for this is really for multistage
    # workflows (or externally invoked workflows) where the Starbase needs to perform fan-out operations (to be placed on the InvocationQueueUrl above)
    starbase_invocation_topic_arn = fields.String(required=False, data_key="StarbaseInvocationTopicArn")

    @post_load
    def validate_eventbridge_timed_frequencies(self, in_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:  # pylint: disable=W0613
        """This will perform the custom validation where if EVENTBRIDGE_TIMED_EVENT is in the InvocationSources, that an accompanying EventBridgeTimedFrequency is provided."""
        if InvocationSources.EVENTBRIDGE_TIMED_EVENT in in_data["invocation_sources"]:
            if not in_data.get("eventbridge_timed_frequency"):
                raise ValidationError("A EventBridgeTimedFrequency is required when specifying an invocation event of EVENTBRIDGE_TIMED_EVENT.")

        return in_data

    class Meta:
        """By default, we will include unknown values without raising an error."""

        unknown = INCLUDE


WorkerShipPayloadBaseTemplateInstance = TypeVar("WorkerShipPayloadBaseTemplateInstance", bound=WorkerShipPayloadBaseTemplate)


class StarfleetWorkerShip:
    """The base class for Starfleet worker ship plugins. All the attributes here should either be defined statically or in the __init__ of the subclass.

    The instantiated object type hint is `StarFleetWorkerShipInstance`."""

    # TODO: Should the invocation sources be defined here or the configuration?? (right now it's in the configuration)

    # This is the fan out strategy for the worker. This is very important and defines the type of job the worker is supposed to do (this also influences the template type).
    fan_out_strategy: FanOutStrategy = FanOutStrategy.SINGLE_INVOCATION

    # This is the name for the worker ship plugin (this should be UpperCamelCase). This is also the name of the Configuration section for the given worker ship plugin:
    worker_ship_name: str
    configuration_template_class: Type[WorkerShipBaseConfigurationTemplate] = WorkerShipBaseConfigurationTemplate  # Default to the base

    # This is the template class for the worker ship. All worker ship payload templates need to be defined.
    payload_template_class: Type[WorkerShipPayloadBaseTemplate] = WorkerShipPayloadBaseTemplate  # Default to the base
    payload: WorkerShipPayloadBaseTemplateInstance

    def load_template(self, raw_template: Dict[str, Any]) -> None:
        """This will load the template and store it in the loaded_template attribute. This will raise
        exceptions if there are validation errors."""
        self.payload = self.payload_template_class().load(raw_template)

    def execute(self, commit: bool = False) -> None:
        """This will execute the job from the payload."""
        raise NotImplementedError("pew pew pew")  # pragma: no cover


StarfleetWorkerShipInstance = TypeVar("StarfleetWorkerShipInstance", bound=StarfleetWorkerShip)
