import boto3
import paramiko
import urllib.request
import time
import yaml

def main():
    # Read configuration from file
    with open('config.yaml') as file:
        config = yaml.safe_load(file)

    # Connect to EC2
    ec2 = boto3.client('ec2', region_name='us-east-1')

    # Create a new security group
    security_group = ec2.create_security_group(
        GroupName=config['EC2']['GroupName'],
        Description=config['EC2']['Description']
    )

    # Get public IP address
    my_ip = urllib.request.urlopen('http://checkip.amazonaws.com/').read().decode('utf-8').strip()

    # Authorize inbound traffic to security group from my IP address only
    ec2.authorize_security_group_ingress(
        GroupId=security_group['GroupId'],
        IpPermissions=[
            {
                'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{'CidrIp': my_ip + '/32'}]
            },
            {
                'IpProtocol': 'tcp',
                'FromPort': 443,
                'ToPort': 443,
                'IpRanges': [{'CidrIp': my_ip + '/32'}]
            },
            {
                'IpProtocol': 'tcp',
                'FromPort': 5000,
                'ToPort': 5000,
                'IpRanges': [{'CidrIp': my_ip + '/32'}]
            },
            {
                'IpProtocol': 'tcp',
                'FromPort': 5001,
                'ToPort': 5001,
                'IpRanges': [{'CidrIp': my_ip + '/32'}]
            }
        ]
    )

    # Launch EC2 instances
    instances = ec2.run_instances(
        ImageId=config['EC2']['ImageId'],
        InstanceType=config['EC2']['InstanceType'],
        KeyName=config['EC2']['KeyName'],
        MinCount=int(config['EC2']['MinCount']),
        MaxCount=int(config['EC2']['MaxCount']),
        SecurityGroupIds=[security_group['GroupId']],
        IamInstanceProfile={
        'Arn': 'arn:aws:iam::123456789012:role/your-iam-role-name'
        }
    )['Instances']

    # Add a name tag to each instance
    instance_ids = [instance['InstanceId'] for instance in instances]
    ec2.create_tags(
        Resources=instance_ids,
        Tags=[
            {'Key': 'Name', 'Value': config['Instance']['InstanceName']},
        ]
    )

    # Wait for the instances to be running
    for instance_id in instance_ids:
        status = ''
        while status != 'running':
            response = ec2.describe_instances(InstanceIds=[instance_id])
            status = response['Reservations'][0]['Instances'][0]['State']['Name']
            if status == 'running':
                break
            time.sleep(10)  # Wait for 10 seconds before checking again

    # Wait for the instances to have IP addresses
    statuses = {}
    while True:
        response = ec2.describe_instances(InstanceIds=instance_ids)
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                if 'PublicIpAddress' in instance:
                    statuses[instance_id] = instance['PublicIpAddress']
        if len(statuses) == 2:
            break
        time.sleep(5)

    time.sleep(10)

    # Connect to the instances via SSH
    ssh_clients = []
    for instance_id, instance_ip in statuses.items():
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
        for command in config['Commands'].values():
            stdin, stdout, stderr = ssh.exec_command(command)
            print(stdout.read().decode())
            print(stderr.read().decode())

    # Close SSH connections
    for _, ssh in ssh_clients:
        ssh.close()

# Create a Boto3 IAM client
iam_client = boto3.client('iam')

# Define the role name and trust policy
role_name = 'YourRoleName'
trust_policy = {
    'Version': '2012-10-17',
    'Statement': [{
        'Effect': 'Allow',
        'Principal': {
            'Service': 'ec2.amazonaws.com'
        },
        'Action': 'sts:AssumeRole'
    }]
}

# Create the IAM role
response = iam_client.create_role(
    RoleName=role_name,
    AssumeRolePolicyDocument=json.dumps(trust_policy)
)

# Print the ARN of the created role
print(f"Created IAM role ARN: {response['Role']['Arn']}")


if __name__ == '__main__':
    main()
