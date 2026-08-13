"""Pretend to be an OpenFlight launch monitor, so the integration can be tested
with no radar hardware.

A real OpenFlight rig talks to GarageTEC on TWO channels, and this script fakes
both:

  1. GSPro OpenConnect V1 over TCP 921 (it dials us) -- the canonical shot.
  2. A Socket.IO server on port 8080 emitting `shot` events -- the additive
     "enrichment" record carrying per-field source/confidence, which the
     OpenConnect wire format cannot express.

It deliberately sends a realistic baseline rig: launch angle MEASURED (the
IWR6843 angle radar), spin MODELLED (spin_rpm present but spin_rpm_measured
None), and no club speed at all. So you should see GarageTEC grade the launch
angle but mark the spin as an estimate, which is the whole point of the feature.

Shot 1 arrives before GarageTEC has discovered us, so it gets no enrichment --
that is realistic and exercises the conservative fallback. Later shots exercise
both correlation orderings (enrichment-first and shot-first).

Usage (with the GarageTEC dev server already running):
    python scripts/simulate_openflight.py
    python scripts/simulate_openflight.py --shots 5
"""
import argparse
import asyncio
import json
import socket
import sys

try:
    import socketio
    import uvicorn
except ImportError:
    sys.exit("needs python-socketio and uvicorn: "
             'python -m pip install "python-socketio[client]" uvicorn')

OPENCONNECT_PORT = 921
WEB_PORT = 8080          # OpenFlight's Flask/Socket.IO default
DEVICE_ID = "OpenFlight"  # what our device profile keys off

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
asgi_app = socketio.ASGIApp(sio)
_client_connected = asyncio.Event()


@sio.event
async def connect(sid, environ):
    print("  [enrichment] GarageTEC connected to our Socket.IO channel")
    _client_connected.set()


@sio.event
async def disconnect(sid):
    print("  [enrichment] GarageTEC disconnected")


def wire_shot(n: int, ball_speed: float) -> dict:
    """An OpenConnect shot exactly as OpenFlight sends it: real measurements,
    0.0 padding for everything it did not measure, ContainsClubData False."""
    return {
        "DeviceID": DEVICE_ID, "Units": "Yards", "ShotNumber": n,
        "APIversion": "1",
        "BallData": {
            "Speed": ball_speed, "SpinAxis": 0.0, "TotalSpin": 7000.0,
            "BackSpin": 7000.0, "SideSpin": 0.0, "HLA": 0.0,
            "VLA": 16.3, "CarryDistance": 171.0,
        },
        # Always sent, always padded when unmeasured.
        "ClubData": {"Speed": 0.0, "AngleOfAttack": 0.0,
                     "FaceToTarget": 0.0, "Path": 2.1},
        "ShotDataOptions": {
            "ContainsBallData": True, "ContainsClubData": False,
            "LaunchMonitorIsReady": True, "LaunchMonitorBallDetected": True,
            "IsHeartBeat": False,
        },
    }


def enrichment(ball_speed: float) -> dict:
    """The truth OpenFlight keeps for itself: launch angle measured by the angle
    radar, spin only modelled (no measured twin), club speed genuinely absent."""
    return {
        "ball_speed_mph": ball_speed,
        "club_speed_mph": None,             # never detected -> ABSENT
        "estimated_carry_yards": 171,
        "carry_range": [166, 176],
        "launch_angle_vertical": 16.3,
        "launch_angle_vertical_source": "iwr6843",
        "launch_angle_vertical_confidence": 0.91,   # -> MEASURED
        "launch_angle_horizontal": None,
        "spin_rpm": 7000,
        "spin_rpm_measured": None,          # modelled -> ESTIMATED
        "spin_confidence": None,
        "spin_source": "per_club_model",
        "spin_axis_deg": None,
        "club_path_deg": 2.1,
    }


def send(sock, payload: dict):
    sock.sendall(json.dumps(payload).encode("utf-8"))
    try:
        sock.settimeout(3)
        return sock.recv(4096).decode("utf-8", "replace").strip()
    except OSError:
        return "(no ack)"


async def main(n_shots: int):
    config = uvicorn.Config(asgi_app, host="0.0.0.0", port=WEB_PORT,
                            log_level="error")
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())
    await asyncio.sleep(1)
    print(f"fake OpenFlight enrichment channel listening on :{WEB_PORT}")

    try:
        sock = socket.create_connection(("127.0.0.1", OPENCONNECT_PORT), timeout=5)
    except OSError as e:
        sys.exit(f"cannot reach GarageTEC on TCP {OPENCONNECT_PORT}: {e}\n"
                 "Is the dev server (or GarageTEC.exe) running?")

    sock.settimeout(3)
    print("handshake from GarageTEC:", sock.recv(4096).decode().strip())

    speed = 121.4
    for n in range(1, n_shots + 1):
        speed = round(speed + 0.7, 1)     # distinct speeds = clean correlation

        if n == 1:
            print(f"\nshot {n}: wire only "
                  "(GarageTEC has not discovered us yet -> no enrichment)")
            print("  ack:", send(sock, wire_shot(n, speed)))
            print("  waiting for GarageTEC to dial our enrichment channel...")
            try:
                await asyncio.wait_for(_client_connected.wait(), timeout=20)
            except asyncio.TimeoutError:
                print("  WARNING: it never connected. Enrichment will be absent "
                      "for every shot; check the Connect screen status row.")
        elif n % 2 == 0:
            print(f"\nshot {n}: enrichment FIRST, then the wire shot "
                  "(buffer-claim path)")
            await sio.emit("shot", {"shot": enrichment(speed), "stats": {}})
            await asyncio.sleep(0.3)
            print("  ack:", send(sock, wire_shot(n, speed)))
        else:
            print(f"\nshot {n}: wire shot FIRST, then enrichment "
                  "(late-attach path)")
            print("  ack:", send(sock, wire_shot(n, speed)))
            await asyncio.sleep(0.3)
            await sio.emit("shot", {"shot": enrichment(speed), "stats": {}})

        await asyncio.sleep(1.5)

    print("\ndone. Leaving the enrichment channel up for 5s, then exiting.")
    await asyncio.sleep(5)
    sock.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shots", type=int, default=3,
                    help="how many shots to send (default 3)")
    args = ap.parse_args()
    try:
        asyncio.run(main(args.shots))
    except KeyboardInterrupt:
        pass
