# AWS Config Worker Ship User Guide
This is the main user guide for the AWS Config worker ship. This page documents all that there is to know about this worker ship.

!!! warning "Schema Change June 2023"
    The initial schema for this worker was changed in June 2023 to introduce support for AWS Config's resource
    exclusion feature in the recorders. See the Payload Templates section for details on what the current schema is.

## What does it do?
This is a very important worker ship as it allows you to easily enable [AWS Config](https://aws.amazon.com/config/) to all accounts and regions in your infrastructure. AWS Config will also be used with other workers to act as a cache of AWS resources. This is done to avoid API rate limiting when describing resources.

## Why did we make this?
AWS Config is a very important visibility tool in AWS. It is also a very effective cache of resource state that can be queried without causing rate limits for the respective services. However, AWS Config recorder enablement is not simple to do without this tool. AWS Organizations lacks the ability to enable AWS Config recorders across your environment, and more importantly, you will likely need the ability to customize how AWS Config is configured throughout your accounts and regions.
Being able to customize how AWS Config is enabled across your infrastructure is highly desireable. This is because AWS Config bills you for each configuration change that is recorded. If you have an AWS account and region with a lot of changes being made to a given resource type, then you may incur a lot of charges for those resources being recorded. In such a case, you may still want to enable it for the resource types that don't frequently change so you can still have reasonable configuration history coverage.
With this worker, you can have it all, as you can define in one place how AWS Config should be configured, and you can specify account/region specific overrides. Starfleet will task the workers accordingly to implement the changes throughout very quickly. This will also do both, detect and correct any drift that appears with AWS Config recorders.

## What does it NOT do?
It's important that we discuss what this does not do, and that is the aggregator setup. That is not performed by this worker, because AWS Organizations does this for you exceptionally well. We strongly recommend that you follow the [instructions here to set up AWS Config aggregators](https://docs.aws.amazon.com/config/latest/developerguide/set-up-aggregator-cli.html#add-an-aggregator-organization-cli) for your entire Organization.

## How it works
The AWS Config worker is an `ACCOUNT_REGION` worker, that is to say that it schedules a task for every account and region that the payload template outlines. This will go out and verify that:

1. The AWS Config Recorder is configured to the template's spec
1. The Delivery Channel is configured to the template's spec
1. The Retention Configuration is configured to the template's spec
1. The Recorder is either On or Off based on the template's spec

This worker ship plugin can be invoked on any EventBridge timed event and/or by updating the S3 template. We recommend that at a minimum, you run this once daily. As mentioned above, we do not set up aggregators because AWS Organizations does this very nicely for you. See the documentation above for more details on how to set that up.

The next sections describe how to configure, set up, and use this worker ship plugin.

## Alerting
The Config worker supports alerts to Slack. It will alert on any errors that are encountered during execution. It will also emit `SUCCESS` notices if it makes a change to the AWS Config configuration.
