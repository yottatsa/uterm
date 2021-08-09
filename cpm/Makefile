CC      = g++
CFLAGS  = -Icompat -Wno-narrowing

Z88DK_HOME = /usr/local/share/z88dk
Z88DK_TARGET = cpm

CC      = $(Z88DK_HOME)/bin/zcc
CFLAGS  = +$(Z88DK_TARGET) -lm -subtype=zxplus3
LDFLAGS = +$(Z88DK_TARGET) -lm -subtype=zxplus3 -create-app -pragma-define:CRT_ENABLE_COMMANDLINE=0
#LDFLAGS = +$(Z88DK_TARGET) -lm -lcpccpm -create-app --generic-console -pragma-define:CONSOLE_COLUMNS=51 -pragma-define:CONSOLE_ROWS=24

PROG = uterm
OBJS = slip.o proto.o $(PROG).o

.PHONY: all format clean

all: $(PROG)

$(PROG): $(OBJS) 
	PATH=$(Z88DK_HOME)/bin:$(PATH) $(CC) $(LDFLAGS) $^ -o $@

%.o: %.c
	PATH=$(Z88DK_HOME)/bin:$(PATH) $(CC) $(CFLAGS) -c $< -o $@

format:
	clang-format -i *.c *.h

clean:
	rm $(PROG) $(OBJS)
