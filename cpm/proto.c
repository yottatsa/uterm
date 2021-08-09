#include "slip.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define EP_TERMSPEC "unix socket terminal"

extern int getch();
extern int kbhit();

int mainloop() {
  unsigned char buff[8192];
  unsigned char *p;
  int l, i;

  while (1) {
    memset(buff, 0, sizeof(buff));
    l = recv_packet(buff, sizeof(buff));
    if (l == 0)
      continue;
    if (buff[0] == 0x00 && buff[1] == 0x00) {
      p = buff;
      *(p++);
      *(p++);
      strncpy((char *)p, EP_TERMSPEC, sizeof(EP_TERMSPEC));
      send_packet(buff, 2 + sizeof(EP_TERMSPEC));
    }
    if (buff[0] == 0x01 && buff[1] == 0x01) {
      if (kbhit()) {
        buff[2] = getch();
        send_packet(buff, 3);
      } else {
        send_packet(buff, 2);
      }
    }
    if (buff[0] == 0x02 && buff[1] == 0x02) {
      p = buff;
      *(p++);
      *(p++);
      printf("%s", (char *)p);
      send_packet(buff, 2);
    }
  }
  return 0;
}
