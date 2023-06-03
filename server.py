from flask import Flask, request, jsonify
import hashlib
import uuid
import threading

app = Flask(__name__)

# In-memory queue to store the submitted work items
queue = []
queue_lock = threading.Lock()

# Dictionary to store the completed work items
completed_work = {}

# Worker function to process the work items
def process_work():
    while True:
        # Check if there is any work in the queue
        with queue_lock:
            if len(queue) == 0:
                continue

            # Get the next work item from the queue
            buffer, iterations, work_id = queue.pop(0)

        # Perform the computation
        output = hashlib.sha512(buffer).digest()
        for i in range(iterations - 1):
            output = hashlib.sha512(output).digest()

        # Store the completed work item
        completed_work[work_id] = output

# Start the worker thread
worker_thread = threading.Thread(target=process_work)
worker_thread.daemon = True
worker_thread.start()

# Endpoint for submitting work
@app.route('/enqueue', methods=['PUT'])
def enqueue_work():
    buffer = request.data
    iterations = int(request.args.get('iterations', 1))
    work_id = str(uuid.uuid4())

    # Add the work item to the queue
    with queue_lock:
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
