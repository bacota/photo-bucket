#!/bin/bash
cd auth
python -m py_compile lambda_function.py
if [ $? -eq 0 ]; then
    zip auth.zip lambda_function.py
    aws lambda update-function-code --function-name photoauth --zip-file fileb://auth.zip
fi

