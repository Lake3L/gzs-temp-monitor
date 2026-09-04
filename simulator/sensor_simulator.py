"""
Симулятор температурных датчиков.
Генерирует реалистичные показания температуры для демонстрации системы.
"""

import random
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime


class SimulationMode(Enum):
    """Режимы симуляции"""
    NORMAL = "Нормальный"
    HEATING = "Нагрев"
    COOLING = "Охлаждение"
    SPIKE = "Скачок"
    FAILURE = "Сбой"


@dataclass
class SensorSimState:
    """Состояние симулируемого датчика"""
    sensor_id: int
    current_temp: float
    target_temp: float
    mode: SimulationMode
    failure_active: bool = False
    spike_remaining: int = 0


class SensorSimulator:
    """
    Симулятор температурных датчиков.
    Генерирует реалистичные показания с поддержкой различных сценариев.
    """
    
    # Базовые параметры температуры
    DEFAULT_TEMP = 25.0
    MIN_TEMP = 15.0
    MAX_TEMP = 100.0
    NORMAL_VARIATION = 2.0  # ±2°C случайные колебания
    
    # Параметры симуляции
    HEATING_RATE = 3.0  # °C за такт при нагреве
    COOLING_RATE = 2.0  # °C за такт при охлаждении
    SPIKE_DURATION = 5  # количество тактов для скачка
    SPIKE_TEMP = 85.0   # температура при скачке
    
    def __init__(self):
        """Инициализация симулятора"""
        self._sensors: Dict[int, SensorSimState] = {}
        self._global_mode = SimulationMode.NORMAL
    
    def register_sensor(self, sensor_id: int, initial_temp: float = None):
        """
        Зарегистрировать датчик в симуляторе.
        
        Args:
            sensor_id: ID датчика
            initial_temp: Начальная температура (если не указана, используется DEFAULT_TEMP)
        """
        if initial_temp is None:
            initial_temp = self.DEFAULT_TEMP + random.uniform(-5, 5)
        
        self._sensors[sensor_id] = SensorSimState(
            sensor_id=sensor_id,
            current_temp=initial_temp,
            target_temp=initial_temp,
            mode=SimulationMode.NORMAL
        )
    
    def unregister_sensor(self, sensor_id: int):
        """Удалить датчик из симулятора"""
        if sensor_id in self._sensors:
            del self._sensors[sensor_id]
    
    def get_temperature(self, sensor_id: int) -> Optional[float]:
        """
        Получить текущую температуру датчика.
        
        Args:
            sensor_id: ID датчика
            
        Returns:
            Температура или None, если датчик не зарегистрирован или в сбое
        """
        if sensor_id not in self._sensors:
            # Автоматически регистрируем новый датчик
            self.register_sensor(sensor_id)
        
        state = self._sensors[sensor_id]
        
        # Если датчик в режиме сбоя, возвращаем None
        if state.failure_active:
            return None
        
        return round(state.current_temp, 1)
    
    def update(self):
        """
        Обновить состояние всех датчиков.
        Вызывать на каждом такте симуляции.
        """
        for sensor_id, state in self._sensors.items():
            self._update_sensor(state)
    
    def _update_sensor(self, state: SensorSimState):
        """Обновить состояние одного датчика"""
        mode = state.mode if state.mode != SimulationMode.NORMAL else self._global_mode
        
        # Обработка режима сбоя
        if mode == SimulationMode.FAILURE:
            if not state.failure_active:
                state.failure_active = True
            return
        else:
            state.failure_active = False
        
        # Обработка скачка температуры
        if state.spike_remaining > 0:
            state.spike_remaining -= 1
            # Резкий скачок вверх
            state.current_temp = self.SPIKE_TEMP + random.uniform(-2, 5)
            if state.spike_remaining == 0:
                state.mode = SimulationMode.NORMAL
            return
        
        if mode == SimulationMode.SPIKE:
            state.spike_remaining = self.SPIKE_DURATION
            state.current_temp = self.SPIKE_TEMP
            return
        
        # Нормальное поведение с целевой температурой
        if mode == SimulationMode.HEATING:
            state.target_temp = min(state.target_temp + self.HEATING_RATE, self.MAX_TEMP)
        elif mode == SimulationMode.COOLING:
            state.target_temp = max(state.target_temp - self.COOLING_RATE, self.MIN_TEMP)
        elif mode == SimulationMode.NORMAL:
            # Плавное возвращение к норме
            if state.target_temp > self.DEFAULT_TEMP + 5:
                state.target_temp -= self.COOLING_RATE * 0.5
            elif state.target_temp < self.DEFAULT_TEMP - 5:
                state.target_temp += self.HEATING_RATE * 0.5
            else:
                state.target_temp = self.DEFAULT_TEMP + random.uniform(-2, 2)
        
        # Плавное изменение текущей температуры к целевой
        diff = state.target_temp - state.current_temp
        change = diff * 0.3 + random.uniform(-self.NORMAL_VARIATION, self.NORMAL_VARIATION)
        state.current_temp += change
        
        # Ограничение диапазона
        state.current_temp = max(self.MIN_TEMP, min(self.MAX_TEMP, state.current_temp))
    
    def set_sensor_mode(self, sensor_id: int, mode: SimulationMode):
        """
        Установить режим симуляции для конкретного датчика.
        
        Args:
            sensor_id: ID датчика
            mode: Режим симуляции
        """
        if sensor_id not in self._sensors:
            self.register_sensor(sensor_id)
        
        self._sensors[sensor_id].mode = mode
        
        if mode == SimulationMode.FAILURE:
            self._sensors[sensor_id].failure_active = True
        else:
            self._sensors[sensor_id].failure_active = False
    
    def set_global_mode(self, mode: SimulationMode):
        """
        Установить глобальный режим симуляции для всех датчиков.
        
        Args:
            mode: Режим симуляции
        """
        self._global_mode = mode
    
    def trigger_spike(self, sensor_id: int):
        """Вызвать скачок температуры для датчика"""
        self.set_sensor_mode(sensor_id, SimulationMode.SPIKE)
    
    def trigger_failure(self, sensor_id: int):
        """Вызвать сбой датчика"""
        self.set_sensor_mode(sensor_id, SimulationMode.FAILURE)
    
    def reset_sensor(self, sensor_id: int):
        """Сбросить датчик в нормальный режим"""
        if sensor_id in self._sensors:
            state = self._sensors[sensor_id]
            state.mode = SimulationMode.NORMAL
            state.failure_active = False
            state.spike_remaining = 0
            state.target_temp = self.DEFAULT_TEMP
    
    def reset_all(self):
        """Сбросить все датчики в нормальный режим"""
        self._global_mode = SimulationMode.NORMAL
        for sensor_id in self._sensors:
            self.reset_sensor(sensor_id)
    
    def get_sensor_state(self, sensor_id: int) -> Optional[SensorSimState]:
        """Получить состояние датчика"""
        return self._sensors.get(sensor_id)
    
    def get_all_states(self) -> Dict[int, SensorSimState]:
        """Получить состояния всех датчиков"""
        return self._sensors.copy()
