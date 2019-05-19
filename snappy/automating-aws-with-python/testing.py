import boto3 
from botocore.exceptions import ClientError 

rds_client = boto3.client('rds')
HTTP_OK = 200 

def get_all_db_instances(): 
    db_api_response = [] 
    pagination_marker = "" 
    print("get_db_instances ") 
 
    # There's no Do While in Python, this is the alternative. 
    while True: 
        response = get_db_instances(pagination_marker) 
 
        if response['ResponseMetadata']['HTTPStatusCode'] == HTTP_OK and any(response['DBInstances']): 
 
            db_api_response += response['DBInstances'] 
 
            if 'Marker' in response.keys(): 
                pagination_marker = response['Marker'] 
            else: 
                print("No Pagination Marker, we have all DB Instances. Items found: " + str(len(db_api_response))) 
                break 
        else: 
            print("Exiting HTTP CODE: " + str(response['ResponseMetadata']['HTTPStatusCode']) + 
                  " DBInstances count: " + str(len(response['DBInstances']))) 
            break 
 
    # Prepare a collection of DbInstance objects. 
    all_db_instances = [] 
 
    for db in db_api_response: 
        tag_list = get_db_tags(db['DBInstanceArn']) 
 
        db_instance = DbInstance(db['DBInstanceIdentifier'], db['Engine'], db['AllocatedStorage'], tag_list) 
 
        all_db_instances.append(db_instance) 
 
    return all_db_instances 


def get_db_tags(db_arn): 
    tag_list = [] 
    response = rds_client.list_tags_for_resource(ResourceName=db_arn) 
 
    if response['ResponseMetadata']['HTTPStatusCode'] == HTTP_OK: 
        tag_list = response['TagList'] 
 
    return tag_list 

def get_db_instances(marker=""): 
    
    response = rds_client.describe_db_instances(Marker=marker) 
    response_marker = "" 
 
    if 'Marker' in response.keys(): 
        response_marker = response['Marker'] 
 
    if response['ResponseMetadata']['HTTPStatusCode'] == HTTP_OK: 
        print("describe_db_instances returned HTTP_OK 200. Marker: " + response_marker) 
 
    return response 

# DBInstance class, this lets us only store the information we need about each instance. 
class DbInstance: 
 
    def __init__(self, instance_identifier, engine, allocated_storage, tag_list): 
 
        # convert it all to lowercase strings. 
        self.instance_identifier = str(instance_identifier).lower() 
        self.engine = str(engine).lower() 
        self.allocated_storage = str(allocated_storage).lower() 
        # default to Dev in case we cant get this from Tags. 
        self.environment = "dev" 
        self.translate_tags(tag_list) 
 
        print("-- Initialised DbInstance object, identifier: {0}, environment: {1}, engine: {2}, allocated_storage: {3}" 
              .format(self.instance_identifier, self.environment, self.engine, self.allocated_storage, )) 
 
        self.alarms = [] 
 
    def translate_tags(self, tag_list): 
 
        # check list is not empty: 
        if any(tag_list): 
            for tag in tag_list: 
                if tag['Key'] == 'Environment': 
                    # print("Environment tag exists with value: " + tag['Value']) 
                    self.environment = tag["Value"] 
                    self.environment = self.environment.lower() 
        else: 
            print("### Did not find Environment Tag, default is dev ### ") 
 
if __name__ == "__main__":
     get_all_db_instances()