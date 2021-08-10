.PHONY: all format

all:
	#make -C ansi all
	make -C cpm all
	make -C utermhost all

format:
	#make -C ansi format
	make -C cpm format
	make -C utermhost format
