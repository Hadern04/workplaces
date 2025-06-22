import asyncio
import json
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .video_processing import VideoProcessor
from .models import Workplace

class VideoConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        print("WebSocket: Клиент подключен.")
        
        # --- Получаем источник видео из URL ---
        query_string = self.scope['query_string'].decode()
        params = parse_qs(query_string)
        source_param = params.get('source', ['0'])[0] # По умолчанию '0' (веб-камера)
        
        # Преобразуем источник в число, если это возможно, иначе оставляем как строку (путь к файлу)
        try:
            self.video_source = int(source_param)
        except ValueError:
            self.video_source = source_param

        print(f"Источник видео для этого соединения: {self.video_source}")

        # Загружаем начальные данные о рабочих местах из БД
        self.workplaces_dict = await self.get_workplaces_from_db()
        
        # Запускаем обработку видео в фоновой задаче
        self.video_task = asyncio.create_task(self.stream_video())

    async def disconnect(self, close_code):
        print(f"WebSocket: Клиент отключен, код: {close_code}")
        if hasattr(self, 'video_task') and not self.video_task.done():
            self.video_task.cancel()

    async def stream_video(self):
        """
        Основной цикл, который получает кадры от процессора и отправляет клиенту.
        """
        processor = None
        try:
            # Передаем выбранный источник в процессор
            processor = VideoProcessor(video_source=self.video_source, initial_workplaces=self.workplaces_dict)
            
            async for frame_bytes, proposal in self.async_frame_generator(processor):
                await self.send(bytes_data=frame_bytes)
                
                if proposal:
                    print(f"Получено предложение о создании рабочего места: {proposal}")
                    new_wp_id = await self.create_workplace_in_db(proposal)
                    if new_wp_id:
                        self.workplaces_dict = await self.get_workplaces_from_db()
                        processor.update_workplaces(self.workplaces_dict)
                        await self.send_workplace_update()

        except asyncio.CancelledError:
            print("Задача потоковой передачи видео была отменена.")
        except Exception as e:
            # Если процессор не смог запуститься (напр. неверный путь к файлу)
            print(f"!!! Произошла ошибка в потоке видео: {e}")
            await self.send(text_data=json.dumps({'type': 'error', 'message': str(e)}))
            await self.close() # Закрываем соединение, если видео не доступно
        finally:
            print("Завершение потоковой передачи видео.")
            # Здесь можно добавить логику очистки, если процессор использует ресурсы, которые нужно освободить
            del processor

    async def async_frame_generator(self, processor):
        loop = asyncio.get_event_loop()
        try:
            frame_iterator = iter(processor.process_frames())
            while True:
                frame_tuple = await loop.run_in_executor(None, lambda: next(frame_iterator, (None, None)))
                if frame_tuple[0] is None:
                    break
                yield frame_tuple
        except Exception as e:
            # Перехватываем ошибку из генератора, чтобы сообщить клиенту
            print(f"Ошибка в генераторе кадров: {e}")
            raise # Передаем ошибку выше, чтобы stream_video мог ее обработать

    @database_sync_to_async
    def get_workplaces_from_db(self):
        workplaces = Workplace.objects.all()
        return {str(wp.id): {'name': wp.name, 'bbox': wp.bbox} for wp in workplaces}

    @database_sync_to_async
    def create_workplace_in_db(self, proposal_data):
        try:
            new_wp = Workplace.objects.create(
                name=proposal_data['name'],
                bbox=proposal_data['bbox']
            )
            print(f"Успешно создано рабочее место '{new_wp.name}' в БД.")
            return new_wp.id
        except Exception as e:
            print(f"!!! Ошибка создания рабочего места в БД: {e}")
            return None
            
    async def send_workplace_update(self):
        await self.send(text_data=json.dumps({
            'type': 'workplace_update'
        }))

