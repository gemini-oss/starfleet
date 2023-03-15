# Worker Ships

The first component of Starfleet to discuss are the Worker Ships. These are Lambda functions that go out and do the work that is needed in each account, account/region pair, or non-AWS account. The choice is yours!

A worker ship has the following components:

1. The logic to do the work
1. A configuration that outlines important details required to make it functional
1. A payload template(s) and corresponding schema that informs the worker what to do and where to do it
1. A "Fan Out" strategy
1. An Invocation SQS queue
1. An "invocation source" -- this is outlined more in the Starbase section

## The Logic
The workers are just AWS Lambda functions written in Python. They do whatever they are coded to do. For AWS related activities, these are largely going to be `boto3` calls to the AWS API.

!!! note
    Starfleet Lambda functions are designed to be idempotent and stateless. If a failure occurs, the Lambda function should retry the payload. As mentioned below, a DLQ is set to capture failed payloads after several failed attempts (should they occur).

## The Configuration
The next section of the documentation goes into more detail about Starfleet's configuration. But the long and the short of it is that there is a YAML configuration in the Starfleet directory tree that describes how a worker is to be configured. Each worker defines the required items in the configuration via a schema (using the Python [Marshmallow](https://marshmallow.readthedocs.io/en/stable/) schema framework).

For now, just know that workers require a configuration entry that details what is required for it to execute properly.

### The SQS Queue
Each worker ship has an SQS queue and a corresponding dead-letter queue (DLQ). The SQS queue for the worker is used for invoking the Lambda function. SQS is used for a variety of reasons, namely it scales Lambda invocations very nicely, has great retry-capabilities, and DLQ integration. The DLQ is used to help debug why given payloads have failed.

### Invocation Source
A worker also needs an ==Invocation Source==. This is discussed in much more detail later when the Starbase component is explored. Instead of bouncing you back and forth, we are just going to leave a TL;DR summary of what this is: the Invocation Source is what will determine *when* the worker ship gets invoked. The worker ship can be invoked by a CRON-like event (`EVENT_BRIDGE_TIMED_EVENT`), or by an update to the worker's template in S3 (`S3`).

If using a CRON-like syntax, the configuration will need something that looks like this:
```yaml
InvocationSources:
  - EVENTBRIDGE_TIMED_EVENT
EventBridgeTimedFrequency: HOURLY  # This is for an hourly job. See the Starbase section for more details.
```

If getting invoked by updates to the payload template in S3, it needs:
```yaml
InvocationSources:
  - S3
```

Or a mixture of both:
```yaml
InvocationSources:
  - EVENTBRIDGE_TIMED_EVENT
  - S3
EventBridgeTimedFrequency: HOURLY  # This is for an hourly job. See the Starbase section for more details.
```

The `InvocationSources` is a list and thus the worker can be invoked by a variety of sources if it is developed to do so.

!!! warning
    There are other invocation sources that are being considered, like SNS or SQS, but that has not yet been ironed out or implemented. At this time the `InvocationSources` configuration is subject to change.

## The Fan Out Strategy
All workers have what is called a ==Fan Out Strategy==. This describes how a worker should be tasked. This defines whether or not a worker should be tasked to operate as a single invocation, or if there should be a worker dedicated to each AWS account, or a worker dedicated to each AWS account and region pair.

This is a property of the worker ship itself and defined in the code for it. The developer guide has more details, but for now a worker can be coded for one of the following 3 options:

```yaml
# This means that there is 1 Lambda function required to complete the task. No AWS account context is provided to the worker.
- SINGLE_INVOCATION

# This means that there should be 1 Lambda function for each AWS account to complete the task. Most workers would likely require this.
# This will provide the AWS account ID to the worker that it should operate in. The worker would assume an IAM role in that account in order
# to operate within in.
- ACCOUNT

# This means that there is 1 Lambda function for each account AND enabled AWS region. This is very similar to the ACCOUNT fan out, but this one
# also includes context on the region to operate in as well (only if that region is enabled for the given AWS account).
# This will spawn the most Lambda invocations.
- ACCOUNT_REGION
```

A worker can only be configured to have one fan out strategy.

## The Payload Template
More information is provided about the payload YAML templates in the next sections, but the key thing to note is that each worker ship has at least 1 YAML payload template. The template is intended to inform the worker what it needs to do in an invocation. Each worker defines it's own template schema (using the Python [Marshmallow](https://marshmallow.readthedocs.io/en/stable/)). A worker can be configured to support many templates. An example would be a worker that synchronizes IAM roles; in this example, there would be 1 template for each IAM role that Starfleet maintains.

All of the templates are stored in an S3 bucket (referred to loosely as the ==Template Bucket== or ==Template Payload Bucket==). It is _**required**_ that the worker's configuration specify where in the template S3 bucket it's template files exist. This can either be a path to a single file, or to a directory-like prefix where many files reside.

Here is what that configuration looks like:

```yaml
# For a single template file:
TemplatePrefix: NAME-OF-WORKER-SHIP/worker_template.yaml

# -- OR -- for many templates within a prefix (standard S3 prefix syntax):
TemplatePrefix: NAME-OF-WORKER-SHIP/
```

!!! note
    All templates must be YAML files that end in `.yaml`. Starfleet relies on S3 object listing to find the templates, so nested directory paths will also be looked at automatically.


## Next sections
Now that you understand the general gist of the worker ships, the next sections will provide more clarity about how to configure the workers, make payload templates, and also how the workers get tasked.
