CC      = g++
CFLAGS  = -Icompat -Wno-narrowing

.PHONY: all format host

all: ep

format:
	clang-format -i ep.c
	python3 -m isort .
	black host.py

host: host.py
	pyre
