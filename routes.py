from flask import jsonify, request
from app import app, queue, completed_work, workers, maxNumOfWorkers
import uuid
import json
import datetime

@app.route('/enqueue', methods=['PUT'])
def enqueue_work():
    buffer = request.data
    iterations = int(request.args.get('iterations', 1))
    work_id = str(uuid.uuid4())

    # Add the work item to the queue
    queue.append((buffer, iterations, work_id, datetime.datetime.now()))

    return jsonify({'work_id': work_id})

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

@app.route('/ip', methods=['POST'])
def getIp():
    nodes = json.loads(request.data)
    print(nodes)
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
    

