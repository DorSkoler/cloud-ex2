import hashlib
from flask import Flask, request, jsonify
import requests
import datetime
import time
import json

app = Flask(__name__)

nodes = []
instanceId = ''

@app.route('/instanceId', methods=['POST'])
def getInstanceId():
    global instanceId
    instanceId = json.loads(request.data)
    print(nodes, instanceId)
    if len(nodes) > 0 and instanceId != '':
        return loop()
    return 'added instanceId'

@app.route('/newNode', methods=['POST'])
def getNewNode():
    nodes = json.loads(request.data)
    print(nodes, instanceId)
    if len(nodes) > 0 and instanceId != '':
        return loop()
    return 'added newNode'

def process_work(data):
    # Get the next work item from the queue
    buffer = data['buffer']
    iterations = int(data['iterations'])
    print(buffer, iterations)
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
    return http_post(f'{nodes[0]}/killMe', instanceId)

def loop():
    lastTime = datetime.datetime.now()
    print(lastTime)
    while datetime.datetime.now() - lastTime <= datetime.timedelta(minutes=10):
        for node in nodes:
            work = http_get(f'{node}/getWork')

            if work != '':
                result = process_work(work)
                http_post(f'{node}/completeWork', result)
                lastTime = datetime.datetime.now()
                continue

        time.sleep(10)

    killMe()
    
app.run(host='0.0.0.0', port=5000)
