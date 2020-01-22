#!/usr/bin/env python2
import getpass
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import configparser
import tempfile
import subprocess
from pathlib import Path
from six import ensure_str

import boto3
import click
from crontab import CronTab

# TODO: Typically, a lot of this code would be split out into several modules,
# but I'm not sure how that will work with Pyinstaller.
# Try it out so this code is more maintainable.
# TODO: Logging is confusing here. simplify it by moving it into it's own module.

os.environ.update(
    {"LC_CTYPE": "en_US.UTF-8",}
)

APP_NAME = "svo-print"
AWS_CONFIG_SECTION = "AWS"
CRON_CONFIG_SECTION = "CRON"
CONFIGURED_PRINTERS_SECTION = "CONFIGURED_PRINTERS"
EXECUTABLE_PATH = ensure_str(str(Path(__file__).absolute()))

CONFIG_FILE = os.path.join(click.get_app_dir(APP_NAME), "config.json")

LOG_FILE = ensure_str(
    str(Path(click.get_app_dir(APP_NAME), "log/{}.log".format(APP_NAME)))
)
LOG_LEVEL_LOOKUP = {
    "error": logging.ERROR,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}

CLI_WARN = "yellow"
CLI_ERROR = "red"
CLI_SUCCESS = "green"
CLI_INFO = "blue"

ENV_VARS_TO_PASS_TO_COMMAND = {"LC_CTYPE", "LOG_FILE", "LOG_LEVEL"}


def setup_logging(
    name, default_level="error", env_log_file="LOG_FILE", env_log_level="LOG_LEVEL"
):
    path = os.getenv(env_log_file, LOG_FILE)
    if not os.path.exists(path):
        Path(path).parent.mkdir()
    level = LOG_LEVEL_LOOKUP.get(os.getenv(env_log_level, default_level), logging.ERROR)
    stream_handler = logging.StreamHandler()
    file_handler = RotatingFileHandler(path, maxBytes=2000, backupCount=3)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s")
    )

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


LOGGER = setup_logging(__name__)


def _get_config():
    config_file =  Path(CONFIG_FILE)
    if not config_file.parent.exists():
        config_file.parent.mkdir(parents=True)
    if not config_file.exists():
        config_dict = {}
    else: 
        with config_file.open() as f:
            config_dict = json.load(f)

    for section in [AWS_CONFIG_SECTION, CRON_CONFIG_SECTION, CONFIGURED_PRINTERS_SECTION]:
        if section not in config_dict:
            config_dict[section] = {}

    return config_dict


# doing this so the click options can have some defaults if the wizard is run again, or the config file is
# otherwise present when a user tries to run this.
CONFIG = _get_config()


def _get_aws_session():
    LOGGER.debug("Getting s3 session")
    session = boto3.Session(
        aws_access_key_id=CONFIG[AWS_CONFIG_SECTION]["access_key"],
        aws_secret_access_key=CONFIG[AWS_CONFIG_SECTION]["secret_access_key"],
        region_name=CONFIG[AWS_CONFIG_SECTION]["region"],
    )
    return session


def _get_available_printers():
    LOGGER.debug("Searching for printers")
    lpstat = subprocess.Popen(["lpstat", "-a"], stdout=subprocess.PIPE)
    printers = subprocess.check_output(
        ["cut", "-f1", "-d", " "], stdin=lpstat.stdout
    ).split()
    lpstat.wait()
    printers = [ensure_str(printer) for printer in printers]
    LOGGER.debug("Found {} printers".format(",".join(printers)))
    return printers


def _get_default_printer():
    try:
        printer = _get_available_printers()[0]
    except IndexError:
        printer = ""
    return printer


def _generate_config(val_dict):
    cfg = {}
    cfg[AWS_CONFIG_SECTION] = {
        "access_key": val_dict["access_key"],
        "secret_access_key": val_dict["secret_access_key"],
        "region": val_dict["region"],
        "queue_name": val_dict["queue_name"],
    }
    cfg[CONFIGURED_PRINTERS_SECTION] = val_dict["printers"]
    cfg[CRON_CONFIG_SECTION] = {
        "executable_path": val_dict["executable_path"],
        "cmd": "run",
        "default_log_level": val_dict["default_log_level"],
    }

    with open(CONFIG_FILE, "w") as config_file:
        json.dump(cfg, config_file)
    LOGGER.info("Saved config file to {}".format(CONFIG_FILE))
    return cfg


def _schedule(config):
    """
    Setups up a cron job to make sure the print job process is running. Run this every minute
    on workdays between 7am and 9pm
    """
    crontab = CronTab(user=getpass.getuser())
    cmd = "{} {} {} {}".format(
        " ".join(
            "{}={}".format(key, value)
            for key, value in os.environ.items()
            if key in ENV_VARS_TO_PASS_TO_COMMAND
        ),
        "LOG_LEVEL={}".format(config[CRON_CONFIG_SECTION]["default_log_level"]),
        config[CRON_CONFIG_SECTION]["executable_path"],
        config[CRON_CONFIG_SECTION]["cmd"],
    )
    LOGGER.info("Adding command: '{}'".format(cmd))
    try:
        job = next(crontab.find_comment("print-job"))
        LOGGER.info("Cron exists. Updating.")
        job.command = cmd
    except StopIteration:
        LOGGER.info("Adding new cron job.")
        crontab.new(comment="print-job", command=cmd)
        job = next(crontab.find_comment("print-job"))
    job.setall("* 7-21 * * *")
    crontab.write()


def _print_file(file_to_print, printer_name):
    """ Send the job to the printer. This assumes Mac or Unix like system where lpr exists."""
    subprocess.check_call(
        [
            "lp",
            "-d",
            printer_name,
            "-o",
            "fit-to-page",
            file_to_print,
        ]
    )


def _jobs():
    session = _get_aws_session()
    sqs = session.resource("sqs")
    queue = sqs.get_queue_by_name(QueueName=CONFIG[AWS_CONFIG_SECTION]["queue_name"])
    done = False
    while not done:
        response = queue.receive_messages(WaitTimeSeconds=19, MaxNumberOfMessages=10)
        done = not bool(response)
        for message in response:
            records = json.loads(message.body)["Records"]
            for record in records:
                s3_record = dict(
                    key=record["s3"]["object"]["key"],
                    bucket=record["s3"]["bucket"]["name"],
                )
                yield message, s3_record

def _download_file(s3, message, job):
    file_to_print, printer_config = None, None
    try:
        file_to_print = os.path.join(
            tempfile.gettempdir(), os.path.basename(job["key"])
        )
        _, printer_config, _ = job["key"].split("/")
        LOGGER.info("Fetching {} from s3".format(file_to_print))
        s3.Bucket(job["bucket"]).download_file(job["key"], file_to_print)
        LOGGER.info("Printer config is {}".format(printer_config))
        LOGGER.info("Printing {}".format(file_to_print))
    except OSError:
        # This appears to happen when trying to download a dir key instead of a single object.
        # Delete the message
        LOGGER.warning("Looks like we tried to download a directory; message will be deleted. Key was {}".format(job["key"]))
        message.delete()
    return str(file_to_print), str(printer_config)

def _send_jobs_to_printer(s3):
    """ Loops through the queue messages, and attempts to download the pdf object, and send it to the printer(s). """
    for message, job in _jobs():
        file_to_print, printer_config = _download_file(s3, message, job)
        if file_to_print and printer_config in CONFIG[CONFIGURED_PRINTERS_SECTION]:
            try:
                _print_file(file_to_print, CONFIG[CONFIGURED_PRINTERS_SECTION][printer_config])
            except Exception:
                LOGGER.exception("Error sending jobs to printer")
            else:
                message.delete()
        else:
            LOGGER.warning("file_to_print was empty or Printer config {} doesn't exist in CONFIG".format(printer_config))

@click.group()
def svo_print():
    """Commands to send SVO print requests to the network printer"""


@svo_print.command()
@click.option(
    "--access-key",
    help="AWS access key",
    required=True,
    prompt=True,
    default=CONFIG[AWS_CONFIG_SECTION].get("access_key", ""),
)
@click.option(
    "--secret-access-key",
    help="AWS Secret access key",
    required=True,
    prompt=True,
    default=CONFIG[AWS_CONFIG_SECTION].get("secret_access_key", ""),
)
@click.option(
    "--region",
    help="AWS region",
    default=CONFIG[AWS_CONFIG_SECTION].get("region", "us-east-1"),
    prompt=True,
)
@click.option(
    "--queue-name",
    help="The SQS name to pull jobs from; should be the id of your store",
    required=True,
    prompt=True,
    default=CONFIG[AWS_CONFIG_SECTION].get("queue_name", ""),
)
@click.option(
    "--executable-path",
    help="Full path to this python file.",
    required=True,
    prompt=True,
    type=click.Path(exists=True, dir_okay=False, file_okay=True),
    show_default=True,
    default=EXECUTABLE_PATH,
)
@click.option(
    "--default-log-level",
    help="Default Logging level to use",
    default="error",
    type=click.Choice(["error", "info", "debug"]),
)
@click.option(
    "--us-letter-printer",
    help="printer to use for us-letter size",
    required=True,
    prompt=True,
    type=click.Choice(_get_available_printers()),
    default=CONFIG[CONFIGURED_PRINTERS_SECTION].get("us_letter", None)

)
@click.option(
    "--label-printer",
    help="printer to use for labels",
    required=True,
    prompt=True,
    type=click.Choice(_get_available_printers()),
    default=CONFIG[CONFIGURED_PRINTERS_SECTION].get("label", None)
)
def setup(
    access_key,
    secret_access_key,
    region,
    queue_name,
    executable_path,
    default_log_level,
    us_letter_printer,
    label_printer
):
    """
    Setup the printing application. You may pass in the variables from the commandline directly, or
    omit them, and enter them via the wizard prompt.
    """
    config_vals = dict(
        access_key=access_key,
        secret_access_key=secret_access_key,
        region=region,
        queue_name=queue_name,
        executable_path=executable_path,
        default_log_level=default_log_level,
        printers = {"us_letter": us_letter_printer, "label": label_printer}
    )
    config = _generate_config(config_vals)
    _schedule(config)


@svo_print.command()
def run():
    """Poll the SQS queue for jobs, and send them to the printer."""
    # Let's just allow a single process to be running at a time.
    LOGGER.debug("Starting attempts")
    try:
        attempts = 3
        s3 = _get_aws_session().resource("s3")
        while attempts > 0:
            _send_jobs_to_printer(s3)
            attempts -= 1
            LOGGER.info("Attempts left: {}".format(attempts))
    except Exception:
        LOGGER.exception("Error in run.")


if __name__ == "__main__":
    svo_print()
