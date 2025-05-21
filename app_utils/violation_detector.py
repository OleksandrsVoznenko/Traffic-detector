import cv2
import torch
import numpy as np
from datetime import datetime, timedelta, time
from ultralytics import YOLO  # svarīgi: lieto oficiālo YOLO
from app_utils.traffic_light_detector import TrafficLightDetector

class ViolationDetector:
    def __init__(self): #Šajā definīcijā atrodas viena no svarīgākajām informācija, viss kas atrodas te tiek izmantots turpmāk un spēlē lielu lomu
        self.model = YOLO("yolov5su.pt")
        self.model.conf = 0.6  # confidence threshold
        self.target_classes = [
            'car', 
            'truck', 
            'traffic light'
        ]
        self.conf_thresh = 0.6

        # Piemērs: definējam šķērsojamo zonu (tu vēlāk vari to pielāgot)
        self.intersection_area = np.array([[600, 350], [800, 350], [800, 500], [600, 500]], dtype=np.float32)
        self.light_detector = TrafficLightDetector()

    def analyze_frame(self, frame, frame_id): #Galvenā definīcija, kura nosaka vai visas pārējās definīcijas darbojas.
        #Šis modulis izmanto laika zonu starpību, lai noteikt, kurā laikā algoritmam ir jābūt ON vai OFF
        now = (datetime.now() - timedelta(hours=9)).time()
        start_time = time(6, 0)
        end_time = time(23, 59)

        self.current_frame = frame

        if not (start_time <= now <= end_time):
            # Zīmē tekstu uz kadra, lai norādītu, ka detekcija ir izslēgta
            cv2.putText(
                frame,
                "Detekcija izslegta (nakts rezims)",
                (10, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),  # Sarkans teksts
                2,
                cv2.LINE_AA
            )
            return frame

        # DETEKCIJAS BLOKS
        light_status = self.light_detector.get_light_status(frame)
        results = self.model(frame, verbose=False)[0]
        detections = self._process_detections(results, frame)

        if not detections:
            return frame

        frame_width = frame.shape[1]
        violations = self._check_violations(frame, detections, frame_width)

        if violations:
            self._log_violations(frame, frame_id, violations)
            frame = self._draw_violations(frame, violations)

        return frame


    def _process_detections(self, results, frame): #Šī definīcija izpilda darbību, kurā tā analizē pārkāpumus un ierauga kādi objekti pārkāp un apzīmē tos ar box.
        processed = []
        names = self.model.names  # klases vārdnīca

        for box in results.boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            if conf < self.conf_thresh:
                continue

            label = names[cls_id]
            if label not in self.target_classes:
                continue

            coords = box.xyxy[0].cpu().numpy().astype(int)
            x1, y1, x2, y2 = coords
            label_info = {
                'label': label,
                'box': [x1, y1, x2, y2],
                'confidence': conf
            }

            if label == 'traffic light':
                label_info['color'] = self._detect_light_color(frame, [x1, y1, x2, y2])

            processed.append(label_info)
        return processed

    def _check_violations(self, frame, detections, frame_width): #Šī definīcija meklē iespējamos pārkāpumus
        light_status = self.light_detector.get_light_status(frame)
        violations = []

        for obj in detections:
            box = obj['box']
            direction = self._get_vehicle_direction(box)

            if direction == "unknown":
                continue

            if light_status.get(direction) == "red" and self._in_intersection(box):
                violations.append(obj)
        return violations

    def _detect_light_color(self, frame, box): #Tiek apskatīts kādā krāsā deg luksofors
        x1, y1, x2, y2 = box
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return 'unknown'

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        red_mask = cv2.inRange(hsv, (0,70,50), (10,255,255)) + cv2.inRange(hsv, (170,70,50), (180,255,255))
        green_mask = cv2.inRange(hsv, (40,40,40), (90,255,255))

        if cv2.countNonZero(red_mask) > 50:
            return 'red'
        if cv2.countNonZero(green_mask) > 50:
            return 'green'
        return 'unknown'

    def _get_light_status(self, detections): #Luksofora krāsa tiek atspoguļota uz izvadītā attēla ar boz un uzrakstu.
        for obj in detections:
            if obj['label'] == 'traffic light' and obj.get('color') == 'green':
                return 'green'
        return 'red'

    def _is_violation(self, box, frame_width, light_status): #
        if light_status != 'red':
            return False
        if not self._in_intersection(box):
            return False
        return self._estimate_distance(box, frame_width) < 50

    def _in_intersection(self, box): #Pārbauda vai automašīna ir šķērsojusi krustojuma robežas un iebraukusi tajā.
        x_center = float((box[0] + box[2]) // 2)
        y_center = float((box[1] + box[3]) // 2)
        return cv2.pointPolygonTest(self.intersection_area, (x_center, y_center), False) >= 0

    def _estimate_distance(self, box, frame_width):
        box_width = box[2] - box[0]
        return (frame_width * 0.8 * 2.5) / box_width  # 2.5m = vidējais auto platums

    def _log_violations(self, frame, frame_id, violations): #Fiksē pārkāpumu un nosūta to uz failu, kurš tiek saglabāts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        img_path = f"violations/violation_{frame_id}_{timestamp}.jpg"
        txt_path = f"violations/violation_{frame_id}_{timestamp}.txt"

        cv2.imwrite(img_path, frame)
        with open(txt_path, 'w') as f:
            for v in violations:
                f.write(f"{v['label']} parkapums: {v['box']}\n")

    def _draw_violations(self, frame, violations): #Ar atsevišķu box tiek apzīmēta automašīna, kura ir veikusi pārkāpumu.
        for v in violations:
            x1, y1, x2, y2 = v['box']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(frame, "PARKAPUMS!", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame

    def _get_vehicle_direction(self, box): #Definīcija pēta kādā virzienā dotas automobīlis.
        x1, y1, x2, y2 = box
        width = x2 - x1
        height = y2 - y1
        center_x = x1 + width // 2
        center_y = y1 + height // 2

            # Šie skaitļi var būt jāpielāgo pēc reāla kadra
        if center_x < 700 and 200 < center_y < 500:
            return "west_east"
        elif 700 < center_x < 1200 and center_y > 300:
            return "north_south"
        return "unknown"
