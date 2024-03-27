"""File to handle the IAMbic imports. This is done to avoid logger issues.

:Module: starfleet.worker_ships.plugins.iam.iambic_imports
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

# pylint: disable=unused-import,wrong-import-position,wrong-import-order
from unittest import mock

from starfleet.utils.logging import LOGGER


def _format_message(message: str, **kwargs) -> str:
    """Takes in the logging message and the kwargs and formats them so the default Python logger will be happy."""
    return f"{message} - logger_kwargs: {kwargs}"


class StarfleetIAMbicLoggerOverrider:
    """Class that addresses IAMbic's custom logging functionality."""

    def debug(self, text: str, **kwargs) -> None:
        """Mocks out the IAMbic logger debug log."""
        LOGGER.debug(_format_message(text, **kwargs))

    def info(self, text: str, **kwargs) -> None:
        """Mocks out the IAMbic logger info log."""

        LOGGER.info(_format_message(text, **kwargs))

    def error(self, text: str, **kwargs) -> None:
        """Mocks out the IAMbic logger error log."""

        LOGGER.error(_format_message(text, **kwargs))


iambic_logger = StarfleetIAMbicLoggerOverrider()

# Mock out the iambic logger, as it's bossy and overrides Starfleet's:
mock.patch("iambic.core.logger.log", iambic_logger).start()

# Now continue to import the rest:
from iambic.core.context import ctx as iambic_ctx  # noqa: E402,F401
from iambic.core.models import Variable  # noqa: E402,F401
from iambic.plugins.v0_1_0.aws.iam.role.models import AwsIamRoleTemplate  # noqa: E402,F401
from iambic.plugins.v0_1_0.aws.models import AWSAccount  # noqa: E402,F401
