#!/usr/bin/env bash

AWS_PROFILE=${1:-svo}

read -p "You're about to deploy to production with the profile ${AWS_PROFILE}! Continue? [n\Y] "
echo
if [[ ${REPLY} =~ ^[Yy]$ ]]
then
    # make sure we have the latest python code built, and npm code for lambda is up to date
    ./build.sh
    aws --profile=${AWS_PROFILE} s3 cp html-to-pdf/html-to-pdf.zip s3://svo-print/lambda_code/
    aws --profile=${AWS_PROFILE} lambda update-function-code --region=us-east-1 --function-name=html-to-pdf --s3-bucket=svo-print --s3-key=lambda_code/html-to-pdf.zip
fi
