"""Starfleet's worker ship plugin loader logic.

This does all the logic required to load Starfleet plugins.

:Module: starfleet.util.plugin_loader
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

# from importlib.metadata import entry_points
import importlib
from pkgutil import iter_modules
from typing import Dict, List, Type

from starfleet.utils.logging import LOGGER


class InvalidPluginListException(Exception):
    """Exception raised if the name for where to pull out a list of plugins isn't actually a list."""


class InvalidPluginClassException(Exception):
    """Exception raised if the plugin is not a valid Starfleet plugin object."""


def find_plugins(package_path: str, package_prefix: str, plugin_attr_name: str, plugin_super_class: Type, verify_class=True) -> Dict[str, List[Type]]:
    """This is a function that will be used for loading Starfleet plugins. It will work by iterating for plugins that reside in packages in the given path. This will then
    attempt to load the modules for that path.

    For all Starfleet plugins, there needs to be an __init__.py that specifies the `plugin_attr_name` that is passed in here, which is a list of the plugin classes to load.
    There is also a `plugin_super_class`, which is the superclass that the plugin must be a subclass of (`verify_class` = True) -- OR --
    it will check if the object is an instance of the super class -- this is set by the boolean flag passed in as `verify_class` = False
    """
    plugins = {}
    if verify_class:
        verify_method = issubclass
    else:
        verify_method = isinstance

    LOGGER.debug(f"[🏗️] Loading plugins in the {package_path} location...")
    for package in iter_modules(package_path, package_prefix):
        LOGGER.debug(f"[⚙️] Processing module named: {package.name}")
        module = importlib.import_module(package.name)

        # Next, check that the module contains the variable that will hold the plugin classes:
        if hasattr(module, plugin_attr_name):
            # Next, check that it's a list:
            list_of_plugins = getattr(module, plugin_attr_name)
            if not isinstance(list_of_plugins, list):
                raise InvalidPluginListException(
                    f"[💥] The package: {package.name} needs a variable named {plugin_attr_name} that is of type List, not " f"type: {type(list_of_plugins)}"
                )

            for plugin in list_of_plugins:
                if not verify_method(plugin, plugin_super_class):
                    raise InvalidPluginClassException(
                        f"[💥] The plugin: {plugin.__name__} in package: {package.name} does not properly subclass: {plugin_super_class.__name__}"
                    )

            plugins[package.name] = list_of_plugins
            LOGGER.debug(f"[👍] Found {len(list_of_plugins)} plugins in {package_path}")

        else:
            LOGGER.debug(f"[⏭️] Skipping module: {package.name} because it lacks the {plugin_attr_name} List")

    return plugins
