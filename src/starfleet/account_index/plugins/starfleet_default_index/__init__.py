"""The Starfleet default Account Index Plugin

This is the module for the Default Account Index plugin that utilizes the index geneated by the AccountIndexGeneratorShip plugin.

:Module: starfleet.account_index.plugins.starfleet_default_index.ship
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

from starfleet.account_index.plugins.starfleet_default_index.ship import StarfleetDefaultAccountIndex

ACCOUNT_INDEX_PLUGINS = [StarfleetDefaultAccountIndex]
