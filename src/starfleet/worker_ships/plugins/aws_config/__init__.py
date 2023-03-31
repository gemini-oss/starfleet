"""Starfleet's worker ship for enabling AWS Config recording

This is a worker ship that will operate on all accounts/regions, and ti will enable AWS Config recorders in all accounts. This will not
enable aggregation, which we are recommending that you leverage the AWS Organizations feature for. But, this worker will allow you to get
AWS Config recording in place such that you are able to make use of the organization aggregation feature.

:Module: starfleet.worker_ships.plugins.aws_config
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from starfleet.worker_ships.plugins.aws_config.ship import AwsConfigWorkerShip, aws_config

WORKER_SHIP_PLUGINS = [AwsConfigWorkerShip]
CLICK_CLI_GROUPS = [aws_config]
