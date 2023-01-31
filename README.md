# Starfleet

## 🚧🏗️👷⚠️Special Note: This project is under heavy development

## What is it?
This is a whole AWS infrastructure automation tool that is able to run Lambda functions with AWS account specific workloads.
It's primary purpose is to enable cloud and infrastructure security teams the ability to run automation for ensuring infrastructure
state across an entire AWS organization in a manner that cannot adequately be achieved with AWS Organizations.

You can make lambdas to do whatever it is that you want to do with the proper context of the AWS account or region that you want
to operate in. Starfleet operates with the following components and concepts:

1. Cloud Account Index (Completed) - This is an index of all AWS accounts that you need to operate over. This provides Starfleet with the context
   of what worklaods to run in which accounts (workloads assume an IAM role in the target account)
2. Worker "ships" - These are Lambda functions that execute a payload in the context of an AWS account. Ships can be tasked to run a workload in any
   variety of AWS accounts, regions, or even just a single invocation for a 1 time task
3. Template YAMLs - Human readable templates that describe what the state of an infrastructure component should be across your infrastructure.
   Example: an IAM role that should be configured the same across all accounts, but maybe slightly differently in 1 account vs. another.
4. The "Starbase" - this is the component that will task the Lambda functions accordingly. This looks at the templates and figures out how many
   worker ship Lambdas to task to complete the job
5. Events and Triggers - Starfleet is invoked by a variety of mechanisms, including EventBridge timed events (cron-like), or events from updates to
   worker templates in S3, or a combination thereof

## Configuration
Starfleet's base configuration resides as YAML files in the `starfleet/configuration_files` directory. It will load this on startup as the first thing that is done.

All the application's main configuration entries reside in the `STARFLEET` section, such as `LogLevel`. Each component (worker, and the starbase) will have their own
respective sections.

## Worker Ships
Each worker is a "worker ship", or a plugin. Plugins are loaded based on where they are placed in the directory path. All workers needs to reside in the
`worker_ships/plugins/*` path. Each plugin needs to implement (subclass) the `StarfleetWorkerShip` class. This class outlines the configuration templates
and also the payload templates for each worker. This will also contain a list of `click.group()` wrapped functions that is added to the `clis` list.

Each worker has 2 primary functions:
1. `load_template`, which loads the payload template, and stores it in the `self.payload` attribute as a Dictionary to be referenced easily by the worker
2. `execute`, which will perform the work for the plugin

For the worker to function, in addition to the plugin details to be implemented, you also need:
1. In the plugin's `__init__.py`, a `WORKER_SHIP_PLUGINS` `list` that contains a list the subclassed `StarfleetWorkerShip` classes that the plugin exposes.
2. The plugin needs a configuration entry (defined in the plugin's `worker_ship_name` attribute), with `Enabled: True` being set for the plugin to be usable.

_TODO: Add details about the entrypoints_

## CLI
CLIs are based entirely on the Python [click](https://click.palletsprojects.com) library. On startup, all the plugins are loaded and the CLIs are dynamically determined.

There are some convenience functions to help solve common boilerplate operations:
1. `load_payload` - used with `@click.option("--payload", required=True, type=click.File("r"), callback=load_payload)`: This decorator will return the dictionary of the payload
    that has _not_ been verified. It only does the work to load a payload off disk and return the YAML as a Dictionary.
