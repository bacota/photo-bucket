import boto3
import datetime
import json
import os
import os.path
import time
import zipfile

bucketName = os.environ['BUCKET_NAME']
region = os.environ['REGION']
rolePrefix = os.environ['ROLE_PREFIX'] #should probably rename this since it's a unversal prefix
username = os.environ['USERNAME']
password = os.environ['PASSWORD']

bucketArn = "arn:aws:s3:::" + bucketName
bucketArnWildCard = bucketArn + '/*'

s3 = boto3.client('s3')
iam = boto3.client('iam')

#Policy that allows lambdas to assume the role
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

#Policy that allows to log themselves
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


#Create a role for lambdas
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

def contentType(fileName):
    if fileName.endswith('.html'):
        return 'text/html'
    elif fileName.endswith('.js'):
        return 'application/javascript'
    else:
        return 'binary/octet-stream'

def copyToS3(fileName):
    body = readFile(fileName, 'rb')
    s3.put_object(Bucket=bucketName, ACL='public-read', Body=body,
                  Key=fileName, ContentType=contentType(fileName))

def replAndCopyToS3(fileName):
    body = readFile(fileName, 'r').replace('${region}', region).replace('${bucketName}', bucketName)
    s3.put_object(Bucket=bucketName, ACL='public-read', Body=body,
                  Key=fileName, ContentType=contentType(fileName))

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

#Upload a zip file for creating a lambda and do it now since it might
#take a few seconds to become visible across all AZs.
thumbLambdaZipFile = 'thumbLambda.zip'
copyToS3(thumbLambdaZipFile) 
    
s3.put_bucket_website(
    Bucket=bucketName,
    WebsiteConfiguration={
        'IndexDocument': {'Suffix': 'index.html'}
    })


#Policy that allows management of photos
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

#Allow the authorization to create a session for photo management
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

#The put_bucket_policy often fails without some sleep.  Occasionally, it
#fails even after 6 second sleep, but 6 seconds works for me most of
#the time
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

#The create function occasionally fails without a sleep after creating the role.
time.sleep(4)

#Create the lambda that will authorize users for managing the photos.
#The code for this is small so we include the body as a parameter to
#the create_function call.
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

#Create the api gateway endpoint (from a swagger definition) for the auth lambda
apig = boto3.client('apigateway')
apiName = rolePrefix + 'AuthApi'
apiResponse = apig.create_rest_api(name=apiName)
apiId = apiResponse['id']
swagger = readFile('photoauth-Production-swagger-apigateway.json', 'r').replace(
    '${apiId}', apiId).replace('${region}', region).replace('${authLambdaArn}', lambdaArn).replace('${title}', apiName)
apig.put_rest_api(restApiId=apiId, body=swagger)
apig.create_deployment(restApiId=apiId, stageName='Production')

#Upload required javasccript and html files.  
copyToS3('photoalbum.js')
copyToS3('photos.js')
replAndCopyToS3('index.html')
replAndCopyToS3('index-template.html')
replAndCopyToS3('private-index.html')

#Create a javascript library for using the authorization endpoint.
#This results in a downloaded zip file.  We unzip it and upload each
#individual js file to the s3 bucket.
zipFileName = 'sdk.zip'
sdk = apig.get_sdk(restApiId=apiId, stageName='Production', sdkType='javascript')['body'].read()
zipFile = open(zipFileName, 'wb')
zipFile.write(sdk)
zipFile.close()
zip = zipfile.ZipFile(zipFileName, 'r')
zip.extractall(".")
zip.close()

def copyDir(dirName):
    for f in os.listdir(dirName):
        fullpath = os.path.join(dirName, f)
        if os.path.isdir(fullpath):
            copyDir(fullpath)
        else:
            copyToS3(fullpath)

copyDir('apiGateway-js-sdk')

#Create the lambda for processing images.  This is from a zip file,
#which includes some image processing libraries.
thumbLambdaName = rolePrefix + 'ThumbLambda'
objectWaiter  = s3.get_waiter('object_exists')
objectWaiter.wait(Bucket=bucketName, Key=thumbLambdaZipFile)
thumbResponse = lambdaClient.create_function(
    FunctionName = thumbLambdaName,
    Runtime = 'python3.6',
    Role = photoManagerArn,
    Code = { 'S3Bucket': bucketName, 'S3Key' : thumbLambdaZipFile },
    Handler = 'lambda_function.lambda_handler'
)
thumbArn = thumbResponse['FunctionArn']

#Create a rule to trigger the image processing lambda when an image is added to the bucket.

#The add_permission insists on some kind of unique id that we never use later
uniqueId = str(datetime.datetime.utcnow().timestamp()).replace('.', '')
lambdaClient.add_permission(
    StatementId = uniqueId,
    FunctionName = thumbLambdaName,
    Action = 'lambda:InvokeFunction',
    Principal = 's3.amazonaws.com',
    SourceArn = bucketArn
)
    
    
s3.put_bucket_notification_configuration(
    Bucket=bucketName,
    NotificationConfiguration = {
        'LambdaFunctionConfigurations':[
            { 'LambdaFunctionArn': thumbArn,
              'Events': ['s3:ObjectCreated:Put', 's3:ObjectCreated:Post']
            }
        ]
    }
)
