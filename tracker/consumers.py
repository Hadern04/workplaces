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
        
        query_string = self.scope['query_string'].decode()
        params = parse_qs(query_string)
        source_param = params.get('source', ['0'])[0]
        
        try:
            self.video_source = int(source_param)
        except ValueError:
            self.video_source = source_param

        print(f"Источник видео для этого соединения: {self.video_source}")

        self.workplaces_dict = await self.get_workplaces_from_db()
        self.processor = None
        self.video_task = asyncio.create_task(self.stream_video())

    async def disconnect(self, close_code):
        print(f"WebSocket: Клиент отключен, код: {close_code}")
        if hasattr(self, 'video_task') and not self.video_task.done():
            self.video_task.cancel()
        if hasattr(self, 'processor') and self.processor:
            del self.processor

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            try:
                data = json.loads(text_data)
                if data['type'] == 'set_threshold':
                    threshold = int(data['value'])
                    if self.processor and threshold > 0:
                        self.processor.set_stay_threshold(threshold)
                        print(f"Порог времени обновлен: {threshold} сек")
                elif data['type'] == 'confirm_workplace':
                    wp_id = data['id']
                    await self.confirm_workplace_in_db(wp_id)
                    self.workplaces_dict = await self.get_workplaces_from_db()
                    if self.processor:
                        self.processor.update_workplaces(self.workplaces_dict)
                    await self.send_workplace_update()  # Уведомляем фронтенд
                    print(f"Рабочее место {wp_id} подтверждено и обновлено на видео")
                elif data['type'] == 'delete_workplace':
                    wp_id = data['id']
                    await self.delete_workplace_in_db(wp_id)
                    self.workplaces_dict = await self.get_workplaces_from_db()
                    if self.processor:
                        self.processor.update_workplaces(self.workplaces_dict)
                    await self.send_workplace_update()
                    print(f"Рабочее место {wp_id} удалено и обновлено на видео")
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Ошибка обработки сообщения: {e}")

    async def stream_video(self):
        try:
            self.processor = VideoProcessor(video_source=self.video_source, initial_workplaces=self.workplaces_dict)
            
            async for frame_bytes, proposal in self.async_frame_generator(self.processor):
                await self.send(bytes_data=frame_bytes)
                
                if proposal:
                    print(f"Получено предложение о создании рабочего места: {proposal}")
                    new_wp_id = await self.create_workplace_in_db(proposal)
                    if new_wp_id:
                        self.workplaces_dict = await self.get_workplaces_from_db()
                        self.processor.update_workplaces(self.workplaces_dict)
                        await self.send(text_data=json.dumps({
                            'type': 'workplace_proposal',
                            'id': str(new_wp_id),
                            'name': proposal['name']
                        }))

        except asyncio.CancelledError:
            print("Задача потоковой передачи видео была отменена.")
        except Exception as e:
            print(f"!!! Произошла ошибка в потоке видео: {e}")
            await self.send(text_data=json.dumps({'type': 'error', 'message': str(e)}))
            await self.close()
        finally:
            print("Завершение потоковой передачи видео.")
            if self.processor:
                del self.processor

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
            print(f"Ошибка в генераторе кадров: {e}")
            raise

    @database_sync_to_async
    def get_workplaces_from_db(self):
        workplaces = Workplace.objects.all()
        return {str(wp.id): {'name': wp.name, 'bbox': wp.bbox, 'is_confirmed': wp.is_confirmed} for wp in workplaces}

    @database_sync_to_async
    def create_workplace_in_db(self, proposal_data):
        try:
            new_wp = Workplace.objects.create(
                name=proposal_data['name'],
                bbox=proposal_data['bbox'],
                is_confirmed=False
            )
            print(f"Успешно создано временное рабочее место '{new_wp.name}' в БД.")
            return new_wp.id
        except Exception as e:
            print(f"!!! Ошибка создания рабочего места в БД: {e}")
            return None

    @database_sync_to_async
    def confirm_workplace_in_db(self, wp_id):
        try:
            wp = Workplace.objects.get(id=wp_id)
            wp.is_confirmed = True
            wp.save()
            print(f"Рабочее место '{wp.name}' подтверждено.")
        except Exception as e:
            print(f"Ошибка подтверждения рабочего места: {e}")

    @database_sync_to_async
    def delete_workplace_in_db(self, wp_id):
        try:
            wp = Workplace.objects.get(id=wp_id)
            wp.delete()
            print(f"Рабочее место '{wp.name}' удалено из БД.")
        except Exception as e:
            print(f"Ошибка удаления рабочего места: {e}")

    async def send_workplace_update(self):
        workplaces = await self.get_workplaces_from_db()
        await self.send(text_data=json.dumps({
            'type': 'workplace_update',
            'workplaces': [
                {'id': wp_id, 'name': data['name'], 'bbox': data['bbox'], 'is_confirmed': data['is_confirmed']}
                for wp_id, data in workplaces.items()
            ]
        }))