# Developer Guide

This section is to guide you in being able to develop features for Starfleet. This will go into depth on how Starfleet is architected and how to develop worker ships and other plugins.

## Basic Overview
Starfleet is built on Python 3 and is run on AWS Lambda. Starfleet has some major dependencies:

1. [Marshmallow](https://marshmallow.readthedocs.io/en/stable/) - For defining schemas and validating Starfleet configurations and payload templates
    - In case you are wondering, we chose Marshmallow over [pydantic](https://docs.pydantic.dev/) because Marshmallow has _excellent_ flexibility capabilities that greatly benefits a project like Starfleet vs. raw performance and simplicity where pydantic really shines
1. [Click](https://click.palletsprojects.com/) - For making the Starfleet CLIs
1. [pytest](https://docs.pytest.org/) - The unit testing framework
1. [pyproject.toml](https://pip.pypa.io/en/stable/reference/build-system/pyproject-toml/) - For defining the Python package itself
1. [tox](https://tox.wiki/en/latest/) - Tool for automating the run of our unit tests and linting
1. [black](https://github.com/psf/black) - To make our code look very nice
1. [AWS SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html) For deploying Starfleet and it's components to AWS
1. [Mkdocs](https://www.mkdocs.org/) and [Material for Mkdocs](https://squidfunk.github.io/mkdocs-material/) - The docs you are looking at right now :)

## General Advice
Starfleet's code can look very intimidating because there are a bunch of distributed items. The best way to get to learn Starfleet is to dig into the code for existing plugins, add some breakpoints, and then run the tests in debug mode. We strongly recommend using [PyCharm](https://www.jetbrains.com/pycharm/) to do this.

You may also want to review some of the dependencies, like Marshmallow and pytest (especially pytest fixtures), to get a better feel for what the code is really doing.

### Some Etiquette and Terminology
Throughout this guide, we will interchangeably refer to paths of files in the Python import format like: `some.package.in.python.file.resource` vs. `src/starfleet/some/package/in/python/file.py`. We will use the latter format when we are specifically referring to non-python specific paths.

## Common Themes
There are a number of common themes throughout the codebase that you may notice. We are a big fan of the [singleton pattern](https://en.wikipedia.org/wiki/Singleton_pattern), and use it extensively throughout the code for providing major components like the:

- Logger
- Configuration Manager
- Account Index
- Worker Ships Registry
- CLIs

Additionally, we are also a very big fan of plugins. We try to make everything in Starfleet a plugin because this is an open source project, and making everything a plugin means we (and you!) can extend Starfleet's capabilities with ease.

The next section discusses the major singleton components that are used throughout the code base and how to make use of them.

## Getting Started
To get started you will need to have a proper Python 3 environment set up. We recommend using [pyenv](https://github.com/pyenv/pyenv). You'll also need to install the [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html), which you will also want to install [Docker](https://docs.docker.com/get-docker/) too when building the Starfleet Lambdas that get deployed to AWS.

These docs are making an assumption that you are running macOS or Linux.

Starfleet uses the latest version of Python 3 [that is supported by AWS Lambda](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html). You will want to have that installed and configured.

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

## Requirements and Updates
The Starfleet primary requirements are set in `src/requirements.txt`. This is placed here so that AWS SAM knows where to find and install the dependencies. The requirements for unit tests reside in the `pyproject.toml` file under the `[project.optional-dependencies]` section.

## Packaging & Deployment Considerations
In this section, we discuss some considerations when packaging and deploying your internal code.

### Internal Repo
You will want to make an internal repository that holds all your configuration and internal plugins. We recommend that you have something simple that clones the Starfleet upstream, and then copies over your specific configuration details into the `starfleet` directory paths. From there you would want to run your SAM commands to build and deploy your "baked" Starfleet deployment which would be ready to go.

### Worker Development
When developing your worker, you'll likely want to develop it against the upstream since that will make it easy to debug and get a local working version. However, and this can't be stressed enough:

!!! danger "Don't pull-request your internal code!!"
    Always copy your code out of the upstream and into your internal repo!

Another strategy is to have an internal repo that pulls from upstream via a git submodule or even if you just maintain your local copy. There are many different ways to package and deploy for your own internal purposes. Pick the approach that works best for your organization.

!!! tip "Keep your tests separate from your logic"
    You will want to keep your tests separate from your logic as well. This will help reduce the size of the packaged .zip file that is packaged with your Lambda function.

We highly recommend running `tox` against the unified code to make sure that all the tests pass and everything looks copasetic.

### Contributing Back
We just love to get contributions from the community! Make sure you thoroughly test your code. Remember: this is code that will run potentially _EVERYWHERE_ in your infrastructure so 100% test coverage is not a bad idea, even if it seems excessive. The last thing you want to see is an exception in your logs because you referenced a variable that wasn't declared yet in a certain `if` statement, or logging out the value of something that was wrong. The more tests, the less hair-pulling once deployed.

## Next Sections
The next sections provide an in-depth look at the primary components of Starfleet. The worker ships guide is a separate section as it requires a lot of depth!
