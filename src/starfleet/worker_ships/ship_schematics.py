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

from marshmallow import Schema, fields, INCLUDE, post_load, ValidationError, validate

from starfleet.utils.slack import SLACK_CLIENT
from starfleet.worker_ships.base_payload_schemas import WorkerShipPayloadBaseTemplate


class InvocationSource(Enum):
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

    FIVE_MIN = "FIVE_MIN"  # Every 5 min
    FIFTEEN_MIN = "FIFTEEN_MIN"  # Every 15 min
    THIRTY_MIN = "THIRTY_MIN"  # Every 30 min / half-hourly
    HOURLY = "HOURLY"  # Every 60 min / hourly
    SIX_HOURLY = "SIX_HOURLY"  # Every 6 hours
    TWELVE_HOURLY = "TWELVE_HOURLY"  # Every 12 hours / half-daily
    DAILY = "DAILY"  # Once a day / every 24 hours


class AlertPriority(Enum):
    """
    These are the valid values for the types of alerts that should be emitted (if at all).

    This is somewhat similar to the way that Python logging levels work in that levels encompass other levels. For example this goes by ranking from
    least noisy to most noisy. If you select PROBLEM, then you will only receive alerts that are a PROBLEM. If you select INFORMATIONAL, then you will
    receive alerts that are INFORMATIONAL, SUCCESS, IMPORTANT, and PROBLEM.
    """

    NONE = 0  # Alert nothing
    PROBLEM = 1  # For errors or other items of significance to note (typically used for "bad" things)
    IMPORTANT = 2  # For information that is important but not necessarily an error
    SUCCESS = 3  # For information that would highlight that something was successful
    INFORMATIONAL = 4  # For informational messages


class AlertConfiguration(Schema):
    """This defines a schema for a worker's configuration defining details about what alerts should be emitted."""

    channel_id = fields.String(required=True, data_key="ChannelId")
    alert_priority = fields.String(required=True, validate=validate.OneOf([priority.name for priority in AlertPriority]), data_key="AlertPriority")


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
    invocation_sources = fields.List(fields.Enum(InvocationSource), required=True, data_key="InvocationSources")

    # If a EventBridgeTimed event is specified, then you need to add details on the invocation frequency (this manually configured below):
    eventbridge_timed_frequency = fields.Enum(EventBridgeFrequency, required=False, data_key="EventBridgeTimedFrequency")

    # This is an (Optional) SNS topic ARN that gets Starbase to invoke this Lambda function. The purpose for this is really for multistage
    # workflows (or externally invoked workflows) where the Starbase needs to perform fan-out operations (to be placed on the InvocationQueueUrl above)
    starbase_invocation_topic_arn = fields.String(required=False, data_key="StarbaseInvocationTopicArn")

    # This is an optional alert configuration (i.e. for sending to Slack) that a worker that opts in to can use to send alerts to.
    alert_configuration = fields.Nested(AlertConfiguration(), required=False, data_key="AlertConfiguration")

    @post_load
    def validate_eventbridge_timed_frequencies(self, in_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:  # pylint: disable=W0613
        """This will perform the custom validation where if EVENTBRIDGE_TIMED_EVENT is in the InvocationSources, that an accompanying EventBridgeTimedFrequency is provided."""
        if InvocationSource.EVENTBRIDGE_TIMED_EVENT in in_data["invocation_sources"]:
            if not in_data.get("eventbridge_timed_frequency"):
                raise ValidationError("A EventBridgeTimedFrequency is required when specifying an invocation event of EVENTBRIDGE_TIMED_EVENT.")

        return in_data

    class Meta:
        """By default, we will include unknown values without raising an error."""

        unknown = INCLUDE


WorkerShipPayloadBaseTemplateInstance = TypeVar("WorkerShipPayloadBaseTemplateInstance", bound=WorkerShipPayloadBaseTemplate)


class StarfleetWorkerShip:
    """
    The base class for Starfleet worker ship plugins. All the attributes here should either be defined statically or in the __init__ of the subclass.

    The instantiated object type hint is `StarFleetWorkerShipInstance`.
    """

    # This is the template class for the worker ship. All worker ship payload templates need to be defined.
    payload_template_class: Type[WorkerShipPayloadBaseTemplate] = WorkerShipPayloadBaseTemplate  # Default to the base
    payload: WorkerShipPayloadBaseTemplateInstance
    configuration_template_class: Type[WorkerShipBaseConfigurationTemplate] = WorkerShipBaseConfigurationTemplate  # Default to the base

    # This is the fan out strategy for the worker. This is very important and defines the type of job the worker is supposed to do (this also influences the template type).
    fan_out_strategy: FanOutStrategy = FanOutStrategy.SINGLE_INVOCATION

    @classmethod
    def get_worker_ship_name(cls: Type["StarfleetWorkerShip"]) -> str:
        """Static method to return the worker ship name."""
        return cls.__name__

    def __init__(self):
        """Default constructor. By default, this will set empty alerting details -- for sending messages to Slack with a priority of NONE."""
        # By default, do not set an alert priority. This will be set later if required by the @worker_lambda decorator.
        self.alert_priority = AlertPriority.NONE
        self.alert_channel = None

    # This is the name for the worker ship plugin (this should be UpperCamelCase). This is also the name of the Configuration section for the given worker ship plugin.
    # You can override this if you want in your own subclass to just be a flat string, but by default this is a property that returns the name of the class.
    @property
    def worker_ship_name(self) -> str:
        """Returns the name of the worker ship, which is by default the name of the class."""
        return self.get_worker_ship_name()

    def load_template(self, raw_template: Dict[str, Any]) -> None:
        """
        This will load the template and store it in the loaded_template attribute. This will raise
        exceptions if there are validation errors.
        """
        self.payload = self.payload_template_class().load(raw_template)

    def execute(self, commit: bool = False) -> None:
        """This will execute the job from the payload."""
        raise NotImplementedError("pew pew pew")  # pragma: no cover

    def send_alert(self, message_priority: AlertPriority, title: str, body_markdown: str) -> None:
        """This will do the work to send an alert to the Alerting plugin (Slack) if it is configured."""
        if (
            self.alert_priority.value >= message_priority.value > AlertPriority.NONE.value
        ):  # the `> None` part is done to prevent NONE being passed in to the message_priority
            # Send the message
            if message_priority == AlertPriority.INFORMATIONAL:
                SLACK_CLIENT.post_info(self.alert_channel, title, body_markdown)

            elif message_priority == AlertPriority.SUCCESS:
                SLACK_CLIENT.post_success(self.alert_channel, title, body_markdown)

            elif message_priority == AlertPriority.IMPORTANT:
                SLACK_CLIENT.post_important(self.alert_channel, title, body_markdown)

            elif message_priority == AlertPriority.PROBLEM:
                SLACK_CLIENT.post_problem(self.alert_channel, title, body_markdown)


StarfleetWorkerShipInstance = TypeVar("StarfleetWorkerShipInstance", bound=StarfleetWorkerShip)
