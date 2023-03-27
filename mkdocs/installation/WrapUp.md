# Wrapping It Up

🤞Hopefully🤞 everything was successful in deploying and getting the account index working. If there were error messages you will want to review them and double-check that everything is set up properly.

## Debugging
Debugging is best accomplished by reviewing the logs. You can review the logs in the AWS console for your Starfleet account by going to CloudWatch in the region Starfleet is deployed in, and reviewing the Log Groups for the Lambdas. AWS SAM will generally name these according to the entry in the SAM template YAML.

You will want to verify that the `/aws/lambda/starfleet-StarbaseFanoutFunction-...`, `/aws/lambda/starfleet-StarbaseEventBridgeFunction-...` (this should be made when the EventBridge events are fired off), and the `/aws/lambda/starfleet-AccountIndexGenerator-...` exist.

The logs are quite verbose and should contain a lot of details about errors that are caused. In general, you will want to check the EventBridge function's logs to see if there are issues with the Starbase EventBridge scheduling, the Starbase fan out function's logs for issues with fanning out workers, and the individual worker logs to see if there are issues with them.

!!! tip
    By default, CloudWatch logs have no expiration. To save money, set a retention policy on the log groups to have logs automatically deleted after a certain period of time. You need to do this manually... or write a Starfleet worker to do this everywhere... 😏

## Deploy to Production
Deploying to production is basically the same exact steps as test, but you will want to replace the test values with production ones. Don't forget to re-run the SAM guided deploy in Prod and correct the SAM configuration so that it's identical to test with production values.

## Deployment Considerations
Now that you have Starfleet up and running, you may be thinking about how to manage the templates and all your environment specific configurations (and even custom workers).

The [Developer Guide](../developerGuide/Overview.md#packaging-deployment-considerations) has some suggestions on how to set up a proper deployment package. The TL;DR is you want a script that would download the upstream Starfleet, and merge in your configuration YAMLs, run SAM, and then perform the deployment.
