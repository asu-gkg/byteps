import byteps.torch as bps
import torch
import torch.nn as nn
import torch.optim as optim

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