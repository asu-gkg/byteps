import byteps.torch as bps
import torch
import torch.nn as nn
import torch.optim as optim
import os

os.environ["DMLC_NUM_WORKER"] = "1"
os.environ["DMLC_NUM_SERVER"] = "1"
os.environ["DMLC_PS_ROOT_URI"] = "10.4.5.140"
os.environ["DMLC_PS_ROOT_PORT"] = "1234"
os.environ["BYTEPS_LOG_LEVEL"] = "INFO"
os.environ["BYTEPS_MIN_COMPRESS_BYTES"] = "0"
os.environ["BYTEPS_PARTITION_BYTES"] = "2147483647"
os.environ["NVIDIA_VISIBLE_DEVICES"] = "0"
os.environ["DMLC_WORKER_ID"] = "0"
os.environ["DMLC_ROLE"] = "worker"
os.environ["BYTEPS_THREADPOOL_SIZE"] = "4"
os.environ["BYTEPS_FORCE_DISTRIBUTED"] = "1"
os.environ["BYTEPS_LOCAL_RANK"] = "0"
os.environ["BYTEPS_LOCAL_SIZE"] = "1"


bps.init(lazy=False)

# BytePS: pin GPU to local rank.
print('bps.local_rank()', bps.local_rank())
torch.cuda.set_device(bps.local_rank())
net = nn.Sequential()
# layers may be added in a random order for all workers
layers = {'ones_': 1, 'zeros_': 0}
for name, init in layers.items():
    layer = nn.Linear(10, 10, bias=False)
    with torch.no_grad():
        layer.weight.fill_(init)
    net.add_module(name, layer)
print(net)
params = net.named_parameters()
# BytePS: wrap optimizer with DistributedOptimizer.
optimizer = optim.SGD(net.parameters(), lr=0.01)
optimizer = bps.DistributedOptimizer(optimizer=optimizer,
                                        named_parameters=net.named_parameters(),
                                        compression=bps.Compression.none)
bps.broadcast_parameters(net.state_dict(), root_rank=0)