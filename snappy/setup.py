from setuptools import setup

setup(
    name='snappy',
    version='0.1',
    author='Sukhsue',    
    description="Tool to manage ec2 instances list/stop/start",
    license="GPLv3+",    
    packages=['ec2action'],    
    install_requires=[
        'click',
        'boto3'
    ],    entry_points=['''
        [console_scripts]
        ec2action=ec2action.ec2action:cli
        '''
    ]
) 

