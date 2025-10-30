#!/usr/bin/env python3
"""Test client for RuneCore_Sentinel dev receiver.

Sends a sample CBOR payload (length-prefixed: 4-byte big-endian length + payload)
via Windows named pipe, Unix domain socket, or TCP for quick integration testing.

Usage examples:
  # Windows named pipe
  python test_client.py --pipe \\.\pipe\runecore-sentinel

  # Unix socket
  python3 test_client.py --unix-socket /tmp/runecore-sentinel.sock

  # TCP
  python3 test_client.py --tcp 127.0.0.1:6000
"""

import argparse
import struct
import time
import socket
import sys

try:
    import cbor2
except Exception:
    print('Missing dependency: cbor2. Install with: pip install -r dev_requirements.txt')
    raise


def make_sample_payload():
    ts = int(time.time() * 1000)
    obj = {
        'ts': ts,
        'host': 'test-client',
        'cpu_usage': 3.14,
        'total_memory': 8192,
        'used_memory': 1234,
    }
    return cbor2.dumps(obj)


def send_tcp(addr, payload):
    host, port = addr.split(':')
    port = int(port)
    with socket.create_connection((host, port), timeout=5) as s:
        length = struct.pack('>I', len(payload))
        s.sendall(length + payload)
    print(f'Sent payload to TCP {addr}')


def send_unix_socket(path, payload):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    length = struct.pack('>I', len(payload))
    s.sendall(length + payload)
    s.close()
    print(f'Sent payload to unix socket {path}')


def send_named_pipe(pipe_name, payload):
    # pipe_name should be full path like \\\\.\\pipe\\name or just name
    try:
        import win32file
        import win32pipe
        import pywintypes
    except Exception:
        print('pywin32 is required for named pipe support. Install with: pip install pywin32')
        raise

    full_name = pipe_name
    if not full_name.startswith('\\\\.\\pipe\\'):
        full_name = r'\\.\\pipe\\' + pipe_name

    # Open existing pipe
    handle = None
    try:
        # GENERIC_WRITE: 0x40000000
        handle = win32file.CreateFile(
            full_name,
            win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )
        length = struct.pack('>I', len(payload))
        win32file.WriteFile(handle, length + payload)
        print(f'Sent payload to named pipe {full_name}')
    finally:
        if handle:
            try:
                win32file.CloseHandle(handle)
            except Exception:
                pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pipe', help='Windows named pipe name (e.g. \\\\.\\pipe\\runecore-sentinel or simply runecore-sentinel)')
    p.add_argument('--unix-socket', help='Unix domain socket path')
    p.add_argument('--tcp', help='TCP host:port')
    args = p.parse_args()

    payload = make_sample_payload()

    if args.pipe:
        send_named_pipe(args.pipe, payload)
    elif args.unix_socket:
        send_unix_socket(args.unix_socket, payload)
    elif args.tcp:
        send_tcp(args.tcp, payload)
    else:
        print('Specify --pipe or --unix-socket or --tcp')
        sys.exit(2)


if __name__ == '__main__':
    main()
