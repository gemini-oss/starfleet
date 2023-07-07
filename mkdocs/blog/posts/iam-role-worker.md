---
date: 2023-07-20
authors:
  - mikegrima
categories:
  - Workers
  - IAM
  - New Features
---

# IAM Role Worker
We have developed a Starfleet worker for syncing IAM roles. This worker wraps the excellent [IAMbic](https://iambic.org/) library to perform the heavy lifting of the actual IAM work. If you haven't checked out [IAMbic](https://iambic.org) yet, please take a look at it. It's a full-featured IaC that unifies IAM management across the AWS world (and other identity providers) with lots of features and capabilities.

Most of the documentation for this worker resides in our [User Guide](../../userGuide/IAM/Roles/Overview.md).

## How does this work?
The long and the short of it, we are simply embedding an IAMbic template within a Starfleet template. Starfleet performs the heavy lifting of tasking worker lambdas with the AWS account context to operate in. Starfleet then embeds the current account context within the IAMbic template that gets passed into the IAMbic library to sync the role.

Here is a sample role template:

```yaml
TemplateName: DevOpsAutomationRole
TemplateDescription: This is a role for DevOps automation to do DevOps things
IncludeAccounts:
  ByNames:
    - DevOpsTest
    - DevOpsProd
IambicRoleTemplate:  # <----- The IAMbic template gets embedded into here
  properties:
    role_name: DevOpsAutomationRole
    description: 'The DevOpsRole for DevOpsAutomation in {{ var.account_name }}'
    assume_role_policy_document:
      statement:
        - action: sts:AssumeRole
          effect: Allow
          principal:
            service: ec2.amazonaws.com
      version: '2012-10-17'
    managed_policies:
      - policy_arn: arn:aws:iam::aws:policy/ReadOnlyAccess
    inline_policies:
      - policy_name: DevOpsThings
        statement:
          - sid: DevOpsThings
            effect: Allow
            action:
              - ec2:*
              - elasticloadbalancing:*
              - iam:PassRole
            resource: '*'
            version: '2012-10-17'

      # Give the DevOpsTest account access to the DevOpsTest S3 Bucket:
      - StarfleetIncludeAccounts:
          ByNames:
            - DevOpsTest
        policy_name: ArtifactBucket
        statement:
          - effect: allow
            action:
              - s3:Get*
              - s3:List*
              - s3:PutObject
            resource:
              - aws:s3:::some-devops-bucket-devopstest
              - aws:s3:::some-devops-bucket-devopstest/*
        version: '2012-10-17'

      # Give the DevOpsProd account access to the DevOpsProd S3 Bucket:
      - StarfleetIncludeAccounts:
          ByNames:
            - DevOpsProd
        policy_name: ArtifactBucket
        statement:
          - effect: allow
            action:
              - s3:Get*
              - s3:List*
              - s3:PutObject
            resource:
              - aws:s3:::some-devops-bucket-devopsprod
              - aws:s3:::some-devops-bucket-devopsprod/*
        version: '2012-10-17'
```

## What is different between this and vanilla IAMbic?
Starfleet is simply wrapping the IAMbic library so that you use Starfleet instead of vanilla IAMbic. The primary benefit is that if you are already using Starfleet, then you can start rolling out IAM roles where you need it with drift prevention. You just need to familiarize yourself with the IAMbic template format to begin using it.

There are however, some caveats. This is documented more in the [User Guide](../../userGuide/IAM/Roles/Overview.md).

#### Other IAMbic features
IAMbic has a lot of other standalone features, like support for other cloud provider identities, the ability to import existing IAM principals into IAMbic templates, and also the ability to implement time-limited policies that are not presently supported in Starfleet. The Starfleet worker is ideal if you don't have a need for those features and you just want to define an IAM role that must be consistently deployed in all the places you need it.

## Other IAM capabilities?
At the time of writing, the IAM role worker is the main need we have, but we would love to add more IAM features in the future. IAMbic makes this really easy for us to do. Of course, if you would like to contribute, we would love to help!
