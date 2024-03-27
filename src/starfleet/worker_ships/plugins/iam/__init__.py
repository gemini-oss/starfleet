"""Starfleet workers for IAM related things

These are worker ships for IAM related things, like roles.

:Module: starfleet.worker_ships.plugins.iam
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

import click

from starfleet.worker_ships.plugins.iam.role_ship import IamRoleWorkerShip, role


# Roll up the IAM CLI commands under one group:
@click.group()
def iam() -> None:
    """
    This is the parent command group for all Starfleet worker commands. Each worker implements their own subcommands for this.

    All IAM workers leverage the 3rd party iambic library. Please see iambic.org for details on how to write IAM templates. Also, check out the Starfleet
    documentation on this worker as Starfleet has some implementation specific details.

    Note: The account index is utilized for these commands and as such, AWS credentials may be required to run them.
    """


# Add in role commands:
iam.add_command(role)  # noqa


WORKER_SHIP_PLUGINS = [IamRoleWorkerShip]
CLICK_CLI_GROUPS = [iam]
