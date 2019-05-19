# coding: utf-8

import boto3
ec2 = boto3.resource('ec2')
key_name = 'python_automation_key'
0key_path = key_name + '.pem'
key = ec2.create_key_pair(keyName=key_name)
   
with open(key_path,'w') as key_file:
    key_file.write(key.key_material)
    
ec2.images.filter(Owners=['amazon'])
list(ec2.images.filter(Owners=['amazon']))
img = ec2.Image('ami-0c6b1d09930fac512')
img
img.name
ami_name='amzn2-ami-hvm-2.0.20190508-x86_64-gp2'
filters = [{'Name': 'name','Values':[ami_name]}]

list(ec2.images.filter(Owners=['amazon'],Filters=filters))
instances = ec2.create_instances(ImageId=img.id, MinCount=1, MaxCount=1, InstanceType='t2.micro', KeyName=key.key_name)

inst.terminate()
inst.wait_until_running()
inst.reload()
inst.public_dns_name
inst.security_groups
sg = ec2.SecurityGroup(inst.security_groups[0]['GroupId'])

sg.authorize_ingress(IpPermissions=[{'FromPort': 22, 'ToPort': 22, 'IpProtocol': 'TCP', 'IpRanges':[{'CidrIp':'125.254.45.49/32'}]}])
sg.authorize_ingress(IpPermissions=[{'FromPort': 80, 'ToPort': 80, 'IpProtocol': 'TCP', 'IpRanges':[{'CidrIp':'0.0.0.0/0'}]}])

