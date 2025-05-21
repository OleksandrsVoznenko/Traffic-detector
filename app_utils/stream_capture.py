import os
import time
import cv2
from yt_dlp import YoutubeDL
from app_utils.violation_detector import ViolationDetector

# Konstantes
FRAMES_DIR = os.getenv("FRAMES_DIR", "frames")
VIOL_DIR   = "violations"

os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(VIOL_DIR,   exist_ok=True)

# Straumes uztveršanas un apstrādes klase
class StreamCapture:
    """
    Загружает YouTube-трансляцию, детектирует нарушения и:
      • выводит окно «Traffic Monitor» (cv2.imshow),
      • дублирует видео во Flask, постоянно перезаписывая frames/latest.jpg.
    """
    def __init__(self):
        self.detector    = ViolationDetector()
        self.youtube_url = "https://www.youtube.com/watch?v=1EiC9bvVGnk"

    def start_capture(self):
        """Bezgalīgi mēģina iegūt straumes tiešo URL un to apstrādāt."""
        while True:
            stream_url = self._get_stream_url()
            if stream_url:
                self._process_stream(stream_url)
            else:
                print("Neizdevās iegūt straumi. Atkārtosana pēc 10 sekundēm...")
                time.sleep(10)

    def _get_stream_url(self) -> str | None:
        """Izvelk tiešu saiti uz multivides straumi no YouTube lapas."""
        try:
            with YoutubeDL({'format': 'best', 'quiet': True}) as ydl:
                info = ydl.extract_info(self.youtube_url, download=False)
                return info["url"]
        except Exception as e:
            print(f"Izvelkot straumi, radās kļūda: {e}")
            return None

    def _process_stream(self, stream_url: str):
        """nolasa kadrus, apstrādā tos un saglabā tos Flask."""
        cap      = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
        frame_id = 0

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    print("Plūsma tika pārtraukta. Notiek savienojuma atjaunošana...")
                    break

                processed = self.detector.analyze_frame(frame, frame_id)

                # Frame Flask (MJPEG)
                latest_path = os.path.join(FRAMES_DIR, "latest.jpg")
                cv2.imwrite(
                    latest_path,
                    processed,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 90]  # kvalitāti 90 %
                )

                # ——— локальное окно (можно закрыть по Esc) ———
                cv2.imshow("Traffic Monitor", processed)
                if cv2.waitKey(1) & 0xFF == 27:
                    break

                frame_id += 1
        finally:
            cap.release()
            cv2.destroyAllWindows()
