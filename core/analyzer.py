"""
Анализатор температурных данных.
Определяет превышения порогов и создаёт события.
"""

from datetime import datetime
from typing import Optional, List
from PyQt6.QtCore import QObject, pyqtSignal

from database.db_manager import DatabaseManager
from database.models import (
    Sensor, Event, EventType, EventStatus, SensorStatus
)


class TemperatureAnalyzer(QObject):
    """
    Анализатор температурных данных.
    Отслеживает превышения порогов и создаёт/закрывает события.
    """
    
    # Сигналы
    event_created = pyqtSignal(int, object)  # event_id, Event
    event_closed = pyqtSignal(int)  # event_id
    threshold_exceeded = pyqtSignal(int, float, str)  # sensor_id, temperature, event_type
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Инициализация анализатора.
        
        Args:
            db_manager: Менеджер базы данных
        """
        super().__init__()
        self.db = db_manager
        
        # Кэш активных событий по датчикам
        self._active_events: dict[int, Event] = {}
        
        # Загружаем активные события при старте
        self._load_active_events()
    
    def _load_active_events(self):
        """Загрузить активные события из БД"""
        events = self.db.get_active_events()
        for event in events:
            self._active_events[event.sensor_id] = event
    
    def analyze_reading(self, sensor_id: int, temperature: float, 
                        timestamp: datetime = None):
        """
        Анализировать показание температуры.
        
        Args:
            sensor_id: ID датчика
            temperature: Температура
            timestamp: Время показания
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Получаем данные датчика
        sensor = self.db.get_sensor(sensor_id)
        if not sensor:
            return
        
        # Определяем тип события по порогам
        event_type = self._check_thresholds(sensor, temperature)
        
        # Получаем текущее активное событие для датчика
        active_event = self._active_events.get(sensor_id)
        
        if event_type is not None:
            # Есть превышение порога
            if active_event is None:
                # Создаём новое событие
                self._create_event(sensor, temperature, event_type)
            elif active_event.event_type != event_type:
                # Изменился тип события (например, с предупреждения на критическое)
                if event_type == EventType.CRITICAL and active_event.event_type == EventType.WARNING:
                    # Эскалация события
                    self._escalate_event(active_event, sensor, temperature)
        else:
            # Температура в норме
            if active_event is not None:
                # Закрываем событие
                self._close_event(active_event)
    
    def _check_thresholds(self, sensor: Sensor, temperature: float) -> Optional[EventType]:
        """
        Проверить превышение порогов.
        
        Returns:
            EventType или None если превышения нет
        """
        if temperature >= sensor.danger_threshold:
            return EventType.CRITICAL
        elif temperature >= sensor.warning_threshold:
            return EventType.WARNING
        return None
    
    def _create_event(self, sensor: Sensor, temperature: float, 
                      event_type: EventType):
        """Создать новое событие"""
        threshold = (sensor.danger_threshold if event_type == EventType.CRITICAL 
                     else sensor.warning_threshold)
        
        # Получаем информацию о помещении
        room = self.db.get_room(sensor.room_id)
        room_name = room.name if room else "Неизвестно"
        
        description = (
            f"Датчик '{sensor.name}' в помещении '{room_name}': "
            f"температура {temperature}°C превысила "
            f"{'критический' if event_type == EventType.CRITICAL else 'предупредительный'} "
            f"порог ({threshold}°C)"
        )
        
        event_id = self.db.add_event(
            sensor_id=sensor.id,
            event_type=event_type,
            temperature=temperature,
            threshold_exceeded=threshold,
            description=description
        )
        
        event = self.db.get_event(event_id)
        if event:
            self._active_events[sensor.id] = event
            self.event_created.emit(event_id, event)
            self.threshold_exceeded.emit(sensor.id, temperature, event_type.value)
    
    def _escalate_event(self, event: Event, sensor: Sensor, temperature: float):
        """Эскалировать событие до критического уровня"""
        # Закрываем предыдущее событие
        self.db.close_event(event.id)
        self.event_closed.emit(event.id)
        
        # Создаём новое критическое событие
        self._create_event(sensor, temperature, EventType.CRITICAL)
    
    def _close_event(self, event: Event):
        """Закрыть событие (температура вернулась в норму)"""
        self.db.close_event(event.id)
        
        if event.sensor_id in self._active_events:
            del self._active_events[event.sensor_id]
        
        self.event_closed.emit(event.id)
    
    def handle_sensor_failure(self, sensor_id: int):
        """
        Обработать сбой датчика.
        
        Args:
            sensor_id: ID датчика
        """
        sensor = self.db.get_sensor(sensor_id)
        if not sensor:
            return
        
        room = self.db.get_room(sensor.room_id)
        room_name = room.name if room else "Неизвестно"
        
        description = (
            f"Потеря связи с датчиком '{sensor.name}' в помещении '{room_name}'"
        )
        
        event_id = self.db.add_event(
            sensor_id=sensor_id,
            event_type=EventType.SENSOR_FAILURE,
            temperature=0.0,
            threshold_exceeded=0.0,
            description=description
        )
        
        event = self.db.get_event(event_id)
        if event:
            self._active_events[sensor_id] = event
            self.event_created.emit(event_id, event)
    
    def handle_sensor_recovery(self, sensor_id: int):
        """
        Обработать восстановление датчика.
        
        Args:
            sensor_id: ID датчика
        """
        active_event = self._active_events.get(sensor_id)
        if active_event and active_event.event_type == EventType.SENSOR_FAILURE:
            self._close_event(active_event)
    
    def get_active_events(self) -> List[Event]:
        """Получить список активных событий"""
        return list(self._active_events.values())
    
    def has_active_event(self, sensor_id: int) -> bool:
        """Проверить наличие активного события для датчика"""
        return sensor_id in self._active_events
    
    def get_active_event(self, sensor_id: int) -> Optional[Event]:
        """Получить активное событие для датчика"""
        return self._active_events.get(sensor_id)
    
    def refresh_active_events(self):
        """Обновить кэш активных событий из БД"""
        self._active_events.clear()
        self._load_active_events()
