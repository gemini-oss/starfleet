# Starbase User Guide
This is the main user guide for the Starbase component. Most of the user guide details for the Starbase has been covered in the Architecture and Installation docs (and also in the developer guide).

## How to use it?
The Starbase is the heart of Starfleet. The only way to use it is to make sure that it's configured properly. The Starbase must also have a proper account inventory prepared, which we discussed in the [installation guide](../installation/MakeAccountIndex.md).

The primary things to keep in mind for using Starfleet is that:

1. All of the components are actually deployed
1. The account index needs to be available - without this the Starbase has no way of knowing which AWS accounts and/or regions to task the workers for
1. The template S3 bucket needs to contain the payloads for the workers _AND_ those payloads need to be properly conformant with the corresponding worker payload schemas
1. The template file names end in `.yaml`
1. The Starbase IAM role need to have access to the template bucket and also the corresponding worker SQS queues
1. The configuration for the Starbase (the `STARFLEET` section) and the workers have all the correct details on which SQS queues to use, the template bucket, and the template prefixes within the bucket
1. The EventBridge timed events are _enabled_ for the given timing task
1. The Lambda function permissions and the SQS queue permissions are configured to allow Lambda to pull events off of them (this should not be a problem if you use the included AWS SAM templates)
1. For the Starbase specifically, you will want to ensure that it will operate with an SQS batch size of 1 for fanouts (this is also configured in the SAM template)

Other than that, the Starbase is mostly not something that you need to worry about, but is something that you should review the logs of if you aren't seeing a worker get tasked. The Starbase is split across 2 Lambda functions:

1. The EventBridge Timed Event responder
2. The worker Fan Out - this is also invoked directly by the template S3 bucket on template object uploads

If you aren't seeing a worker get invoked, definitely review the logs of each one to see what's going on.
