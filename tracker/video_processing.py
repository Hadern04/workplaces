import cv2
import numpy as np
import time
import uuid
from collections import defaultdict
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

class VideoProcessor:
    def __init__(self, video_source=0, initial_workplaces=None):
        YOLO_MODEL_PATH = 'yolo11l.pt'
        self.CONFIDENCE_THRESHOLD = 0.4
        self.VIDEO_SOURCE = video_source
        self.STAY_THRESHOLD_SECONDS = 20
        self.MIN_TRACK_POINTS_FOR_WP_CHECK = 20
        self.MAX_DISTANCE_FOR_STAY_PX = 30
        self.WORKPLACE_SIZE_PX = 75
        self.PREVIEW_DURATION_SECONDS = 5

        try:
            self.model_yolo = YOLO(YOLO_MODEL_PATH)
        except Exception as e:
            print(f"!!! Ошибка загрузки модели YOLO: {e}")
            raise
            
        self.deepsort_tracker = DeepSort(max_age=30)
        self.workplaces = initial_workplaces if initial_workplaces else {}
        self.track_history = defaultdict(list)
        self.last_wp_creation_time_for_track = {}
        self.preview_workplace_proposal = None
        self.occupancy_status = {}  # {wp_id: {'track_id': track_id, 'start_time': time}}

    def set_stay_threshold(self, threshold):
        """Обновляет порог времени для анализа."""
        self.STAY_THRESHOLD_SECONDS = max(1, threshold)
        print(f"Обновлен порог времени: {self.STAY_THRESHOLD_SECONDS} сек")

    def update_workplaces(self, new_workplaces):
        """Метод для обновления списка рабочих мест извне."""
        self.workplaces = new_workplaces
        # Очищаем occupancy_status для удаленных рабочих мест
        self.occupancy_status = {
            wp_id: status for wp_id, status in self.occupancy_status.items() if wp_id in new_workplaces
        }
        print(f"Обновлен список рабочих мест: {len(self.workplaces)} мест")

    def _is_overlapping(self, bbox1, bbox2):
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        if (x1 >= x2 + w2 or x2 >= x1 + w1 or y1 >= y2 + h2 or y2 >= y1 + h1):
            return False
        return True

    def _analyze_tracks_and_draw(self, frame, tracks):
        current_time = time.time()
        new_workplace_proposal = None

        # Обновляем историю и проверяем занятость
        active_tracks = {}
        for track in tracks:
            if not track.is_confirmed():
                continue
            
            track_id = track.track_id
            ltrb = track.to_ltrb()
            x1, y1, x2, y2 = map(int, ltrb)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            # Отрисовка трека
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"ID: {track_id}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Обновление истории
            self.track_history[track_id].append((cx, cy, current_time))
            self.track_history[track_id] = [t for t in self.track_history[track_id] if current_time - t[2] <= self.STAY_THRESHOLD_SECONDS * 2]
            active_tracks[track_id] = (cx, cy)

        # Проверяем занятость рабочих мест
        for wp_id, wp_data in self.workplaces.items():
            if not wp_data.get('is_confirmed', True):
                continue
            wp_bbox = wp_data['bbox']
            x, y, w, h = wp_bbox
            is_occupied = False
            current_track_id = None

            for track_id, (cx, cy) in active_tracks.items():
                if x <= cx < x + w and y <= cy < y + h:
                    is_occupied = True
                    current_track_id = track_id
                    break

            current_status = self.occupancy_status.get(wp_id, {})
            if is_occupied and current_status.get('track_id') != current_track_id:
                if current_status.get('track_id'):
                    self._end_occupancy(wp_id, current_time)
                self.occupancy_status[wp_id] = {'track_id': current_track_id, 'start_time': current_time}
            elif not is_occupied and current_status.get('track_id'):
                self._end_occupancy(wp_id, current_time)

        # Анализируем стабильность треков для создания новых мест
        for track_id, history in list(self.track_history.items()):
            relevant_history = [p for p in history if current_time - p[2] <= self.STAY_THRESHOLD_SECONDS * 2]

            if len(relevant_history) < self.MIN_TRACK_POINTS_FOR_WP_CHECK:
                continue

            # Проверяем, что трек существует достаточно долго (не менее STAY_THRESHOLD_SECONDS)
            if len(relevant_history) > 1:
                time_span = relevant_history[-1][2] - relevant_history[0][2]
                if time_span < self.STAY_THRESHOLD_SECONDS:
                    continue

                distances = [np.sqrt((relevant_history[i][0] - relevant_history[i-1][0])**2 + (relevant_history[i][1] - relevant_history[i-1][1])**2) for i in range(1, len(relevant_history))]
                if not distances or max(distances) >= self.MAX_DISTANCE_FOR_STAY_PX:
                    continue

            avg_x = int(np.mean([p[0] for p in relevant_history]))
            avg_y = int(np.mean([p[1] for p in relevant_history]))
            
            potential_wp_bbox = (avg_x - self.WORKPLACE_SIZE_PX // 2, avg_y - self.WORKPLACE_SIZE_PX // 2, self.WORKPLACE_SIZE_PX, self.WORKPLACE_SIZE_PX)

            is_overlapping = False
            for wp_data in self.workplaces.values():
                if self._is_overlapping(potential_wp_bbox, wp_data['bbox']):
                    is_overlapping = True
                    break
            
            if is_overlapping:
                continue

            last_creation_time = self.last_wp_creation_time_for_track.get(track_id, 0)
            if current_time - last_creation_time < self.STAY_THRESHOLD_SECONDS * 5:
                continue

            new_workplace_proposal = {
                'name': f'Seat {str(uuid.uuid4())[:4]}',
                'bbox': potential_wp_bbox,
                'track_id': track_id,
                'start_time': relevant_history[0][2]
            }
            self.preview_workplace_proposal = {
                'bbox': potential_wp_bbox,
                'end_time': current_time + self.PREVIEW_DURATION_SECONDS
            }
            self.last_wp_creation_time_for_track[track_id] = current_time
            break

        # Отрисовка рабочих мест
        for wp_id, wp_data in self.workplaces.items():
            x, y, w, h = wp_data['bbox']
            color = (0, 255, 255) if not wp_data.get('is_confirmed', True) else (255, 0, 0)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, wp_data['name'], (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        if self.preview_workplace_proposal and time.time() < self.preview_workplace_proposal['end_time']:
            x, y, w, h = self.preview_workplace_proposal['bbox']
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 3)
            cv2.putText(frame, "Новое место?", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        elif self.preview_workplace_proposal and time.time() >= self.preview_workplace_proposal['end_time']:
            self.preview_workplace_proposal = None
        
        return new_workplace_proposal

    def _end_occupancy(self, wp_id, end_time):
        """Записывает завершение периода занятости в базу."""
        from .models import Workplace
        try:
            wp = Workplace.objects.get(id=wp_id)
            if wp.is_confirmed:
                current_status = self.occupancy_status.get(wp_id, {})
                if current_status.get('track_id'):
                    wp.times.append({
                        'start': current_status['start_time'],
                        'end': end_time
                    })
                    wp.save()
                    print(f"Занятость для {wp.name} сохранена: {current_status['start_time']} - {end_time}")
            self.occupancy_status.pop(wp_id, None)
        except Workplace.DoesNotExist:
            print(f"Рабочее место с ID {wp_id} не существует, пропускаем сохранение занятости.")
            self.occupancy_status.pop(wp_id, None)
        except Exception as e:
            print(f"Ошибка сохранения занятости: {e}")

    def process_frames(self):
        cap = cv2.VideoCapture(self.VIDEO_SOURCE)
        if not cap.isOpened():
            print(f"!!! Ошибка: не удалось открыть источник видео {self.VIDEO_SOURCE}")
            return

        while True:
            ret, frame = cap.read()
            if not ret:
                print("Конец видео или ошибка чтения. Перезапуск...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            
            results = self.model_yolo(frame, verbose=False, classes=[0])
            
            detections_for_deepsort = [
                ([int(b[0]), int(b[1]), int(b[2]-b[0]), int(b[3]-b[1])], float(conf), "person")
                for r in results for b, conf in zip(r.boxes.xyxy, r.boxes.conf) if float(conf) > self.CONFIDENCE_THRESHOLD
            ]
            
            tracks = self.deepsort_tracker.update_tracks(detections_for_deepsort, frame=frame)
            
            proposal = self._analyze_tracks_and_draw(frame, tracks)

            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            
            yield (buffer.tobytes(), proposal)

        cap.release()