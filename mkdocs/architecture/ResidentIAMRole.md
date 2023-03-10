# Resident IAM Role

For Starfleet worker ships to function, there must be an IAM role (or roles) in all of the accounts that it can assume with the permissions to allow the worker to do the things that it needs to do.

Starfleet is deployed to 1 AWS account, which is a _**security sensitive account**_ and the IAM roles for the Starfleet worker ships will need `sts:AssumeRole` permissions to perform their workloads.

The User Guide contains more details on how to set this up, but just know that the account resident IAM Roles exist for Starfleet to work.
