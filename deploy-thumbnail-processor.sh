#!/bin/bash
cd thumbnail
python3 -m py_compile lambda_function.py
if [ $? -eq 0 ]; then
    zip -g thumbnails.zip lambda_function.py
    aws lambda update-function-code --function-name ThumbnailPhotoGenerator --zip-file fileb://thumbnails.zip
fi

