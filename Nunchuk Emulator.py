import threading
import socket
import base64
import hashlib
import json
from flask import Flask, render_template_string
from flask_socketio import SocketIO

INVERT_X_AXIS = True  # Set to False to disable X axis inversion

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

PHONE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no"/>
<title>UFO WATCHER PHONE CONTROLLER</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
  body { background:#020205; color:#00f0ff; user-select:none; font-family:'Share Tech Mono', monospace; text-align:center; margin:0; height:100vh; overflow:hidden; }
  .hud { background:rgba(0,20,40,0.82); max-width:360px; margin:4em auto; border:2px solid #00f0ff; border-radius:28px; box-shadow:0 0 30px #00f0ff44; padding:2em 1.5em; }
  .heading { font-family:'Orbitron', sans-serif; letter-spacing:0.15em; color:#fff; font-size:2.2em; margin-bottom:1em; }
  .button-fire, #btnRequest { user-select:none; }
  .button-fire { 
    width:180px; height:180px; border-radius:90px; background:#00f0ff; color:#020205; font-family:'Orbitron', sans-serif; 
    font-weight:bold; font-size:3em; line-height:180px; box-shadow:0 0 20px #00ffff; margin-bottom:1.4em; border:none; display:none; 
  }
  #btnRequest { 
    font-size: 1.4em; padding: 0.7em 1.2em; background:#007fa8; border:none; border-radius:12px; color:#00f0ff; 
    cursor:pointer; font-family:'Share Tech Mono', monospace; margin-bottom:1em; 
  }
  .status { font-family:'Share Tech Mono', monospace; font-size:1em; color:#0ff; letter-spacing:.12em; }
  #fullScreenFire { 
    position: fixed; top:0; left:0; width:100vw; height:100vh; background:#00f0ff; color:#020205; font-family:'Orbitron', 
    sans-serif; font-size:7em; display:none; justify-content:center; align-items:center; user-select:none; 
  }
</style>
</head>
<body>
<div class="hud">
  <div class="heading drop-shadow-[0_0_10px_rgba(0,240,255,0.8)]">UFO WATCHER</div>
  <button id="btnRequest" onclick="requestPermission()">Enable Motion Control</button>
  <div class="status" id="status">Motion permission not granted</div>
</div>

<button id="fullScreenFire">FIRE</button>

<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
<script>
  let joy = {jx:128, jy:128, ax:512, ay:512, c:0, z:0};
  const statusEl = document.getElementById('status');
  const btnRequest = document.getElementById('btnRequest');
  const fullScreenFire = document.getElementById('fullScreenFire');
  const INVERT_X_AXIS = {{ invert_x | lower }};
  const wsio = io();

  wsio.on('connect', () => statusEl.innerText = 'Connected, waiting for accelerometer permission.');
  wsio.on('disconnect', () => statusEl.innerText = 'Disconnected');

  function mapAccelToJoy(rawX) {
    let valX = INVERT_X_AXIS ? -rawX : rawX;
    let val = Math.round(128 + (valX || 0) * 40);
    joy.jx = Math.min(255, Math.max(0, val));
    send();
  }

  function listenMotion() {
    statusEl.innerText = 'Motion enabled - move your device';
    btnRequest.style.display = 'none';
    fullScreenFire.style.display = 'flex';

    // Track touch and mouse events on full screen fire button
    fullScreenFire.addEventListener('touchstart', () => press('z', 1), { passive: true });
    fullScreenFire.addEventListener('touchend', () => press('z', 0), { passive: true });
    fullScreenFire.addEventListener('mousedown', () => press('z',1));
    fullScreenFire.addEventListener('mouseup', () => press('z',0));

    window.addEventListener('devicemotion', event => {
      if (event.accelerationIncludingGravity) {
        mapAccelToJoy(event.accelerationIncludingGravity.x);
      }
    }, true);
  }

  async function requestPermission() {
    statusEl.innerText = 'Requesting accelerometer permission...';
    if(typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function') {
      try {
        let perm = await DeviceMotionEvent.requestPermission();
        if (perm === 'granted') {
          listenMotion();
        } else {
          statusEl.innerText = 'Permission denied, please allow to use motion control.';
        }
      } catch(e) {
        statusEl.innerText = 'Permission request error, falling back to legacy API.';
        listenMotion();
      }
    } else {
      listenMotion();
    }
  }

  function send() {
    wsio.emit('nunchuk', joy);
  }

  function press(button,state) {
    joy[button] = state;
    send();
  }
</script>
</body>
</html>
"""

@app.route('/phone')
def phone():
    return render_template_string(PHONE_HTML, invert_x=str(INVERT_X_AXIS).lower())

GAME_CLIENTS = []
lock = threading.Lock()

@socketio.on('nunchuk')
def on_nunchuk(data):
    msg = json.dumps(data)
    with lock:
        for ws in GAME_CLIENTS[:]:
            try:
                ws.sendall(to_ws_frame(msg))
            except:
                GAME_CLIENTS.remove(ws)

def to_ws_frame(msg):
    b = msg.encode('utf-8')
    length = len(b)
    if length < 126:
        return bytes([0x81, length]) + b
    elif length < 65536:
        return bytes([0x81, 126]) + length.to_bytes(2,'big') + b
    else:
        return bytes([0x81, 127]) + length.to_bytes(8,'big') + b

def ws_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", 81))
    sock.listen(5)
    print("WebSocket server running on port 81")
    while True:
        conn, addr = sock.accept()
        handshake = b""
        while b'\r\n\r\n' not in handshake:
            handshake += conn.recv(1024)
        key = None
        for line in handshake.decode(errors='ignore').split("\r\n"):
            if "Sec-WebSocket-Key" in line:
                key = line.split(":")[1].strip()
        if key:
            accept_key = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
            )
            conn.send(response.encode())
            with lock:
                GAME_CLIENTS.append(conn)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == '__main__':
    threading.Thread(target=ws_server, daemon=True).start()
    ip = get_local_ip()
    print(f"Phone controller URL: http://{ip}:5000/phone")
    print(f"Game websocket connects to: ws://{ip}:81")
    socketio.run(app, host='0.0.0.0', port=5000)
