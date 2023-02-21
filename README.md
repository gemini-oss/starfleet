# Starfleet

## 🚧🏗️👷⚠️Special Note: This project is under heavy development

## What is it?
This is a whole AWS infrastructure automation tool that is able to run Lambda functions with AWS account specific workloads.
It's primary purpose is to enable cloud and infrastructure security teams the ability to run automation for ensuring infrastructure
state across an entire AWS organization in a manner that cannot adequately be achieved with AWS Organizations.

You can make lambdas to do whatever it is that you want to do with the proper context of the AWS account or region that you want
to operate in.

## Documentation
Starfleet is extensively documented here: https://gemini-oss.github.io/starfleet


## TODO Move these into the mkdocs:
## Worker Ships
Each worker is a "worker ship", or a plugin. Plugins are loaded based on where they are placed in the directory path. All workers need to reside in the
`worker_ships/plugins/*` path. Each plugin needs to implement (subclass) the `StarfleetWorkerShip` class. This class outlines the configuration templates
and also the payload templates for each worker. This will also contain a list of `click.group()` wrapped functions that are added to the `clis` list.

Each worker has 2 primary functions:
1. `load_template`, which loads the payload template, and stores it in the `self.payload` attribute as a Dictionary to be referenced easily by the worker
2. `execute`, which will perform the work for the plugin

For the worker to function, in addition to the plugin details to be implemented, you also need:
1. In the plugin's `__init__.py`, a `WORKER_SHIP_PLUGINS` `list` that contains a list of the subclassed `StarfleetWorkerShip` classes that the plugin exposes.
2. The plugin needs a configuration entry (defined in the plugin's `worker_ship_name` attribute), with `Enabled: True` being set for the plugin to be usable.

## CLI
CLIs are based entirely on the Python [click](https://click.palletsprojects.com) library. On startup, all the plugins are loaded and the CLIs are dynamically determined.

There are some convenience functions to help solve common boilerplate operations:
1. `load_payload` - used with `@click.option("--payload", required=True, type=click.File("r"), callback=load_payload)`: This decorator will return the dictionary of the payload
    that has _not_ been verified. It only does the work to load a payload off disk and return the YAML as a Dictionary.
