CC      = g++
CFLAGS  = -Icompat -Wno-narrowing

Z88DK_HOME = /usr/local/share/z88dk
Z88DK_TARGET = cpm

CC      = $(Z88DK_HOME)/bin/zcc
CFLAGS  = +$(Z88DK_TARGET) 
LDFLAGS = +$(Z88DK_TARGET) -lndos -create-app

PROG = uterm
OBJS = slip.o proto.o $(PROG).o

.PHONY: all format

all: $(PROG)

$(PROG): $(OBJS) 
	PATH=$(Z88DK_HOME)/bin:$(PATH) $(CC) $(LDFLAGS) $^ -o $@

%.o: %.c
	PATH=$(Z88DK_HOME)/bin:$(PATH) $(CC) $(CFLAGS) -c $< -o $@

format:
	clang-format -i *.c *.h
