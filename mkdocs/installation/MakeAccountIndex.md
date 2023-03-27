# Make the Account Index

It's now time to make the account index via the Starfleet CLI. After you run the CLI to get the account index working, Starfleet should _just work_.

The instructions below are very similar to what's in the Developer Guide, but are pasted here for convenience.

## Set Up Python Environment
You'll need a proper Python 3 environment set up. We recommend using [pyenv](https://github.com/pyenv/pyenv). Starfleet uses the latest version of Python 3 [that is supported by AWS Lambda](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html). You will want to have that installed and configured.

### Set Up Virtual Environment
_**Always make use of a python virtual environment with Starfleet. Always.**_

To get started you will make a virtual environment:

```bash
# Git clone the repo ... (recommended you make a fork on GitHub and pull from that for development -- you
#                         can also add the upstream repository as a remote with
#                         `git remote add upstream git@github.com:gemini-oss/starfleet.git` followed by `git fetch --all`)
cd starfleet/
python3 -m venv venv
source venv/bin/activate
```

After running the above you now have a working virtual environment.

!!! warning
    Make sure that everything you run is within this virtual environment! You can always get back into it by running `source venv/bin/activate`.

### Install The Dependencies
Once you have your virtual environment created and activated, you are now ready to install the package and the dependencies:

```bash
# Install the main starfleet components with dependencies:
pip install -e .

# Install the test components:
pip install -e ."[tests]"
```

### Test It!
You can test that it's all working by running `tox`:

```bash
tox
# ... a lot of output ...
```
If you see errors about tests failing then there is a problem! The command at the end should say something along the lines of:

```
  py39: OK (10.14=setup[3.61]+cmd[6.53] seconds)
  lint: OK (9.69=setup[2.83]+cmd[0.83,0.40,5.63] seconds)
  congratulations :) (19.88 seconds)
```

## Run the CLI
Once you are in the virtual environment then you are now ready to run Starfleet's account index generator. For reference:

```bash
(venv) your_username starfleet % starfleet account-inventory generate --help
Usage: starfleet account-inventory generate [OPTIONS]

  This will generate an AWS account inventory from the organizations API

Options:
  --payload FILENAME  This is the worker payload YAML  [required]
  --commit            Must be supplied for changes to be made  [default:
                      False]
  --help              Show this message and exit.
```

1. Remember we mentioned [that you should have IAM credentials that allow you to assume the Starfleet roles](./IAM.md#starfleet-account-resident-roles)? You need to obtain those credentials and export them into your environment. This is required so that you can run _as_ Starfleet!
1. Remember you made that [payload template for the Account Index generator](./PreparePayload.md)? You are going to use that now!
1. Remember you set up [the configuration for Starfleet](./PrepareConfiguration.md)? It comes into play here!
1. Run the cli!:
    ```bash
    # Activate your virtual environment: source venv/bin/activate
    # export your AWS credentials...
    starfleet account-inventory generate --payload path/to/your/payload.yaml --commit
    ```

If it's all working, then you should see:
```
2023-03-17 14:39:21,073 - INFO - [🪣] Saving the report as accountIndex.json in starfleet-templates-YOUR-ACCOUNT-ID - /path/to/starfleet
2023-03-17 14:39:21,932 - INFO - [✅] Done! - /path/to/starfleet
```

Once this is in S3, then the last step is for you to upload that payload YAML to your S3 bucket _in the prefix that is configured in your `configuration.yaml`_.

At this point you should be done with test and you would want to repeat the steps for prod. All these things should be done:

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
- [x] AWS SAM:
    - [x] SAM's administrative resources deployed
    - [x] SAM's TEST deployment configuration all set up
    - [x] Starfleet deployed in your environment
- [x] And now: You set up a local development environment
- [x] And now: You now have an account index JSON file in the account index S3 bucket
- [x] Your test Starfleet deploying is all set and working! (hopefully)

The next steps are to wrap things up.
