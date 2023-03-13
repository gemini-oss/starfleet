# Worker Ship Plugins Developer Guide

Worker ship development is such an important section that we made a dedicated section for it!

!!! note
    Throughout this section we will often refer to the `AccountIndexGeneratorShip` worker ship plugin that resides in `starfleet.worker_ships.plugins.account_index_generator.ship` as it's an existing plugin that you can reference that demonstrates all the concepts.

## Worker Ship Residency
The worker ship plugins must ultimately land in the `src/starfleet/worker_ships.plugins/` directory (`starfleet.worker_ships.plugins.YOUR_PLUGIN`).

At a minimum, you'll need a `__init__.py` file. We'll cover more about this file in the Worker Ship Loader portion. For now, just now that you will need a directory that looks like this:

```
...
worker_ships
└── plugins
    └── your_plugin
            └── __init__.py
            └── some_other_python_file.py
            └── ...
```

See the [Developer Guide Overview](../../Overview.md#packaging-deployment-considerations) page on more details on packaging non-OSS and internal worker ship plugins.

## Additional Requirements
If your worker needs to have additional Python requirements installed, then don't forget you will need to have those added to the `requirements.txt` file under `src/requirements.txt`. See the [Developer Guide Overview](../../Overview.md#packaging-deployment-considerations) page on more details on packaging non-OSS and internal components.

## Worker Ship Schematics
Worker ships are the Lambda functions that go out and do all the work. For them to do this there are a number of components that they define and use. We call these the "schematics".

All of the Worker Ship Schematics reside in `starfleet.worker_ships.ship_schematics`. This file defines a _bunch_ of things. We'll go over them one-by-one, but first understand that each "worker ship" is nothing more than a plugin. They are plugins that inherit from a Python class and implement an entrypoint for AWS Lambda to invoke it.

### The Worker Ship Class
All Starfleet Worker Ship plugins _**must**_ sub-class the `StarfleetWorkerShip` class. This class is very simple and serves a few main purposes:

1. It's used to define the name of the ship - this is the value that is used to locate the ship's configuration entry
1. It's used to define the ship's fan out strategy - i.e. does this worker need to run in all AWS accounts or regions?
1. It's used to define the configuration Marshmallow schema
1. It's used to define the payload Marshmallow schema
1. It has a function to load (and verify) the payload template
1. It has a function that executes a payload

### Configuration
Each worker ship _**must**_ define a configuration Marshmallow schema. The Marshmallow schema _must_ either directly use or sub-class the `WorkerShipBaseConfigurationTemplate` class.

There are fields here that are required for ALL worker ships, like for example the `Enabled` field. These are discussed [in detail in](../../../architecture/Configuration.md#worker-ship-configurations) in the configuration architecture section.

You are able to define whatever fields your worker class needs to have a proper configuration. A great example is with the `AccountIndexGeneratorShip`, which extends the base schema:

```python
class AccountIndexGeneratorShipConfigurationTemplate(WorkerShipBaseConfigurationTemplate):
    """The configuration for the AccountIndexGeneratorShip. This largely defines where the Organization root is and the role to assume to query for accounts."""

    org_account_assume_role = fields.String(required=True, data_key="OrgAccountAssumeRole")
    org_account_id = fields.String(required=True, data_key="OrgAccountId")
    org_root_id = fields.String(required=True, data_key="OrgRootId")  # Needed to list all the OUs. Get from the AWS Orgs console. Starts with `r-...`
    describe_regions_assume_role = fields.String(required=True, data_key="DescribeRegionsAssumeRole")

# ...

class AccountIndexGeneratorShip(StarfleetWorkerShip):
    """This is a worker that will periodically dump out a summary of the AWS Organizations accounts to S3."""
    # ...
    configuration_template_class = AccountIndexGeneratorShipConfigurationTemplate
```

In the case of the `AccountIndexGeneratorShip`, we add configuration options to define which IAM role name we need to assume. We also identify which AWS account is the organization root so that we can assume a role to that account and make the AWS organization API calls.

The configuration will be validated when the worker ship plugin is loaded. This is discussed later.

### Fan Out Strategy
Each worker must define the [fan out strategy](../../../architecture/WorkerShips.md#the-fan-out-strategy) that it uses. I.e. is this a workload that just needs to run once? Then it should be set for `FanOutStrategy.SINGLE_INVOCATION`. If it needs to be set per-account, then it needs to be set to `FanOutStrategy.ACCOUNT`. If this needs to run on every account/region pair then it should be set to `FanOutStrategy.ACCOUNT_REGION`.

By default the base worker class sets this to `FanOutStrategy.SINGLE_INVOCATION`.

### Payload Template
The payload template is used to inform the worker on how to do the actual job in question. This is a necessity when running in multiple accounts or regions where there are unique things to do.

Each worker ship _**must**_ define a payload Marshmallow schema. The Marshmallow schema _must_ either directly use or sub-class one of the ==Base Payload Template== classes, which are located in `starfleet.worker_ships.base_payload_schemas`. All the schemas will ultimately sub-class `WorkerShipPayloadBaseTemplate`.

If you are making a Starfleet worker that needs to have a Fan-Out Strategy of `SINGLE_INVOCATION`, then having your payload template schema sub-class off of `WorkerShipPayloadBaseTemplate` is appropriate. However, if you are using `ACCOUNT`, then your payload template schema _**must**_ sub-class off of `BaseAccountPayloadTemplate`, or `BaseAccountRegionPayloadTemplate` for `ACCOUNT_REGION`.

Like with the configuration, you can define whichever fields you want for your worker to do the job. A great example is with the `AccountIndexGeneratorShip`, which extends the `WorkerShipPayloadBaseTemplate` schema as it's a `SINGLE_INVOCATION` worker:

```python
class AccountIndexGeneratorShipPayloadTemplate(WorkerShipPayloadBaseTemplate):
    """The payload for the AccountIndexGeneratorShip. This largely defines the S3 buckets to dump the report to."""

    account_inventory_bucket = fields.String(required=True, data_key="AccountInventoryBucket")
    inventory_bucket_region = fields.String(required=True, data_key="InventoryBucketRegion")
    inventory_object_prefix = fields.String(required=False, data_key="InventoryObjectPrefix", load_default="accountIndex.json")

# ...

class AccountIndexGeneratorShip(StarfleetWorkerShip):
    """This is a worker that will periodically dump out a summary of the AWS Organizations accounts to S3."""
    # ...
    payload_template_class = AccountIndexGeneratorShipPayloadTemplate
```

### Payload Execution
Before a payload can be executed (AKA do the work that is tasked), the worker ship needs to be instantiated with a validated payload.

We'll discuss how the worker class gets instantiated in the next section, but for now know that when a worker is instantiated, it will validate the payload by calling the super class `load_template(payload)` method, which will keep the payload stored as an attribute that is accessible by calling `self.payload`. The payload will be a regular Python dictionary that is indexed by the _Python_ snake_case field names. The `load_template` method de-serializes the Marshmallow schema into a dictionary. As mentioned below in the important notes section, the payload is intended to have whatever Marshmallow mutations you want to have on it for the convenience of the developer making the worker ship plugins.

!!! important
    The worker references its payload attributes based on what the *Python* template field names (snake_case) are vs. the YAML field names (UpperCamelCase). This is because the stored payload for the worker is the deserialized Marshmallow dictionary. We decided to do this so that the payload schema can perform whatever modifications and mutations are needed to be usable by the worker ship.

Once the template is loaded, then the code in the `execute` method an be performed. This is where all the logic should reside to do the job that is needed to be done. The `execute` method takes in a `commit` boolean flag argument. It is highly desireable for you to design your workloads with both a read-only and write-mode capability. If the `commit` flag passed in is false, then your code should _not_ make any changes and just output what it would do if the `commit=True` flag were set.

#### Exception Handling?
Because Starfleet is based on Lambda with SQS invocation, we want our functions to be as stateless and idempotent as possible. That doesn't mean you _have_ to make them stateless, but we strongly recommend it. It's totally OK to allow exceptions encountered to be raised to the top so that the Lambda can re-try. It's normal for you to sometimes have an unhealthy Lambda invocation. Fortunately, if you design your Lambda payload execution to be stateless and idempotent, then it will happily retry and should hopefully work well on the next invocation.

### Important Notes
!!! question "Configuration or Payload Template?"
    When should you use the configuration or the payload template to define something the worker needs? This is something you may be thinking about.

    Our guidance is that if this is something that _**each and every**_ Lambda invocation needs to do its job properly, then it should reside in the configuration YAML. Otherwise, it should reside in the payload template.

    Also, the configuration should not contain Marshmallow mutations. The configuration is referenced based on what the values look like in the YAML. The configuration is merely validated and loaded. However, the Payload is referenced based on what the values are in the loaded schema. Feel free to make whatever Marshmallow mutations you want on the payload.

!!! tip "Styling the Configuration and Payloads"
    We want to be consistent with styling our templates. We want YAML field names to be written in UpperCamelCase, but the raw Python code to be written in snake_case.

    This is easily achievable in Marshmallow templates. Define the fields in snake_case but then in the `fields.TYPE()` call, set the `data_key=` key word argument to the UpperCamelCase name. For example:
    `org_account_assume_role = fields.String(required=True, data_key="OrgAccountAssumeRole")`

!!! warning "Special Note"
    When you are specifying the schemas that the worker ship class uses for both the configuration and the payload, you are setting the value to a class _not_ an instantiation of the class. For example:

    ```python
    # Correct ✅
    payload_template_class = AccountIndexGeneratorShipPayloadTemplate    # <-- You are referencing the class itself

    # Wrong ❌
    payload_template_class = AccountIndexGeneratorShipPayloadTemplate()  # <-- We are not instantiating yet
    ```
