export DMLC_NUM_WORKER=1
export DMLC_NUM_SERVER=1
export DMLC_ROLE=worker
export DMLC_PS_ROOT_URI=127.0.0.1
export DMLC_PS_ROOT_PORT=1234



export PS_VERBOSE=2
export BYTEPS_LOG_LEVEL=DEBUG
export SERVER_ENABLE_SCHEDULE=1
export BYTEPS_SERVER_DEBUG=1
export BYTEPS_TRACE_ON=1
export BYTEPS_FORCE_DISTRIBUTED=1
export BYTEPS_THREADPOOL_SIZE=1


install:
	sudo python3 setup.py install

build:
	sudo python3 setup.py build_ext --inplace

clean:
	sudo python3 setup.py clean
	sudo rm -rf build *.egg-info dist

run-server:
	export DMLC_ROLE=server; python3 -c "import byteps.server"

run-scheduler:
	export DMLC_ROLE=scheduler; python3 -c "import byteps.server"