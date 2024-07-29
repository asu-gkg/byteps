export DMLC_NUM_WORKER=1
export DMLC_NUM_SERVER=1
export DMLC_ROLE=worker
export DMLC_PS_ROOT_URI=10.4.164.30
export DMLC_PS_ROOT_PORT=1234

export DMLC_WORKER_ID=0
export BYTEPS_LOCAL_RANK=0
export BYTEPS_LOCAL_SIZE=1

export PS_VERBOSE=2
export BYTEPS_LOG_LEVEL=DEBUG
export SERVER_ENABLE_SCHEDULE=1
export BYTEPS_SERVER_DEBUG=1
export BYTEPS_TRACE_ON=1
export BYTEPS_FORCE_DISTRIBUTED=1
export BYTEPS_THREADPOOL_SIZE=4
export BYTEPS_ENABLE_MIXED_MODE=1
export CUDA_VISIBLE_DEVICES=0

install:
	sudo python3 setup.py install

build:
	python3 setup.py build_ext --inplace

clean:
	sudo python3 setup.py clean
	sudo rm -rf build *.egg-info dist

run-server:
	export DMLC_ROLE=server; bpslaunch

run-scheduler:
	export DMLC_ROLE=scheduler; bpslaunch

test-benchmark:
	bpslaunch python3 example/pytorch/benchmark_byteps.py

install-server:
	export BYTEPS_WITHOUT_PYTORCH=1; sudo python3 setup.py install

build-server:
	export BYTEPS_WITHOUT_PYTORCH=1; python3 setup.py build_ext --inplace
