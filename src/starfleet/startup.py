"""The main module for Starfleet's startup.

This contains the basic code for startup in Starfleet. All Lambda and CLI invocations will need to execute this.

:Module: starfleet.startup
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

from starfleet.utils.logging import LOGGER  # noqa pylint: disable=W0611
from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.account_index.loader import ACCOUNT_INDEX
from starfleet.worker_ships.loader import STARFLEET_WORKER_SHIPS


def base_start_up() -> None:
    """This is a function that will execute all startup related tasks that needs to be performed for Starfleet to function.

    The start-up order is as follows:
    1. Load the base configuration
    2. Set up the logger (TODO: add metrics plugins)
    """
    # Step 1: Load the base configuration, which also configures the logger for the app:
    STARFLEET_CONFIGURATION.config  # noqa pylint: disable=pointless-statement


def starbase_start_up() -> None:
    """This is a function that will execute all startup related tasks that needs to be performed for Starfleet's starbase to function.

    The start-up order is as follows:
    1. Load the base startup
    2. Set up the account index
    3. Set up the worker ships
    """
    base_start_up()

    # Account Index:
    ACCOUNT_INDEX.index  # noqa pylint: disable=pointless-statement

    # Worker Ships:
    STARFLEET_WORKER_SHIPS.get_worker_ships()  # noqa pylint: disable=pointless-statement
