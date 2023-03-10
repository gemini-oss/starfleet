# Lambda Entrypoints

For the worker ship to do anything, it needs to define the entrypoint for AWS Lambda to invoke it. This is effectively just a function that AWS Lambda will call.

We have defined some convenience functions that make this an easy(ier) process. For this, we will take the `AccountIndexGeneratorShip` as an example:


```python
@worker_lambda(AccountIndexGeneratorShip)
def lambda_handler(event: Dict[str, Any], context: object, worker: AccountIndexGeneratorShipInstance, commit: bool) -> None:  # noqa pylint: disable=W0613
    """This is the Lambda entrypoint for the AccountIndexGeneratorShip event from the Starbase."""
    for record in event["Records"]:
        # Load the payload:
        payload = json.loads(record["body"])
        LOGGER.debug(f"[⚙️] Processing Payload: {payload}")
        worker.load_template(payload)

        # Process it!
        worker.execute(commit=commit)

    LOGGER.info("[🏁] Completed generating the account index.")
```

There are a bunch of things to unpack. First: AWS Lambda needs a `lambda_handler` function. This is what Lambda will call when it wants to invoke your Lambda function. For consistency we should always name our Lambda handler function `lambda_handler`. There is usually some boilerplate work associated with Lambda and also with Starfleet. It's hard to fully abstract this away, however we are able to make it easy to copy and paste :).

## The Decorator
You'll notice in the code above that we make use of a decorator called `@worker_lambda`. You _must_ use this decorator for your Lambda handler function. What does this do? This is defined in the `starfleet.worker_ships.lambda_utils` package. This does a number of _very nice_ things for you:

1. This will automatically load the Starfleet configuration when your worker starts up, and verify that worker's configuration is configured properly
1. This instantiates the worker class
1. This handles the `commit` flag parsing (see note on that below)
1. This calls out to your Lambda handler function with the AWS Lambda provided event, `context` object, and your instantiated worker class.

The code for it even has a nice example in the doc strong on how to use this (copying here for convenience):

```python
YourWorkerShipInstance = TypeVar("YourWorkerShipInstance", bound=YourStarfleetWorkerShipClass)


@worker_lambda(WorkerShipClass)
def lambda_handler(event: Dict[str, Any], context: object, worker: YourWorkerShipInstance, commit: bool) -> None:
    for record in event["Records"]:
        payload = json.loads(record["body"])

        # Validate the payload: (don't worry about the exception handling -- that is done in the decorator!)
        LOGGER.debug(f"[⚙️] Processing Payload: {payload}")
        worker.load_template(payload)

        # Process it!
        worker.execute(commit=commit)
```

An important note is that when you wrap your `lambda_handler` function with the decorator, you need to supply the class (not the instantiation!) into the decorator. I.e. if you have a worker ship class named `FooWorkerShip`, then your lambda handler will look like this:

```python
FooWorkerShipInstance = TypeVar("FooWorkerShipInstance", bound=FooWorkerShip)

@worker_lambda(FooWorkerShip)  # <-- Pass in the worker ship class here
def lambda_handler(event: Dict[str, Any], context: object, worker: FooWorkerShipInstance, commit: bool) -> None:
    # ...
```

Once you do that, you get all the benefits you need!

## Copy and Paste Time!
Once you do have the decorated function correct, then you will just want to copy and paste in the `for` loop, as is. This will handle multiple events being provided by Lambda (you can also configure that in AWS SAM later), and it will verify and load the payload template, and then execute the workload.
