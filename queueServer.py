import requests
import random
from flask import Flask, request

app = Flask(__name__)

# Instance A and Instance B URLs
instance_a_url = 'http://<INSTANCE_A_IP>:5000/entry'
instance_b_url = 'http://<INSTANCE_B_IP>:5000/entry'

# Get a random instance URL
def get_random_instance_url():
    return random.choice([instance_a_url, instance_b_url])

# Handle the incoming requests
@app.route('/api/entry', methods=['POST'])
def handle_request():
    try:
        # Get the request data
        data = request.json

        # Send the request to a random instance
        instance_url = get_random_instance_url()
        response = requests.post(instance_url, json=data)

        if response.status_code == 200:
            return 'Request processed successfully'
        else:
            return 'Error processing request', 500

    except Exception as e:
        return f'Error processing request: {e}', 500

# Start the Flask server
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
