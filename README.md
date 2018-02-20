#svo-print

##Installation
1. git clone git@github.com:kirkhansen/svo-print.git
2. pip install -r requirements-dev.txt (or pip install -r requirements.txt if you're just using it)


## CLI Usage
First time use:
1. Run `python cli.py setup`
2. Add your information as the prompts dictate, or you can call `python cli.py setup` with the arguments directly

## Dev Usage
There are two scripts, `build.sh` and `deploy.sh`. At the time of writing, deploy also called build.
`build.sh` will bundle up the html-to-pdf lambda code and run pyinstaller.
`deploy.sh` will send the bundled apps to s3, and will call the aws cli to make sure the lambda gets the updated code.

There's also a cloudformation template that will setup the lambda, sqs, and s3 triggers.
