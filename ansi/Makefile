CC      = g++
CFLAGS  = -Icompat -Wno-narrowing

PROG = ep
SRCS = ../cpm/proto.c ../cpm/slip.c $(PROG).c

.PHONY: all format

all: $(PROG)

$(PROG): $(SRCS)
#	$(CC) $(CFLAGS) $(LDFLAGS) $^ -o $@

format:
	clang-format -i ep.c
