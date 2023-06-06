import hashlib
from flask import Flask, request, jsonify


app = Flask(__name__)

# Worker function to process the work items
@app.route('/work', methods=['post'])
def process_work():
    # Get the next work item from the queue
    buffer, iterations, work_id = request.data

    # Perform the computation
    output = hashlib.sha512(buffer).digest()
    for i in range(iterations - 1):
        output = hashlib.sha512(output).digest()

    # Store the completed work item
    return output, work_id