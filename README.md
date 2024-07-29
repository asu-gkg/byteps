# BytePS
With slower network, BytePS offers even more performance advantages -- up to 2x of Horovod+NCCL. You can find more evaluation results at [performance.md](docs/performance.md).

## Quick Start

We provide a [step-by-step tutorial](docs/step-by-step-tutorial.md) for you to run benchmark training tasks. The simplest way to start is to use our [docker images](docker). Refer to [Documentations](docs) for how to [launch distributed jobs](docs/running.md) and more [detailed configurations](docs/env.md). After you can start BytePS, read [best practice](docs/best-practice.md) to get the best performance.

Below, we explain how to install BytePS by yourself. There are two options.

### Install by pip

```
pip3 install byteps
```

### Use Docker file to develop
```
sudo docker import byteps.tar byteps:0.1
```

```
sudo docker run \
    --gpus all      \
    --device /dev/nvidia0:/dev/nvidia0         \
    --device /dev/nvidiactl:/dev/nvidiactl     \
    --device /dev/nvidia-uvm:/dev/nvidia-uvm   \
    --device /dev/nvidia-uvm-tools:/dev/nvidia-uvm-tools \
    --cap-add=SYS_PTRACE \
    --security-opt seccomp=unconfined \
    --name=bps \
    --net=host    \
    -itd byteps:0.1 \
    zsh
```

``` 
sudo docker exec -it bps zsh
sudo /etc/init.d/ssh start
```

``` 
docker export -o byteps.tar bps
```

### Build from source code

You can try out the latest features by directly installing from master branch:

```
git clone https://github.com/asu-gkg/byteps.git
cd byteps
python3 setup.py install
```

Notes for above two options:
- BytePS assumes that you have already installed one or more of the following frameworks: TensorFlow / PyTorch / MXNet.
- BytePS depends on CUDA and NCCL. You should specify the NCCL path with `export BYTEPS_NCCL_HOME=/path/to/nccl`. By default it points to `/usr/local/nccl`.
- The installation requires gcc>=4.9. If you are working on CentOS/Redhat and have gcc<4.9, you can try `yum install devtoolset-7` before everything else. In general, we recommend using gcc 4.9 for best compatibility ([how to pin gcc](https://github.com/bytedance/byteps/blob/3fba75def0d81c1d3225f8f397cc985200f57de7/docker/Dockerfile.mxnet#L72-L80)).
- RDMA support: During setup, the script will automatically detect the RDMA header file. If you want to use RDMA, make sure your RDMA environment has been properly installed and tested before install ([install on Ubuntu-18.04](https://github.com/bytedance/byteps/blob/3fba75def0d81c1d3225f8f397cc985200f57de7/docker/Dockerfile.mxnet#L29-L33)).
