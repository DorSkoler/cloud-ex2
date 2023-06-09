from flask import Flask
import boto3
import yaml
import time
import threading
import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# Read configuration from file
with open('config.yaml') as file:
    config = yaml.safe_load(file)

ec2_client = boto3.client('ec2', region_name=config['EC2']['region'])
app = Flask(__name__)

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

from handler import *
from routes import *

def run_server():
    global queue
    global maxNumOfWorkers
    global nodes
    global workers
    global completed_work
    app.run(host='0.0.0.0')


def check_workers():
    global queue
    global maxNumOfWorkers
    global nodes
    global workers
    global completed_work
    while True:
        
        print("nodes worker:", nodes)
        # Perform the worker checking logic here
        print("Checking workers...")
        time.sleep(10)  # Sleep for 10 seconds between each check
        if len(queue) > 0:
            if datetime.datetime.now() - queue[-1][3] > datetime.timedelta(seconds=15):
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

    server_thread = threading.Thread(target=check_workers)
    server_thread.start()
