"""# Account Index Plugin Loader

This defines the loader for the account index plugin. This uses the same logic as the other loaders. The loader here will locate
the account index plugins and it will instantiate the plugin that is set by the Starfleet `AccountIndex` configuration field.
That plugin must exist. Once instantiated, then it is accessible by the loader and can be used by anything that needs it.

:Module: starfleet.account_index.loader
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import starfleet.account_index.plugins
from starfleet.account_index.schematics import AccountIndex, AccountIndexInstance
from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER
from starfleet.utils.plugin_loader import find_plugins


class UnknownAccountIndexError(Exception):
    """Exception that is raised when a requested account index isn't in the registry."""


class StarfleetAccountIndexLoader:
    """This will load the account index plugins and is used by the Starbase to interact with them."""

    # These are defined here for easy testability:
    _index_ship_path: str = starfleet.account_index.plugins.__path__
    _index_ship_prefix: str = starfleet.account_index.plugins.__name__ + "."

    def __init__(self):
        self._index: AccountIndexInstance = None  # noqa

    def reset(self):
        """Used for unit tests. This resets the index."""
        self._index = None

    def load_indexes(self):
        """
        This will load all the account index plugins and add them to a registry. Once in the registry the chosen account index class will be
        instantiated and accessed.
        """
        registry = {}
        self._index = None

        LOGGER.debug("[📇] Loading the account index plugins...")
        try:
            for _, plugin_classes in find_plugins(self._index_ship_path, self._index_ship_prefix, "ACCOUNT_INDEX_PLUGINS", AccountIndex).items():
                for plugin in plugin_classes:
                    LOGGER.debug(f"[🔧] Configuring account index ship: {plugin.__name__}")

                    # Register the plugin:
                    registry[plugin.__name__] = plugin  # noqa
                    LOGGER.debug(f"[🌟] Account Index: {plugin.__name__} has been discovered.")

            # Load the chosen one in the main configuration
            chosen_index_plugin = STARFLEET_CONFIGURATION.config["STARFLEET"]["AccountIndex"]
            index = registry.get(chosen_index_plugin)
            if not index:
                LOGGER.error(
                    f"[🤷] Can't find the chosen account index plugin: {chosen_index_plugin}. The following {len(registry)} plugins were detected:"
                    f" {','.join(registry.keys())}"
                )
                raise UnknownAccountIndexError(chosen_index_plugin)

            # Instantiate the index:
            LOGGER.debug(f"[🏗️] Loading up the index: {chosen_index_plugin}...")
            self._index = index()

        except Exception as exc:
            LOGGER.error("[💥] Problem loading the account index plugins. See the stacktrace for details.")
            LOGGER.exception(exc)
            raise

    @property
    def index(self) -> AccountIndexInstance:
        """This will prepare the selected index for use."""
        if not self._index:
            self.load_indexes()

        return self._index


ACCOUNT_INDEX = StarfleetAccountIndexLoader()
