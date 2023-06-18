# Distributed Hashing System

The Distributed Hashing System is a server-worker architecture that performs distributed hashing computations. It consists of a server and multiple worker nodes that collaborate to process hash computations efficiently.

## Features

- **Server:** The server acts as a central coordinator and manages the work distribution among the worker nodes.
- **Worker Nodes:** Worker nodes perform the actual hashing computations based on the work assigned by the server.
- **Dynamic Scaling:** The system dynamically scales the number of worker nodes based on the workload and availability.
- **Fault Tolerance:** The system can handle failures by redistributing the work among available worker nodes.
- **RESTful API:** The system provides a RESTful API for enqueueing work, retrieving completed work, and managing the system.

## Prerequisites

Before running the Distributed Hashing System, make sure you have the following dependencies installed:

- Python 3
- Flask
- Boto3
- Paramiko
- YAML

You also need to configure your AWS credentials to use the EC2 service for launching worker instances.

## Installation

1. Clone the repository: `git clone <repository-url>`
2. Install the dependencies: `pip install -r requirements.txt`
3. Configure your AWS credentials: [AWS CLI Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
4. Update the `config.yaml` file with your desired configuration parameters.

## Usage

1. Start the server by running the following command: `python app.py`
2. Start the worker nodes by running the following command: `python worker.py`
3. To deploy it to AWS use: `python deploy.py`

Once the server and worker nodes are running, you can enqueue work items and retrieve completed work using the provided RESTful API endpoints.

## API Endpoints

- `PUT /enqueue`: Enqueue work by sending a PUT request with the work data.
- `POST /pullCompleted`: Retrieve completed work by sending a POST request.
- `POST /pullCompletedNode`: Retrieve completed work from another node by sending a POST request.
- `POST /ip`: Provide the IP addresses of the servers nodes to the server.
- `GET /getQueueLen`: Check if the other server has available worker to slot.
- `POST /notifyKilled`: Notify the server that a worker node has been killed.
- `GET /getWork`: Request a work item from the server.
- `POST /completeWork`: Notify the server that a work item has been completed.

Refer to the server and worker code files for more details on the API endpoints and their implementation.

## License

The Distributed Hashing System is licensed under the [MIT License](https://opensource.org/licenses/MIT).

---

This README file provides an overview of the project, installation instructions, usage guidelines, API endpoints, contributing information, license details, and contact information. You can customize it further to include specific details about your project and its functionalities.