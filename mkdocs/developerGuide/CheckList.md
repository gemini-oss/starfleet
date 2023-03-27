# Development Check List

This page is a simple check list to double-check that you have done all the steps you needed.

- [x] You set up the virtual environment and are inside of the virtual environment - [Link](Overview.md#set-up-virtual-environment)
- [x] You installed the requirements - [Link](Overview.md#install-the-dependencies)
- [x] You created (or your deployment script places) your Worker Ship Python package under `src/starfleet/worker_ships/plugins/` - [Link](primaryComponents/workerShips/Overview.md#worker-ship-residency)
- [x] Your Worker Ship Plugin has a configuration schema that is a subclass of `WorkerShipBaseConfigurationTemplate` - [Link](primaryComponents/workerShips/Overview.md#configuration)
- [x] Your Worker Ship Plugin has a payload template schema that is a subclass of `WorkerShipPayloadBaseTemplate` (this includes the account and account/region base classes) - [Link](primaryComponents/workerShips/Overview.md#payload-template)
- [x] Your Worker Ship Plugin contains a class that subclasses `StarfleetWorkerShip` _and_ configures it with all the required components, like the schemas, and also implements the `execute` function to do the thing that needs to be done - [Link](primaryComponents/workerShips/Overview.md#the-worker-ship-class)
- [x] You created a `lambda_handler` function that is wrapped by the `@worker_lambda` decorator - [Link](primaryComponents/workerShips/LambdaEntrypoints.md)
- [x] You created a `click.group` decorated function, and also some CLI commands for that group - [Link](primaryComponents/workerShips/CLI.md)
- [x] In your plugin package's `__init__.py`, you defined both `WORKER_SHIP_PLUGINS` set to a list of the `StarfleetWorkerShip` classes you defined - [Link](primaryComponents/workerShips/Loader.md#make-starfleet-see-your-worker-and-clis)
- [x] In your plugin package's `__init__.py`, you defined both `CLICK_CLI_GROUPS` set to a list of the `click.group()` decorated functions you defined - [Link](primaryComponents/workerShips/Loader.md#make-starfleet-see-your-worker-and-clis)
- [x] You made extensive pytest tests for your Worker Ship Plugin with nice fixtures 100% test coverage. Yes 💯% test coverage! See the existing tests for details on how to make good tests.
- [x] You created (or your deployment script places) your Starfleet configuration with the proper configuration entries in `src/starfleet/configuration` - [Link](primaryComponents/ConfigurationManager.md)
- [x] You made the necessary changes to the SAM Template for your Lambdas to get deployed (don't forget to update the configuration to include the SQS URLs!) - [Link](SAMConfiguration.md)
- [x] Your payload template resides in the template S3 bucket where your worker expects it
- [x] Make sure your Lambda has enough time and memory to run. You'll need to monitor the logs to see how much RAM and time it takes to run your workload to make adjustments in the SAM template.

There are probably more but this should help you isolate and detect issues should they arise.
