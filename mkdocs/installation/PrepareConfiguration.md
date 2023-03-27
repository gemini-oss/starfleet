# Prepare Configuration For Installation

Starfleet needs a proper configuration to function properly. Let's revisit the main configuration for Starfleet. As mentioned in the [Architecture](../architecture/Configuration.md) section, all the configuration files are YAML files that reside in `src/starfleet/configuration_files/`.

We include a sample [`configuration.yaml`](https://github.com/gemini-oss/starfleet/blob/main/src/starfleet/configuration_files/configuration.yaml) file that contains 3 stanzas, one for `STARFLEET`, one for the `AccountIndexGeneratorShip`, and one for the `StarfleetDefaultAccountIndex`.
The included file is very heavily documented and it should be self-explanatory. The configuration file is set up to conform to what is included in the provided AWS SAM template.

1. Open the `src/starfleet/configuration_files/configuration.yaml` file in your favorite text editor.
1. Go through and update the values of that file accordingly. For the `TemplatePrefix` under the `AccountIndexGeneratorShip` we are going to make that file in the next section. The default value set is perfect: `AccountIndexGenerator/SaveAccountInventory.yaml`.
1. Save the changes

At this point you should now have:

- [x] Enable AWS Organizations if you haven't already done so and move some accounts into it
- [x] Pick out an AWS account for deploying a testing version of Starfleet
- [x] Work on getting a read-only Starfleet IAM role deployed with the permissions outlined above in all your AWS accounts. This role is _not_ very permissive and is only able to describe the enabled regions for an account.
    - [x] In the organization root, it has permissions to list the Organizations accounts.
    - [x] If you use StackSets then you need to manually make the role in the org root since StackSets won't operate in the org root.
    - [x] Important: Make sure that you have some IAM principal that you can use locally that can assume all these roles. This will be needed to run the Starfleet CLI. If you use AWS SSO, then use the ARN for the permissions set provisioned administrative role in the Starfleet account. See the note above for an example.
- [x] Starfleet worker IAM roles deployed everywhere
- [x] And now: the `configuration.yaml` file in `src/starfleet/configuration_files` modified with values unique to your environment
