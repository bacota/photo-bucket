import boto3
from PIL import Image
from io import BytesIO
import logging, os, sys

thumbHeight=128.0
logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3 = boto3.client('s3')


def lambda_handler(event,context):
    logger.info(event)
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        newKey = key.replace('new/', '', 1)
        #hopefully no folder will be called 'main'
        thumbKey = newKey.replace('/main/', '/thumb/')
        s3.copy_object(Bucket=bucket,
                       CopySource = {'Bucket': bucket, 'Key':key},
                       Key=newKey)
        #s3.put_object(Bucket=bucket, Body=mainBody, Key=newKey)
        mainBody = s3.get_object(Bucket=bucket, Key=key)['Body']
        bytes_array = BytesIO()
        image = Image.open(mainBody)
        width,height = image.size
        size = round(width*thumbHeight/height), thumbHeight
        image.thumbnail(size, Image.ANTIALIAS)
        image.save(bytes_array, 'JPEG')
        bytes_array.seek(0)
        s3.put_object(Bucket=bucket, Key=thumbKey, Body=bytes_array)
        s3.delete_object(Bucket=bucket, Key=key)
