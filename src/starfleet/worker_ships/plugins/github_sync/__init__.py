"""Starfleet's worker for syncing a GitHub repository contents to S3

This is a worker ship that will periodically verify that a GitHub repository's contents are identical to that
of an S3 bucket. It will add, remove, and update any file in S3 that is not in the corresponding GitHub repo.

This is primarily used for syncing Starfleet templates to S3 for CI/CD, but can be used for any other purpose.

:Module: starfleet.worker_ships.plugins.github_sync
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from starfleet.worker_ships.plugins.github_sync.ship import GitHubSyncWorkerShip, sync_github

WORKER_SHIP_PLUGINS = [GitHubSyncWorkerShip]
CLICK_CLI_GROUPS = [sync_github]
