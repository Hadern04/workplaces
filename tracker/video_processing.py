import cv2
import numpy as np
import time
import uuid
from collections import defaultdict
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

class VideoProcessor:
    def __init__(self, video_source=0, initial_workplaces=None):
        # --- Конфигурация ---
        YOLO_MODEL_PATH = 'yolo11l.pt'  # Убедитесь, что модель находится в корне проекта
        self.CONFIDENCE_THRESHOLD = 0.5
        self.VIDEO_SOURCE = video_source

        # --- Настраиваемые параметры анализа ---
        self.STAY_THRESHOLD_SECONDS = 10
        self.MIN_TRACK_POINTS_FOR_WP_CHECK = 20
        self.MAX_DISTANCE_FOR_STAY_PX = 30
        self.WORKPLACE_SIZE_PX = 100
        self.PREVIEW_DURATION_SECONDS = 5

        # --- Инициализация моделей ---
        try:
            self.model_yolo = YOLO(YOLO_MODEL_PATH)
        except Exception as e:
            print(f"!!! Ошибка загрузки модели YOLO: {e}")
            raise
            
        self.deepsort_tracker = DeepSort(max_age=30)
        
        # --- Состояние ---
        self.workplaces = initial_workplaces if initial_workplaces else {}
        self.track_history = defaultdict(list)
        self.last_wp_creation_time_for_track = {}
        self.preview_workplace_proposal = None # {'bbox': ..., 'end_time': ...}
        
    def update_workplaces(self, new_workplaces):
        """Метод для обновления списка рабочих мест извне (от Consumer)."""
        self.workplaces = new_workplaces

    def _is_overlapping(self, bbox1, bbox2):
        """
        Проверяет, пересекаются ли два прямоугольника (bbox1 и bbox2).
        bbox: (x, y, w, h), где x, y - координаты верхнего левого угла, w, h - ширина и высота.
        Возвращает True, если прямоугольники пересекаются, иначе False.
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # Проверяем, что один прямоугольник не находится полностью слева, справа, выше или ниже другого
        if (x1 >= x2 + w2 or x2 >= x1 + w1 or y1 >= y2 + h2 or y2 >= y1 + h1):
            return False
        return True

    def _analyze_tracks_and_draw(self, frame, tracks):
        """
        Основная логика анализа поведения треков и отрисовки на кадре.
        Возвращает предложение о новом рабочем месте, если оно есть.
        """
        current_time = time.time()
        new_workplace_proposal = None

        # 1. Обновляем историю и отрисовываем треки
        for track in tracks:
            if not track.is_confirmed():
                continue
            
            track_id = track.track_id
            ltrb = track.to_ltrb()
            x1, y1, x2, y2 = map(int, ltrb)

            # Отрисовка трека
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"ID: {track_id}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Обновление истории
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            self.track_history[track_id].append((cx, cy, current_time))
            # Очистка старой истории
            self.track_history[track_id] = [t for t in self.track_history[track_id] if current_time - t[2] <= self.STAY_THRESHOLD_SECONDS * 2]

        # 2. Анализируем стабильность каждого трека
        for track_id, history in list(self.track_history.items()):
            relevant_history = [p for p in history if current_time - p[2] <= self.STAY_THRESHOLD_SECONDS]

            if len(relevant_history) < self.MIN_TRACK_POINTS_FOR_WP_CHECK:
                continue

            if len(relevant_history) > 1:
                distances = [np.sqrt((relevant_history[i][0] - relevant_history[i-1][0])**2 + (relevant_history[i][1] - relevant_history[i-1][1])**2) for i in range(1, len(relevant_history))]
                if not distances or max(distances) >= self.MAX_DISTANCE_FOR_STAY_PX:
                    continue # Слишком много двигался

            # Объект стабилен, определяем его центр
            avg_x = int(np.mean([p[0] for p in relevant_history]))
            avg_y = int(np.mean([p[1] for p in relevant_history]))
            
            potential_wp_bbox = (avg_x - self.WORKPLACE_SIZE_PX // 2, avg_y - self.WORKPLACE_SIZE_PX // 2, self.WORKPLACE_SIZE_PX, self.WORKPLACE_SIZE_PX)

            # Проверяем, не пересекается ли с существующими местами
            is_overlapping = False
            for wp_data in self.workplaces.values():
                wp_bbox = wp_data['bbox']
                if self._is_overlapping(potential_wp_bbox, wp_bbox):
                    is_overlapping = True
                    break
            
            if is_overlapping:
                continue

            # Проверяем, не предлагали ли мы место для этого трека недавно
            last_creation_time = self.last_wp_creation_time_for_track.get(track_id, 0)
            if current_time - last_creation_time < self.STAY_THRESHOLD_SECONDS * 5: # Увеличим задержку
                continue

            # Все условия выполнены: генерируем предложение
            new_workplace_proposal = {
                'name': f'Место {str(uuid.uuid4())[:4]}',
                'bbox': potential_wp_bbox,
                'track_id': track_id,
                'start_time': relevant_history[0][2]
            }
            # Устанавливаем предпросмотр
            self.preview_workplace_proposal = {
                'bbox': potential_wp_bbox,
                'end_time': current_time + self.PREVIEW_DURATION_SECONDS
            }
            self.last_wp_creation_time_for_track[track_id] = current_time
            break # Предлагаем только одно место за раз

        # 3. Отрисовка существующих и предпросмотра новых мест
        for wp_data in self.workplaces.values():
            x, y, w, h = wp_data['bbox']
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2) # Синий
            cv2.putText(frame, wp_data['name'], (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        if self.preview_workplace_proposal and time.time() < self.preview_workplace_proposal['end_time']:
            x, y, w, h = self.preview_workplace_proposal['bbox']
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 3) # Желтый
            cv2.putText(frame, "Новое место?", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        elif self.preview_workplace_proposal and time.time() >= self.preview_workplace_proposal['end_time']:
            self.preview_workplace_proposal = None # Сброс предпросмотра
        
        return new_workplace_proposal

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
            
            # --- Обработка кадра ---
            results = self.model_yolo(frame, verbose=False, classes=[0])
            
            detections_for_deepsort = [
                ([int(b[0]), int(b[1]), int(b[2]-b[0]), int(b[3]-b[1])], float(conf), "person")
                for r in results for b, conf in zip(r.boxes.xyxy, r.boxes.conf) if float(conf) > self.CONFIDENCE_THRESHOLD
            ]
            
            tracks = self.deepsort_tracker.update_tracks(detections_for_deepsort, frame=frame)
            
            proposal = self._analyze_tracks_and_draw(frame, tracks)

            # --- Кодирование и возврат результата ---
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            
            yield (buffer.tobytes(), proposal)

        cap.release()