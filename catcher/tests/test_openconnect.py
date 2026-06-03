import json
import socket
import threading
import time

from catcher.openconnect import OpenConnectListener


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_listener_parses_newline_and_concatenated_json():
    received = []
    lock = threading.Lock()

    def on_message(obj, source):
        with lock:
            received.append(obj)

    port = _free_port()
    listener = OpenConnectListener(port=port, on_message=on_message,
                                   handedness="RH")
    listener.start()
    try:
        # wait for the server to be listening
        deadline = time.time() + 5.0
        while not listener.is_listening and time.time() < deadline:
            time.sleep(0.02)
        assert listener.is_listening

        # fake R50 dials the listener (like the real device connecting in)
        client = socket.create_connection(("127.0.0.1", port), timeout=5)
        client.settimeout(5)

        # server must send a 201 handshake on connect
        handshake = b""
        client.settimeout(5)
        while b"\n" not in handshake:
            handshake += client.recv(4096)
        first = json.loads(handshake.split(b"\n")[0].decode("utf-8"))
        assert first["Code"] == 201
        assert first["Player"]["Handed"] == "RH"

        # send TWO json objects concatenated with NO delimiter, plus a
        # newline-delimited third — exercises the tolerant stream parser.
        msg1 = {"ShotNumber": 1, "BallData": {"Speed": 100.0},
                "ShotDataOptions": {"IsHeartBeat": False}}
        msg2 = {"ShotNumber": 2, "BallData": {"Speed": 110.0},
                "ShotDataOptions": {"IsHeartBeat": False}}
        msg3 = {"ShotDataOptions": {"IsHeartBeat": True}}
        payload = (json.dumps(msg1) + json.dumps(msg2)
                   + json.dumps(msg3) + "\n").encode("utf-8")
        client.sendall(payload)

        # each inbound message is acked with a 200; read until we've seen 3 acks
        acks = 0
        buf = b""
        client.settimeout(5)
        deadline = time.time() + 5.0
        while acks < 3 and time.time() < deadline:
            try:
                data = client.recv(4096)
            except socket.timeout:
                break
            if not data:
                break
            buf += data
            acks = buf.count(b'"Code": 200') + buf.count(b'"Code":200')

        client.close()

        # the listener should have emitted all three parsed messages
        deadline = time.time() + 5.0
        while len(received) < 3 and time.time() < deadline:
            time.sleep(0.02)
        with lock:
            got = list(received)
        assert len(got) == 3
        assert got[0]["ShotNumber"] == 1
        assert got[1]["ShotNumber"] == 2
        assert got[2]["ShotDataOptions"]["IsHeartBeat"] is True
    finally:
        listener.stop()
