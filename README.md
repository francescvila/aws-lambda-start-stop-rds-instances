# RDS Instances: Stopping nightly & starting daily on working days

## About The Project

This project aims to show how to create scheduled rules in AWS EventBridge to automate every night the auto-shutdown and every day the startup of all RDS instances on working days whose tag with key "always-running" has the value "no".
By tuning off instances at night and weekends we can reduce the AWS bill.

## Prerequistes

In order to check AWS configurations and the creation of resources and services we'll need to install the AWS client application (See the links section).

For this project, we'll create a new AWS profile. I've named mine "sandbox".
If you already have an AWS profile created for other purposes, backup your ~/.aws/config and ~/.aws/credentials files.

```sh
mkdir ~/.aws
echo -e "[profile sandbox]\nregion = us-east-1\noutput = json" > ~/.aws/config
echo -e "[sandbox]\naws_access_key_id = AWS_ACCESS_KEY  >\naws_secret_access_key = AWS_SECRET_KEY" > ~/.aws/credentials
```

If you prefer to create your infrastructure in a different region than "us-east-1", feel free to change it in the config file.
Replace "AWS_ACCESS_KEY" and AWS_SECRET_KEY with yours.
If you prefer another profile name you can change it in the config file.

I rather prefer to define an environment variable to save the value of the profile name I'll be using.
```sh
PROFILE=sandbox
```

To check the profile is correctly configured execute the command:
```sh
aws configure --profile $PROFILE
```

We'll also need to install jq JSON processor, as we are going to manipulate AWS CLI output in JSON format.

## Instructions

### Create the RDS instances

Manually launch two RDS instances. These instances will be used solely as a means to test our lambda functions.

You can create the RDS instances using the AWS RDS web dashboard. You might change the region with yours.
https://us-east-1.console.aws.amazon.com/rds/home?region=us-east-1#Home

You can also do it using the AWS CLI application.

Define environment variables with proper values to create some demo RDS instances.
```sh
INSTANCE_ID=testdb1
INSTANCE_TYPE=db.t3.micro
ENGINE=mysql
USERNAME=admin
PASSWORD=p4sSw0Rd
STORAGE=20
TAG_NAME=always-running
TAG_VALUE=no
```

Check the environment variables to confirm they have the expected values.
```sh
echo $INSTANCE_TYPE
echo $ENGINE
echo $USERNAME
echo $PASSWORD
echo $STORAGE
echo $TAG_NAME
echo $TAG_VALUE
```

And now it's time to create the RDS instance.
```sh
aws rds create-db-instance \
    --db-instance-identifier $INSTANCE_ID \
    --db-instance-class $INSTANCE_TYPE \
    --engine $ENGINE \
    --master-username $USERNAME \
    --master-user-password $PASSWORD \
    --allocated-storage $STORAGE \
    --tags "[{\"Key\": \"$TAG_NAME\",\"Value\": \"$TAG_VALUE\"}]" \
    --profile $PROFILE
```

Let's create another RDS instance but with the tag value "yes" for key "always-running".
```sh
INSTANCE_ID=testdb2
TAG_VALUE=yes
aws rds create-db-instance \
    --db-instance-identifier $INSTANCE_ID \
    --db-instance-class $INSTANCE_TYPE \
    --engine $ENGINE \
    --master-username $USERNAME \
    --master-user-password $PASSWORD \
    --allocated-storage $STORAGE \
    --tags "[{\"Key\": \"$TAG_NAME\",\"Value\": \"$TAG_VALUE\"}]" \
    --profile $PROFILE
```

Let's check if the instances have been created correctly.
```sh
aws rds describe-db-instances --profile $PROFILE
```

List only instances by InstanceId.
```sh
aws rds describe-db-instances --profile $PROFILE | jq ".DBInstances[] | [.DBInstanceIdentifier]"
```

### Create the IAM rules and policies

In this project we need to create a policy and a role that will be used by our lambda functions to have permissions to access RDS resources.

You can create the rules and policies using the IAM web dashboard. You might change the region with yours.
https://us-east-1.console.aws.amazon.com/iamv2/home?region=us-east-1#/home

You can also do it using the AWS CLI application.

Define environment variables with values to create the IAM rule and its corresponding policy.
```sh
POLICY_NAME=LambdaStartStopRdsInstancesPolicy
ROLE_NAME=LambdaStartStopRdsInstancesRole
```

Check the environment variables to confirm they have the expected values.
```sh
echo $POLICY_NAME
echo $ROLE_NAME
```

Now we create our lambda IAM policy.
```sh
aws iam create-policy --policy-name $POLICY_NAME --policy-document file://$PWD/iam-policy.json --profile $PROFILE
```

Let's check if the policy has been created correctly.
```sh
aws iam list-policies --scope Local --query "Policies[?PolicyName==\`$POLICY_NAME\`]" --profile $PROFILE
```

We can catch the policy ARN from the last command output or get it executing the following:
```sh
POLICY_ARN=$(aws iam list-policies --scope Local --query "Policies[?PolicyName==\`$POLICY_NAME\`].{Arn: Arn}" --profile $PROFILE | jq ".[].Arn" | sed 's/"//g')
```

Check its value.
```sh
echo $POLICY_ARN
```

We'll need the policy ARN to attach it later to the IAM role.

Now we create the lambda IAM role.
```sh
aws iam create-role --role-name $ROLE_NAME --assume-role-policy-document file://$PWD/trust-policy.json --profile $PROFILE
```

We attach the permissions policy to the role.
```sh
aws iam attach-role-policy --policy-arn $POLICY_ARN --role-name $ROLE_NAME --profile $PROFILE
```

Let's check if the role has been created correctly.
```sh
aws iam list-roles --query "Roles[?RoleName==\`$ROLE_NAME\`]" --profile $PROFILE
```

We can catch the role ARN from the last command output or get it executing the following command:
```sh
ROLE_ARN=$(aws iam list-roles --query "Roles[?RoleName==\`$ROLE_NAME\`].{Arn: Arn}" --profile $PROFILE | jq ".[].Arn" | sed 's/"//g')
```

Check its value.
```sh
echo $ROLE_ARN
```

We'll need the role ARN to create the lambda functions.

### Create the lambda functions

You can create the lambda functions using the AWS Lambda web dashboard. You might change the region with yours.
https://us-east-1.console.aws.amazon.com/lambda/home?region=us-east-1#/functions

You can also do it using the AWS CLI application.

We'll define some environment variables to create the Lambda functions.
```sh
FUNCTION_NAME=StopRDSInstances
FUNCTION_FILE=function_stop.zip
HANDLER=lambda_function_stop.lambda_handler
RUNTIME=python3.7
TIMEOUT=60
```

Check the environment variables to confirm they have the expected values.
```sh
echo $FUNCTION_NAME
echo $FUNCTION_FILE
echo $HANDLER
echo $RUNTIME
echo $TIMEOUT
```

We'll create the Lambda function that stops nightly all RDS instances tagged as always-running=no on working days.
Later we'll do the same with the Lambda that starts daily all RDS instnaces tagged as always-running=no on working days.
The Python code is contained in files both lambda_function_stop.py and lambda_start.py.

We'll need to zip it in order to pass it to the Lambda function through the AWS CLI application.
```sh
zip $FUNCTION_FILE lambda_function_stop.py
```

Now we create the Lambda function.
```sh
aws lambda create-function --function-name $FUNCTION_NAME --zip-file fileb://$PWD/$FUNCTION_FILE --handler $HANDLER --runtime $RUNTIME --timeout $TIMEOUT --role $ROLE_ARN --profile $PROFILE
```

Let's check if the function has been created correctly.
```sh
aws lambda list-functions --query "Functions[?FunctionName==\`$FUNCTION_NAME\`]" --profile $PROFILE
```

We can catch the function ARN from the last command output or get it executing the following command:
```sh
STOP_FUNCTION_ARN=$(aws lambda list-functions --query "Functions[?FunctionName==\`$FUNCTION_NAME\`].{FunctionArn: FunctionArn}" --profile $PROFILE | jq ".[].FunctionArn" | sed 's/"//g')
```

Check its value.
```sh
echo $STOP_FUNCTION_ARN
```

We'll need the function ARN to create the EventBridge rules.

Now we do the same for the start Lambda function:
```sh
FUNCTION_NAME=StartRDSInstances
FUNCTION_FILE=function_start.zip
HANDLER=lambda_function_start.lambda_handler
zip $FUNCTION_FILE lambda_function_start.py
aws lambda create-function --function-name $FUNCTION_NAME --zip-file fileb://$PWD/$FUNCTION_FILE --handler $HANDLER --runtime $RUNTIME --timeout $TIMEOUT --role $ROLE_ARN --profile $PROFILE
START_FUNCTION_ARN=$(aws lambda list-functions --query "Functions[?FunctionName==\`$FUNCTION_NAME\`].{FunctionArn: FunctionArn}" --profile $PROFILE | jq ".[].FunctionArn" | sed 's/"//g')
```

### Create the EventBridge rules

We want to schedule event rules to execute the start Lambda function daily and the stop Lambda function nightly.

You can create the event rules using the Amazon EventBridge web dashboard. You might change the region with yours.
https://us-east-1.console.aws.amazon.com/events/home?region=us-east-1#/rules

You can also do it using the AWS CLI application.

We'll define some environment variables to create the event rules.
```sh
RULE_NAME=StopRDSInstancesNightly
CRON_EXPRESSION='cron(0 21 ? * MON-FRI *)'
TARGET_ID=StopRDSInstancesId
```

In the cron expression time is expressed in UTC.

Check the environment variables to confirm they have the expected values.
```sh
echo $RULE_NAME
echo $CRON_EXPRESSION
echo $TARGET_ID
```

Now we create the event rule to stop RDS instances, and we add the corresponding Lambda function as target.

```sh
# Stop RDS instances event rule
aws events put-rule --name $RULE_NAME --schedule-expression $CRON_EXPRESSION --profile $PROFILE
aws events put-targets --rule $RULE_NAME --targets "Id"=$TARGET_ID,"Arn"=$STOP_FUNCTION_ARN --profile $PROFILE
```

Add the resource-based policy statement for the event rule to the lambda function.
```sh
FUNCTION_NAME=StopRDSInstances
RULE_NAME=StopRDSInstancesNightly
aws lambda add-permission \
--function-name $FUNCTION_NAME \
--statement-id $RULE_NAME \
--action 'lambda:InvokeFunction' \
--principal events.amazonaws.com \
--source-arn $STOP_FUNCTION_ARN \
--profile $PROFILE
```

Let's check if the function has been created correctly.
```sh
aws events list-rules --query "Rules[?Name==\`$RULE_NAME\`]" --profile $PROFILE
```

List attached targets by rule:
```sh
aws events list-targets-by-rule --rule $RULE_NAME --profile $PROFILE
```

We also create the event rule to start RDS instances, and we add the corresponding Lambda function as target.

```sh
# Start RDS instances event rule
RULE_NAME=StartRDSInstancesDaily
CRON_EXPRESSION='cron(0 5 ? * MON-FRI *)'
TARGET_ID=StartRDSInstancesId
aws events put-rule --name $RULE_NAME --schedule-expression $CRON_EXPRESSION --profile $PROFILE
aws events put-targets --rule $RULE_NAME --targets "Id"="$TARGET_ID","Arn"="$START_FUNCTION_ARN" --profile $PROFILE
```

Add the resource-based policy statement for the event rule to the lambda function.
```sh
FUNCTION_NAME=StartRDSInstances
RULE_NAME=StartRDSInstancesDaily
aws lambda add-permission \
--function-name $FUNCTION_NAME \
--statement-id $RULE_NAME \
--action 'lambda:InvokeFunction' \
--principal events.amazonaws.com \
--source-arn $START_FUNCTION_ARN \
--profile $PROFILE
```

Let's check if the function has been created correctly.
```sh
aws events list-rules --query "Rules[?Name==\`$RULE_NAME\`]" --profile $PROFILE
```
List attached targets by rule:
```sh
aws events list-targets-by-rule --rule $RULE_NAME --profile $PROFILE
```

### Test lambda functions

We might not wait until night or early in the morning to test our Lambda functions.
There's the option of executing the Lambda functions manually from the AWS Lambda web dashboard.
But we also want to check if EventBridge rules are working correctly.
We can change the cron expression to a time close to our current time (expressed in UTC time zone).

Let's change the cron expression for the StopRDSInstancesNightly event rule to a different time.

```sh
RULE_NAME=StopRDSInstancesNightly
CRON_EXPRESSION='cron(0 9 ? * * *)'
aws events put-rule --name $RULE_NAME --schedule-expression $CRON_EXPRESSION --profile $PROFILE
```

We can list the instances and see if one of them stopped (tag always-running=no).
```sh
aws rds describe-db-instances --profile $PROFILE | jq ".DBInstances[] | [.DBInstanceIdentifier, .DBInstanceStatus, (.TagList[]|select(.Key==\"$TAG_NAME\")|.Value)]"
```

The following command shows how to retrieve base64-encoded logs for Lambda function StopRDSInstances.
```sh
FUNCTION_NAME=StopRDSInstances
aws lambda invoke --function-name $FUNCTION_NAME out --log-type Tail --query 'LogResult' --output text --profile $PROFILE |  base64 -d
```

Let's change the cron expression for the StartRDSInstancesDaily event rule to a different time.

```sh
RULE_NAME=StartRDSInstancesDaily
CRON_EXPRESSION='cron(10 9 ? * * *)'
aws events put-rule --name $RULE_NAME --schedule-expression $CRON_EXPRESSION --profile $PROFILE
```

List again the instances and see if the stopped RDS instance started as expected.
```sh
aws rds describe-db-instances --profile $PROFILE | jq ".DBInstances[] | [.DBInstanceIdentifier, .DBInstanceStatus, (.TagList[]|select(.Key==\"$TAG_NAME\")|.Value)]"
```

Retrieve the base64-encoded logs for Lambda function StartRDSInstances.
```sh
FUNCTION_NAME=StartRDSInstances
aws lambda invoke --function-name $FUNCTION_NAME out --log-type Tail --query 'LogResult' --output text --profile $PROFILE |  base64 -d
```

Now we can finally set the cron expressions to their original values.
```sh
RULE_NAME=StopRDSInstancesNightly
CRON_EXPRESSION='cron(0 21 ? * MON-FRI *)'
aws events put-rule --name $RULE_NAME --schedule-expression $CRON_EXPRESSION --profile $PROFILE
RULE_NAME=StartRDSInstancesDaily
CRON_EXPRESSION='cron(0 5 ? * MON-FRI *)'
aws events put-rule --name $RULE_NAME --schedule-expression $CRON_EXPRESSION --profile $PROFILE
```

## Links
* AWS Free Tier: https://aws.amazon.com/free
* Installing or updating the latest version of the AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
* Install jq on Ubuntu 22.04: https://lindevs.com/install-jq-on-ubuntu
