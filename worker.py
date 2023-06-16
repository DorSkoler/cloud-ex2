import hashlib
from flask import Flask, request, jsonify
import requests
import datetime
import time
import json
import os
import threading

app = Flask(__name__)

nodes = []
instanceId = ''

lockNodes = threading.Lock()
lockWork = threading.Lock()
lockInstanceId = threading.Lock()

@app.route('/instanceId', methods=['POST'])
def getInstanceId():
    global instanceId
    with lockInstanceId:
        instanceId = json.loads(request.data)
    print("Received instanceId:", instanceId)
    return 'Added instanceId'

@app.route('/newNode', methods=['POST'])
def getNewNode():
    global nodes
    with lockNodes:
        nodes = json.loads(request.data)
    print("Received new nodes:", nodes)
    print("Instance ID:", instanceId)
    return 'Added newNode'

def process_work(data):
    # Get the next work item from the queue
    buffer = data['buffer']
    iterations = int(data['iterations'])
    print("Processing work item:")
    print("Buffer:", buffer)
    print("Iterations:", iterations)
    # Perform the computation
    encoded_buffer = buffer.encode('utf-8')
    output = hashlib.sha512(encoded_buffer).digest()
    for i in range(iterations - 1):
        output = hashlib.sha512(output).digest()

    # Store the completed work item
    return output

def http_post(url, data):
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None
    
def http_get(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        return json.loads(response.text)
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

def killMe():
    os.system('sudo shutdown -h now')
    return "Killing the worker: " + str(instanceId)

def loop():
    if len(nodes) > 0 and instanceId != '':
        lastTime = datetime.datetime.now()
        print("Loop started. Last time:", lastTime)
        while datetime.datetime.now() - lastTime <= datetime.timedelta(minutes=10):
            for node in nodes:
                work = http_get(f'{node}/getWork')
                
                if work != '':
                    print("Received work:", work)
                    result = process_work(work)
                    http_post(f'{node}/completeWork', [result, work['work_id']])
                    lastTime = datetime.datetime.now()
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

    server_thread = threading.Thread(target=loop)
    server_thread.start()