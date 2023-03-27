# Prepare a Payload Template

We are going to create a payload template for the `AccountIndexGeneratorShip` plugin so that we can generate the account index.

!!! note "Important Note for Now"
    Starfleet will have a chicken and egg problem: it requires an account index to function. But there is also a worker that makes an account index. The account index worker can't run unless an account index exists.

    We will solve that problem by running the CLI to generate that index after we perform a deployment. For now don't worry about this and just focus on making a payload template. All of this will come together in the next sections! We promise! :)

1. Open your favorite text editor and you are going to create a new file. We will revisit this file so keep it somewhere you can reference to later.
1. We are going to name this file: `SaveAccountInventory.yaml`
1. In this file, copy and paste in the following, which is a payload template that will inform the `AccountIndexGeneratorShip` with additional details on how and where to save the account index:
    ```yaml
    TemplateName: AccountIndexGeneratorShip
    TemplateDescription: The Account Index Generator Worker Ship template
    AccountInventoryBucket: starfleet-account-index-DEPLOYMENT-ACCOUNT-ID
    InventoryBucketRegion: DEPLOYMENT-REGION
    ```
1. In that file, replace the `DEPLOYMENT-ACCOUNT-ID` and `DEPLOYMENT-REGION` with the AWS account ID for your deployment and region, and save the file.

!!! note "Why do we need the payload template for this?"
    In case you are wondering "why" we need a payload template for this worker, the payload template tells the worker which S3 bucket to save the index to. It also tells the worker and what to call the index file (by default it uses `accountIndex.json`). This makes this super flexible. Let's say you want to dump multiple indexes to multiple S3 buckets and prefixes. You can do that! Just make a separate payload template to describe that action and it will be done!

    However, for now, we are just setting this up to be consistent with what the AWS SAM template is doing, which is going to address 99.99% of use cases.

At this point you should now have:

- [x] Enable AWS Organizations if you haven't already done so and move some accounts into it
- [x] Pick out an AWS account for deploying a testing version of Starfleet
- [x] Work on getting a read-only Starfleet IAM role deployed with the permissions outlined above in all your AWS accounts. This role is _not_ very permissive and is only able to describe the enabled regions for an account.
    - [x] In the organization root, it has permissions to list the Organizations accounts.
    - [x] If you use StackSets then you need to manually make the role in the org root since StackSets won't operate in the org root.
    - [x] Important: Make sure that you have some IAM principal that you can use locally that can assume all these roles. This will be needed to run the Starfleet CLI. If you use AWS SSO, then use the ARN for the permissions set provisioned administrative role in the Starfleet account. See the note above for an example.
- [x] AWS Account identified for deployment
- [x] Starfleet worker IAM roles deployed everywhere
- [x] The `configuration.yaml` file in `src/starfleet/configuration_files` modified with values unique to your environment
- [x] And now: a payload template (not stored as a configuration file) in a different place than your configuration that describes what the Starfleet Account Index Generator is supposed to do
