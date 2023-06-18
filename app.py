import os
import logging
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
from paramiko import AuthenticationException, SSHException
from paramiko.ssh_exception import NoValidConnectionsError

'''
init
'''
# Read configuration from file
with open('cloud-ex2/config.yaml') as file:
    config = yaml.safe_load(file)

ec2_client = boto3.client('ec2', region_name=config['EC2']['region'])
app = Flask(__name__)

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a file handler and set the log level
file_handler = logging.FileHandler('app.log')

# Create a formatter and add it to the file handler
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

def create_key_pair(KeyName):
    # Create a new key pair
    key_pair = ec2_client.create_key_pair(KeyName=KeyName)

    # Save the private key to a file
    with open(f'{KeyName}.pem', 'w') as file:
        file.write(key_pair['KeyMaterial'])

    os.system(f'sudo chmod 400 {KeyName}.pem')
    os.system(f'sudo chown ubuntu {KeyName}.pem')

    logger.info(f"Key pair '{KeyName}' created and saved to '{KeyName}.pem'.")

now_str = datetime.datetime.now()
KeyName = now_str.strftime("%Y-%m-%d-%H-%M-%S.%f").strip()[:-7]

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
        # Perform the worker checking logic here
        logger.info("Checking workers...")
        if (len(workers) == 0):
            time.sleep(5)  # Sleep for 60 seconds between each check
        else: 
            time.sleep(150)
        if len(queue) > 0:
            if datetime.datetime.now() - queue[0][3] > datetime.timedelta(seconds=15):
                if len(workers) < maxNumOfWorkers:
                    logger.info(f"creating worker number {len(workers) + 1}")
                    launch_ec2_instance()
                else:
                    try:
                        response = http_get(nodes[1] + '/getQueueLen')
                        if response == "True":
                            with lockNum:
                                maxNumOfWorkers += 1
                            logger.info(f"creating worker number {len(workers) + 1}")
                            launch_ec2_instance()
                    except requests.exceptions.RequestException as e:
                        logger.error(f"An error occurred during HTTP request: {e}")


'''
routes
'''
@app.route('/enqueue', methods=['PUT'])
def enqueue_work():
    buffer = json.loads(request.data)
    iterations = int(request.args.get('iterations', 1))
    work_id = str(uuid.uuid4())
    work = (buffer, iterations, work_id, datetime.datetime.now())
    logger.info(f'Work: {work}')
    # Add the work item to the queue
    global queue
    with lockQueue:
        queue.append(work)

    return jsonify({'work_id': work_id})

@app.route('/pullCompleted', methods=['POST'])
def pull_completed_work():
    top = int(request.args.get('top', 1))
    work_items = get_completed_work(top, True)
    return jsonify({'work_items': work_items})

@app.route('/pullCompletedNode', methods=['POST'])
def pull_completed_work_node():
    top = int(request.args.get('top', 1))
    work_items = get_completed_work(top, False)
    return jsonify({'work_items': work_items})

@app.route('/ip', methods=['POST'])
def getIp():
    global nodes
    with lockNodes:
        nodes = json.loads(request.data)
    logger.info(f"Nodes server: {nodes}")
    return jsonify('Added nodes')

@app.route('/getQueueLen', methods=['GET'])
def TryGetNodeQuota():
    global maxNumOfWorkers
    if len(workers) < maxNumOfWorkers:
        with lockNum:
            maxNumOfWorkers -= 1
        return ("True", 200)
    return ("False", 404)

@app.route('/notifyKilled', methods=['POST'])
def workerKilledInAction():
    global workers
    instanceId = json.loads(request.data)
    if instanceId in workers.keys():
        with lockWorkers:
            del workers[instanceId]
        logger.info(f"worker {instanceId} killed in action")
        return (jsonify('worker killed'), 200)
    else:
        return (jsonify('not exists'), 404)
    
@app.route('/getWork', methods=['GET'])
def giveWork():
    global queue
    if len(queue) > 0:
        response = ''
        with lockQueue:
            response = jsonify(queue.pop())
        return (response, 200)
    else:
        response = jsonify('')
        return response

@app.route('/completeWork', methods=['POST'])
def completeWork():
    data = json.loads(request.data)
    global completed_work
    with lockComplete:
        completed_work[data[1]] = data[0]
    return jsonify('Work completed')

'''
handler functions
'''
def http_post(url, data):
    try:
        logger.info(f"Sending POST request to: {url}")
        logger.info(f"Request data: {data}")
        
        response = requests.post(url, data=json.dumps(data))
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response data: {response.text}")
        
        return response.text
    
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred: {e}")
        return None

def http_get(url):
    try:
        logger.info(f"Sending GET request to: {url}")

        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response data: {response.text}")
        
        return json.loads(response.text)
    
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred: {e}")
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

    ssh_and_run_code(workers[instance_id], KeyName)
    time.sleep(5)
    url = f'http://{workers[instance_id]}:5000/instanceId'
    url2 = f'http://{workers[instance_id]}:5000/newNode'
    
    http_post(url, instance_id)
    logger.info("Ran" + url)
    http_post(url2, nodes)
    logger.info("Ran" + url2)
    logger.info(f"Launched EC2 instance: {instance_id}")

def get_completed_work(n, askOtherNode):
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
        if askOtherNode:
            # Ask the second node for the items
            response = requests.post(nodes[1] + '/pullCompletedNode', params={'top': n})
            if response.status_code == 200:
                data = response.json()
                return data['work_items']
            else:
                return []
        else:
            return []

def ssh_and_run_code(instance_ip, KeyName):
    connected = False

    while not connected:
        try:
            # Connect to the instance via SSH
            logger.info('Connecting to Worker using SSH...')
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                hostname=instance_ip,
                username='ubuntu',
                key_filename=KeyName + '.pem'
            )

            connected = True  # SSH connection successful
            logger.info('Connected to Worker using SSH')

            for command in config['CommandsWorker']:
                logger.info(f"Executing command: {command}")
                stdin, stdout, stderr = ssh.exec_command(command)
                logger.info(stderr.read().decode())

        except AuthenticationException:
            logger.error("Authentication failed. Please check your credentials.")
            break  # Authentication failed, break out of the loop
        except SSHException as e:
            logger.error(f"SSH connection failed: {str(e)}")
            logger.info("Retrying in 5 seconds...")
            time.sleep(5)  # Wait for 5 seconds before retrying
        except NoValidConnectionsError as e:
            logger.error(f"Unable to establish SSH connection: {str(e)}")
            logger.info("Retrying in 5 seconds...")
            time.sleep(5)  # Wait for 5 seconds before retrying

    # Close SSH connection
    logger.info('Closing SSH to Worker')
    ssh.close()


if __name__ == '__main__':
    # Create and start the server thread
    server_thread = threading.Thread(target=run_server)
    server_thread.start()

    server_thread = threading.Thread(target=check_workers)
    server_thread.start()
