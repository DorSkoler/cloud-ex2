import hashlib
from flask import Flask, request, jsonify
import requests
import datetime
import time
import json
import os
import threading
import logging

app = Flask(__name__)

nodes = []
instanceId = ''

lockNodes = threading.Lock()
lockWork = threading.Lock()
lockInstanceId = threading.Lock()

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a file handler and set the log level
file_handler = logging.FileHandler('worker.log')

# Create a formatter and add it to the file handler
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

@app.route('/instanceId', methods=['POST'])
def getInstanceId():
    global instanceId
    with lockInstanceId:
        instanceId = json.loads(request.data)
    logger.info("Received instanceId: %s", instanceId)
    return 'Added instanceId'

@app.route('/newNode', methods=['POST'])
def getNewNode():
    global nodes
    with lockNodes:
        nodes = json.loads(request.data)
    logger.info("Received new nodes: %s", nodes)
    logger.info("Instance ID: %s", instanceId)
    return 'Added newNode'

def process_work(data):
    buffer = data[0]
    iterations = int(data[1])
    work_id = data[2]
    timestamp = data[3]

    logger.info("Processing work item:")
    logger.info(f"Buffer: {buffer}")
    logger.info(f"Iterations: {iterations}")
    logger.info(f"Work ID: {work_id}")
    logger.info(f"Timestamp: {timestamp}")

    # Hash the buffer using SHA-256
    hash_object = hashlib.sha256(buffer.encode())
    hash_result = hash_object.hexdigest()

    # Perform additional hash iterations
    for _ in range(iterations):
        hash_object = hashlib.sha256(hash_result.encode())
        hash_result = hash_object.hexdigest()

    return hash_result

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
        logger.info("Sending GET request to: %s", url)

        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        
        logger.info("Response status code: %d", response.status_code)
        logger.info("Response data: %s", response.text)
        
        return json.loads(response.text)
    
    except requests.exceptions.RequestException as e:
        logger.error("An error occurred: %s", e)
        return None

def killMe():
    http_post(f'{nodes[0]}/notifyKilled', data=instanceId)
    os.system('sudo shutdown -h now')
    return "Killing the worker: " + str(instanceId)

def loop():
    while True:
        logger.info('entered worker loop')
        if len(nodes) > 0 and instanceId != '':
            last_time = datetime.datetime.now()
            logger.info("Loop started. Last time: %s", last_time)
            while datetime.datetime.now() - last_time <= datetime.timedelta(minutes=10):
                for node in nodes:
                    work = http_get(f'{node}/getWork') 
                    
                    if work != '' and work != None:
                        logger.info("Received work: %s", work)
                        result = process_work(work)
                        logger.info(f"complete work: {result}")
                        time.sleep(2)
                        http_post(f'{node}/completeWork', [result, work[2]])
                        last_time = datetime.datetime.now()
                        logger.info("Completed work item: %s", work[2])
                        continue

                time.sleep(10)
            killMe()
        else:
            time.sleep(10)


def run_server():
    app.run(host='0.0.0.0')

if __name__ == '__main__':
    # Create and start the server thread
    server_thread = threading.Thread(target=run_server)
    server_thread.start()

    worker_thread = threading.Thread(target=loop)
    worker_thread.start()
