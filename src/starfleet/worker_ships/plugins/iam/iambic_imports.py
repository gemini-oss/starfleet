"""File to handle the IAMbic imports. This is done to avoid logger issues.

:Module: starfleet.worker_ships.plugins.iam.iambic_imports
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-import,wrong-import-position,wrong-import-order
from unittest import mock

from starfleet.utils.logging import LOGGER

# Mock out the iambic logger, as it's bossy and overrides Starfleet's:
mock.patch("iambic.core.logger.log", LOGGER).start()

# Now continue to import the rest:
from iambic.core.context import ctx as iambic_ctx  # noqa: E402,F401
from iambic.core.models import Variable  # noqa: E402,F401
from iambic.plugins.v0_1_0.aws.iam.role.models import AwsIamRoleTemplate  # noqa: E402,F401
from iambic.plugins.v0_1_0.aws.models import AWSAccount  # noqa: E402,F401
