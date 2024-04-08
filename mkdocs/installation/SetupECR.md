# Set Up Private ECR (Elastic Container Registry)

This is not required but highly recommended as the Starfleet package may be too big for Lambda to accept it as a `.zip` file. As such, we recommend setting up Starfleet with a Dockerized Lambda hosted in a private ECR.

The steps to do this will largely involve setting up ECR, which you can find in [the AWS documentation here](https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-create.html).

When creating your registry please adhere to the following:

1. You are creating a **PRIVATE** registry. **DO NOT MAKE THIS PUBLIC!**
2. This must reside in the same account and region that you are deploying Starfleet to
3. Recommend that you set up tag immutability
4. Recommend that you set up a lifecycle policy to expire older images (recommend to expire any `Image count more than 3`)

!!! danger "Public Access"
    DO NOT make your ECR repository public!

Once you have your ECR registry set up, there will be a URL associated with it. That URL is the where your image will be pushed to. You will need that in the next steps for AWS SAM.

!!! note "Note: ECR URL"
    You will need the ECR URL for the next sections. This is in the format of `aws_account_id.dkr.ecr.region.amazonaws.com`

## Note about Dockerizing Starfleet
Included in the main code base is a `Dockerfile` that is intended to build Starfleet. This file should be all good to go. This is configured to use the AWS official Lambda docker container for a specific Python version. This also:

1. Copies the Starfleet code to the container in the `var/runtime` directory, which is where Lambda wants the code to live.
2. Cleans up some unnecessary files.
2. It runs `pip install` to install the Starfleet packages
3. Lastly, and _very importantly_ it **removes** the built-in `boto3` and `botocore` packages that is shipped by default with the container. This is necessary because Lambda will prefer to use the preloaded version of boto instead of the Starfleet packaged one. The pre-loaded version can be out of date and can result in very bizarre errors with unsupported boto APIs - this is because you may be using boto features that are newer than the included boto packages. Thus, we remove them so only the Starfleet included boto packages are there.

For more information about Dockerizing Lambda functions, [see the docs here](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html).

## Continuing

At this point you will have the following:

- [x] Enable AWS Organizations if you haven't already done so and move some accounts into it
- [x] Pick out an AWS account for deploying a testing version of Starfleet
- [x] Work on getting a read-only Starfleet IAM role deployed with the permissions outlined above in all your AWS accounts. This role is _not_ very permissive and is only able to describe the enabled regions for an account.
    - [x] In the organization root, it has permissions to list the Organizations accounts.
    - [x] If you use StackSets then you need to manually make the role in the org root since StackSets won't operate in the org root.
    - [x] Important: Make sure that you have some IAM principal that you can use locally that can assume all these roles. This will be needed to run the Starfleet CLI. If you use AWS SSO, then use the ARN for the permissions set provisioned administrative role in the Starfleet account. See the note above for an example.
- [x] AWS Account identified for deployment
- [x] Starfleet worker IAM roles deployed everywhere
- [x] The `configuration.yaml` file in `src/starfleet/configuration_files` modified with values unique to your environment
- [x] A payload template (not stored as a configuration file) in a different place than your configuration that describes what the Starfleet Account Index Generator is supposed to do
- [x] An optional ECR Repository set up to make dockerized Lambda builds
- [x] And Now: AWS SAM:
    - [x] SAM's administrative resources deployed
    - [x] SAM's TEST deployment configuration all set up
    - [x] Starfleet deployed in your environment

While it's now deployed, it won't work without an Account Index. The next section describes how to get it set up.
