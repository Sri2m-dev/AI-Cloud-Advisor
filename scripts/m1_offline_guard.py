"""Explicit pytest plugin: forbid network, database connections and dotenv reads."""

import socket
import sqlite3
import sys

import dotenv

_ORIGINAL_CONNECT = socket.socket.connect


def guarded_connect(sock, address):
    caller = sys._getframe(1)
    # Windows asyncio uses stdlib socketpair over ephemeral loopback sockets.
    # Permit only that internal IPC construction, never a service connection.
    if (
        caller.f_code.co_name == "socketpair"
        and caller.f_code.co_filename == socket.__file__
        and isinstance(address, tuple)
        and address[0] in {"127.0.0.1", "::1"}
    ):
        return _ORIGINAL_CONNECT(sock, address)
    return forbidden()


def forbidden(*args, **kwargs):
    raise AssertionError("M1 guard: network/database activity is forbidden")


def pytest_load_initial_conftests(early_config, parser, args):
    dotenv.load_dotenv = lambda *a, **kw: False
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = forbidden
    socket.create_connection = forbidden
    sqlite3.connect = forbidden
    try:
        import psycopg2

        psycopg2.connect = forbidden
    except ImportError:
        pass
    try:
        import supabase

        supabase.create_client = forbidden
    except ImportError:
        pass
