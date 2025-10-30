#!/usr/bin/env python3
"""Dev receiver/adapter for RuneCore_Sentinel

Listens on a local IPC endpoint (Unix domain socket or TCP) and accepts length-prefixed CBOR frames
(4-byte big-endian length + payload). Decodes CBOR into JSON and forwards it to CoreMemory's
HTTP API (/v1/memories) as a JSON memory entry for easy integration testing.

Usage examples:
  # Linux/macOS (unix socket)
  python dev_receiver.py --unix-socket /tmp/runecore-sentinel.sock --core http://127.0.0.1:5010

  # Windows (TCP fallback)
  python dev_receiver.py --tcp 127.0.0.1:6000 --core http://127.0.0.1:5010

Notes:
- Named pipe support for Windows can be added if pywin32 is available; the script falls back to TCP.
- This is a development helper and not intended for production use.
"""

import argparse
import socket
import struct
import sys
import os
import json
import time

try:
    import requests
except Exception:
    print("Missing dependency: requests. Install with: pip install -r dev_requirements.txt")
    raise

try:
    import cbor2
except Exception:
    print("Missing dependency: cbor2. Install with: pip install -r dev_requirements.txt")
    raise


def forward_to_core(core_url, payload_obj):
    url = core_url.rstrip('/') + '/v1/memories'
    body = {'text': 'sentinel.metrics', 'metadata': payload_obj}
    try:
        r = requests.post(url, json=body, timeout=5)
        r.raise_for_status()
        print(f"Forwarded to CoreMemory: {r.status_code}")
    except Exception as e:
        print(f"Failed to forward to CoreMemory: {e}")


def handle_connection(conn, core_url):
    """Reads length-prefixed frames from a connected socket and forwards them."""
    with conn:
        while True:
            # read 4 bytes length
            data = b''
            while len(data) < 4:
                chunk = conn.recv(4 - len(data))
                if not chunk:
                    return
                data += chunk
            length = struct.unpack('>I', data)[0]
            # read payload
            payload = b''
            while len(payload) < length:
                chunk = conn.recv(min(4096, length - len(payload)))
                if not chunk:
                    print('connection closed while reading payload')
                    return
                payload += chunk
            try:
                obj = cbor2.loads(payload)
            except Exception as e:
                print(f"Failed to decode CBOR payload: {e}")
                # still try to forward base64
                obj = {'_cbor_base64': payload.hex()}
            print(f"Received payload: {obj}")
            forward_to_core(core_url, obj)


def run_unix_socket(path, core_url):
    # remove stale socket
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    srv.listen(5)
    print(f"Listening on unix socket {path}")
    try:
        while True:
            conn, _ = srv.accept()
            print("Accepted connection")
            handle_connection(conn, core_url)
    finally:
        try:
            srv.close()
        except Exception:
            pass
        try:
            os.remove(path)
        except Exception:
            pass


def run_tcp(bind_addr, core_url):
    host, port = bind_addr.split(':')
    port = int(port)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(5)
    print(f"Listening on TCP {host}:{port}")
    try:
        while True:
            conn, addr = srv.accept()
            print(f"Accepted TCP connection from {addr}")
            handle_connection(conn, core_url)
    finally:
        try:
            srv.close()
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--unix-socket', help='Path to unix domain socket to listen on (Linux/macOS)')
    p.add_argument('--tcp', help='Bind address for TCP in form host:port (Windows dev fallback)')
    p.add_argument('--core', default='http://127.0.0.1:5010', help='CoreMemory base URL (default http://127.0.0.1:5010)')
    args = p.parse_args()

    if args.unix_socket:
        run_unix_socket(args.unix_socket, args.core)
    elif args.tcp:
        run_tcp(args.tcp, args.core)
    else:
        print('Specify --unix-socket or --tcp')
        sys.exit(2)


if __name__ == '__main__':
    main()
