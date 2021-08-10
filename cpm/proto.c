#include "slip.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define EP_TERMSPEC "unix socket terminal"

// interface
extern unsigned char has_recv_char();

int mainloop() {
  unsigned char buff[128];
  unsigned char kbd[64];
  unsigned char *p, *kbd_p;
  int l, i, c;

  kbd_p = kbd;

  putchar(0x1B);
  putchar("j"[0]);

  while (1) {
    if (c = getk()) {
      *(kbd_p++) = c;
      putchar(c);
      continue;
    }
    if (has_recv_char() == 0)
      continue;

    l = recv_packet(buff, sizeof(buff));
    if (l == 0)
      continue;

    if (buff[0] == 0x00 && buff[1] == 0x00) {
      p = buff + 2;
      strncpy((char *)p, EP_TERMSPEC, sizeof(EP_TERMSPEC));
      send_packet(buff, 2 + sizeof(EP_TERMSPEC));
    }
    if (buff[0] == 0x01 && buff[1] == 0x01) {
      p = buff + 2;
      i = kbd_p - kbd;
      strncpy((char *)p, (char *)kbd, i);
      send_packet(buff, i + 2);
      kbd_p = kbd;
    }
    if (buff[0] == 0x02 && buff[1] == 0x02) {
      putchar(0x1B);
      putchar("k"[0]);
      for (i = 2; i < l; i++)
        putchar(buff[i]);
      putchar(0x1B);
      putchar("j"[0]);
      send_packet(buff, 2);
    }
    if (buff[0] == 0x03 && buff[1] == 0x03) {
      puts("SIGINT");
      exit(0);
    }
  }
  return 0;
}
