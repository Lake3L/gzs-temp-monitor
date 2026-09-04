"""
Модели данных для системы учёта сигналов о превышении температуры.
Описание структур данных, используемых в системе.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class SensorStatus(Enum):
    """Статус датчика"""
    ONLINE = "в сети"
    OFFLINE = "потеря связи"
    ERROR = "ошибка"


class EventType(Enum):
    """Тип события"""
    WARNING = "Предупреждение"          # Превышен первый порог (warning_threshold)
    CRITICAL = "Критическая ситуация"   # Превышен второй порог (danger_threshold)
    SENSOR_FAILURE = "Сбой датчика"     # Датчик неисправен или не отвечает


class EventStatus(Enum):
    """Статус обработки события"""
    ACTIVE = "Активно"
    ACKNOWLEDGED = "Подтверждено"
    RESOLVED = "Разрешено"


@dataclass
class Room:
    """Помещение/зона объекта"""
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    
@dataclass
class Sensor:
    """Датчик температуры"""
    id: Optional[int] = None
    room_id: int = 0
    name: str = ""
    status: SensorStatus = SensorStatus.ONLINE
    warning_threshold: float = 60.0  # Предупредительный порог (°C)
    danger_threshold: float = 80.0   # Аварийный порог (°C)
    filter_enabled: bool = True      # Фильтрация ложных срабатываний
    created_at: datetime = field(default_factory=datetime.now)
    

@dataclass
class Reading:
    """Показание температуры с датчика"""
    id: Optional[int] = None
    sensor_id: int = 0
    temperature: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    sensor_status: SensorStatus = SensorStatus.ONLINE
    

@dataclass
class Event:
    """Событие превышения температуры"""
    id: Optional[int] = None
    sensor_id: int = 0
    event_type: EventType = EventType.WARNING
    status: EventStatus = EventStatus.ACTIVE
    temperature: float = 0.0
    threshold_exceeded: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    notes: str = ""
    description: str = ""  # Описание события (для сбоев датчиков)
    action_taken: str = ""  # Предпринятое действие при разрешении


@dataclass 
class SuspiciousReading:
    """Подозрительное показание (не привело к событию)"""
    id: Optional[int] = None
    sensor_id: int = 0
    temperature: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""  # Причина подозрительности


@dataclass
class NotificationLog:
    """Журнал уведомлений"""
    id: Optional[int] = None
    event_id: int = 0
    channel: str = ""  # email, sms
    recipient: str = ""
    message: str = ""
    sent_at: datetime = field(default_factory=datetime.now)
    status: str = "sent"  # sent, failed


@dataclass
class AuditLog:
    """Журнал аудита действий"""
    id: Optional[int] = None
    action: str = ""
    entity_type: str = ""  # sensor, room, event, threshold
    entity_id: int = 0
    old_value: str = ""
    new_value: str = ""
    user: str = "operator"
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class NotificationSettings:
    """Настройки уведомлений"""
    id: Optional[int] = None
    room_id: Optional[int] = None  # None = для всех помещений
    event_type: EventType = EventType.CRITICAL
    email: str = ""
    enabled: bool = True
