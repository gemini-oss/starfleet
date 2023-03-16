# Configuration

Starfleet needs a configuration to inform it how to run and where to find foundational components.  The User Guide will have additional details and a TL;DR summary of what you should set to get things going. This section goes into depth about the fields and what they do.

## Location
The configuration files reside within the Starfleet code tree. Below is a sample of where it's located:

```
starfleet
├── src
│   ├── starfleet
│   │   ├── configuration_files  # <-- This is where the configuration YAML files go.
│   │   │   └── config_file_one.yaml
│   │   │   └── config_file_two.yaml
│   │   │   └── ...
│   │   ├── ...
│   ├── ...
├── ...
```

All the configuration files are YAML files that reside in the `src/starfleet/configuration_files` directory path. The YAML files in this path are packaged into the Lambda function that is deployed to AWS.

## Format and Schema
The configuration files are loaded on start up. All of the files are walked through in the directory path and are compiled into one big configuration map (a Python Dictionary). You can have 1 file or many. Choice is yours.

The configuration is set up in sections. Each section describes a component of Starfleet that needs to reference a configuration. The configurations must conform to a schema (Python Marshmallow) which is validated on startup. It is highly recommended that for consistency, that fields are in UpperCamelCase.

## Configuration Sections
There are a number of important sections to the configuration file for key parts of Starfleet.

Here is an example configuration file, and the sections will be explained below:

```yaml
STARFLEET:
    DeploymentRegion: us-east-2
    TemplateBucket: starfleet-templates-YOUR-ACCOUNT-ID
    FanOutQueueUrl: https://sqs.DEPLOYEMENT-REGION.amazonaws.com/ACCOUNT-ID/starbase-fanout-queue
    LogLevel: DEBUG
    ThirdPartyLoggerLevels:
        botocore: CRITICAL
        'urllib3.connectionpool': CRITICAL

AccountIndexGeneratorShip:
    Enabled: True
    TemplatePrefix: AccountIndexGenerator/Payload.yaml
    InvocationQueueUrl: https://sqs.DEPLOYEMENT-REGION.amazonaws.com/ACCOUNT-ID/starfleet-account-index-generator
    InvocationSources:
        - S3
        - EVENTBRIDGE_TIMED_EVENT
    EventBridgeTimedFrequency: HOURLY
    OrgAccountAssumeRole: starfleet-worker-role
    OrgAccountId: "YOUR-ORGANIZATION-ROOT-ACCOUNT-ID-HERE"
    OrgRootId: YOUR-ORG-ROOT-ID
    DescribeRegionsAssumeRole: starfleet-worker-role

StarfleetDefaultAccountIndex:
    IndexBucket: your-template-s3-bucket-replace-me
    BucketRegion: your-template-s3-bucket-region
    IndexObjectPath: accountIndex.json
```

### Starfleet Base Configuration - Required
The base configuration configures the primary Starfleet components. This is in the `STARFLEET` section, which is *required*. This section has some very important fields:

#### Required Fields
* **`DeploymentRegion`** - This is the AWS region that Starfleet is deployed in. This is used by some foundational components, like the Starbase (described in later sections).
* **`TemplateBucket`** - This is the S3 bucket that holds all the payload templates that are provided to the worker ships on invocation. The region for this bucket is the _same_ as the `DeploymentRegion`. If you deploy with the included AWS SAM template, then all you need to do is add in the AWS account ID that Starfleet is deployed in and you are good to go!
* **`FanOutQueueUrl`** - This is the SQS queue url for the fan out queue. This is used by the Starbase component described in later sections. This is an SQS queue that will be used drive the given worker ship's fan out strategy so that the worker can be tasked accordingly. If you are deploying with the Starfleet AWS SAM template, then all you need to do is add in the account ID and region to this string and you are good to go!
* **`AccountIndex`** - This is the _name_ of the Account Index plugin that Starfleet will use for getting an inventory of AWS accounts. This is outlined in more detail later, but is required. By default, this will use the `StarfleetDefaultAccountIndex` plugin which relies on the `AccountIndexGeneratorShip` worker ship to generate an AWS account inventory for an AWS Organization. That is also described later, but for now just know that Starfleet needs to know which plugin to consult with to obtain an index or inventory of AWS accounts and their enabled regions.

#### Optional Fields
* **`ScopeToRegions`** - This is a set of AWS regions that should be scoped for `ACCOUNT_REGION` worker templates. This is useful if you have an SCP that restricts the regions that are allowed to be operated in. This ensures that `ACCOUNT_REGION` workers can only operate in those regions specified in this list. By default this is not set.
* **`LogLevel`** - This is the Python log level to make use of. The valid fields are the [Python log level names](https://docs.python.org/3/library/logging.html#levels). The default value is `INFO`.
* **`ThirdPartyLoggerLevels`** - This is a dictionary of Python logger name, and the corresponding log level for it. By default we silence the loggers for `botocore` and `urllib3.connectionpool`, because they can be noisy when making `boto3` API calls. Feel free to add or modify this section as you see fit.

### Worker Ship Configurations
Each worker ship must have a configuration entry. The configuration entry has a number of required fields that _**every**_ worker ship needs. But, each worker ship can extend their own schemas as they see fit. You should consult with the documentation for each worker ship to know what it should look like.

#### Minimum Required Fields
* **`Enabled`** - Each worker ship needs to have this field, which is set to the boolean of `True` or `False`. This specifies if the worker ship plugin is enabled or not.
* **`TemplatePrefix`** - As described in the [Worker Ship section](WorkerShips.md#the-payload-template), this specifies where in the S3 bucket the worker ship's payload templates are located.
* **`InvocationQueueUrl`** - As described in the [Worker Ship section](WorkerShips.md#the-sqs-queue), this is the SQS queue URL for where the Lambda's invocation will happen. The AWS SAM template has an example of what this should be. If you rely on the SAM template, than simply swap out the account ID and region, and you are good to go!
* **`InvocationSources`** - As described in the [Worker Ship section](WorkerShips.md#invocation-source), this defines when the given worker gets invoked. This is used to inform the Starbase component when to task the worker.

!!! Note
    Each worker has it's own schema and can define other required and optional components. The fields above are required for all worker ships.