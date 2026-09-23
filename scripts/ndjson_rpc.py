"""Shared NDJSON-over-unix-socket RPC plumbing for board helper scripts.

The server handles one request per connection and then closes it, so this module
owns socket resolution, connection, send, and read-to-first-newline behavior.

    request:  {"id":"<str>","method":"<name>","params":{...}}

Stdlib only.
"""
from __future__ import annotations

import json
import os
import socket
from typing import Any, Iterable

CHUNK_SIZE = 4096


def socket_path(env_vars: Iterable[str], default: str) -> str:
    """First non-empty value among `env_vars`, else the expanded `default`."""
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            return value
    return os.path.expanduser(default)


def parse_params(raw: str) -> Any:
    """Decode the CLI's JSON params argument. Raises json.JSONDecodeError."""
    return json.loads(raw)


def request_line(path: str, request_id: str, method: str, params: Any) -> str:
    """Send one request and return the first response line (`""` if none).

    Raises OSError when the socket cannot be reached, which each front end
    reports with its own program-prefixed message.
    """
    request = {"id": request_id, "method": method, "params": params}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(path)
        connection.sendall((json.dumps(request) + "\n").encode("utf-8"))
        buffer = b""
        while b"\n" not in buffer:
            chunk = connection.recv(CHUNK_SIZE)
            if not chunk:
                break
            buffer += chunk
    return buffer.split(b"\n", 1)[0].decode("utf-8", "replace")
