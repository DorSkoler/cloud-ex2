from flask import Flask
import boto3
import yaml
import time
import threading
import datetime

# Read configuration from file
with open('config.yaml') as file:
    config = yaml.safe_load(file)

ec2_client = boto3.client('ec2', region_name=config['EC2']['region'])
app = Flask(__name__)

# Import routes from routes.py
from routes import *

# Import functions from functions.py
from handler import *

# In-memory queue to store the submitted work items
queue = []
# Dictionary to store the completed work items
completed_work = {}
# The paths to reach both nodes
nodes = []
workers = {}
maxNumOfWorkers = 5

def run_server():
    app.run(host='0.0.0.0', port=5001)

def check_workers():
    while True:
        # Perform the worker checking logic here
        print("Checking workers...")
        time.sleep(10)  # Sleep for 10 seconds between each check
        if len(queue) > 0:
            if datetime.datetime.now() - queue[-1][4] > datetime.timedelta(seconds=15):
                if len(workers) < maxNumOfWorkers:
                    launch_ec2_instance()
                else:
                    response = http_get(nodes[1] + '/getQueueLen')
                    if response:
                        maxNumOfWorkers =+ 1

if __name__ == '__main__':
    # Create and start the server thread
    server_thread = threading.Thread(target=run_server)
    server_thread.start()

    # Start the worker checking loop in the main thread
    check_workers()
