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
First, have the user go to https://www.python.org/downloads/ and install python. This is bundled in a mac osx
installer, and went smoothly on my 8 year old mac running 10.6.8.


The end user should be able to fill out a form in the web app that generates a
signed URL for download access to the `svo_print-config/svo_print-[version+python-version]-any.whl` see
[aws docs ruby signed url](https://docs.aws.amazon.com/AmazonS3/latest/dev/UploadObjectPreSignedURLRubySDK.html)

After they have the .whl (wheel) file, they can run
`pip2.7 install [the file].whl` in terminal.

After that succeeds, there should be a new binary `svo-print`. Test by typing `svo-print` in a terminal.

If that works, let's get a list of printers available printers with: `svo-print setup --help`

Look for the `--printer-name` field. There should be a `|` separated list of available printers.

Once you have that, you can go through the wizard with `sudo svo-print setup`.

The web app _could_ produce a command that could be copy pasted into a terminal.
It would look something like the following.

```bash
# assuming user ran `sudo su` to get a true root terminal first...
pushd / && \
curl "https://aws-signed-url-to-svo-.whl" -o ~/svo-print.whl && \
pip2.7 install svo-print.whl && \
svo-print setup \
    --access-key="AKIAJUNJIN5FPYVGHHTA" \
    --secret-access-key="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" \
    --region="us-east-1" \
    --queue-name="test-svo-print-store" \
    --default-log-level="info"
popd
```

This provides most of the config options, but the printer config options will need to be filled in by the user when prompted.
The cli should list the available printers to choose from, e.g.,

```bash
$ svo-print setup \
    --access-key="AKIAJUNJIN5FPYVGHHTA" \
    --secret-access-key="YcJexWW6tmZTsktk7oXWPssIqsz6jpaMMhn3NXcX" \
    --region="us-east-1" \
    --queue-name="test-svo-print-store" \
    --default-log-level="info"
Executable path [/home/kirk/wokspace/svo-print/svo_print.py]:
Us letter printer (HP_ENVY_5540_series) [HP_ENVY_5540_series]:
Label printer (HP_ENVY_5540_series) [HP_ENVY_5540_series]:
```

Note the `Us letter printer` and `Label printer` options. I only have one printer on the my network, so the choice is that listed in ().

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
   store users would have. This is best practice, but is probably overkill.
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
