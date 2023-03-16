# Installation Guide

!!! warning
    Starfleet is a very sophisticated tool geared towards security and infrastructure engineers with AWS and software development experience. A lot of the instructions are geared towards that audience and in some cases, you may need to roll up your sleeves.

This page is a guide for installing Starfleet. Our instructions are generally geared around [AWS SAM](https://aws.amazon.com/serverless/sam/). If you haven't already, please install the AWS SAM CLI.

There are other components that are not covered by SAM, like the Starfleet IAM role, which is also discussed.

## Included components
Separate docs exist for each included worker ship, but for the purposes of installation, the following are the minimum installed components:

1. Starfleet account resident IAM roles
1. The Starbase Lambda Functions
1. The `AccountIndexGeneratorShip`, which is a worker ship that generates an AWS account inventory by assuming a role in the Organization Root account, listing all the accounts, then fetching specific details about each account, and then finally saves the result as a JSON file to an S3 bucket.
1. The `StarfleetDefaultAccountIndex`, which is an Account Indexer that relies on the generated JSON file produced by the `AccountIndexGeneratorShip`.
1. AWS resources like the SQS Queues, the template S3 bucket, the account index bucket, the EventBridge events, and all the Starfleet Lambda IAM roles

Most of these are created with AWS SAM template, but some sleeve rolling is required for several of the others.

## SAM Template Summary
AWS SAM templates are YAML files that are effectively CloudFormation templates with some additional (very nice) abstractions. SAM will also manage the building and uploading of artifacts to S3 so that CloudFormation can properly deploy your Lambdas.

Included in the base repository directory `starfleet/` is a _sample_ SAM template named [`test_sam_template.yaml`](https://github.com/gemini-oss/starfleet/blob/main/test_sam_template.yaml). The SAM template outlines the primary components, like the SQS queues, the template S3 bucket, the Starbase Lambdas, and the worker Lambda functions.

However, before deploying anything with AWS SAM, please review the Prerequisites below.

## Prerequisites
Before deployment you need to review the following 3 things:

1. AWS Organizations is enabled and used
1. The AWS account for Starfleet deployment
1. IAM roles used by Starfleet

### Starfleet AWS Account(s)
Starfleet is a security sensitive tool with powerful capabilities that can operate across your entire cloud infrastructure. As such, you will want to have this live in a security sensitive account with few co-tenant applications.

It is also recommended to have an account for a test version of Starfleet. This guide assumes that you have 2 accounts, a separate testing and production account, that you can deploy a testing and production Starfleet to.

!!! warning
    Starfleet is a very privileged application. It is intended to operate over your entire AWS cloud infrastructure. Please place it in an Account with limited access and few other deployed applications.

Our default account inventory makes the assumption that you are making use of AWS organizations and have your accounts registered with it (seriously, you need to do this if you haven't already).

Before you can move forward, you will need to do the following:

- [x] Enable AWS Organizations if you haven't already done so and move some accounts into it
- [x] Pick out an AWS account for deploying a testing version of Starfleet
