class EndpointNode:

    workQueue = []
    workComplete = []
    maxNumOfWorkers = 0
    numOfWorkers = 0

    def _init_(self) -> None:
        if self is Avishag:
            sleep(3min)
        pass


    def add_sibling(other):
        pass

    def timer_10_sec_describe_instances():
        # rate limit - number of new workers per time period
        # rate limit - total number of new workers
        if Date.now - workQueue.peek().time > 15sec:
            instances = ec2.describe_isntances(tag: 'workers')
            if len(instances) < maxNumOfWorkers:
                spawnWorker()


    def timer_10_sec():
        # rate limit - number of new workers per time period
        # rate limit - total number of new workers
        if Date.now - workQueue.peek().time > 15sec:
            
            if numOfWorkers < maxNumOfWorkers:
                spawnWorker()
            else:
                if otherNode.TryGetNodeQuota():
                    maxNumOfWorkers+=1

    def TryGetNodeQuota():
        if numOfWorkers < maxNumOfWorkers :
            maxNumOfWorkers-=1
            return True
        return False

    def enqueueWork(text, iterations):
        workQueue.push( (text, iterations, Date.now()) )

    def giveMeWork():
        return workQueue.pop() or None

    def pullComplete(n):
        
        if len(completed) > 0:
            return completed.pop(n)
        try:
            return otherNode.pullCompleteInternal(n)
        except:
            return []


# nohup python3 my-script.py noa avishag


# a = spawn_endpoint 
# b = spawn_endpoint 

# a.add_Sibling(b)
# b.add_Sibling(a)

Noa     = EndpointNode(2, me: 'noa', other: 'avishag')
Avishag = EndpointNode(3, me: 'avishag', other: 'noa')


# curl http://noa-ip/enqueue
# curl http://avishag-ip/pullComplete



for i in range(25):
    Noa.enqueueWork("cup", 30)


for i in range(25):
    Avishag.enqueueWork("cup", 30)

for i in range(2500):
    Noa.enqueueWork("cup", 30)


while True:
    result = Avishag.pullComplete(10)
    print (result)