# Start RDS instances

import json
import boto3

def lambda_handler(event, context):

    rds_client = boto3.client('rds')

    # Get only running instances
    allDatabases = rds_client.describe_db_instances()
    dbInstances = allDatabases['DBInstances']
    instances = [ (db['DBInstanceIdentifier'], db['DBInstanceArn']) for db in dbInstances if db['DBInstanceStatus'] != 'available' ]
    
    # Start the instances
    for instance in instances:
        response = rds_client.list_tags_for_resource(ResourceName=instance[1])
        for tag in response['TagList']:
            if tag['Key'] == 'always-running' and tag['Value'] == 'no':
                rds_client.start_db_instance(DBInstanceIdentifier=instance[0])
                print('Started instance: ', instance[0])

    return {
        'statusCode': 200,
        'body': json.dumps('Script finished')
    }
