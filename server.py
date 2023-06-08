from flask import Flask, request, jsonify
import uuid
import boto3
import yaml
import requests

# Read configuration from file
with open('config.yaml') as file:
    config = yaml.safe_load(file)

app = Flask(__name__)

# In-memory queue to store the submitted work items
queue = []

# Dictionary to store the completed work items
completed_work = {}

# Endpoint for submitting work
@app.route('/enqueue', methods=['PUT'])
def enqueue_work():
    buffer = request.data
    iterations = int(request.args.get('iterations', 1))
    work_id = str(uuid.uuid4())

    # Add the work item to the queue
    queue.append((buffer, iterations, work_id))

    return jsonify({'work_id': work_id})

# Endpoint for retrieving completed work
@app.route('/pullCompleted', methods=['POST'])
def pull_completed_work():
    top = int(request.args.get('top', 1))

    # Get the latest completed work items
    work_items = []
    for work_id in list(completed_work.keys())[-top:]:
        work_items.append({
            'work_id': work_id,
            'output': completed_work[work_id]
        })

        # Remove the work item from the completed work dictionary
        del completed_work[work_id]

    return jsonify({'work_items': work_items})

def http_post(url, data):
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None
    
def launch_ec2_instance(image_id, instance_type):
    ec2_client = boto3.client('ec2')
    response = ec2_client.run_instances(
        ImageId=config['EC2']['ImageId'],
        InstanceType=config['EC2']['InstanceType'],
        KeyName=config['EC2']['KeyName'],
        SecurityGroupIds=config['EC2']['GroupName'],
        MinCount=1,
        MaxCount=1
    )
    instance_id = response['Instances'][0]['InstanceId']
    print(f"Launched EC2 instance: {instance_id}")
    return instance_id

def terminate_ec2_instance(instance_id):
    ec2_client = boto3.client('ec2')
    response = ec2_client.terminate_instances(InstanceIds=[instance_id])
    print(f"Terminating EC2 instance: {instance_id}")
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)