# Run AWS SAM

Now you are ready to run AWS SAM and get the infrastructure components deployed! To do this you should follow the instructions to get the AWS SAM CLI installed on your system. Also note, you will also need to build Starfleet in a docker container to properly install all the dependencies (this is doable via the SAM CLI as we'll discuss below.)

!!! danger "Help Wanted!"
    This section could use some assistance from the community for simplifying the installation process and documentation. We would love for assistance on the creation of things like an installation script, for example that would set all of this up for you.

## The Test Template
We include a file called `test_sam_template.yaml`, so you can later clone it for production with production specific values in. The commands below will assume that the template is named `test_sam_template.yaml`.

## Build Starfleet
To build the code, in the main checked out directory you will run:

```bash
sam build --use-container --template-file test_sam_template.yaml --parameter-overrides ParameterKey=EnvironmentName,ParameterValue=TEST
```

If all is good, it should say at the end: `Build Succeeded`.

## Fetch AWS Credentials
You will need administrative AWS credentials in your environment that is able to create resources. You will need a lot of permissions as this will create IAM roles and also create S3 buckets, along with other resources.

You will need to ensure that these credentials are present in your environment, i.e. export the environment variables.

## Prepare SAM Components
SAM requires that there be some components in AWS. The best way to provide this is to follow the instructions for a `guided deploy`.

### First time running
You can do that by running the command:
```bash
sam deploy --guided --template-file test_sam_template.yaml --parameter-overrides ParameterKey=EnvironmentName,ParameterValue=TEST
```

During this stage, it will attempt to create a `samconfig.toml` file (more on that below). Follow the instructions and you will want to have the following values generally set:

```
        Setting default arguments for 'sam deploy'
        =========================================
        Stack Name [sam-app]: starfleet
        AWS Region [us-east-1]: ADD YOUR REGION HERE
        Parameter EnvironmentName [TEST]: TEST or PROD -- Use TEST for now
        #Shows you resources changes to be deployed and require a 'Y' to initiate deploy
        Confirm changes before deploy [y/N]: y  # Choose Yes (Y)
        #SAM needs permission to be able to create roles to connect to the resources in your template
        Allow SAM CLI IAM role creation [Y/n]:  # Choose Yes (Y)
        #Preserves the state of previously provisioned resources when an operation fails
        Disable rollback [y/N]: N  # Choose No (N)
        Save arguments to configuration file [Y/n]:  # Choose Yes (Y)
        SAM configuration file [samconfig.toml]:  # Just press enter for the default.
        SAM configuration environment [default]: TEST  # TEST or PROD -- Use TEST for now
```

This should try to create an S3 bucket (if prompted, choose Yes). Let SAM create the AWS managed resources required. This will allow SAM to do whatever it needs to do to get your resources deployed. **However, there will be an error when you deploy for the first time**, _this is expected_ because of an annoying CloudFormation issue: and that issue is `capabilities`.

### Update the SAM configuration
We need to update the SAM configuration, _manually_, to allow it to create IAM resources. You have to edit the `samconfig.toml` file, locate the `capabilities` variable and set it to:

```toml
[TEST.deploy.parameters]
# ...
capabilities = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"]

[TEST.validate.parameters]
region = "YOUR_REGION_HERE"
template_file = "test_sam_template.yaml"
lint = true

[TEST.build.parameters]
use_container = true
template_file = "test_sam_template.yaml"
```

It's recommended that you copy and paste in the other fields above too.

### Validate It's All Good
You will next want to run a validation, which will do some stuff to kind of sort of validate the template, and it uses an IAM role that SAM creates to do it. After you updated the SAM config, you can now run:

```bash
sam validate --config-env TEST
# Notice the --config-env parameter. This will rely on the TEST configuration section in samconfig.toml, which is nice
```

This should not show any errors.

### Deploy For Real This Time
After you do this, go back and re-run the deploy command _without adding `--guided` to it_, so run:

```bash
sam deploy --config-env TEST
```

This should go through and generate the CloudFormation stack and attempt to deploy your resources. Follow any prompts that are provided. This should be deployed successfully. However, Starfleet won't function properly because the account index hasn't been built yet. We will solve that in the next section.

!!! note
    You will need to re-run the guided deploy in production to have SAM create all the AWS resources it needs. Once that's done, then copy and paste as much as possible in the SAM configuration section below, since that will make managing the deployments very nice and simple.

    Unfortunately, the SAM CLI doesn't do any of this by default so you have to finagle with it a bit. Once you do this a few times, you will get the hang of it.

## SAM Configuration
When setting up SAM, it will create a configuration. A sample configuration has been provided here that you should use: [`sample_samconfig.toml`](https://github.com/gemini-oss/starfleet/blob/main/sample_samconfig.toml) - make a copy of this named as `samconfig.toml`.

More details about this is described in the [Developer Guide](../developerGuide/SAMConfiguration.md#sam-config).

Once you have the configuration set up, then you can run:

```bash
# Build test:
sam build --config-env TEST

# Validate test:
sam validate --config-env TEST

# Validate test:
sam deploy --config-env TEST

# ... and for prod:

# Build prod:
sam build --config-env PROD

# Validate prod:
sam validate --config-env PROD

# Validate prod:
sam deploy --config-env PROD
```

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
- [x] And Now: AWS SAM:
    - [x] SAM's administrative resources deployed
    - [x] SAM's TEST deployment configuration all set up
    - [x] Starfleet deployed in your environment

While it's now deployed, it won't work without an Account Index. The next section describes how to get it set up.
