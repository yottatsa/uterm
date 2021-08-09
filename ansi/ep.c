#include "../cpm/proto.h"
#include "compat/conio.h"
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <sys/un.h>

#define SERVER_SOCK_FILE "comm"

int fd;

void send_char(unsigned char c) {
  if (send(fd, &c, 1, 0) == -1) {
    perror("send");
    close(fd);
    exit(1);
  }
}

unsigned char recv_char() {
  unsigned char c = 0;
  if (recv(fd, &c, 1, 0) < 0) {
    perror("recv");
    close(fd);
    exit(1);
  }
  return c;
}

#undef getch
#undef kbhit
#define _getch ___CONIO_H.getch
#define _kbhit ___CONIO_H.kbhit
int getch() { return _getch(); }
int kbhit() { return _kbhit(); }

int main() {
  struct sockaddr_un addr;
  unsigned char buff[8192];
  unsigned char *p;
  int l, i;

  if ((fd = socket(AF_UNIX, SOCK_STREAM, 0)) < 0) {
    perror("socket");
    return 1;
  }

  memset(&addr, 0, sizeof(addr));
  addr.sun_family = AF_UNIX;
  strcpy(addr.sun_path, SERVER_SOCK_FILE);
  if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) == -1) {
    perror("connect");
    return 1;
  }

  mainloop();

  close(fd);
  return 0;
}

/* vim: set ts=2 sw=2 tw=0 et : */
