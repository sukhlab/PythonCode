import boto3
import click

s3=boto3.resource('s3')

@click.group()
def cli():
    "webotran deploys website to aws"
    pass

@cli.command('list-buckets')
def list_buckets():
    "List all s3 buckets"
    for buckets in s3.buckets.all():
        print (buckets)

@cli.command('list-buckets-objects')
@click.argument('bucket')
def list_buckets_objects(bucket):
    "List all s3 buckets objects"
    for obj in s3.Bucket(bucket).objects.all():
        print(obj)

if __name__ == "__main__":
    cli()
    