# Account Indexer

The Account Index plugin is loaded by the Starbase and optionally other worker ships if they need it. [As mentioned](../../architecture/AccountIndex.md), the purpose is to provide an inventory of AWS accounts that Starfleet can operate on.

An Account Indexer is required for the Starbase to function, and for your account and account/region based workers to function. Starfleet requires the name of an account index plugin to be provided in the `STARFLEET` stanza of the configuration with the field `AccountIndexer: AccountIndexPluginNameHere`.

## Default Account Index
By default, Starfleet will leverage the `StarfleetDefaultAccountIndex` plugin. This plugin leverages the generated account index JSON that is produced by the `AccountIndexGeneratorShip` plugin saved to S3. You will first need to have that index generator run before any other workers can be used with this account index.

If the default account index is not sufficient for your use case, then you are welcome to make your own. See below.

## Account Index Plugin Residency
Account index plugins need to reside in the `src/starfleet/account_index/plugins/` directory. This is exactly the same pattern that is used for worker ship plugins.

At a minimum, you'll need a `__init__.py` file. We'll cover more about this file in the Worker Ship Loader portion. For now, just now that you will need a directory that looks like this:

```
...
account_index
└── plugins
    └── your_plugin
            └── __init__.py
            └── some_other_python_file.py
            └── ...
```

See the [Developer Guide Overview](../Overview.md#packaging-deployment-considerations) page on more details on packaging non-OSS and internal worker ship plugins.

## Base Class
Like with worker ships, there is a base class named `AccountIndex` that resides in `starfleet.account_index.schematics` that you need to sub-class. This class has a number of methods that resolve AWS account IDs. The plugin needs to interact with whatever AWS account inventory system you use to pull out the requested details. Generally, the methods will return a Python set of AWS Account ID strings back out. The Starbase will heavily rely on Python `set` logic for coming up with the proper list of accounts to iterate over.

## Registering the Plugin
Similar to the worker ships, the account index plugin needs to have a `__init__.py` file that has a list named `ACCOUNT_INDEX_PLUGINS` equal to a list of `AccountIndex` sub-classes.

The `StarfleetDefaultAccountIndex` is a great example:
```python
from starfleet.account_index.plugins.starfleet_default_index.ship import StarfleetDefaultAccountIndex

ACCOUNT_INDEX_PLUGINS = [StarfleetDefaultAccountIndex]
```

### Configuration
For Starfleet to use your account index plugin, you need to have it configured to use it. At a minimum, you need to set the name of the plugin class in the `STARFLEET` configuration stanza's `AccountIndex` field. I.e. if your class is named `class FooAccountIndexPlugin`, then you will want to have `AccountIndex: FooAccountIndexPlugin` in your `STARFLEET` configuration stanza.

As far as Marshmallow schemas are concerned, we do not require you to define one, however you are welcome to should you desire. If you do this, then add the logic in your plugin's `init()` function call. See the `StarfleetDefaultAccountIndex` plugin's code in `starfleet.account_index.plugins.starfleet_default_index` for details.

## Loader
Account index plugins are loaded and exposed via the `ACCOUNT_INDEX` singleton. The account index plugins are registered and the _configured_ (see above) plugin is instantiated by the singleton by calling the `ACCOUNT_INDEX.index` property to get the loaded and ready-to-go account index object back out.

The singleton has an pytest fixture named `test_index` in `tests.account_index.conftest` that overrides the path for the plugins to load plugins from `tests.account_index.testing_plugins`.

This otherwise works exactly like the worker ship loader.

!!! tip
    We recommend that if you make an account index plugin that it be as fast as possible. Reducing network IO would be desireable. But, also keep memory usage in mind since you don't want to run out of memory for your Lambda.
