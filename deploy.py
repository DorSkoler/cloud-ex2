import boto3
import paramiko
import urllib.request
import time
import yaml
import json
import requests
import os;

# Read configuration from file
with open('config.yaml') as file:
    config = yaml.safe_load(file)
    
iam_client = boto3.client('iam', region_name='us-east-1')
ec2_client = boto3.client('ec2', region_name='us-east-1')

def open_iam_role_to_ec2(role_name):
    """
    Opens the specified IAM role to EC2, allowing the creation and termination of EC2 instances.

    Args:
        role_name (str): The name of the IAM role.

    Returns:
        str: The ARN of the IAM role's instance profile.
    """
    instance_profile_name = role_name + "-InstanceProfile"
    try:
        role = iam_client.get_role(RoleName=role_name)
        instance_profile_arn = role['Role']['Arn']
        print(f'Role exists - ARN: {instance_profile_arn}')
        existing_profile = iam_client.get_instance_profile(InstanceProfileName=instance_profile_name)
        instance_profile_arn = existing_profile['InstanceProfile']['Arn']
        print(f'Instance profile exists - ARN: {instance_profile_arn}')
        return instance_profile_name
    except iam_client.exceptions.NoSuchEntityException:
        pass
    
    # Create the IAM role
    role = iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }]
        })
    )

    # Create the policy to allow EC2 actions
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "ec2:RunInstances",
                "ec2:TerminateInstances"
            ],
            "Resource": "*"
        }]
    }

    # Attach the policy to the IAM role
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName='default',
        PolicyDocument=json.dumps(policy)
    )

    # Attach the role to an instance profile
    
    iam_client.create_instance_profile(InstanceProfileName=instance_profile_name)
    iam_client.add_role_to_instance_profile(
        InstanceProfileName=instance_profile_name,
        RoleName=role_name
    )

    # Wait for the instance profile to propagate
    waiter = iam_client.get_waiter('instance_profile_exists')
    waiter.wait(InstanceProfileName=instance_profile_name)

    # Retrieve the IAM role's instance profile ARN
    role = iam_client.get_role(RoleName=role_name)
    instance_profile_arn = role['Role']['Arn']
    print(f'Role created - ARN: {instance_profile_arn}')

    return instance_profile_name

def create_ec2_instance(iam_role, security_group_id, instance_name):
    """
    Creates an EC2 instance with the specified IAM role, security group ID, instance type,
    image ID, key name, and instance name.

    Args:
        iam_role (str): The name or ARN of the IAM role.
        security_group_id (str): The ID of the security group.
        instance_type (str): The type of the EC2 instance (e.g., 't2.micro').
        image_id (str): The ID of the AMI (Amazon Machine Image).
        key_name (str): The name of the key pair.
        instance_name (str): The name to assign to the EC2 instance.

    Returns:
        tuple: A tuple containing the IP address and instance ID of the newly created EC2 instance.
    """

    # Create the EC2 instance
    response = ec2_client.run_instances(
        ImageId=config['EC2']['ImageId'],
        InstanceType=config['EC2']['InstanceType'],
        MinCount=1,
        MaxCount=1,
        KeyName=config['EC2']['KeyName'],
        SecurityGroupIds=[security_group_id],
        # IamInstanceProfile={
        #     'Arn': iam_role
        # },
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': instance_name
                    },
                ]
            },
        ]
    )

    instance_id = response['Instances'][0]['InstanceId']
    # Wait for the instance to have an IP address
    while True:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        if 'PublicIpAddress' in instance:
            break
        time.sleep(5)

    public_ip = instance['PublicIpAddress']
    print(f'ec2 created - {instance_id},  {public_ip}')
    
    waiter = ec2_client.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])
    
    response = ec2_client.associate_iam_instance_profile(
        IamInstanceProfile={
            'Name': iam_role
        },
        InstanceId=instance_id
    )

    return public_ip, instance_id

def create_security_group_id():
    # Check if the security group already exists
    try:
        existing_group = ec2_client.describe_security_groups(
            Filters=[
                {
                    'Name': 'group-name',
                    'Values': [config['EC2']['GroupName']]
                }
            ]
        )
        if existing_group['SecurityGroups']:
            print(f'SecurityGroups exists - {existing_group["SecurityGroups"][0]["GroupId"]}')
            return existing_group['SecurityGroups'][0]['GroupId']
    except ec2_client.exceptions.ClientError:
        # Error occurred while describing security groups, assuming it doesn't exist
        pass
    
    # Create a new security group
    security_group = ec2_client.create_security_group(
        GroupName=config['EC2']['GroupName'],
        Description=config['EC2']['Description']
    )

    # Get public IP address
    my_ip = urllib.request.urlopen('http://checkip.amazonaws.com/').read().decode('utf-8').strip()

    # Authorize inbound traffic to security group from my IP address only
    ec2_client.authorize_security_group_ingress(
        GroupId=security_group['GroupId'],
        IpPermissions=[
            {
                'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            },
            {
                'IpProtocol': 'tcp',
                'FromPort': 443,
                'ToPort': 443,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            },
            {
                'IpProtocol': 'tcp',
                'FromPort': 5000,
                'ToPort': 5000,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            }
        ]
    )
    print(f'SecurityGroups created - {security_group["GroupId"]}')
    return security_group['GroupId']
    
def notify_new_instance(statuses):
    # Create an array with the original order
    array1 = [('ip', 'http://' + ip + ':5000') for ip in statuses.values()]
    
    # Create a list of URLs with the opposite order
    array2 = [('ip', 'http://' + ip + ':5000') for ip in reversed(statuses.values())]
    
    def http_post(url, data):
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()  # Raise an exception for non-2xx status codes
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None
    print(http_post(array1[0][1] + '/ip', json.dumps(array1)))
    print(http_post(array2[0][1] + '/ip', json.dumps(array2)))

def create_key_pair(KeyName):
    # Check if the key pair already exists
    try:
        existing_key_pairs = ec2_client.describe_key_pairs(
            KeyNames=[KeyName]
        )
        if existing_key_pairs['KeyPairs']:
            print(f"Key pair '{KeyName}' already exists.")
            return
    except ec2_client.exceptions.ClientError:
        # Error occurred while describing key pairs, assuming it doesn't exist
        pass
    # Create a new key pair
    key_pair = ec2_client.create_key_pair(KeyName=KeyName)

    # Save the private key to a file
    with open(f'{KeyName}.pem', 'w') as file:
        file.write(key_pair['KeyMaterial'])
        
    os.chmod(f'{KeyName}.pem', 0o400)
        
    print(f"Key pair '{KeyName}' created and saved to '{KeyName}.pem'.")
    
def ssh_and_run_code(statuses):
    # Connect to the instances via SSH
    ssh_clients = []
    for instance_id, instance_ip in statuses.items():
        print(f"Connecting to instance {instance_id} at {instance_ip}...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
       
        ssh.connect(
            hostname=instance_ip,
            username='ubuntu',
            key_filename=config['EC2']['KeyName'] + '.pem'
        )
        ssh_clients.append((instance_id, ssh))

    # Execute commands on instances using SSH
    for instance_id, ssh in ssh_clients:
        print(f"Executing commands on instance {instance_id}...")
        for command in config['Commands']:
            print(f"Executing command: {command}")
            stdin, stdout, stderr = ssh.exec_command(command)
            print(stdout.read().decode())
            print(stderr.read().decode())

    # Close SSH connections
    for instance_id, ssh in ssh_clients:
        print(f"Closing SSH connection to instance {instance_id}...")
        ssh.close()

def main():

    # Create a new security group
    security_group_id = create_security_group_id()
    
    # Create IAM role
    instance_profile_name = open_iam_role_to_ec2(config['EC2']['RoleName'])
    
    # Create key pair
    create_key_pair(config['EC2']['KeyName'])
    
    # Launch EC2 instances
    statuses = {}
    public_ip, instance_id = create_ec2_instance(instance_profile_name, security_group_id, 'node1')
    statuses[instance_id] = public_ip
    public_ip, instance_id = create_ec2_instance(instance_profile_name, security_group_id, 'node2')
    statuses[instance_id] = public_ip
    
    time.sleep(10)
    ssh_and_run_code(statuses)
    time.sleep(5)
    notify_new_instance(statuses)
    
    array1 = ['http://' + ip + ':5000' for ip in statuses.values()]
    for index, node in enumerate(array1):
        print(f'node {index} - {node}')

if __name__ == '__main__':
    main()
