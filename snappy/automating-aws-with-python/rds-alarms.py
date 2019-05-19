import boto3 
from botocore.exceptions import ClientError 
 
HTTP_OK = 200 
 
# Engine Types: 
AURORA = "aurora" 
 
 
def lambda_handler(event, context): 
    if not validate_input(event): 
        raise Exception("Invalid Json Input from CloudWatch. Exiting") 
 
    role_name = event['roleName'] 
    sns_name = event['snsName'] 
 
    for account_id in event['accounts']: 
 
        credentials = get_credentials(account_id, role_name) 
 
        for region in event['regions']: 
 
            print("getting db_instances for: " + region + " account: " + account_id) 
 
            alarm_tools = AwsAlarmTools(event['alarmConfig'], credentials, region) 
 
            sns_arn = "arn:aws:sns:{0}:{1}:{2}".format(region, account_id, sns_name) 
 
            db_instances = get_all_db_instances(credentials, region) 
 
            if any(db_instances): 
 
                print("I have {0} db_instances to process for: {1} account: {2}" 
                      .format(len(db_instances), region, account_id)) 
 
                for db_instance in db_instances: 
 
                    # calculate the alarm configs needed for this DB Instance. 
                    db_instance.alarm_configs = alarm_tools.get_all_rds_alarm_configs(db_instance, sns_arn) 
 
                    # create the required alarms. 
                    for alarm in db_instance.alarm_configs: 
                        alarm_tools.create_alarm(alarm, namespace='AWS/RDS') 
 
            else: 
                print("No db_instances to process for: " + region + " account: " + account_id) 
 
 
def validate_input(event): 
    # We should build this out. 
 
    result = False 
 
    if event is None: 
        print("Event object is null") 
    elif event['roleName'] is None: 
        print("roleName is null") 
    elif event['accounts'] is None: 
        print("Accounts is null") 
    elif event['regions'] is None: 
        print("Regions is null") 
    else: 
        result = True 
 
    return result 
 
 
def get_credentials(account_id, role_name): 
    print("AccountId: " + account_id + " RoleName: " + role_name) 
 
    sts = boto3.client('sts') 
    role_arn = "arn:aws:iam::" + account_id + ":role/" + role_name 
    response = sts.assume_role(RoleArn=role_arn, 
                               RoleSessionName=role_name) 
 
    if response['ResponseMetadata']['HTTPStatusCode'] == HTTP_OK: 
        print("Assumed Credentials for " + role_name + "successfully") 
        credentials = response['Credentials'] 
 
    if credentials is None or credentials['AccessKeyId'] is None: 
        raise Exception("STS gave an invalid response for assume role ARN: " + role_arn) 
 
    return credentials 
 
 
def get_rds_client(credentials, region): 
    return boto3.client('rds', aws_access_key_id=credentials['AccessKeyId'], 
                        aws_secret_access_key=credentials['SecretAccessKey'], 
                        aws_session_token=credentials['SessionToken'], 
                        region_name=region) 
 
 
# Max number of RDS instances returned by AWS API is 100. If more exists, the response will include a Marker. 
# Keep feeding the Marker to the API until it returns no Marker. At this point we have all RDS instances. 
def get_all_db_instances(credentials, region): 
    db_api_response = [] 
    pagination_marker = "" 
    print("get_db_instances for region: " + region) 
 
    # There's no Do While in Python, this is the alternative. 
    while True: 
        response = get_db_instances(credentials, region, pagination_marker) 
 
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
        tag_list = get_db_tags(credentials, region, db['DBInstanceArn']) 
 
        db_instance = DbInstance(db['DBInstanceIdentifier'], db['Engine'], db['AllocatedStorage'], tag_list) 
 
        all_db_instances.append(db_instance) 
 
    return all_db_instances 
 
 
def get_db_instances(credentials, region, marker=""): 
    rds_client = get_rds_client(credentials, region) 
    response = rds_client.describe_db_instances(Marker=marker) 
    response_marker = "" 
 
    if 'Marker' in response.keys(): 
        response_marker = response['Marker'] 
 
    if response['ResponseMetadata']['HTTPStatusCode'] == HTTP_OK: 
        print("describe_db_instances returned HTTP_OK 200. Marker: " + response_marker) 
 
    return response 
 
 
def get_db_tags(credentials, region, db_arn): 
    tag_list = [] 
 
    rds_client = get_rds_client(credentials, region) 
 
    response = rds_client.list_tags_for_resource(ResourceName=db_arn) 
 
    if response['ResponseMetadata']['HTTPStatusCode'] == HTTP_OK: 
        tag_list = response['TagList'] 
 
    return tag_list 
 
 
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
 
 
class AwsAlarmTools: 
 
    def __init__(self, all_alarms_config, credentials, region): 
        self.all_alarms_config = all_alarms_config 
        self.client = boto3.client('cloudwatch', aws_access_key_id=credentials['AccessKeyId'], 
                                   aws_secret_access_key=credentials['SecretAccessKey'], 
                                   aws_session_token=credentials['SessionToken'], 
                                   region_name=region) 
 
    # Given a config, creates the alarm if it doesn't exist. If it does, updates the existing alarm with new values. 
    def create_alarm(self, config, namespace): 
 
        try: 
            exists_response = self.alarm_exists(config.name) 
 
            if "MetricAlarms" in exists_response.keys() and any(exists_response['MetricAlarms']): 
                print("- Found existing alarm. Updating settings") 
            else: 
                print("No existing alarm found.") 
                print("- Creating new alarm. Metric: {0}, Threshold: {1}, EvalPeriod: {2}" 
                      .format(config.metric_name, config.threshold, config.evaluation_period)) 
 
            response = self.client.put_metric_alarm( 
                AlarmName=config.name, 
                ComparisonOperator=config.comparison_operator, 
                DatapointsToAlarm=config.datapoints_to_alarm, 
                EvaluationPeriods=config.evaluation_period, 
                MetricName=config.metric_name, 
                Namespace=namespace, 
                Period=config.period, 
                Statistic='Average', 
                Threshold=config.threshold, 
                ActionsEnabled=True, 
                AlarmActions=config.alarm_action, 
                AlarmDescription=config.description, 
                Dimensions=config.dimensions, 
                Unit=config.unit 
            ) 
 
            if response['ResponseMetadata']['HTTPStatusCode'] != HTTP_OK: 
                print( 
                    "Unexpected response in alarm_exists HTTP CODE: " + response['ResponseMetadata']['HTTPStatusCode']) 
            else: 
                print("-- Done Alarm {0} HTTP-OK".format(config.name)) 
 
        except ClientError as e: 
            print("Unexpected client error create_alarm: failed to create: {0} error: {1}" 
                  .format(config.name, e.response)) 
 
    def alarm_exists(self, alarm_name): 
 
        print("checking if alarm exists " + alarm_name) 
 
        # see if we can find an existing alarm. 
        response = self.client.describe_alarms(AlarmNames=[alarm_name]) 
 
        if response['ResponseMetadata']['HTTPStatusCode'] != HTTP_OK: 
            print("Unexpected response in alarm_exists HTTP CODE: " + response['ResponseMetadata']['HTTPStatusCode']) 
 
        return response 
 
    # Given a db instance, get the relevant alarm configs this db instance will need. 
    def get_all_rds_alarm_configs(self, db_instance, sns_arn): 
 
        alarms = [] 
        environment = db_instance.environment 
        identifier = db_instance.instance_identifier 
        allocated_storage = db_instance.allocated_storage 
 
        alarms.append(self.get_alarm_config("rds-cpu", identifier, environment, allocated_storage, sns_arn)) 
 
        # Aurora is a special case, we only need CPU alarms. 
        if AURORA in db_instance.engine: 
            return alarms 
 
        alarms.append(self.get_alarm_config("rds-storage", identifier, environment, allocated_storage, sns_arn)) 
 
        alarms.append(self.get_alarm_config("rds-queuelength", identifier, environment, allocated_storage, sns_arn)) 
 
        return alarms 
 
    # Simple factory: Gets the required config and handles any shared properties like Description and Dimension. 
    # Logic for calculating each type of alarm is handled in separate functions. 
    # I've separated this in-case we need to extend to more use cases. 
    def get_alarm_config(self, alarm_type, instance_identifier, environment, allocated_storage, sns_arn): 
 
        config = "" 
        if alarm_type == 'rds-cpu': 
            config = self.get_cpu_alarm_config(environment, instance_identifier) 
        elif alarm_type == 'rds-storage': 
            config = self.get_storage_alarm_config(environment, instance_identifier, allocated_storage) 
        elif alarm_type == 'rds-queuelength': 
            config = self.get_queue_length_alarm_config(environment, instance_identifier, allocated_storage) 
        else: 
            raise ValueError(alarm_type) 
 
        config.dimensions = [ 
            { 
                'Name': 'DBInstanceIdentifier', 
                'Value': config.instance_identifier 
            }, 
        ] 
 
        # Default period is 5 min. 
        config.period = 300 
 
        config.alarm_action = [ 
            sns_arn, 
        ] 
 
        config.description = "{0} {1} {2} for {3} DataPoints".format(config.metric_name, config.comparison_operator, 
                                                                     config.threshold_desc, config.datapoints_to_alarm) 
 
        # We need to guarantee Int's for these values 
        try: 
            config.threshold = int(config.threshold) 
            config.evaluation_period = int(config.evaluation_period) 
            config.datapoints_to_alarm = int(config.datapoints_to_alarm) 
        except ValueError: 
            print( 
                "Invalid value for threshold: {0} or evaluation_period: {1} or datapoints_to_alarm{3}. DBInstance: {2}".format( 
                    config.treshold, 
                    config.evaluation_period, 
                    config.instance_identifier), 
                config.datapoints_to_alarm) 
 
            return 
 
        return config 
 
    def get_cpu_alarm_config(self, environment, instance_identifier): 
 
        if environment == "live" or environment == "liveb": 
            config = Alarm(self.all_alarms_config['liveCpuAlarm']) 
        else: 
            config = Alarm(self.all_alarms_config['testCpuAlarm']) 
 
        config.instance_identifier = instance_identifier 
        config.name = "aws-rds-" + instance_identifier + "-High-CPU-Utilization" 
        config.metric_name = "CPUUtilization" 
        config.threshold_desc = str(config.threshold) + "%" 
        config.unit = "Percent" 
 
        return config 
 
    def get_storage_alarm_config(self, environment, instance_identifier, allocated_storage): 
 
        if environment == "live" or environment == "liveb": 
            config = Alarm(self.all_alarms_config['liveStorageAlarm']) 
        else: 
            config = Alarm(self.all_alarms_config['testStorageAlarm']) 
 
        config.instance_identifier = instance_identifier 
        config.name = "aws-rds-" + instance_identifier + "-Low-FreeStorageSpace" 
        config.metric_name = "FreeStorageSpace" 
 
        # We want to alarm when the storage reaches (threshold * allocated storage) 
        # Allocated storage is in GB 
        config.threshold = int(allocated_storage) * (int(config.threshold) / 100) 
 
        # Create a sensible treshold description for the alarm so we dont show a million bytes. 
        config.threshold_desc = str(config.threshold) + "GB" 
 
        # Convert to Bytes, CloudWatch needs this in Bytes. 
        config.threshold = config.threshold * 1073741824 
        config.unit = "Bytes" 
 
        return config 
 
    def get_queue_length_alarm_config(self, environment, instance_identifier, allocated_storage): 
 
        if environment == "live" or environment == "liveb": 
            config = Alarm(self.all_alarms_config['liveQueueLengthAlarm']) 
        else: 
            config = Alarm(self.all_alarms_config['testQueueLengthAlarm']) 
 
        config.instance_identifier = instance_identifier 
        config.name = "aws-rds-" + instance_identifier + "-High-DiskQueueDepth" 
        config.metric_name = "DiskQueueDepth" 
 
        allocated_storage = int(allocated_storage) 
 
        # queue length treshold = ((3*storage) * (ql_percentage)) 
        ql_percentage = 0.1 
        if allocated_storage >= 1000: 
            ql_percentage = 0.05 
 
        config.threshold = (ql_percentage * (3 * allocated_storage)) 
        config.threshold_desc = str(config.threshold) + " Count" 
        config.unit = "Count" 
 
        return config 
 
 
# Used to de-serialise the data from the alarmConfig json into an object we can work with. 
class Alarm(object): 
 
    def __init__(self, config): 
        for key in config: 
            setattr(self, key, config[key]) 
 
 
# USED FOR TESTING LOCALLY 
if __name__ == "__main__": 
    AWS_PROFILE = "kg-training-default" 
    AWS_REGION = 'ap-southeast-2' 
    boto3.setup_default_session(profile_name=AWS_PROFILE, region_name=AWS_REGION) 
 
    event = { 
        "roleName": "AWS-RdsAlarmAutomation", 
        "snsName": "cloud-infrastructure-critical-rds", 
        "accounts": [ 
            "055479987233" 
        ], 
        "regions": [ 
            "ap-southeast-2" 
        ], 
        "alarmConfig": { 
            "liveCpuAlarm": { 
                "threshold": "85", 
                "comparison_operator": "GreaterThanThreshold", 
                "datapoints_to_alarm": "2", 
                "evaluation_period": "3" 
            }, 
            "testCpuAlarm": { 
                "threshold": "90", 
                "comparison_operator": "GreaterThanThreshold", 
                "datapoints_to_alarm": "3", 
                "evaluation_period": "5" 
            }, 
            "liveStorageAlarm": { 
                "threshold": "20", 
                "comparison_operator": "LessThanOrEqualToThreshold", 
                "datapoints_to_alarm": "1", 
                "evaluation_period": "1" 
            }, 
            "testStorageAlarm": { 
                "threshold": "10", 
                "comparison_operator": "LessThanOrEqualToThreshold", 
                "datapoints_to_alarm": "1", 
                "evaluation_period": "1" 
            }, 
            "liveQueueLengthAlarm": { 
                "comparison_operator": "GreaterThanOrEqualToThreshold", 
                "datapoints_to_alarm": "2", 
                "evaluation_period": "3" 
            }, 
            "testQueueLengthAlarm": { 
                "comparison_operator": "GreaterThanOrEqualToThreshold", 
                "datapoints_to_alarm": "3", 
                "evaluation_period": "5" 
            } 
        } 
    } 
 
    context = [] 
    lambda_handler(event, context) 