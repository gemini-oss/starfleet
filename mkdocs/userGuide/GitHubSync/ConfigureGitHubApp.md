# Configure the GitHub Application Components
The GitHub Repo Sync worker leverages a [GitHub App](https://docs.github.com/en/apps/creating-github-apps/setting-up-a-github-app/about-creating-github-apps) to interact with GitHub repos. In this case, we need to have permissions to download a given repository in question. We use GitHub Apps in place of Personal Access Tokens (PATs).

!!! warning
    The GitHub instructions and screenshots below are from June 2023 and could be outdated in the future. Please consider submitting a Pull Request to update if that happens!

## Create the App
We are going to create a GitHub App for Starfleet. You will be creating an app in each organization that contains the (private) repos that you need to access. If you are accessing a public repo, you will still need the App made, but it need not live in the same GitHub org. The instructions for both should be the same.

!!! tip
    Before moving forward, make sure that you have the Secrets Manager secret made. If you don't yet have one, then you will want to create one in the AWS console.

!!! note
    To create the App, you will need to have Owner permissions on the GitHub organization in question.

1. Go to your GitHub organization page (`https://github.com/ORGNAME`)
1. Scroll down on the left-hand side to `Developer Settings`, and click on `GitHub Apps`<br />![GitHub Apps under Developer Settings](../../images/GitHubAppMenu.png){: style="width:40%"}
1. Click on `New GitHub App`
1. On the `Register new GitHub App` page, you will need to fill out the following details:
    1. `GitHub App name`: This is _globally unique_, so come up with a name for your Starfleet app that doesn't exist elsewhere. You can call this whatever you like.
    1. `Homepage URL`: Make this whatever you want.
    1. Uncheck `Expire user authorization tokens` - we don't use them
    1. Uncheck `Active` for webhook - we don't use them
    1. Select the following `Repository` permissions:
        1. `Metadata`: `Read-only`
        1. `Contents`: `Read-only`
    1. You don't need any additional permissions
    1. Lastly -- and _very important_, for `Where can this GitHub App be installed?`, select `Only on this account`
1. Click on `Create GitHub App`

The page you are at is the GitHub Application administrative page. On the page at the top, you should see a field called `App ID`. **Keep note of the App ID - you will need it later when creating the worker payload.**

!!! note
    You will need to keep track of the GitHub App ID, Private Key (will get stored in Secrets Manager), and the Installation ID. We will note these as we continue in the instructions.

#### Prepare the Secret
Once your GitHub App is created, you will need to generate a Private Key for it. This is where Secrets Manager comes in.

1. On the App page, click on `Generate a private key`
1. You will be prompted to download a `.cer` file. This file contains the RSA private key. This is sensitive!
1. You will need to find and replace all the newlines with a `\n`. We recommend using [VS Code](https://code.visualstudio.com/) for this. In VS Code, open the find menu, click on the `.*` icon at the right to enable regular expression search, and type in `\n`. You will want to replace that with `\\n`. You will then click on the `Replace All` button. Here is what your find menu should look like:<br />![VS Code find and replace](../../images/CertFindReplace.png)<br />This will make the private key all on one line with the actual new lines replaced with a `\n` separating the lines. This is the string value that needs to be coped over into the secret.
1. You will need to prepare the JSON for Secrets Manager. The dictionary needs a top-level dictionary field named `GitHubSyncWorker`, and within that is a dictionary of the organization name, and the App's corresponding Private Key as a string. Paste in the private key above such that you have something that looks like this:
    ```json
    {
        "STARFLEET": {...},
        "GitHubSyncWorker": {
            "YOUR-GITHUB-ORG-NAME-HERE": "-----BEGIN RSA PRIVATE KEY-----\nREDACTED\nREDACTED\nREDACTED\n...\n-----END RSA PRIVATE KEY-----",
            "ADD MORE GITHUB ORGS HERE IF REQUIRED": "-----BEGIN RSA PRIVATE KEY-----\nTHIS IS THE KEY FOR YOUR OTHER ORG'S APP -- ONE APP PER ORG\n-----END RSA PRIVATE KEY-----"
        }
    }
    ```
    ^^ This assumes that you haven't yet created a secret. If you already have a secret, then fetch that out of Secrets Manager, copy it to your text editor, and modify it with the required GitHub details added into it.
1. Update the Secrets Manager entry in the AWS console with the all the details added to it

Feel free to make other adjustments to your app, like configuring a fun icon for it.

#### Install the App
The last step is to "Install" the GitHub app to your organization. Right now the GitHub app exists, but can't actually do anything on your organization yet. You need to install it to the organization and give it access to the repositories in question.

1. At the top of the App administrative page, click on `Install App`<br />![GitHub App Install Menu](../../images/GitHubInstallAppMenu.png){: style="width:40%"}
1. On the next page, you should see your Organization listed and a green `Install` button at the right. Click on `Install`
1. On the next page, you can select `All repositories` or `Only select repositories`. We recommend only selecting the repositories that you want to sync. Click the `Install` button. You should see something that looks something like this:<br />![Install App Page](../../images/GitHubInstallAppPage.png){: style="width:40%"}

##### Fetch the Installation ID
After the application is installed, you now need to fetch the **Installation ID**. To do this:

1. Go back to your organization settings page (`https://github.com/ORGNAME/settings`)
1. Click on `GitHub Apps` under `Third-party Access`<br />![3rd Party Apps Menu](../../images/GitHub3rdPartyAppsMenu.png){: style="width:40%"}
1. On the page, locate the app you created and click on the `Configure` button
1. Note the address at the URL bar. You should see something along the lines of `https://github.com/organizations/ORGNAME/settings/installations/SOME-ID`. The numbers in the `SOME-ID` part is the **Installation ID**. You will need to keep track of this for configuring the payload.<br />![URL Bar](../../images/GItHubInstallationId.png)

### Making Changes
If you need to make changes in the future to support different repos in the same org, then you need to go to the App's installation and configure it to support more repos.

!!! note
    If you need to support more private repos that are not in the same GitHub organization, then you need to repeat ALL of the steps here in the org in question and update the secret with that org's version of the GitHub App's private key as depicted in the secret JSON above.

## Next Steps
At this point, you should have:

 - [x] The GitHub app created for the org you need to fetch repos for
 - [x] The GitHub app and configured with the correct permissions in the org
 - [x] The Private Key generated for the app
 - [x] The Secrets Manager secret has been updated with the Private Key set for the worker as depicted above
 - [x] The App is installed to the org
 - [x] You have App ID, and Installation ID

Once all that is completed, then move onto the next section for configuration and worker installation.
