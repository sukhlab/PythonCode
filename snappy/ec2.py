import boto3
import botocore
import click

ec2 = boto3.resource('ec2')

def filter_instances(project):
    instances = []
    if project:
        filters = [{'Name':'tag:Project','Values': [project] }]
        instances = ec2.instances.filter(Filters=filters)
    else:
        instances = ec2.instances.all()        
    return instances

@click.group()
def instances():
     """Command for instances"""

@instances.command('list')
@click.option('--project', default=None, help="Ec2 instances for project")
def list_instances(project):
    "List Ec2 Instances"
        
    instances = filter_instances(project)
    for i in instances:
    
            tags = { t['Key']: t['Value'] for t in i.tags or [] }
            print(','.join((
                i.id,
                i.instance_type,
                i.state['Name'],
                tags.get('Project','<no project>')
            )))
    return

@instances.command('stop')
@click.option('--project', default=None, help="Ec2 instances for project")
def stop_instances(project):
    "Stop Ec2 Instances"
        
    instances = filter_instances(project)
    for i in instances:
        print('stopping instance {0}..'.format(i.id))
        i.stop()
            
    return

@instances.command('start')
@click.option('--project', default=None, help="Ec2 instances for project")
def start_instances(project):
    "Start Ec2 Instances"
        
    instances = filter_instances(project)
    for i in instances:
        print('starting instance {0}..'.format(i.id))
        i.start()
            
    return

if __name__ == "__main__":
    instances()

