import boto3
import json
import os
import time

bucketName = os.environ['BUCKET_NAME']
region = os.environ['REGION']
rolePrefix = os.environ['ROLE_PREFIX']
username = os.environ['USERNAME']
password = os.environ['PASSWORD']

bucketArn = "arn:aws:s3:::" + bucketName
bucketArnWildCard = bucketArn + '/*'

s3 = boto3.client('s3')

if (region == 'us-east-1'):
    s3.create_bucket(Bucket=bucketName, ACL='public-read')
else:
    s3.create_bucket(
        Bucket=bucketName,
        ACL='public-read',
        CreateBucketConfiguration = {
            'LocationConstraint': region
        })

bucketWaiter = s3.get_waiter('bucket_exists')
bucketWaiter.wait(Bucket=bucketName)

s3.put_bucket_website(
    Bucket=bucketName,
    WebsiteConfiguration={
        'IndexDocument': {'Suffix': 'index.html'}
    })

iam = boto3.client('iam')
iamWaiter = iam.get_waiter('user_exists')

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


def createRole(roleName, *policies):
    roleResponse = iam.create_role(
        RoleName=roleName,
        AssumeRolePolicyDocument=json.dumps(lambdaTrustPolicy)
    )
    roleArn = roleResponse['Role']['Arn']
    p=0
    for policy in policies:
        p = p+1
        policyName = roleName + 'Policy' + str(p)
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


def readFile(fileName):
    f = open(fileName, "rb")
    content = f.read()
    f.close()
    return content

photoManagerPolicy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": [ bucketArn, bucketArnWildCard ]
        }
    ]
}

photoManagerRoleName = rolePrefix + 'PhotoManager'
photoManagerArn = createRole(photoManagerRoleName, photoManagerPolicy)

authLambdaPolicy = {
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
}

authRoleName = rolePrefix + 'AuthRole'
authRoleArn = createRole(authRoleName, lambdaExecutionPolicy, authLambdaPolicy)

bucketPolicy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": "*"},
            "Action": ["s3:GetObject"],
            "Resource": [bucketArnWildCard]
        },
        {
            "Effect": "Allow",
            "Principal": { "AWS" : [ photoManagerArn ] },
            "Action": "s3:*" ,
            "Resource": [ bucketArnWildCard ]
        }
    ]
}

time.sleep(5)
s3.put_bucket_policy(Bucket=bucketName, Policy=json.dumps(bucketPolicy))
s3.put_bucket_cors(
    Bucket=bucketName,
    CORSConfiguration={
        'CORSRules': [
            {
                'AllowedHeaders': [ '*' ],
                'AllowedMethods': [ 'GET', 'DELETE', 'PUT', 'HEAD' ],
                'AllowedOrigins': [ '*' ],
                'MaxAgeSeconds': 30000
            },
        ]
    }
)

lambdaClient = boto3.client('lambda')
authLambdaCode = readFile("auth/auth.zip")

authLambdaName=rolePrefix + 'AuthLambda'
time.sleep(4)
response = lambdaClient.create_function(
    FunctionName = authLambdaName,
    Runtime = 'python3.6',
    Role = authRoleArn,
    Code = { 'ZipFile' : authLambdaCode },
    Handler = 'lambda_function.lambda_handler',
    Environment = {
        'Variables': {
            'USERNAME' : username,
            'PASSWORD' : password,
            'ROLE_ARN' : photoManagerArn
        }
    }
)
lambdaArn = response['FunctionArn']

apig = boto3.client('apigateway')
apiName = rolePrefix + 'AuthApi'
apiResponse = apig.create_rest_api(name=apiName)
apiId = apiResponse['id']

swagger = readFile('photoauth-Production-swagger-apigateway.json').replace(
    '${apiId}', apiId).replace('${region}', region).replace('${authLambdaArn}', lanbdaArn)
apig.put_rest_api(restApiId=apiId, body=swagger)


#Create Auth Lambda
#Create image processing lambda with S3 trigger
#Copy js files to bucket
#generate index files and copy those to bucket
#Create api gateway endpoint
#Create Cors for API Gateway
#Create apigateway js
#upload apigateway js

