# Starbase

Now that you understand what the Worker ships are and what they do, the configuration and the payload templates, the next phase is to understand the heart of Starfleet, and that's the Starbase.

The Starbase is the component of Starfleet that invokes all the worker ships. As a matter of design, the Starbase is the primary way for a worker ship to be invoked. The Starbase does the heavy lifting of needing to:

1. Determine which worker ships need to run
2. Task the worker ships with the necessary payload for the AWS account to run in

Each worker ship provides details to the Starbase so that it knows how to task it. The worker defines:

1. Which "source" of invocation it should be tasked with
1. How to divvy out the workloads (single, per-account, per-account/region pair)
1. The location of the payload YAML in the template S3 bucket
1. The SQS queue to place the payload for invocation

The Starbase uses a combination of the details above and the account index. The payload (YAML) is written according to a special schema specified by the given worker ship. The Starbase renders the payload schema and attaches the account and regional details (if required) before invoking the worker. The worker is invoked by placing the rendered payload onto an SQS queue that the worker ship is configured to invoke from.

## Invocation Sources
These are the mechanisms that the Starbase is invoked by. This affects how and when the Starbase tasks workers.  The Starbase is invoked 3 ways that you should care about*:

1. EventBridge Timed Events
1. Template S3 Bucket Events (Not yet implemented)
1. SNS for a given worker ship (Not yet implemented)

*See the in the weeds section below for the 4th way - this is not something you need to care about.

!!! Tip
    A worker ship can specify multiple invocation sources

### EventBridge Timed Events
Each worker can be invoked by EventBridge timed events for a CRON like functionality. The worker ship configuration specifies this. At a minimum, it needs:

```yaml
InvocationSources:
  - EVENTBRIDGE_TIMED_EVENT
EventBridgeTimedFrequency: HOURLY  # This is for an hourly job. See below for the types.
```

The general gist is that worker ship's configuration specifies that it is to be invoked by an `EVENTBRIDGE_TIMED_EVENT` and it specifies the `EventBridgeTimedFrequency` for which timed event to get invoked by.

As mentioned, the worker ship's configuration also contains a path in the Payload Template S3 Bucket that stores the worker ship's payload templates. The Starbase will list all the payload YAMLs associated with the worker ship, and then render the payloads for the AWS accounts they are specified to run against. All of these get tasked to the worker ship to perform it's job.

#### Event Frequencies
The following is a list of supported frequencies that a worker can be timed for. These are the exact string values that need to be in the worker's configuration:

```yaml
THIRTY_MIN      # Every 30 min / half-hourly
HOURLY          # Every 60 min / hourly
SIX_HOURLY      # Every 6 hours
TWELVE_HOURLY   # Every 12 hours / half-daily
DAILY           # Once a day / every 24 hours
```

A worker can only specify one event frequency.

### Template S3 Bucket Events -- Not yet implemented
Each worker can be invoked whenever a template in it's configured template path is created or updated. This is useful for CI/CD operations where placing a template in the bucket automatically triggers a payload execution.

The worker ship configuration specifies this. At a minimum, it needs:

```yaml
InvocationSources:
  - S3
```

The Starbase will receive this event, fetch the template from S3, render it in conjunction with the account index and then task the worker to run.

### SNS for a given worker ship -- TBD
This section is still TBD and will be ironed out in the future.


## In the weeds

!!! note
    Timed event invocations actually happen in 2 parts, where the Starbase _will actually task itself_. This is explained here:

    #### Part 1 - Find the associated worker ships
    In part 1 of the timed event invocation, the Starbase locate the workers that are configured for the timed event in question. It will list all the template YAMLs in S3 associated with the worker, and it will then put the details of the Starfleet Worker Ship and the corresponding template YAML path into an SQS queue that the Starbase will invoke from. Then part 2 begins.

    #### Part 2 - Fan out and task the workers for the template
    In part 2 of the timed event invocation, the Starbase will receive a message on it's SQS queue informing it of the name of the Starfleet worker to task and the template YAML in S3 to render. The Starbase will then render the template in conjunction with the account index, and then task the worker ship with the payloads and account details.

    #### Why??
    This may seem overly complicated (maybe it is?), but this is done to prevent the Starbase from timing out when putting SQS messages onto the worker queues. This is done so that the Starbase can parallelize the tasking of workers, which when needing to task workers for every account or every account/region pair, that could be a lot of Lambda functions to task. This keeps things fast and scalable.
