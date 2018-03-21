from setuptools import setup, find_packages

install_requires = [
    'click',
    'boto3',
    "botocore",
    'python-crontab'
]

data_files = ['logging.json']


setup(
    name='svo-print',
    version='0.1',
    py_modules=['svo_print'],
    install_requires=install_requires,
    data_files=data_files,
    entry_points='''
    [console_scripts]
    svo-print=svo_print:svo_print
    ''',
    packages=find_packages(),
    python_requires='>=3.5',
)
