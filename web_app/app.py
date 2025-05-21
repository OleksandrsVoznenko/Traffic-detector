import os, time, json, pathlib, hashlib, sys, multiprocessing as mp
from flask import Flask, render_template, Response, jsonify, \
                  send_from_directory, stream_with_context

#  projektu direktorijas
ROOT       = pathlib.Path(__file__).parent.parent
FRAMES_DIR = pathlib.Path(os.getenv("FRAMES_DIR",  ROOT / "frames"))
VIOL_DIR   = pathlib.Path(os.getenv("VIOLATIONS_DIR", ROOT / "violations"))

FRAMES_DIR.mkdir(parents=True, exist_ok=True)
VIOL_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")

#  detektora procesa kontrole
_DET_PROC: mp.Process | None = None    # pašreizējais apakšprocess

def _is_running() -> bool:
    return _DET_PROC is not None and _DET_PROC.is_alive()

def _detector_worker() -> None:
    """
    Darbojas atsevišķā procesā. Visi cv2.imshow / namedWindow / waitKey ir apspiesti.
    """
    import sys, os, cv2, pathlib
    sys.path.insert(0, str(ROOT))      # skatiet projekta moduļus

    # Filtrs: OpenCV bez logiem
    cv2.imshow      = lambda *a, **k: None
    cv2.namedWindow = lambda *a, **k: None
    cv2.waitKey     = lambda *a, **k: 1

    os.environ["FRAMES_DIR"]     = str(FRAMES_DIR)
    os.environ["VIOLATIONS_DIR"] = str(VIOL_DIR)
    pathlib.Path(VIOL_DIR).mkdir(parents=True, exist_ok=True)

    from app_utils.stream_capture import StreamCapture
    StreamCapture().start_capture()    # bezgalīga cilpa

def _start_detector():
    global _DET_PROC
    if _is_running():
        return
    _DET_PROC = mp.Process(target=_detector_worker, daemon=True)
    _DET_PROC.start()

def _stop_detector():
    global _DET_PROC
    if not _is_running():
        _DET_PROC = None
        return
    _DET_PROC.terminate()
    _DET_PROC.join(timeout=2)
    _DET_PROC = None
    for p in FRAMES_DIR.glob("*.jpg"):
        try:
            p.unlink()
        except Exception:
            pass

#  palīgi MJPEG straumei
def _latest_frame():
    try:
        return max(FRAMES_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
    except ValueError:
        return None

def _safe_read(p: pathlib.Path, retries: int = 3) -> bytes | None:
    for _ in range(retries):
        try:
            d = p.read_bytes()
            if d[:2] == b"\xff\xd8" and d[-2:] == b"\xff\xd9":
                return d
        except Exception:
            pass
        time.sleep(0.01)

def gen_mjpeg():
    last = None
    while True:
        p = _latest_frame()
        if p:
            d = _safe_read(p)
            if d:
                h = hashlib.md5(d).digest()
                if h != last:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
                           d + b"\r\n")
                    last = h
        time.sleep(0.03)

# lapas
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    return Response(stream_with_context(gen_mjpeg()),
                    mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-cache"},
                    direct_passthrough=True)

#  Pogas API
@app.route("/api/detector_status")
def api_detector_status():
    return jsonify({"running": _is_running()})


@app.route("/api/detector_toggle", methods=["POST"])
def api_detector_toggle():
    (_stop_detector if _is_running() else _start_detector)()
    return jsonify({"running": _is_running()})

# Esošās API
@app.route("/api/violations")
def api_violations():
    imgs = sorted(VIOL_DIR.glob("*.jpg"),
                  key=lambda p: p.stat().st_mtime, reverse=True)[:200]
    return jsonify([{"file": p.name,
                     "ts": time.strftime("%Y-%m-%d %H:%M:%S",
                                         time.localtime(p.stat().st_mtime))}
                    for p in imgs])


@app.route("/api/violations_stats")
def api_violations_stats():
    now = time.time()
    labels, values = [], []
    for i in range(6, -1, -1):
        d = time.strftime("%d.%m", time.localtime(now - i * 86400))
        labels.append(d)
        values.append(0)
    idx = {d: n for n, d in enumerate(labels)}
    for p in VIOL_DIR.glob("*.jpg"):
        d = time.strftime("%d.%m", time.localtime(p.stat().st_mtime))
        if d in idx:
            values[idx[d]] += 1
    return jsonify({"labels": labels, "values": values})


@app.route("/viol_stream")
def viol_stream():
    def stream():
        last = 0
        while True:
            try:
                newest = max(VIOL_DIR.glob("*.jpg"),
                             key=lambda p: p.stat().st_mtime)
            except ValueError:
                time.sleep(1)
                continue
            m = newest.stat().st_mtime
            if m != last:
                yield "data: " + json.dumps(
                    {"file": newest.name,
                     "ts": time.strftime("%Y-%m-%d %H:%M:%S",
                                         time.localtime(m))},
                    ensure_ascii=False) + "\n\n"
                last = m
            time.sleep(1)
    return Response(stream(), mimetype="text/event-stream")


@app.route("/violation_img/<path:fname>")
def violation_img(fname):
    return send_from_directory(VIOL_DIR, fname)

# Ieejas punkts
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)
