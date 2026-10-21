"""Opt-in Python-process loopback fence for the local UAT launcher.

Not an OS sandbox: native binaries need host controls for an adversarial setting.
Only destination metadata is recorded, never payloads or document names.
"""
import ipaddress
import json
import os
import socket

if os.environ.get('LICITIA_RUNTIME_LOCAL_ONLY') == '1':
    audit = os.environ.get('LICITIA_NETWORK_AUDIT')
    def verify(address):
        if not isinstance(address, tuple):  # AF_UNIX filesystem socket.
            return
        host = address[0]
        if isinstance(host, bytes):
            host = host.decode('ascii')
        try:
            allowed = host == 'localhost' or ipaddress.ip_address(host).is_loopback
        except ValueError:
            allowed = False
        if audit:
            fd = os.open(audit, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, 'w') as stream:
                stream.write(json.dumps(dict(host=host,port=address[1],allowed=allowed))+'\n')
        if not allowed:
            raise OSError('LICITIA_EXTERNAL_NETWORK_DISABLED')
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo
    original_sendto = socket.socket.sendto
    def connect(self, address):
        verify(address)
        return original_connect(self, address)
    def connect_ex(self, address):
        verify(address)
        return original_connect_ex(self, address)
    def getaddrinfo(host, port, *args, **kwargs):
        verify((host, port))
        return original_getaddrinfo(host, port, *args, **kwargs)
    def sendto(self, data, *args):
        verify(args[-1])
        return original_sendto(self, data, *args)
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.socket.sendto = sendto
    socket.getaddrinfo = getaddrinfo
