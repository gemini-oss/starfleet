"""The main module for Starfleet's startup.

This contains the basic code for startup in Starfleet. All Lambda and CLI invocations will need to execute this.

:Module: starfleet.startup
:Author: Mike Grima <michael.grima@gemini.com>
"""
from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER  # noqa pylint: disable=W0611


def base_start_up() -> None:
    """This is a function that will execute all startup related tasks that needs to be performed for Starfleet to function.

    The start-up order is as follows:
    1. Load the base configuration
    2. Set up the logger (TODO: add metrics plugins)
    """
    # Step 1: Load the base configuration, which also configures the logger for the app:
    STARFLEET_CONFIGURATION.load_base_configuration()
