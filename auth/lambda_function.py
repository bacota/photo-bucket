import boto3
import datetime
import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)
username = os.environ['USERNAME']
password = os.environ['PASSWORD']
roleArn = os.environ['ROLE_ARN']

def authorized(body):
    return ('username' in list(body) and 
    body['username'] == username and 
    'password' in list(body) and
    body['password'] == password
    )

def sts():
    client = boto3.client('sts')
    response = client.assume_role(RoleArn=roleArn, RoleSessionName='PhotoSession')
    return response['Credentials']

def convert_date(d):
    if isinstance(d, datetime.datetime):
        return d.__str__()

def lambda_handler(event,context):
    logger.info('event is {}'.format(event))
    body = json.loads(event['body'])
    logger.info('body is {}'.format(body))
    if (not authorized(body)):
        logger.info('AUTHORIZATION FAILED')
        return {
            'statusCode': str(401)
        }
    else:
        logger.info('AUTHORIZATION SUCCEEDED')
        credentials = sts()
        return {
            'statusCode': str(200),
            'body' : json.dumps(credentials, default=convert_date),
            'headers' : {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }

    
