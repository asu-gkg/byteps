export DMLC_NUM_WORKER=1
export DMLC_NUM_SERVER=1
export DMLC_ROLE=worker
export DMLC_PS_ROOT_URI=127.0.0.1
export DMLC_PS_ROOT_PORT=1234

install:
	sudo python3 setup.py install

build:
	sudo python3 setup.py build_ext --inplace

run-server:
	python3 -c "import byteps.server"