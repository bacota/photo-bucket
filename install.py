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

lambdaExecutionPolicy = {
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
        }
    ]
}


def createRole(name,  *policies):
    roleName = rolePrefix + name
    roleResponse = iam.create_role(
        RoleName=roleName, 
        AssumeRolePolicyDocument=json.dumps(lambdaTrustPolicy)
    )
    roleArn = roleResponse['Role']['Arn']
    p=0
    for policy in policies:
        p = p+1
        policyName = rolePrefix + name + 'Policy' + str(p)
        policyResponse = iam.create_policy(
            PolicyName=policyName,
            PolicyDocument=json.dumps(policy)
        )
        policyArn = policyResponse['Policy']['Arn']
        iam.attach_role_policy(
            PolicyArn=policyArn,
            RoleName=roleName
        )
        return roleArn

photoManagerArn = createRole('PhotoManager', {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": [
                "arn:aws:s3:::"+bucketName,
                "arn:aws:s3:::"+bucketName+"/*"
            ]
        }
    ]
})




createRole('AuthLambda', lambdaExecutionPolicy, {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sts:AssumeRole"
            ],
            "Resource": photoManagerArn
        }
    ]
})



#Add bucket policy to bucket
#Enable cors on the bucket
#Copy js files to bucket
#generate index files and copy those to bucket
#create role for auth lambda
#Create api gateway endpoint
#Create Cors for API Gateway
#Create apigateway js
#upload apigateway js
#Create image processing lambda with S3 trigger

