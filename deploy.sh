#!/usr/bin/env bash

set -e

AWS_PROFILE=${1:default}
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

read -p "You're about to deploy to production with the profile ${AWS_PROFILE}! Continue? [n\Y] "
echo
if [[ ${REPLY} =~ ^[Yy]$ ]]
then
    # make sure we have the latest python code built, and npm code for lambda is up to date
    ./build.sh

    # Update the cli code.
    aws --profile=${AWS_PROFILE} s3 cp --recursive --include="*.whl" "${DIR}/dist/" s3://svo-print-config/

    # Update the lambda code
    aws --profile=${AWS_PROFILE} s3 cp "${DIR}/html-to-pdf/html-to-pdf.zip" s3://svo-print-config/lambda_code/
    aws --profile=${AWS_PROFILE} lambda update-function-code --region=us-east-1 \
        --function-name=html-to-pdf --s3-bucket=svo-print-config --s3-key=lambda_code/html-to-pdf.zip

    # see if we have made changes to cloudformation and attempt to run them.
    aws --profile=${AWS_PROFILE} cloudformation update-stack --stack-name svo-print \
        --template-body "file://${DIR}/svo-print.template" --capabilities CAPABILITY_IAM
fi
