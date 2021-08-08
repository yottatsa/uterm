#!/usr/bin/python3

import argparse
import io
import logging
import os
import pty
import socket
import stat
from typing import Union

import serial

logger: logging.Logger = logging.getLogger(__name__)


TConn = Union[socket.socket, serial.Serial]


class HostController(object):
    GET_KEYS = b"\x01\x01"
    SEND_SCREEN = b"\x02\x02"

    # rfc1055 SLIP special character codes
    END = b"\xc0"  # 0o300 indicates end of packet
    ESC = b"\xdb"  # 0o333 indicates byte stuffing
    ESC_END = b"\xdd"  # 0o334 ESC ESC_END means END data byte
    ESC_ESC = b"\xde"  # 0o335 ESC ESC_ESC means ESC data byte

    _conn: TConn
    _io: io.BytesIO
    _fd: int = -1

    def __init__(self, conn: TConn) -> None:
        self._conn = conn
        self._io = io.BytesIO()

    def attach(self, fd: int) -> None:
        self._fd = fd

    def send(self, data: bytes) -> None:
        raise NotImplemented

    def recv(self, buffersize: int) -> bytes:
        raise NotImplemented

    def send_packet(self, data: bytes) -> None:
        """
        rfc1055 SLIP send_packet
        """
        logger.debug(">>> %s", data)
        self.send(
            self.END
            + data.replace(self.ESC, self.ESC + self.ESC_ESC).replace(
                self.END, self.ESC + self.ESC_END
            )
            + self.END
        )

    def recv_packet(self) -> bytes:
        """
        rfc1055 SLIP recv_packet
        """
        received = io.BytesIO()
        while True:
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

    def send_screen(self) -> None:
        self.send_packet(self.SEND_SCREEN + self._io.getvalue())
        self.recv_packet()

    def _process_screen(self):
        self._io.write(os.read(self._fd, 1))
        self.send_screen()

    def _process_keys(self):
        keystrokes = self.get_keys()
        if keystrokes:
            os.write(self._fd, keystrokes)

    def serve(self) -> None:
        while True:
            # use poll for fd
            self._process_screen()
            self._process_keys()


class SocketHostController(HostController):
    _conn: socket.socket

    def send(self, data: bytes) -> None:
        self._conn.send(data)

    def recv(self, buffersize: int) -> bytes:
        return self._conn.recv(buffersize)


class SerialHostController(HostController):
    _conn: serial.Serial


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
    parser.add_argument("--terminal", default="vt100")

    args = parser.parse_args()
    if not args.device:
        parser.print_help()
        raise SystemExit

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

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

    logger.debug("Connection estabished with %s", ctrl._conn)
    ctrl.attach(fd)
    ctrl.serve()


if __name__ == "__main__":
    main(True)
