import getpass
import json
import logging.config
import os
import configparser
import tempfile
import subprocess

import boto3
import click
from crontab import CronTab

# TODO: Typically, a lot of this code would be split out into several modules,
# but I'm not sure how that will work with Pyinstaller.
# Try it out so this code is more maintainable.

APP_NAME = "svo-print"
AWS_CONFIG_SECTION = 'AWS'
PRINTER_CONFIG_SECTION = 'PRINTER'

CONFIG_FILE = os.path.join(click.get_app_dir(APP_NAME), 'config.ini')

CLI_WARN = 'yellow'
CLI_ERROR = 'red'
CLI_SUCCESS = 'green'
CLI_INFO = 'blue'


def setup_logging(default_path='logging.json', default_level=logging.INFO, env_key='LOG_CFG'):
    path = os.getenv(env_key, default_path)
    try:
        with open(path, 'r') as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    except FileNotFoundError:
        logging.basicConfig(level=default_level)


def _get_config():
    if not os.path.exists(click.get_app_dir(APP_NAME)):
        os.makedirs(click.get_app_dir(APP_NAME), exist_ok=True)
    parser = configparser.ConfigParser()
    parser.read(CONFIG_FILE)

    if not parser.has_section(AWS_CONFIG_SECTION):
        parser.add_section(AWS_CONFIG_SECTION)
    if not parser.has_section(PRINTER_CONFIG_SECTION):
        parser.add_section(PRINTER_CONFIG_SECTION)
    return parser


# doing this so the click options can have some defaults if the wizard is run again, or the config file is
# otherwise present when a user tries to run this.
CONFIG = _get_config()


def _get_aws_session():
    logging.debug("Getting s3 session")
    session = boto3.Session(
        aws_access_key_id=CONFIG[AWS_CONFIG_SECTION]['access_key'],
        aws_secret_access_key=CONFIG[AWS_CONFIG_SECTION]['secret_access_key'],
        region_name=CONFIG[AWS_CONFIG_SECTION]['region']
    )
    return session


def _get_available_printers():
    logging.debug("Searching for printers")
    lpstat = subprocess.Popen(['lpstat', '-a'], stdout=subprocess.PIPE)
    printers = subprocess.check_output(['cut', '-f1', '-d',  ' '], stdin=lpstat.stdout).split()
    lpstat.wait()
    printers = [str(printer, 'utf-8') for printer in printers]
    logging.debug("Found {} printers".format(",".join(printers)))
    return printers


def _generate_config(val_dict):
    cfg = configparser.ConfigParser()

    cfg[AWS_CONFIG_SECTION] = {
        'access_key': val_dict['access_key'],
        'secret_access_key': val_dict['secret_access_key'],
        'region': val_dict['region'],
        'queue_name': val_dict['store_id'],
    }
    cfg[PRINTER_CONFIG_SECTION] = {
        'executable': val_dict['executable_path'],
        'cmd': 'svo-print run',
        'printer_name': val_dict['printer_name'],
    }

    with open(CONFIG_FILE, 'w') as config_file:
        cfg.write(config_file)
    return cfg


def _schedule(config):
    """
    Setups up a cron job to make sure the print job process is running. Run this every minute
    on workdays between 8am and 5pm
    """
    crontab = CronTab(user=getpass.getuser())
    cmd = "{}/{}".format(config[PRINTER_CONFIG_SECTION]['executable'], config[PRINTER_CONFIG_SECTION]['cmd'])
    try:
        job = next(crontab.find_comment('print-job'))
        logging.info('Cron exists. Updating.')
        job.command = cmd
    except StopIteration:
        logging.info('Adding new cron job.')
        crontab.new(comment='print-job', command=cmd)
        job = next(crontab.find_comment('print-job'))
    job.setall('* 8-17 * * 1-5')
    crontab.write()


def _print_file(file_to_print):
    """ Send the job to the printer. This assumes Mac or Unix like system where lpr exists."""
    subprocess.check_call([
        'lpr',
        '-P', CONFIG[PRINTER_CONFIG_SECTION]['printer_name'],
        '-o', 'fit-to-page',
        file_to_print])


def _jobs():
    session = _get_aws_session()
    sqs = session.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName=CONFIG[AWS_CONFIG_SECTION]['queue_name'])
    for message in queue.receive_messages(WaitTimeSeconds=19):
        try:
            records = json.loads(message.body)['Records']
            for record in records:
                s3_record = dict(
                    key=record['s3']['object']['key'],
                    bucket=record['s3']['bucket']['name']
                )
                yield s3_record
        except Exception:
            logging.exception("Error occured trying to print {}".format(message.body), exc_info=True)
        else:
            message.delete()


def _send_jobs_to_printer(s3):
    """ Loops through the queue messages, and attempts to download the pdf object, and send it to the printer. """
    for job in _jobs():
        file_to_print = os.path.join(tempfile.gettempdir(), os.path.basename(job['key']))
        logging.debug("Fetching {} from s3".format(file_to_print))
        s3.Bucket(job['bucket']).download_file(job['key'], file_to_print)
        logging.debug("Printing {}".format(file_to_print))
        _print_file(file_to_print)


@click.group()
def svo_print():
    """Commands to send SVO print requests to the network printer"""


@svo_print.command()
@click.option('--access-key', help='AWS access key', required=True, prompt=True,
              default=CONFIG[AWS_CONFIG_SECTION].get('access_key', ''))
@click.option('--secret-access-key', help='AWS Secret access key', required=True, prompt=True,
              default=CONFIG[AWS_CONFIG_SECTION].get('secret_access_key', ''))
@click.option('--region', help="AWS region", default=CONFIG[AWS_CONFIG_SECTION].get('region', 'us-east-1'), prompt=True)
@click.option('--store-id', help='Id of your store', required=True, prompt=True,
              default=CONFIG[AWS_CONFIG_SECTION].get('queue_name', ''))
@click.option('--printer-name', help='Name of your network printer', required=True, prompt=True,
              default=CONFIG[PRINTER_CONFIG_SECTION].get('printer_name', _get_available_printers()[0]),
              type=click.Choice(_get_available_printers()))
@click.option('--executable-path', help='Path to where you unzipped this program', required=True, prompt=True,
              type=click.Path(exists=True, dir_okay=True, file_okay=False),
              default=CONFIG[PRINTER_CONFIG_SECTION].get('executable', os.getcwd()))
def setup(access_key, secret_access_key, region, store_id, printer_name, executable_path):
    """
    Setup the printing application. You may pass in the variables from the commandline directly, or
    omit them, and enter them via the wizard prompt.
    """
    config_vals = dict(
        access_key=access_key,
        secret_access_key=secret_access_key,
        region=region,
        store_id=store_id,
        printer_name=printer_name,
        executable_path=executable_path,
    )
    config = _generate_config(config_vals)
    _schedule(config)


@svo_print.command()
def run():
    """Poll the SQS queue for jobs, and send them to the printer."""
    # Let's just allow a single process to be running at a time.
    attempts = 3
    s3 = _get_aws_session().resource('s3')
    while attempts > 0:
        _send_jobs_to_printer(s3)
        attempts -= 1


if __name__ == '__main__':
    setup_logging(default_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logging.json'))
    svo_print()
