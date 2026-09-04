"""
Панель мониторинга (дашборд).
Главный экран системы с обзором состояния датчиков.
"""

from datetime import datetime
from typing import Dict, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QGroupBox,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from database.db_manager import DatabaseManager
from database.models import Sensor, Event, EventType, EventStatus, SensorStatus
from simulator.sensor_simulator import SensorSimulator, SimulationMode
from core.data_collector import DataCollector
from core.analyzer import TemperatureAnalyzer


class SensorCard(QFrame):
    """Карточка датчика на дашборде"""
    
    clicked = pyqtSignal(int)  # sensor_id
    
    def __init__(self, sensor: Sensor, parent=None):
        super().__init__(parent)
        self.sensor = sensor
        self.temperature = None
        self.has_event = False
        self.event_type = None
        
        self._setup_ui()
        self._update_style()
    
    def _setup_ui(self):
        """Настройка интерфейса карточки"""
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(2)
        self.setMinimumSize(200, 120)
        self.setMaximumSize(250, 150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Название датчика
        self.name_label = QLabel(self.sensor.name)
        self.name_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)
        
        # Температура
        self.temp_label = QLabel("--°C")
        self.temp_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.temp_label)
        
        # Статус
        self.status_label = QLabel("Ожидание...")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Время обновления
        self.time_label = QLabel("")
        self.time_label.setFont(QFont("Segoe UI", 8))
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("color: gray;")
        layout.addWidget(self.time_label)
    
    def update_temperature(self, temperature: float, timestamp: datetime = None):
        """Обновить отображение температуры"""
        self.temperature = temperature
        self.temp_label.setText(f"{temperature:.1f}°C")
        
        if timestamp:
            self.time_label.setText(timestamp.strftime("%H:%M:%S"))
        
        self._update_style()
    
    def set_event(self, has_event: bool, event_type: EventType = None):
        """Установить состояние события"""
        self.has_event = has_event
        self.event_type = event_type
        
        if has_event and event_type:
            self.status_label.setText(event_type.value)
        else:
            self.status_label.setText("Норма")
        
        self._update_style()
    
    def set_offline(self, offline: bool):
        """Установить статус offline"""
        if offline:
            self.temp_label.setText("--°C")
            self.status_label.setText("Нет связи")
            self.setStyleSheet("""
                SensorCard {
                    background-color: #808080;
                    border: 3px solid #606060;
                    border-radius: 10px;
                }
                QLabel { color: white; }
            """)
        else:
            self._update_style()
    
    def _update_style(self):
        """Обновить стиль карточки в зависимости от состояния"""
        if self.has_event:
            if self.event_type == EventType.CRITICAL:
                self.setStyleSheet("""
                    SensorCard {
                        background-color: #ff4444;
                        border: 3px solid #cc0000;
                        border-radius: 10px;
                    }
                    QLabel { color: white; }
                """)
            elif self.event_type == EventType.WARNING:
                self.setStyleSheet("""
                    SensorCard {
                        background-color: #ffaa00;
                        border: 3px solid #cc8800;
                        border-radius: 10px;
                    }
                    QLabel { color: black; }
                """)
            elif self.event_type == EventType.SENSOR_FAILURE:
                self.setStyleSheet("""
                    SensorCard {
                        background-color: #808080;
                        border: 3px solid #606060;
                        border-radius: 10px;
                    }
                    QLabel { color: white; }
                """)
        else:
            # Нормальное состояние - цвет зависит от температуры
            if self.temperature is not None:
                if self.temperature >= self.sensor.warning_threshold:
                    bg_color = "#ffcc00"
                    border_color = "#cc9900"
                    text_color = "black"
                elif self.temperature >= self.sensor.warning_threshold - 10:
                    bg_color = "#ffffcc"
                    border_color = "#cccc99"
                    text_color = "black"
                else:
                    bg_color = "#44cc44"
                    border_color = "#22aa22"
                    text_color = "white"
            else:
                bg_color = "#e0e0e0"
                border_color = "#c0c0c0"
                text_color = "black"
            
            self.setStyleSheet(f"""
                SensorCard {{
                    background-color: {bg_color};
                    border: 3px solid {border_color};
                    border-radius: 10px;
                }}
                QLabel {{ color: {text_color}; }}
            """)
    
    def mousePressEvent(self, event):
        """Обработка клика по карточке"""
        self.clicked.emit(self.sensor.id)
        super().mousePressEvent(event)


class DashboardView(QWidget):
    """Главный экран мониторинга"""
    
    def __init__(self, db_manager: DatabaseManager,
                 simulator: SensorSimulator,
                 data_collector: DataCollector,
                 analyzer: TemperatureAnalyzer,
                 parent=None):
        super().__init__(parent)
        
        self.db = db_manager
        self.simulator = simulator
        self.collector = data_collector
        self.analyzer = analyzer
        
        self._sensor_cards: Dict[int, SensorCard] = {}
        
        self._setup_ui()
        self._connect_signals()
        self._load_sensors()
    
    def _setup_ui(self):
        """Настройка интерфейса"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Заголовок и управление
        header = QHBoxLayout()
        
        title = QLabel("Панель мониторинга")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.addWidget(title)
        
        header.addStretch()
        
        # Статус сбора данных
        self.status_label = QLabel("Статус: Остановлено")
        self.status_label.setStyleSheet("color: gray;")
        header.addWidget(self.status_label)
        
        # Кнопки управления
        self.start_btn = QPushButton("▶ Запустить")
        self.start_btn.clicked.connect(self._toggle_collection)
        header.addWidget(self.start_btn)
        
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self._refresh_all)
        header.addWidget(self.refresh_btn)
        
        main_layout.addLayout(header)
        
        # Разделитель с датчиками и событиями
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Область датчиков
        sensors_widget = QWidget()
        sensors_layout = QVBoxLayout(sensors_widget)
        sensors_layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок секции датчиков
        sensors_header = QHBoxLayout()
        sensors_title = QLabel("Датчики температуры")
        sensors_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        sensors_header.addWidget(sensors_title)
        
        sensors_header.addStretch()
        
        # Управление симуляцией
        sim_label = QLabel("Симуляция:")
        sensors_header.addWidget(sim_label)
        
        self.sim_mode_combo = QComboBox()
        self.sim_mode_combo.addItems([
            "Нормальный", "Нагрев", "Охлаждение", "Скачок", "Сбой"
        ])
        self.sim_mode_combo.currentTextChanged.connect(self._on_sim_mode_changed)
        sensors_header.addWidget(self.sim_mode_combo)
        
        sensors_layout.addLayout(sensors_header)
        
        # Скролл-область для карточек
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setSpacing(15)
        self.cards_layout.setContentsMargins(5, 5, 5, 5)
        
        scroll.setWidget(self.cards_container)
        sensors_layout.addWidget(scroll)
        
        splitter.addWidget(sensors_widget)
        
        # Таблица активных событий
        events_widget = QGroupBox("Активные события")
        events_layout = QVBoxLayout(events_widget)
        
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(5)
        self.events_table.setHorizontalHeaderLabels([
            "Датчик", "Тип", "Температура", "Время", "Действия"
        ])
        self.events_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.events_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Fixed
        )
        self.events_table.setColumnWidth(4, 150)
        self.events_table.setAlternatingRowColors(True)
        events_layout.addWidget(self.events_table)
        
        splitter.addWidget(events_widget)
        
        # Соотношение размеров
        splitter.setSizes([400, 200])
        
        main_layout.addWidget(splitter)
    
    def _connect_signals(self):
        """Подключение сигналов"""
        # Сигналы от коллектора данных
        self.collector.reading_received.connect(self._on_reading_received)
        self.collector.sensor_offline.connect(self._on_sensor_offline)
        self.collector.sensor_back_online.connect(self._on_sensor_online)
        
        # Сигналы от анализатора
        self.analyzer.event_created.connect(self._on_event_created)
        self.analyzer.event_closed.connect(self._on_event_closed)
    
    def _load_sensors(self):
        """Загрузка датчиков и создание карточек"""
        # Очищаем текущие карточки
        for card in self._sensor_cards.values():
            card.deleteLater()
        self._sensor_cards.clear()
        
        # Получаем датчики по помещениям
        rooms = self.db.get_all_rooms()
        
        row, col = 0, 0
        max_cols = 4
        
        for room in rooms:
            sensors = self.db.get_sensors_by_room(room.id)
            
            for sensor in sensors:
                card = SensorCard(sensor)
                card.clicked.connect(self._on_sensor_clicked)
                
                self.cards_layout.addWidget(card, row, col)
                self._sensor_cards[sensor.id] = card
                
                # Проверяем активное событие
                active_event = self.analyzer.get_active_event(sensor.id)
                if active_event:
                    card.set_event(True, active_event.event_type)
                
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
        
        # Добавляем растяжку
        self.cards_layout.setRowStretch(row + 1, 1)
        
        # Загружаем активные события в таблицу
        self._load_active_events()
    
    def _load_active_events(self):
        """Загрузка активных событий в таблицу"""
        self.events_table.setRowCount(0)
        
        events = self.analyzer.get_active_events()
        
        for event in events:
            self._add_event_row(event)
    
    def _add_event_row(self, event: Event):
        """Добавить строку события в таблицу"""
        row = self.events_table.rowCount()
        self.events_table.insertRow(row)
        
        # Датчик
        sensor = self.db.get_sensor(event.sensor_id)
        sensor_name = sensor.name if sensor else f"#{event.sensor_id}"
        self.events_table.setItem(row, 0, QTableWidgetItem(sensor_name))
        
        # Тип
        type_item = QTableWidgetItem(event.event_type.value)
        if event.event_type == EventType.CRITICAL:
            type_item.setBackground(QColor("#ff4444"))
            type_item.setForeground(QColor("white"))
        elif event.event_type == EventType.WARNING:
            type_item.setBackground(QColor("#ffaa00"))
        self.events_table.setItem(row, 1, type_item)
        
        # Температура
        self.events_table.setItem(row, 2, 
            QTableWidgetItem(f"{event.temperature:.1f}°C"))
        
        # Время
        self.events_table.setItem(row, 3, 
            QTableWidgetItem(event.start_time.strftime("%H:%M:%S")))
        
        # Кнопка подтверждения
        ack_btn = QPushButton("Подтвердить")
        ack_btn.setProperty("event_id", event.id)
        ack_btn.clicked.connect(lambda checked, eid=event.id: self._acknowledge_event(eid))
        self.events_table.setCellWidget(row, 4, ack_btn)
    
    def _toggle_collection(self):
        """Включить/выключить сбор данных"""
        if self.collector.is_running():
            self.collector.stop()
            self.start_btn.setText("▶ Запустить")
            self.status_label.setText("Статус: Остановлено")
            self.status_label.setStyleSheet("color: gray;")
        else:
            self.collector.start()
            self.start_btn.setText("⏹ Остановить")
            self.status_label.setText("Статус: Активно")
            self.status_label.setStyleSheet("color: green;")
    
    def _refresh_all(self):
        """Обновить все данные"""
        self._load_sensors()
        self.analyzer.refresh_active_events()
        self._load_active_events()
    
    def _on_reading_received(self, sensor_id: int, temperature: float, 
                              timestamp: datetime):
        """Обработка нового показания"""
        # Обновляем карточку
        if sensor_id in self._sensor_cards:
            card = self._sensor_cards[sensor_id]
            card.update_temperature(temperature, timestamp)
        
        # Анализируем показание
        self.analyzer.analyze_reading(sensor_id, temperature, timestamp)
    
    def _on_sensor_offline(self, sensor_id: int):
        """Обработка потери связи с датчиком"""
        if sensor_id in self._sensor_cards:
            self._sensor_cards[sensor_id].set_offline(True)
        
        self.analyzer.handle_sensor_failure(sensor_id)
    
    def _on_sensor_online(self, sensor_id: int):
        """Обработка восстановления связи"""
        if sensor_id in self._sensor_cards:
            self._sensor_cards[sensor_id].set_offline(False)
        
        self.analyzer.handle_sensor_recovery(sensor_id)
    
    def _on_event_created(self, event_id: int, event: Event):
        """Обработка создания события"""
        # Обновляем карточку
        if event.sensor_id in self._sensor_cards:
            self._sensor_cards[event.sensor_id].set_event(True, event.event_type)
        
        # Добавляем в таблицу
        self._add_event_row(event)
    
    def _on_event_closed(self, event_id: int):
        """Обработка закрытия события"""
        # Обновляем таблицу
        self._load_active_events()
        
        # Обновляем карточки
        for sensor_id, card in self._sensor_cards.items():
            active_event = self.analyzer.get_active_event(sensor_id)
            if active_event:
                card.set_event(True, active_event.event_type)
            else:
                card.set_event(False)
    
    def _on_sensor_clicked(self, sensor_id: int):
        """Обработка клика по карточке датчика"""
        sensor = self.db.get_sensor(sensor_id)
        if not sensor:
            return
        
        room = self.db.get_room(sensor.room_id)
        room_name = room.name if room else "Неизвестно"
        
        # Получаем последнее показание
        latest = self.db.get_latest_reading(sensor_id)
        temp_str = f"{latest.temperature:.1f}°C" if latest else "Нет данных"
        
        QMessageBox.information(
            self,
            f"Информация о датчике",
            f"Датчик: {sensor.name}\n"
            f"Помещение: {room_name}\n"
            f"Текущая температура: {temp_str}\n"
            f"Порог предупреждения: {sensor.warning_threshold}°C\n"
            f"Критический порог: {sensor.danger_threshold}°C\n"
            f"Статус: {sensor.status.value}"
        )
    
    def _on_sim_mode_changed(self, mode_text: str):
        """Обработка изменения режима симуляции"""
        mode_map = {
            "Нормальный": SimulationMode.NORMAL,
            "Нагрев": SimulationMode.HEATING,
            "Охлаждение": SimulationMode.COOLING,
            "Скачок": SimulationMode.SPIKE,
            "Сбой": SimulationMode.FAILURE
        }
        
        mode = mode_map.get(mode_text, SimulationMode.NORMAL)
        self.simulator.set_global_mode(mode)
    
    def _acknowledge_event(self, event_id: int):
        """Подтвердить событие"""
        self.db.update_event_status(
            event_id, 
            EventStatus.ACKNOWLEDGED,
            acknowledged_by="operator"
        )
        
        # Обновляем таблицу
        self._load_active_events()
        
        QMessageBox.information(
            self,
            "Событие подтверждено",
            f"Событие #{event_id} подтверждено оператором."
        )
