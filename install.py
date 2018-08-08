import boto3
import json
import os

bucketName = os.environ['BUCKET_NAME']
region = os.environ['REGION']
rolePrefix = os.environ['ROLE_PREFIX']
username = os.environ['USERNAME']
password = os.environ['PASSWORD']
s3 = boto3.client('s3')
if (region == 'us-east-1'):
    s3.create_bucket(Bucket=bucketName)
else:
    s3.create_bucket(
        Bucket=bucketName,
        CreateBucketConfiguration = {
            'LocationConstraint': region
        })

s3.put_bucket_website(
    Bucket=bucketName,
    WebsiteConfiguration={
        'IndexDocument': {'Suffix': 'index.html'}
    })

iam = boto3.client('iam')

photoManagerRoleName = rolePrefix + 'PhotoManager'

lambdaTrustPolicy = {
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
  }]
}


iam.create_role(
    RoleName=photoManagerRoleName,
    AssumeRolePolicyDocument=json.dumps(lambdaTrustPolicy)
)

managePhotosPolicyName = rolePrefix + 'ManagePhotosPolicy'
managePhotosPolicy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": managePhotosPolicyName,
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": [
                "arn:aws:s3:::"+bucketName,
                "arn:aws:s3:::"+bucketName+"/*"
            ]
        }
    ]
}

managePhotosPolicyResponse = iam.create_policy(
    PolicyName=managePhotosPolicyName,
    PolicyDocument=json.dumps(managePhotosPolicy)
)
managePhotosPolicyArn = managePhotosPolicyResponse['Policy']['Arn']

iam.attach_role_policy(
    PolicyArn=managePhotosPolicyArn,
    RoleName=photoManagerRoleName
)

authLambdaRoleName = rolePrefix + 'AuthLambda'
authLambdaRoleResponse = iam.create_role(
    RoleName=authLambdaRoleName,
    AssumeRolePolicyDocument=json.dumps(lambdaTrustPolicy)
)
authLambdaRoleArn = authLambdaRoleResponse['Role']['Arn']

authLambdaPolicyName = rolePrefix + 'AuthLambdaPolicy'
authLambdaPolicy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sts:AssumeRole"
            ],
            "Resource": authLambdaRoleArn
        }
    ]
}

authLambdaPolicyResponse = iam.create_policy(
    PolicyName=authLambdaPolicyName,
    PolicyDocument=json.dumps(authLambdaPolicy)
)

authLambdaPolicyArn = authLambdaPolicyResponse['Policy']['Arn']

iam.attach_role_policy(
    PolicyArn=authLambdaPolicyArn,
    RoleName=authLambdaRoleName
)

#Create role that can write to the bucket
#Add bucket policy to bucket
#Enable cors on the bucket
#Copy js files to bucket
#generate index files and copy those to bucket
#create role for auth lambda
#create Auth lambda
#Create api gateway endpoint
#Create Cors for API Gateway
#Create apigateway js
#upload apigateway js
#Create image processing lambda with S3 trigger

