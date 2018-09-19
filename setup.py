from setuptools import setup, find_packages

install_requires = [
    'click',
    'boto3',
    "botocore",
    'python-crontab'
]

setup(
    name='svo-print',
    version='0.2',
    py_modules=['svo_print'],
    install_requires=install_requires,
    entry_points='''
    [console_scripts]
    svo-print=svo_print:svo_print
    ''',
    packages=find_packages(),
    python_requires='>=3.5',
)
