"""
Подсистема сбора данных с датчиков.
Периодически опрашивает датчики и сохраняет показания в БД.
"""

from datetime import datetime
from typing import Callable, Optional
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from database.db_manager import DatabaseManager
from database.models import SensorStatus, Sensor
from simulator.sensor_simulator import SensorSimulator


class DataCollector(QObject):
    """
    Сборщик данных с датчиков.
    Использует QTimer для периодического опроса.
    """
    
    # Сигналы
    reading_received = pyqtSignal(int, float, datetime)  # sensor_id, temperature, timestamp
    sensor_offline = pyqtSignal(int)  # sensor_id
    sensor_back_online = pyqtSignal(int)  # sensor_id
    
    # Интервал опроса по умолчанию (мс)
    DEFAULT_INTERVAL = 5000  # 5 секунд
    
    def __init__(self, db_manager: DatabaseManager, 
                 simulator: SensorSimulator,
                 interval: int = None):
        """
        Инициализация сборщика данных.
        
        Args:
            db_manager: Менеджер базы данных
            simulator: Симулятор датчиков
            interval: Интервал опроса в миллисекундах
        """
        super().__init__()
        
        self.db = db_manager
        self.simulator = simulator
        self._interval = interval or self.DEFAULT_INTERVAL
        
        # Таймер для периодического опроса
        self._timer = QTimer()
        self._timer.timeout.connect(self._collect_readings)
        
        # Отслеживание статуса датчиков
        self._sensor_status: dict[int, SensorStatus] = {}
        
        # Callback для обработки показаний
        self._reading_callback: Optional[Callable] = None
        
        # Счетчик пропущенных показаний для определения offline
        self._missed_readings: dict[int, int] = {}
        self.OFFLINE_THRESHOLD = 3  # После 3 пропусков считаем датчик offline
    
    def start(self):
        """Запустить сбор данных"""
        self._init_sensors()
        self._timer.start(self._interval)
    
    def stop(self):
        """Остановить сбор данных"""
        self._timer.stop()
    
    def is_running(self) -> bool:
        """Проверить, запущен ли сбор данных"""
        return self._timer.isActive()
    
    def set_interval(self, interval: int):
        """
        Установить интервал опроса.
        
        Args:
            interval: Интервал в миллисекундах
        """
        self._interval = interval
        if self._timer.isActive():
            self._timer.stop()
            self._timer.start(interval)
    
    def get_interval(self) -> int:
        """Получить текущий интервал опроса"""
        return self._interval
    
    def set_reading_callback(self, callback: Callable):
        """
        Установить callback для обработки показаний.
        
        Args:
            callback: Функция вида callback(sensor_id, temperature, timestamp)
        """
        self._reading_callback = callback
    
    def _init_sensors(self):
        """Инициализация датчиков из БД"""
        sensors = self.db.get_all_sensors()
        for sensor in sensors:
            self.simulator.register_sensor(sensor.id)
            self._sensor_status[sensor.id] = sensor.status
            self._missed_readings[sensor.id] = 0
    
    def _collect_readings(self):
        """Собрать показания со всех датчиков"""
        # Обновляем симулятор
        self.simulator.update()
        
        # Получаем список датчиков
        sensors = self.db.get_all_sensors()
        
        for sensor in sensors:
            self._collect_sensor_reading(sensor)
    
    def _collect_sensor_reading(self, sensor: Sensor):
        """Собрать показание с одного датчика"""
        # Регистрируем датчик если его нет в симуляторе
        if sensor.id not in self._sensor_status:
            self.simulator.register_sensor(sensor.id)
            self._sensor_status[sensor.id] = sensor.status
            self._missed_readings[sensor.id] = 0
        
        # Получаем температуру
        temperature = self.simulator.get_temperature(sensor.id)
        timestamp = datetime.now()
        
        if temperature is None:
            # Датчик не отвечает
            self._missed_readings[sensor.id] = self._missed_readings.get(sensor.id, 0) + 1
            
            if self._missed_readings[sensor.id] >= self.OFFLINE_THRESHOLD:
                # Датчик offline
                if self._sensor_status.get(sensor.id) != SensorStatus.OFFLINE:
                    self._sensor_status[sensor.id] = SensorStatus.OFFLINE
                    self.db.update_sensor_status(sensor.id, SensorStatus.OFFLINE)
                    self.sensor_offline.emit(sensor.id)
            return
        
        # Датчик ответил
        self._missed_readings[sensor.id] = 0
        
        # Проверяем, был ли датчик offline
        if self._sensor_status.get(sensor.id) == SensorStatus.OFFLINE:
            self._sensor_status[sensor.id] = SensorStatus.ONLINE
            self.db.update_sensor_status(sensor.id, SensorStatus.ONLINE)
            self.sensor_back_online.emit(sensor.id)
        
        # Сохраняем показание в БД
        self.db.add_reading(
            sensor_id=sensor.id,
            temperature=temperature,
            sensor_status=SensorStatus.ONLINE,
            timestamp=timestamp
        )
        
        # Отправляем сигнал
        self.reading_received.emit(sensor.id, temperature, timestamp)
        
        # Вызываем callback если установлен
        if self._reading_callback:
            self._reading_callback(sensor.id, temperature, timestamp)
    
    def force_collect(self):
        """Принудительно собрать показания (без ожидания таймера)"""
        self._collect_readings()
    
    def register_new_sensor(self, sensor_id: int):
        """Зарегистрировать новый датчик для сбора данных"""
        self.simulator.register_sensor(sensor_id)
        self._sensor_status[sensor_id] = SensorStatus.ONLINE
        self._missed_readings[sensor_id] = 0
    
    def unregister_sensor(self, sensor_id: int):
        """Удалить датчик из сбора данных"""
        self.simulator.unregister_sensor(sensor_id)
        if sensor_id in self._sensor_status:
            del self._sensor_status[sensor_id]
        if sensor_id in self._missed_readings:
            del self._missed_readings[sensor_id]
