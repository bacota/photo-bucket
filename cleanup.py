import boto3
import os

bucketName = os.environ['BUCKET_NAME']
region = os.environ['REGION']
rolePrefix = os.environ['ROLE_PREFIX']
username = os.environ['USERNAME']
password = os.environ['PASSWORD']

def deleteLambda(functionName):
    lambdaClient = boto3.client('lambda')
    try: 
        lambdaClient.delete_function(FunctionName=functionName)
    except:
        pass

deleteLambda(rolePrefix + 'AuthLambda')

#delete a role with all attached policies
def deleteRole(roleName):
    iam = boto3.client('iam')
    try:
        attached = iam.list_attached_role_policies(RoleName=roleName)['AttachedPolicies']
        for policy in attached:
            arn = policy['PolicyArn']
            iam.detach_role_policy(RoleName=roleName, PolicyArn=arn)
            iam.delete_policy(PolicyArn=arn)
        iam.delete_role(RoleName=roleName)
    except:
        pass

deleteRole(rolePrefix + 'PhotoManager')
deleteRole(rolePrefix + 'AuthRole')

s3 = boto3.resource('s3')
bucket = s3.Bucket(bucketName)

try:
    bucket.delete()
except:
    pass


