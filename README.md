## Installation
This assumes you have a python3 environment.
1. `git clone git@github.com:kirkhansen/svo-print.git`
2. `workon your-new-virtualenv`
3. `pip install -r requirements-dev.txt` (or `pip install -r requirements.txt` if you're just using it)


## CLI Usage
First time use:
1. Run `python svo-print.py setup`
2. Add your information as the prompts dictate, or you can call `python svo-print.py setup` with the arguments directly

## Dev Usage
There are two scripts, `build.sh` and `deploy.sh`. At the time of writing, deploy also called build.
`build.sh` will bundle up the html-to-pdf lambda code and run pyinstaller. You'll want to run these with
in the python virtualenv your created, if you're using one.

`deploy.sh` will send the bundled apps to s3, and will call the aws svo-print to make sure the lambda gets the updated code.

There's also a cloudformation template that will setup the lambda, sqs, and s3 triggers.

## End User Installation Options
The `deploy.sh` saves a zip file of the svo-print in the `svo-print-config` s3 bucket.

The end user should be able to fill out a form in the web app that generates a
signed URL for download access to the `svo-print.zip` see
[aws docs ruby signed url](https://docs.aws.amazon.com/AmazonS3/latest/dev/UploadObjectPreSignedURLRubySDK.html)

The web app _could_ produce a command that could be copy pasted into a terminal.
It would look something like the following.

```bash
pushd ~/ && \
curl https://aws-signed-url-to-svo-print.zip -o ~/svo-print.zip && \
unzip ~/svo-print.zip && \
pushd svo-print && \
./svo-print setup \
    --access-key="AWS ACCESS KEY FROM WEB APP" \
    --secret-access-key="AWS SECRET ACCESS KEY FROM WEB APP" \
    --region="us-east-1" \
    --store-id="id of the store" \
    --executable-path="$(pwd)"
popd
popd
```

There are several ways to handle the access key stuff. The first few that come to mind are:

1. Create store id users in the cloudformation template, and have the
   web app generate access keys on each request to setup the print (access the form).
   If creds are compromised, you just revoke them in the console and
   email the user (or remote in) and have them re-submit the form to
   generate the access keys. Also, you wouldn't have to store the secret
   key in the web app which is nice.
2. Basically #1, but the web app also has the ability to create users
   if they don't exist already.
3. Use something like Cognito, or other federation service to allow users from
   other systems (LDAP, Google, etc) to assume a role that has the ability the
   store users would have. This is 'best practice', but is probably overkill.
4. Have the form the user submits send a notification to an admin that can
   manually create all this stuff, and send them an email with what to run and
   how to get going.

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
  "key": "test-svo-print-store/test.pdf"
}
```
* html: is a rendered html page to be printed
* bucket: the svo-print bucket where the pdf will be stored.
* key: the s3 key where the pdf will be stored. The prefix should be the store id
  and the filename should be unique (timestamps work well).

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
