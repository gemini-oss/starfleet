# Worker Ship and CLI Loaders

This section covers how we make it all work! At this point you would have set up a worker ship plugin complete with all the configuration and payload schemas. Great! 🎉 But, Starfleet won't yet know about your ship yet. This is where the worker ship loader comes in.

## Make Starfleet See Your Worker and CLIs
In your worker ship Python package, you will have an `__init__.py` file. In that file you _**must**_ to define the following:

```python
WORKER_SHIP_PLUGINS = [YOUR, PLUGIN, CLASSES, HERE]
```

If you want to expose CLIs, then in that same `__init__`.py file, file you _**must**_ to define the following:

```python
CLICK_CLI_GROUPS = [YOUR, CLICK, GROUPS, HERE]
```

A great example is the `AccountIndexGeneratorShip`'s `__init__.py`, which looks like this:

```python
from starfleet.worker_ships.plugins.account_index_generator.ship import AccountIndexGeneratorShip, account_inventory

WORKER_SHIP_PLUGINS = [AccountIndexGeneratorShip]  # NEED TO DEFINE THIS FOR STARFLEET TO KNOW ABOUT YOUR PLUGIN!
CLICK_CLI_GROUPS = [account_inventory]  # NEED TO DEFINE THIS FOR STARFLEET TO KNOW ABOUT YOUR CLI!
```

The `WORKER_SHIP_PLUGINS` is a list of the worker ship plugin classes that you want Starfleet to see. You can add in as many plugins as you want. Starfleet will locate this list and then register the worker ships to the worker ship loader so that is can be interacted with. This is what will allow the Starbase to actually find your worker ship plugin, and task it.

The `CLICK_CLI_GROUPS` works the exact same way! Only for that, you are adding in the list of Click `Group` functions. On startup, there is a CLI loader that will pick this up and register all the commands associated with it dynamically.

## The Worker Ship Loader
You don't need to know the full context of this, but it's here should you be interested in knowing.

Starfleet has a singleton defined in `starfleet.worker_ships.loader` called `STARFLEET_WORKER_SHIPS`. This is a class that will lazy load all the worker ships and verify that worker ship is configured properly and enabled. It does this by iterating through the Python packages that reside in `starfleet.worker_ships.plugins`

Calling the `STARFLEET_WORKER_SHIPS.get_worker_ships()` method returns a dictionary of the worker ship name and the enabled and instantiated worker ship object for interaction.

Feel free to dig around the code in `starfleet.worker_ships.loader` for more details on what that's doing. During unit testing we have a pytest fixture mock out the location of where the worker ships reside to `tests.worker_ship_utils.testing_plugins`. Take a look at the code in those locations for other examples of very basic Starfleet worker ship plugins.

## The CLI Loader
You also don't need to know the full context of this, but it's provided here for context.

This is super similar in concept to the Worker Ship Loader, but is used to register all the Click commands. Starfleet leverages [Python entrypoints](https://packaging.python.org/en/latest/specifications/entry-points/) in combination with [Click's support for it](https://click.palletsprojects.com/en/8.1.x/setuptools/). This is defined in `pyproject.toml` with:

```toml
[project.scripts]
starfleet = "starfleet.cli.entrypoint:cli"
```

The CLI loader has a class defined in `starfleet.cli.entrypoint`. This is the main Click group that is used. This is the `starfleet ...` command. This command group uses a custom class to load up all the CLIs named `StarfleetClickGroup`. `StarfleetClickGroup` is a class that sub-classes `click.Group` (defined in `starfleet.cli.components`), and it will, on startup:

1. Output our awesome Starfleet text logo
1. Set up the Starfleet configuration, load it, and verify it's all good
1. Load up all the worker ships, and verify they are all good
1. And then register all the CLI groups and commands to Click

At this point Click will then do the logic required to run your command. All of this is done very quickly and seamlessly for you!