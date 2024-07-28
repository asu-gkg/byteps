export BYTEPS_CUDA_HOME=/usr/local/cuda
export BYTEPS_NCCL_HOME=/home/asu/DeepINC/nccl/build
export PYTHONPATH=$(pwd):$PYTHONPATH
export PATH=$(pwd)/bin:$PATH


install:
	python3 setup.py install