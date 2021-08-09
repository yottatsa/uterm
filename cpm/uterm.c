#include "proto.h"
#include <cpm.h>
#include <stdio.h>
#include <stdlib.h>

#define BIOS_AUXOUT_FN 6
#define BIOS_AUXIN_FN 7
#define BIOS_AUXIST_FN 18 /* CP/M 3 */

void send_char(unsigned char c) { bios(BIOS_AUXOUT_FN, c, 0); }

unsigned char recv_char() {
  unsigned char c = 0;
  c = bios(BIOS_AUXIN_FN, 0, 0);
  if (c == 26) {
    exit(1);
  }

  return c;
}

unsigned char has_recv_char() {
  unsigned char c = 0;
  c = bios(BIOS_AUXIST_FN, 0, 0);
  return c;
}

int main() { return mainloop(); }

/* vim: set ts=2 sw=2 tw=0 et : */
