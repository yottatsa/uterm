.PHONY: all format

all: host

format:
	python3 -m isort .
	black *.py

host: host.py
	pyre
