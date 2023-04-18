# Account Index Generator User Guide
This is the main user guide for the Account Index Generator worker plugin. Most of the user guide details for the Account Index Generator has been covered in the Architecture and Installation docs (and also in the developer guide). Thus, this page will not be very large.

## How to use it?
!!! info "Read this first!"
    Make sure that for the first time you are using Starfleet, that you have the configuration properly configured to point to the correct S3 bucket to generate the index JSON to, and that you also have the proper IAM roles present. Remember, you need an IAM Role for the Starfleet workers to assume into in all AWS accounts in your organization, and you also need to make sure that the organization root has this account as well.

    If you choose to leverage CloudFormation StackSets to deploy these roles, remember that StackSets doesn't operate in the organization root account. So you will need to either make a separate CloudFormation stack in the organization root account or just manually create the IAM roles in question.

    In all cases, the configuration needs to be set properly. See the [Installation Guide](../installation/IAM.md) for details.

The primary things to keep in mind for using Account Index Generator is that:

1. All of the components are actually deployed
1. The IAM Roles are configured as depicted in the Installation Guide
1. The payload template is configured to properly deploy to the S3 bucket
1. The Starbase is configured properly

Of course, please consult the logs for details on what's going on.

