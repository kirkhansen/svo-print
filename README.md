[![Build Status](https://travis-ci.org/kirkhansen/svo-print.svg?branch=master)](https://travis-ci.org/kirkhansen/svo-print)

## Installation
1. `git clone git@github.com:kirkhansen/svo-print.git`
2. `workon your-new-virtualenv`
3. `pip install -e .`


## CLI Usage
First time use:
1. Run `sudo svo-print setup`
2. Add your information as the prompts dictate, or you can call `svo-print setup` with the arguments directly

## Dev Usage
There are two scripts, `build.sh` and `deploy.sh`. At the time of writing, deploy also called build.
`build.sh` will bundle up the html-to-pdf lambda code and run bdist_wheel. You'll want to run these with
in the python virtualenv your created, if you're using one.

`deploy.sh` will send the bundled apps to s3, and will call the aws svo-print to make sure the lambda gets the updated code.
The `deploy.sh` creates a wheel file in the `svo-print-config` s3 bucket to be installed by the end user later.

There's also a cloudformation template that will setup the lambda, sqs, and s3 triggers.

## End User Installation Options
### Scripted Installation

1. Have the user verify that `pip2.7` exists with `pip2.7 -V`
2.  Have them run the following.
```bash
# assuming user ran `sudo su` to get a true root terminal first...
pushd / && \
curl "https://aws-signed-url-to-svo-py2.whl" -o ~/svo-print.whl && \
pip2.7 install svo-print.whl && \
svo-print setup \
    --access-key="AKIAJUNJIN5FPYVGHHTA" \
    --secret-access-key="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" \
    --region="us-east-1" \
    --queue-name="test-svo-print-store" \
    --default-log-level="info"
popd
```
3. The user will be prompted to fill in some variables. The execuatble path can use the default. The two printer options are what they need to fill in for the two types (us_letter and label). E.g.
```
Executable path [/home/kirk/wokspace/svo-print/svo_print.py]:
Us letter printer (HP_ENVY_5540_series): HP_ENVY_5540_series
Label printer (HP_ENVY_5540_series): HP_ENVY_5540_series
```
Note the `Us letter printer` and `Label printer` options. I only have one printer on the my network, so the choice is that listed in ().

## Additional notes

### Starting the print process
[invoking lambda from ruby](https://docs.aws.amazon.com/sdk-for-ruby/v3/developer-guide/lambda-ruby-example-run-function.html)

To start the print process, the rails app will have to use the aws ruby sdk to
interact with aws lambda. Currently, the payload would be a json document
that looks like
```json
{
  "html": "<!DOCTYPE html><html><head><title>HTML doc</title></head><body>Content<body></html>",
  "bucket": "svo-print",
  "key": "test-svo-print-store/us_letter/test.pdf"
}
```
* html: is a rendered html page to be printed
* bucket: the svo-print bucket where the pdf will be stored.
* key: the s3 key where the pdf will be stored. The prefix should be the store id and the filename should be unique (timestamps work well).
Also, the file needs to be under one of the following keys depending on printer config type: `us_letter`, `label`

You could get the function name from calling cloudformation,
or read the value from a config file,
or just hard-code `html-to-pdf` since that won't change.


### Adding store queues in Cloudformation

1. Add a new queue resource (similar to the `testStoreQueue`)
2. Update the `svoPrintS3` resource
    * Add another block under the `QueueConfigurations` like
    ```
    {
      "Event": "s3:ObjectCreated:*",
      "Filter": {"S3Key": {"Rules": [{"Name": "prefix", "Value": "newStoreId/"}]}},
      "Queue": {"Fn::GetAtt": ["resourceOfNewQueue", "Arn"]}
    }
    ```
    * Add your new queue resource name to the `DependsOn` key.
3. Update the `svoQueuePolicy`
    * Add your new queue resource name to the `DependsOn` key.
    * Update the `Queues` key to have another block like `{"Ref": "resourceOfNewQueue"}`
    * Update the `Resource` key and add another `{"Fn::GetAtt": ["resourceOfNewQueue", "Arn"]}`
