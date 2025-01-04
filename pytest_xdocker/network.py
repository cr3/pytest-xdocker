"""Networking tools."""

import socket

import netifaces


def get_host_ip():
    """Get an IP on this host.

    The function tries to use the IP bound to the docker0 interface
    which should be available on Linux and, if that fails, it defaults
    to the default
    en0-en9 interfaces which should be available on MacOS.
    """
    for interface in netifaces.interfaces():
        try:
            addr = netifaces.ifaddresses(interface)[2][0]["addr"]
            if addr != "127.0.0.1":
                return addr
        except (ValueError, KeyError):
            pass

    raise Exception("Network interfaces not found")


def get_open_port():
    """Get an unused port.

    There is a race condition where the port could be taken after this
    method closes the socket but before the consumer opens it. Since
    this is just for test fixtures I'm not worrying about that.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port
