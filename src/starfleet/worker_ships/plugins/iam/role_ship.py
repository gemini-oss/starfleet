"""Starfleet's worker for IAM role syncing

This is a worker ship that syncs IAM roles. This worker ship utilizes the iambic.org's iambic library to sync the roles out. As such this worker
mostly just does what iambic does.

:Module: starfleet.worker_ships.plugins.iam.role_ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=too-many-locals,too-many-statements,too-many-branches
import asyncio
import json
import os
import sys
from difflib import Differ
from typing import Dict, Any, TypeVar

import click
import yaml
from click import Context

from marshmallow import ValidationError as MarshmallowError
from pydantic import ValidationError as PydanticError

from starfleet.account_index.loader import ACCOUNT_INDEX
from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER

from starfleet.worker_ships.cli_utils import StarfleetAccountCommand, StarfleetSingleInvokeCommand
from starfleet.worker_ships.lambda_utils import worker_lambda
from starfleet.worker_ships.plugins.iam.schemas import (
    IamRoleWorkerConfigurationTemplate,
    IamRoleWorkerShipPayloadTemplate,
    IambicTemplateTypes,
    render_iambic_template,
    make_iambic_variables,
)
from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip, FanOutStrategy, AlertPriority
from starfleet.worker_ships.plugins.iam.iambic_imports import AWSAccount, AwsIamRoleTemplate, iambic_ctx


class IambicFailedError(Exception):
    """Raised if there were exceptions in the iambic result's exceptions_seen list."""


class NiceYamlDump(yaml.Dumper):  # pylint: disable=too-many-ancestors
    """
    This is code that will properly indent YAML since the built-in one doesn't do a great job.
    Special shout out to: https://stackoverflow.com/questions/25108581/python-yaml-dump-bad-indentation/39681672#39681672
    """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


class IamRoleWorkerShip(StarfleetWorkerShip):
    """This is a worker ship for IAM roles. This leverages the iambic library to roll out IAM roles to the desired places."""

    fan_out_strategy = FanOutStrategy.ACCOUNT
    payload_template_class = IamRoleWorkerShipPayloadTemplate
    configuration_template_class = IamRoleWorkerConfigurationTemplate

    def render_iambic_template(self, commit: bool = False) -> Dict[str, Any]:
        """This will render the iambic template and return it back out."""
        return render_iambic_template(self.payload, IambicTemplateTypes.IAM_ROLE, commit)

    def prepare_iambic_template(self, rendered_template: Dict[str, Any]) -> AwsIamRoleTemplate:
        """This will perform the additional validation that is needed to load and generate the iambic template."""
        AwsIamRoleTemplate.update_forward_refs()
        return AwsIamRoleTemplate(**rendered_template)

    def execute(self, commit: bool = False) -> None:
        """Execute the payload to sync out."""
        config = self.configuration_template_class().load(STARFLEET_CONFIGURATION.config[self.worker_ship_name])

        # Pull out the payload details for this account:
        account = self.payload["starbase_assigned_account"]

        # Render out the template:
        try:
            LOGGER.debug("[✨] Rendering the iambic IAM Role template...")
            rendered_template = self.render_iambic_template(commit=commit)
            LOGGER.debug(f"[🧾] The rendered template is:\n{yaml.dump(rendered_template, Dumper=NiceYamlDump)}")

            LOGGER.debug("[🧐] Verifying that iambic can load it...")
            working_template = self.prepare_iambic_template(rendered_template)
            LOGGER.debug("[✅] The template is valid!")

        except MarshmallowError as merr:
            LOGGER.error(f"[❌] The template invalid: {merr}")
            raise

        except PydanticError as perr:
            LOGGER.error(f"[❌] The template failed iambic validation: {perr}")
            raise

        # Generate the iambic account object and all work associated with it:
        account_name = ACCOUNT_INDEX.index.get_account_names({account})[account]
        os.environ["IAMBIC_SESSION_NAME"] = config["worker_role_session_name"]  # The assume role session name is an environment variable: IAMBIC_SESSION_NAME
        aws_account = AWSAccount(
            **{
                "account_id": account,
                "account_name": account_name,
                "partition": "aws",
                "spoke_role_arn": f"arn:aws:iam::{account}:role/{config['worker_role_to_assume']}",
                "assume_role_arn": f"arn:aws:iam::{account}:role/{config['worker_role_to_assume']}",
                "variables": make_iambic_variables(self.payload["iambic_variables"]),
                "iambic_managed": "enforced",  # This must always be set to enforced.
            }
        )

        # Iambic has a read-only switch here as well:
        iambic_ctx.eval_only = not commit  # If not commit, then this is true, and if commit then this is false.

        # Make the loop and asyncio stuff:
        LOGGER.info("[🎹] Running iambic...")
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(working_template._apply_to_account(aws_account))
        except Exception as err:
            LOGGER.error(f"[❌] An error occurred when running iambic: {err}")
            LOGGER.exception(err)
            raise
        finally:
            loop.close()

        if result.exceptions_seen:
            LOGGER.error(f"[❌] Iambic encountered the following exceptions: {', '.join(result.exceptions_seen)}")  # noqa
            raise IambicFailedError(result.exceptions_seen)

        # We need to make the action summary
        if not result.proposed_changes:
            LOGGER.info("[⏭️] No changes detected. Nothing to do.")
            return

        # If we are creating a brand new role then the diff logic is going to be different.
        if result.new_value and not result.current_value:
            diff_text = "Field: The entire role -- the role was missing and was created."

        else:
            differ = Differ()
            diff_texts = []
            for change in result.proposed_changes:
                diff_text = f"Resource ID: {change.resource_id}, Update Type: {change.change_type.value}, Field: {change.attribute},\n"
                diff_text += "".join(
                    list(
                        differ.compare(
                            json.dumps(change.current_value, indent=2, sort_keys=True).splitlines(keepends=True),
                            json.dumps(change.new_value, indent=2, sort_keys=True).splitlines(keepends=True),
                        )
                    )
                )
                diff_texts.append(diff_text)

            diff_text = "\n\n".join(diff_texts)

        if commit:
            LOGGER.info(f"[📝] The following changes have been made:\n{diff_text}")

            # Alerts:
            self.send_alert(
                AlertPriority.IMPORTANT,
                f"IAM Role: {working_template.resource_id} in {account_name} was created/updated",
                f"The following changes have been made:\n>```\n{diff_text}\n```",
            )

        else:
            LOGGER.info(f"[📝] The following changes would have been made if the commit flag was set:\n{diff_text}")


@click.group()
@click.pass_context
def role(ctx: Context) -> None:
    """
    This is the worker ship for processing a Starfleet-wrapped iambic.org IAM role template.

    Note: The account index is utilized for these commands and as such, AWS credentials may be required to run them.
    """
    ctx.obj = IamRoleWorkerShip()


# This specific command is single invoke since we are not doing any account specific logic. This just verifies that the template is valid. For the account specific logic
# we have the sync command where you must specify the account to run in, and that can be used for dry-runs.
@role.command(cls=StarfleetSingleInvokeCommand)
@click.pass_context
def validate_iambic(ctx: Context, **kwargs) -> None:  # noqa # pylint: disable=unused-argument
    """This will validate the supplied Starfleet-wrapped iambic.org template to confirm that it is valid."""
    worker = ctx.obj
    LOGGER.info("[✨] Rendering the iambic IAM Role template...")
    try:
        rendered_template = worker.render_iambic_template()
    except MarshmallowError as verr:
        LOGGER.error(f"[❌] The template is invalid: {verr}")
        sys.exit(-1)

    LOGGER.info(f"[🧾] The rendered template is:\n{yaml.dump(rendered_template, Dumper=NiceYamlDump)}")

    LOGGER.info("[🧐] Verifying that iambic can load it...")
    try:
        worker.prepare_iambic_template(rendered_template)
    except PydanticError as verr:
        LOGGER.error(f"[❌] The template failed iambic validation: {verr}")
        sys.exit(-1)

    # If there are no exceptions, then everything is good.
    LOGGER.info("[✅] The template is valid!")


@role.command(cls=StarfleetAccountCommand)
@click.pass_context
def sync(ctx: Context, commit: bool, **kwargs) -> None:  # noqa # pylint: disable=unused-argument
    """This will invoke iambic to sync out the IAM role."""
    if not commit:
        LOGGER.warning("[⚠️] Commit flag is disabled: not making any changes")

    worker = ctx.obj
    worker.execute(commit=commit)

    LOGGER.info("[✅] Done!")


IamRoleWorkerShipInstance = TypeVar("IamRoleWorkerShipInstance", bound=IamRoleWorkerShip)


@worker_lambda(IamRoleWorkerShip)
def lambda_handler(event: Dict[str, Any], context: object, worker: IamRoleWorkerShipInstance, commit: bool) -> None:  # noqa pylint: disable=W0613
    """This is the Lambda entrypoint for the IamRoleWorkerShip event from the Starbase."""
    for record in event["Records"]:
        # Load the payload:
        payload = json.loads(record["body"])
        LOGGER.debug(f"[⚙️] Processing Payload: {payload}")
        worker.load_template(payload)

        # Process it!
        worker.execute(commit=commit)
        LOGGER.info("[✅] Done!")

    LOGGER.info("[🏁] Completed syncing IAM Role.")
