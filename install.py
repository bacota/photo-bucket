import boto3
import json
import os
import os.path
import time
import zipfile

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


def readFile(fileName, mode="rb"):
    f = open(fileName, mode)
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

time.sleep(6)
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
authLambdaCode = readFile('auth/auth.zip', 'rb')

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

swagger = readFile('photoauth-Production-swagger-apigateway.json', 'r').replace(
    '${apiId}', apiId).replace('${region}', region).replace('${authLambdaArn}', lambdaArn).replace('${title}', apiName)
apig.put_rest_api(restApiId=apiId, body=swagger)

def copyToS3(fileName):
    body = readFile(fileName, 'rb')
    s3.put_object(Bucket=bucketName, ACL='public-read', Body=body, Key=fileName)

def replAndCopyToS3(fileName):
    body = readFile(fileName, 'r').replace('${region}', region).replace('${bucketName}', bucketName)
    s3.put_object(Bucket=bucketName, ACL='public-read', Body=body, Key=fileName)
    
copyToS3('photoalbum.js')
copyToS3('photos.js')
replAndCopyToS3('index.html')
replAndCopyToS3('index-template.html')
replAndCopyToS3('private-index.html')

zipFileName = 'sdk.zip'

sdk = apig.get_sdk(restApiId=apiId, stageName='Production', sdkType='javascript')['body'].read()
zipFile = open(zipFileName, 'w')
f.write(sdk)
f.close()

zip = zipfile.ZipFile(zipFileName, 'r')
zip.extractall(".")
zip.close()

apiDirName = 'apiGateway-js-sdk'
jsfiles = os.listdir(apiDirName)
for f in jsFiles:
    jsFileName = os.path.join(apiDirName, f)
    print(jsFileName)




#Create apigateway js
#upload apigateway js

#Create image processing lambda with S3 trigger


