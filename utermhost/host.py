#!/usr/bin/python3

import argparse
import collections
import fcntl
import io
import logging
import os
import pty
import selectors
import signal
import socket
import stat
import struct
import termios
import time
from enum import Enum
from typing import Deque, Union

import serial

logger: logging.Logger = logging.getLogger(__name__)


TConn = Union[socket.socket, serial.Serial]


def set_winsize(fd, row, col, xpix=0, ypix=0):
    winsize = struct.pack("HHHH", row, col, xpix, ypix)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


class Direction(Enum):
    UND = 0
    IN = 1
    OUT = 2


class HostController(object):
    GET_CAPS = b"\x00\x00"
    GET_KEYS = b"\x01\x01"
    SEND_PTY = b"\x02\x02"
    SIG_INT = b"\x03\x03"

    # rfc1055 SLIP special character codes
    END = b"\xc0"  # 0o300 indicates end of packet
    ESC = b"\xdb"  # 0o333 indicates byte stuffing
    ESC_END = b"\xdd"  # 0o334 ESC ESC_END means END data byte
    ESC_ESC = b"\xde"  # 0o335 ESC ESC_ESC means ESC data byte

    BUFSIZE = 92
    IO_TIMEOUT = 5

    _conn: TConn
    _scr: io.BytesIO
    _kbd: Deque[bytes]
    _pty: Deque[bytes]
    _fd: int = -1
    _enabled = False

    graceful: bool = False

    def __init__(self, conn: TConn) -> None:
        self._conn = conn
        self._scr = io.BytesIO()
        self._kbd = collections.deque()
        self._pty = collections.deque()
        self._sel = selectors.DefaultSelector()

    def _handle_pty(self, conn: int, mask: int) -> None:
        try:
            if mask & selectors.EVENT_READ:
                buf = bytearray(2048)
                l = os.readv(self._fd, [buf])
                if l > 0:
                    self._pty.extend(buf[:l])  # type: ignore

            if mask & selectors.EVENT_WRITE:
                if not self._kbd:
                    return
                buf = bytes(self._kbd)  # type: ignore
                l = os.writev(self._fd, [buf])
                # termios.tcdrain(self._fd)
                if l == len(self._kbd):
                    self._kbd.clear()
                else:
                    raise RuntimeError
        except OSError:
            self.signal_int()
            raise SystemExit

    def attach(self, fd: int) -> None:
        if self._fd != -1:
            raise RuntimeError
        set_winsize(fd, 24, 51)
        os.set_blocking(fd, False)
        self._sel.register(
            fd, selectors.EVENT_READ | selectors.EVENT_WRITE, self._handle_pty
        )
        self._fd = fd

    def send(self, data: bytes) -> None:
        raise NotImplemented

    def recv(self, buffersize: int) -> bytes:
        raise NotImplemented

    def send_packet(self, data: bytes) -> None:
        """
        rfc1055 SLIP send_packet
        """
        logger.debug(">>>---")
        self.set_watchdog()
        self.send(
            self.END
            + data.replace(self.ESC, self.ESC + self.ESC_ESC).replace(
                self.END, self.ESC + self.ESC_END
            )
            + self.END
        )
        logger.debug(">>> %s", data)

    def recv_packet(self) -> bytes:
        """
        rfc1055 SLIP recv_packet
        """
        received = io.BytesIO()
        logger.debug("<<<---")
        while True:
            self.set_watchdog()
            char = self.recv(1)
            if len(char) == 0:
                raise SystemExit
            if char == self.END:
                if received.tell() != 0:
                    data = received.getvalue()
                    logger.debug("<<< %s", data)
                    return data
            elif char == self.ESC:
                esc_char = self.recv(1)
                if esc_char == self.ESC_ESC:
                    received.write(self.ESC)
                elif esc_char == self.ESC_END:
                    received.write(self.END)
                else:
                    received.write(esc_char)
            else:
                received.write(char)

    @classmethod
    def from_socket(cls, path: str) -> "HostController":
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(path)
        sock.listen(1)
        conn, _ = sock.accept()
        return SocketHostController(conn)

    @classmethod
    def from_tty(cls, path: str) -> "HostController":
        conn = serial.Serial(path, rtscts=True)  # type: ignore
        return SerialHostController(conn)

    def get_keys(self) -> bytes:
        self.send_packet(self.GET_KEYS)
        recv = self.recv_packet()
        if recv.startswith(self.GET_KEYS):
            return recv[2:]
        return b""

    def send_pty(self, data: bytes) -> None:
        self.send_packet(self.SEND_PTY + data)
        self.recv_packet()

    def signal_int(self) -> None:
        logger.info("resetting remote side")
        self.send_packet(self.SIG_INT)

    def disable(self) -> None:
        self._enabled = False
        signal.alarm(0)

    def set_watchdog(self) -> None:
        if self._enabled:
            signal.alarm(self.IO_TIMEOUT)

    def serve(self) -> None:
        self.send_packet(self.GET_CAPS)
        logger.info("remote: %s", self.recv_packet()[2:].strip(b"\x00").decode())

        self._enabled = True
        while self._enabled:
            for key, mask in self._sel.select():
                callback = key.data
                callback(key.fileobj, mask)

            keystrokes = self.get_keys()
            if keystrokes:
                self._kbd.extend(keystrokes)  # type: ignore
                logger.info("received keystrokes: %s", keystrokes)
                continue

            while self._pty:
                data = bytes(self._pty)  # type: ignore
                self.send_pty(data[: self.BUFSIZE])
                self._pty.clear()
                self._pty.extend(data[self.BUFSIZE :])  # type: ignore
                logger.info("sent pty: %s", data)

        self.signal_int()


class SocketHostController(HostController):
    _conn: socket.socket

    def send(self, data: bytes) -> None:
        self._conn.send(data)

    def recv(self, buffersize: int) -> bytes:
        return self._conn.recv(buffersize)


class SerialHostController(HostController):
    _conn: serial.Serial
    _last_direction: Direction

    SWAP_DELAY = 0.1

    def __init__(self, conn: TConn) -> None:
        super(SerialHostController, self).__init__(conn)
        self._last_direction = Direction.UND

    def send(self, data: bytes) -> None:
        if self.SWAP_DELAY and self._last_direction != Direction.OUT:
            time.sleep(self.SWAP_DELAY)
            self._last_direction = Direction.OUT
        self._conn.write(data)

    def recv(self, buffersize: int) -> bytes:
        if self.SWAP_DELAY and self._last_direction != Direction.IN:
            time.sleep(self.SWAP_DELAY)
            self._last_direction = Direction.IN
        return self._conn.read(buffersize)


def setup_shell(terminal: str) -> None:
    env = {
        "TERM": terminal,
    }
    os.execve("/bin/sh", ["/bin/sh"], env)


def main(debug: bool = False) -> None:
    parser = argparse.ArgumentParser(
        description="USB-like terminal server for half-duplex serial connections"
    )
    parser.add_argument("--debug", action="store_true", default=debug)
    parser.add_argument("--device", "-D")
    parser.add_argument("--reset", "-R", action="store_true")
    parser.add_argument("--terminal", default="vt52")

    args = parser.parse_args()
    if not args.device:
        parser.print_help()
        raise SystemExit

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if not args.reset:
        (pid, fd) = pty.fork()
        if pid == 0:
            # child process
            return setup_shell(args.terminal)

    if os.path.exists(args.device):
        mode = os.stat(args.device).st_mode
        if stat.S_ISSOCK(mode):
            os.unlink(args.device)
            ctrl = HostController.from_socket(args.device)
        elif stat.S_ISCHR(mode):
            ctrl = HostController.from_tty(args.device)
        else:
            raise ValueError
    else:
        ctrl = HostController.from_socket(args.device)

    if args.reset:
        ctrl.signal_int()
        raise SystemExit

    logger.info("received connection: %s", ctrl._conn)
    ctrl.attach(fd)

    def sigint_handler(*args) -> None:
        if ctrl.graceful:
            ctrl.graceful = False
            logger.info("received SIGINT")
            ctrl.disable()
        else:
            logger.error("SIGINT")
            raise SystemExit

    def sigalrm_handler(*args) -> None:
        if ctrl.graceful:
            ctrl.graceful = False
            logger.warning("timeout, trying to recover")
            # logger.warning("timeout, graceful shutdown")
            # ctrl.signal_int()
            ctrl.send_packet(ctrl.GET_CAPS)
            ctrl.graceful = True
        else:
            logger.error("timeout")
            raise SystemError

    ctrl.graceful = True
    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGALRM, sigalrm_handler)
    ctrl.serve()


if __name__ == "__main__":
    main()
