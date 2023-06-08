import json
import requests
import time
from app import ec2_client, config, workers

def http_get(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        return json.loads(response.text)
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

def http_post(url, data):
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

def launch_ec2_instance():
    response = ec2_client.run_instances(
        ImageId=config['EC2']['ImageId'],
        InstanceType=config['EC2']['InstanceType'],
        KeyName=config['EC2']['KeyName'],
        SecurityGroupIds=config['EC2']['GroupName'],
        MinCount=1,
        MaxCount=1
    )
    instance_id = response['Instances'][0]['InstanceId']

    # Wait for the instance to have an IP address
    while True:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        if 'PublicIpAddress' in instance:
            workers[instance_id] = instance.PublicIpAddress
            break
        time.sleep(5)
    url = f'http://{workers[instance_id]}:443/instanceId'
    url2 = f'http://{workers[instance_id]}:443/newNode'
    http_post(url, instance_id)
    http_post(url2, nodes)
    print(f"Launched EC2 instance: {instance_id}")
    return

def terminate_ec2_instance(instance_id):
    response = ec2_client.terminate_instances(InstanceIds=[instance_id])
    del workers[instance_id]
    print(f"Terminating EC2 instance: {instance_id}")
    return response

def get_completed_work(n):
    if len(completed_work) >= n:
        # Get n items from completed_work
        work_items = []
        for i in range(n):
            work_id, output = completed_work.popitem()
            work_items.append({'work_id': work_id, 'output': output})
        return work_items
    elif len(completed_work) > 0:
        # Get all remaining items from completed_work
        work_items = []
        while len(completed_work) > 0:
            work_id, output = completed_work.popitem()
            work_items.append({'work_id': work_id, 'output': output})
        return work_items
    else:
        # Ask the second node for the items
        response = requests.get('http://second_node_address/getCompleted', params={'top': n})
        if response.status_code == 200:
            data = response.json()
            return data['work_items']
        else:
            return []
