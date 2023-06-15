import os
from flask import Flask, jsonify, request
import boto3
import requests
import yaml
import time
import threading
import json
import datetime
import uuid
import paramiko


'''
init
'''
# Read configuration from file
with open('cloud-ex2/config.yaml') as file:
    config = yaml.safe_load(file)

ec2_client = boto3.client('ec2', region_name=config['EC2']['region'])
app = Flask(__name__)

def create_key_pair(KeyName):
    # Create a new key pair
    key_pair = ec2_client.create_key_pair(KeyName=KeyName)

    # Save the private key to a file
    with open(f'{KeyName}.pem', 'w') as file:
        file.write(key_pair['KeyMaterial'])
        
    os.system(f'sudo chmod 400 {KeyName}.pem')
    os.system(f'sudo chown ubuntu {KeyName}.pem')
        
    print(f"Key pair '{KeyName}' created and saved to '{KeyName}.pem'.")

now_str = datetime.datetime.now()
KeyName = now_str.strftime("%Y-%m-%d%H:%M:%S.%f").strip()[:-7]
 
create_key_pair(KeyName)

# In-memory queue to store the submitted work items
queue = []
# Dictionary to store the completed work items
completed_work = {}
# The paths to reach both nodes
nodes = []
workers = {}
maxNumOfWorkers = 5

lockNodes = threading.Lock()
lockWorkers = threading.Lock()
lockNum = threading.Lock()
lockComplete = threading.Lock()
lockQueue = threading.Lock()

'''
main functions
'''
def run_server():
    app.run(host='0.0.0.0')


def check_workers():
    global maxNumOfWorkers
    while True:
        print("nodes worker:", nodes)
        # Perform the worker checking logic here
        print("Checking workers...")
        time.sleep(30)  # Sleep for 10 seconds between each check
        if len(queue) > 0:
            if datetime.datetime.now() - queue[-1][3] > datetime.timedelta(seconds=15):
                if len(workers) < maxNumOfWorkers:
                    launch_ec2_instance()
                else:
                    try:
                        response = http_get(nodes[1] + '/getQueueLen')
                        if response:
                            with lockNum:
                                maxNumOfWorkers =+ 1
                    except requests.exceptions.RequestException as e:
                        print(f"An error occurred during HTTP request: {e}")
                        
'''
routes
'''
@app.route('/enqueue', methods=['PUT'])
def enqueue_work():
    buffer = request.data
    iterations = int(request.args.get('iterations', 1))
    work_id = str(uuid.uuid4())
    work = (buffer, iterations, work_id, datetime.datetime.now())
    print(f'work: {work}')
    # Add the work item to the queue
    global queue
    with lockQueue:
        queue.append(work)

    return jsonify({'work_id': work_id})

@app.route('/pullCompleted', methods=['POST'])
def pull_completed_work():
    top = int(request.args.get('top', 1))
    work_items = get_completed_work(top);
    return jsonify({'work_items': work_items})

@app.route('/ip', methods=['POST'])
def getIp():
    global nodes
    with lockNodes:
        nodes = json.loads(request.data)
    print("nodes server:", nodes)
    return jsonify('added nodes')

@app.route('/getQueueLen', methods=['GET'])
def TryGetNodeQuota():
    global maxNumOfWorkers
    if len(workers) < maxNumOfWorkers:
        with lockNum:
            maxNumOfWorkers =- 1
        return True
    return False

@app.route('/getWork', methods=['GET'])
def giveWork():
    global queue
    if len(queue) > 0:
        with lockQueue:
            return queue.pop()
    else:
        response = jsonify('no job')
        response.status_code = 404
        return response
    
@app.route('/completeWork', methods=['POST'])
def completeWork():
    data = json.loads(request.data)
    global completed_work
    with lockComplete:
        completed_work[data[1]] = data[0]


'''
handler functions
'''
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
        response = requests.post(url, data=json.dumps(data))
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

def launch_ec2_instance():
    global workers

    response = ec2_client.run_instances(
        ImageId=config['EC2']['ImageId'],
        InstanceType=config['EC2']['InstanceType'],
        KeyName=KeyName,
        SecurityGroupIds=[config['EC2']['GroupName']],
        MinCount=1,
        MaxCount=1,
        InstanceInitiatedShutdownBehavior='terminate',
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': f'worker-{datetime.datetime.now()}-of-{nodes[0]}'
                    },
                ]
            },
        ]
    )
    instance_id = response['Instances'][0]['InstanceId']
    
    waiter = ec2_client.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])
    # Wait for the instance to have an IP address
    while True:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        if 'PublicIpAddress' in instance:
            with lockWorkers:
                workers[instance_id] = instance['PublicIpAddress']
            break
        time.sleep(5)
    
    waiter = ec2_client.get_waiter('instance_status_ok')
    waiter.wait(InstanceIds=[instance_id])
    
    ssh_and_run_code(workers[instance_id], KeyName)
    time.sleep(5)    
    url = f'http://{workers[instance_id]}:5000/instanceId'
    url2 = f'http://{workers[instance_id]}:5000/newNode'
    http_post(url, instance_id)
    http_post(url2, nodes)
    print(f"Launched EC2 instance: {instance_id}")

def get_completed_work(n):
    global completed_work
    if len(completed_work) >= n:
        # Get n items from completed_work
        work_items = []
        for i in range(n):
            with lockComplete:
                work_id, output = completed_work.popitem()
            work_items.append({'work_id': work_id, 'output': output})
        return work_items
    elif len(completed_work) > 0:
        # Get all remaining items from completed_work
        work_items = []
        while len(completed_work) > 0:
            with lockComplete:
                work_id, output = completed_work.popitem()
            work_items.append({'work_id': work_id, 'output': output})
        return work_items
    else:
        # Ask the second node for the items
        response = requests.get(nodes[1] + '/pullCompleted', params={'top': n})
        if response.status_code == 200:
            data = response.json()
            return data['work_items']
        else:
            return []
        
def ssh_and_run_code(instance_ip, KeyName):
    # Connect to the instances via SSH
    print('Connected to Worker using SSH')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    ssh.connect(
        hostname=instance_ip,
        username='ubuntu',
        key_filename=KeyName + '.pem'
    )
        
    for command in config['CommandsWorker']:
            print(f"Executing command: {command}")
            stdin, stdout, stderr = ssh.exec_command(command)
            print(stdout.read().decode())
            print(stderr.read().decode())

    # Close SSH connections
    print('Closing SSH to Worker')
    ssh.close()

if __name__ == '__main__':
    # Create and start the server thread
    server_thread = threading.Thread(target=run_server)
    server_thread.start()

    server_thread = threading.Thread(target=check_workers)
    server_thread.start()
