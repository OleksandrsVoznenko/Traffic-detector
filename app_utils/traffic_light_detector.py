import cv2
import numpy as np

class TrafficLightDetector:
    def __init__(self):
        # Apzīmē zonas, kur atrodas luksofori
        self.light_regions = {
            "north_south": [(1130, 180), (1145, 200)],  # labajā pusē (zaļš tagad)
            "west_east": [(205, 155), (220, 175)]       # kreisajā pusē (sarkans tagad)
        }

    def get_light_status(self, frame):
        status = {}
        for direction, (pt1, pt2) in self.light_regions.items():
            roi = frame[pt1[1]:pt2[1], pt1[0]:pt2[0]]
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

            # Definē HSV krāsu robežas sarkanajam un zaļajam
            red_lower = np.array([0, 70, 50])
            red_upper = np.array([10, 255, 255])
            green_lower = np.array([45, 100, 50])
            green_upper = np.array([75, 255, 255])

            red_mask = cv2.inRange(hsv, red_lower, red_upper)
            green_mask = cv2.inRange(hsv, green_lower, green_upper)

            if cv2.countNonZero(green_mask) > 50:
                status[direction] = "green"
            elif cv2.countNonZero(red_mask) > 50:
                status[direction] = "red"
            else:
                status[direction] = "unknown"

        return status