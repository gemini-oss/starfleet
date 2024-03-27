"""Starfleet's worker for dumping an account inventory to S3.

This is a worker ship that will periodically dump an inventory of AWS accounts from the organizations API.

:Module: starfleet.worker_ships.plugins.account_index_generator
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

from starfleet.worker_ships.plugins.account_index_generator.ship import AccountIndexGeneratorShip, account_inventory

WORKER_SHIP_PLUGINS = [AccountIndexGeneratorShip]
CLICK_CLI_GROUPS = [account_inventory]
