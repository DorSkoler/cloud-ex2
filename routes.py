from flask import jsonify, request
from appOld import app, queue, completed_work, workers, maxNumOfWorkers, lockNodes, nodes
import uuid
import json
import datetime
import threading

from handler import *

@app.route('/enqueue', methods=['PUT'])
def enqueue_work():
    buffer = request.data
    iterations = int(request.args.get('iterations', 1))
    work_id = str(uuid.uuid4())
    work = (buffer, iterations, work_id, datetime.datetime.now())
    print(f'work: {work}')
    # Add the work item to the queue
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
    if len(workers) < maxNumOfWorkers:
        maxNumOfWorkers =- 1
        return True
    return False

@app.route('/getWork', methods=['GET'])
def giveWork():
    if len(queue) > 0:
        return queue.pop()
    else:
        response = jsonify('no job')
        response.status_code = 404
        return response
    
@app.route('/completeWork', methods=['POST'])
def completeWork():
    data = json.loads(request.data)
    completed_work[data[1]] = data[0]
