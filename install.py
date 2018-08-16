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


def uniqueId():
    return str(datetime.datetime.utcnow().timestamp()).replace('.', '')

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

#Upload a zip file for creating a lambda and do it now since it might
#take a few seconds to become visible across all AZs.
thumbLambdaZipFile = 'thumbLambda.zip'
copyToS3(thumbLambdaZipFile) 

#The put_bucket_policy often fails without some sleep.  Occasionally, it
#fails even after 6 second sleep, but 6 seconds works for me most of
#the time
#time.sleep(6)

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
#YEESH!
apiClient = boto3.client('apigateway')
apiName = rolePrefix + 'AuthApi'

restApiId = apiClient.create_rest_api(name=apiName)['id']

#Use root resourceId
resourceId = apiClient.get_resources(restApiId=restApiId)['items'][0]['id']

## create POST method
apiClient.put_method(
    restApiId=restApiId,
    resourceId=resourceId,
    httpMethod="POST",
    authorizationType="NONE",
    apiKeyRequired=False
)

lambdaVersion = lambdaClient.meta.service_model.api_version
lambdaUri = f'arn:aws:apigateway:{region}:lambda:path/{lambdaVersion}/functions/{lambdaArn}/invocations'

## create integration
apiClient.put_integration(
    restApiId=restApiId,
    resourceId=resourceId,
    httpMethod="POST",
    type="AWS",
    integrationHttpMethod="POST",
    uri=lambdaUri
)

apiClient.put_integration_response(
    restApiId=restApiId,
    resourceId=resourceId,
    httpMethod="POST",
    statusCode="200",
    selectionPattern=".*"
)

## create POST method response
apiClient.put_method_response(
    restApiId=restApiId,
    resourceId=resourceId,
    httpMethod="POST",
    statusCode="200"
)

## create OPTIONS method
apiClient.put_method(
    restApiId=restApiId,
    resourceId=resourceId,
    httpMethod="OPTIONS",
    authorizationType="NONE",
    apiKeyRequired=False
)

## create integration
apiClient.put_integration(
    restApiId=restApiId,
    resourceId=resourceId,
    httpMethod="OPTIONS",
    type="MOCK",
    integrationHttpMethod="OPTIONS"
)

apiClient.put_integration_response(
    restApiId=restApiId,
    resourceId=resourceId,
    httpMethod="OPTIONS",
    statusCode="200",
    selectionPattern=".*"
)

## create OPTIONS method response
apiClient.put_method_response(
    restApiId=restApiId,
    resourceId=resourceId,
    httpMethod="OPTIONS",
    statusCode="200"
)


accountId = lambdaArn.split(':')[4]
sourceArn = f'arn:aws:execute-api:{region}:{accountId}:{restApiId}/*/POST/{authLambdaName}'

lambdaClient.add_permission(
    FunctionName=authLambdaName,
    StatementId=uniqueId(),
    Action="lambda:InvokeFunction",
    Principal="apigateway.amazonaws.com",
    SourceArn=sourceArn
)

apiClient.create_deployment(
    restApiId=restApiId,
    stageName='Production',
)


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
sdk = apiClient.get_sdk(restApiId=restApiId, stageName='Production', sdkType='javascript')['body'].read()
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
lambdaClient.add_permission(
    StatementId = uniqueId(),
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

