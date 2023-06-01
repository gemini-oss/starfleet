# Set up IAM Roles

Starfleet needs IAM roles present in all accounts that it needs to operate in. Starfleet operates in a hub-spoke type of model where Starfleet Lambda functions are deployed with IAM roles that can assume role to the target account Starfleet worker roles.

At this time, we recommend the use of CloudFormation StackSets to set up the initial IAM role that Starfleet will need to use organization wide. We provide an example below of a CloudFormation StackSet template that deploys an IAM role Starfleet workers are able to assume across all your accounts in your organization.

## Starfleet Account Resident Roles
You don't need to worry too much about this until the SAM deployment, but for now, we'll describe what IAM permissions the Starfleet worker roles need. The gist is that it mostly needs to be able to `sts:AssumeRole` on `arn:aws:iam::*:starfleet*`. The SAM template provides this via a Managed Policy that is attached to each SAM created worker role like this:

```yaml
  AssumeRoleManagedPolicy:
    Type: AWS::IAM::ManagedPolicy
    DependsOn:
      - AccountIndexGenerator
    Properties:
      Description: Grants Starfleet workers assume role permissions to common Starfleet worker IAM roles
      ManagedPolicyName: StarfleetWorkerAssumeRoles
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Action: 'sts:AssumeRole'
            Resource:
              - !Sub
                - 'arn:aws:iam::*:role/${RoleName}'
                - RoleName: !FindInMap
                    - EnvMap
                    - !Ref 'EnvironmentName'
                    - BaseRoleName
      Roles:
        - !Ref AccountIndexGeneratorRole  # AccountIndexGeneratorRole is created automatically by SAM and can be referenced
        # -!Ref YourWorkerRoleHere # Add your worker roles here to get the policy attached
```

Don't worry too much about the specifics of the above policy. The main point to know is that the worker Lambda functions need IAM roles in all the accounts, which the worker Lambdas can assume, that contain the required permissions in those accounts to perform the actions that need to be performed. We recommend utilizing CloudFormation StackSets to do this. An example of a CloudFormation StackSet template to create the account resident roles is below (we assume that you do this for the rest of the guide):

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: CloudFormation StackSet for the base Starfleet IAM worker roles deployed to all accounts
Resources:
  StarfleetWorkerBasicTestRole:
      Type: AWS::IAM::Role
      Properties:
        AssumeRolePolicyDocument:
          Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Principal:
                AWS:
                  - arn:aws:iam::STARFLEET-PRODUCTION-ACCOUNT:root  # ADD THE STARFLEET PROD ACCOUNT ID IN
                  - arn:aws:iam::STARFLEET-TEST-ACCOUNT:root        # ADD THE STARFLEET TEST ACCOUNT ID IN
              Action: sts:AssumeRole
              Condition:
                ArnLike:
                  aws:PrincipalArn:
                    - 'arn:aws:iam::STARFLEET-PRODUCTION-ACCOUNT:role/starfleet*'  # SAME
                    - 'arn:aws:iam::STARFLEET-TEST-ACCOUNT:role/starfleet*'        # SAME
                    - 'SOME-ARN-TO-AN-IAM-ROLE-YOU-WANT-TO-ASSUME-FOR-LOCAL-DEVELOPMENT-AND-CLI-DEBUGGING-HERE'  # SEE NOTE BELOW
        Description: Account-resident role for the Test Starfleet stack to assume - permissions are only read-only
        RoleName: starfleet-worker-basic-test-role
        Policies:
            # The policies below are used for the AccountIndexGenerator to obtain all the regions that an AWS account supports.
          - PolicyName: ec2
            PolicyDocument:
              Version: '2012-10-17'
              Statement:
                - Sid: GetEnabledRegions
                  Effect: Allow
                  Action: ec2:DescribeRegions
                  Resource: '*'
        Tags:
          - Key: ADD-HERE
            Value: Add whatever tags you want here.

  StarfleetWorkerBasicProdRole:
      Type: AWS::IAM::Role
      Properties:
        AssumeRolePolicyDocument:
          Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Principal:
                AWS:
                    - arn:aws:iam::STARFLEET-PRODUCTION-ACCOUNT:root   # ADD THE STARFLEET PROD ACCOUNT ID IN
              Action: sts:AssumeRole
              Condition:
                ArnLike:
                  aws:PrincipalArn:
                    - 'arn:aws:iam::STARFLEET-PRODUCTION-ACCOUNT:role/starfleet*'  # SAME
                    - 'SOME-ARN-TO-AN-IAM-ROLE-YOU-WANT-TO-ASSUME-FOR-LOCAL-DEVELOPMENT-AND-CLI-DEBUGGING-HERE'  # SEE NOTE BELOW
        Description: Account-resident role for the Prod Starfleet stack to assume
        RoleName: starfleet-worker-basic-prod-role
        Policies:
          - PolicyName: ec2
            PolicyDocument:
              Version: '2012-10-17'
              Statement:
                - Sid: GetEnabledRegions
                  Effect: Allow
                  Action: ec2:DescribeRegions
                  Resource: '*'
        Tags:
          - Key: ADD-HERE
            Value: Add whatever tags you want here.
```

!!! danger "Important Tip about the Organization Root Account"
    If you do decide to go with the CloudFormation StackSets route, you need to keep in mind that StackSets will _NOT_ deploy to the Organization Root account. If you do choose to use StackSets, you will need to _manually_ create an IAM role in the organization root account that has the exact same permissions as what is documented in the StackSet YAML above.

!!! Note
    If you leverage the `AccountIndexGeneratorShip` worker ship for your AWS account inventory (recommended), you will need to make sure that the Starfleet IAM roles in the Organization Root account has the following permissions (in addition to the permissions you grant to the other worker roles):

    ```json
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    [
                      "organizations:Describe*",
                      "organizations:List*"
                    ]
                ]
                "Resource": "*"
            }
        ]
    }
    ```

When using StackSets, you will want to ensure that this is applied to _all accounts_ and to automatically create the apply the stack to newly added accounts in the organization ([see AWS documentation here](https://aws.amazon.com/blogs/aws/new-use-aws-cloudformation-stacksets-for-multiple-accounts-in-an-aws-organization/)).

IAM is a global resource within an AWS account, as such, you should only have the StackSet target 1 region, like `us-east-1`.

!!! tip "Local Development Credentials"
    In the StackSet YAML above, you will see:
    ```yaml
    SOME-ARN-TO-AN-IAM-ROLE-YOU-WANT-TO-ASSUME-FOR-LOCAL-DEVELOPMENT-AND-CLI-DEBUGGING-HERE
    ```

    This should be some IAM role/user/whatever that you are able to obtain credentials for that is
    allowed to `sts:AssumeRole` this role. You will need this to run the Starfleet CLI since that will
    need to perform the role assumption logic to perform whatever the worker does in AWS, but locally
    on your computer.

    If you use AWS SSO, and have permissions set named `Administrator`, and it's applied to your account with `sts:AssumeRole` permissions to either `arn:aws:iam::*:starfleet*` or just `*`, then the ARN above would be something along the lines of:
    ```yaml
    arn:aws:iam::STARFLEET-ACCOUNT-ID:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Administrator_*
    ```

## Deployment with AWS SAM
Once you have sorted out which AWS account(s) you want to use for Starfleet, _and_ have rolled out base worker IAM roles in all accounts, you then need to update the configuration, prep the account index, and then use AWS SAM to deploy all the resources. This is documented in the next sections.

At this point, you should have the following before you can move forward:

- [x] Enable AWS Organizations if you haven't already done so and move some accounts into it
- [x] Pick out an AWS account for deploying a testing version of Starfleet
- [x] Work on getting a read-only Starfleet IAM role deployed with the permissions outlined above in all your AWS accounts. This role is _not_ very permissive and is only able to describe the enabled regions for an account.
    - [x] In the organization root, it has permissions to list the Organizations accounts.
    - [x] If you use StackSets then you need to manually make the role in the org root since StackSets won't operate in the org root.
    - [x] Important: Make sure that you have some IAM principal that you can use locally that can assume all these roles. This will be needed to run the Starfleet CLI. If you use AWS SSO, then use the ARN for the permissions set provisioned administrative role in the Starfleet account. See the note above for an example.
- [x] Starfleet worker IAM roles deployed everywhere
