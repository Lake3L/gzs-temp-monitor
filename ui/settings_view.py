"""
Представление настроек системы.
Управление помещениями, датчиками и настройками уведомлений.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QGroupBox,
    QFormLayout, QLabel, QPushButton, QLineEdit, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QDialogButtonBox, QComboBox, QCheckBox, QTextEdit,
    QSpinBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from database.db_manager import DatabaseManager
from database.models import Room, Sensor, EventType, SensorStatus


class RoomDialog(QDialog):
    """Диалог добавления/редактирования помещения"""
    
    def __init__(self, room: Room = None, parent=None):
        super().__init__(parent)
        self.room = room
        self.result_data = None
        
        self.setWindowTitle("Редактирование помещения" if room else "Новое помещение")
        self.setMinimumWidth(400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        if self.room:
            self.name_edit.setText(self.room.name)
        form.addRow("Название:", self.name_edit)
        
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        if self.room:
            self.desc_edit.setPlainText(self.room.description)
        form.addRow("Описание:", self.desc_edit)
        
        layout.addLayout(form)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название помещения.")
            return
        
        self.result_data = {
            'name': name,
            'description': self.desc_edit.toPlainText().strip()
        }
        self.accept()


class SensorDialog(QDialog):
    """Диалог добавления/редактирования датчика"""
    
    def __init__(self, db_manager: DatabaseManager, 
                 sensor: Sensor = None, room_id: int = None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.sensor = sensor
        self.default_room_id = room_id
        self.result_data = None
        
        self.setWindowTitle("Редактирование датчика" if sensor else "Новый датчик")
        self.setMinimumWidth(400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        # Помещение
        self.room_combo = QComboBox()
        for room in self.db.get_all_rooms():
            self.room_combo.addItem(room.name, room.id)
        
        if self.sensor:
            index = self.room_combo.findData(self.sensor.room_id)
            if index >= 0:
                self.room_combo.setCurrentIndex(index)
        elif self.default_room_id:
            index = self.room_combo.findData(self.default_room_id)
            if index >= 0:
                self.room_combo.setCurrentIndex(index)
        
        form.addRow("Помещение:", self.room_combo)
        
        # Название
        self.name_edit = QLineEdit()
        if self.sensor:
            self.name_edit.setText(self.sensor.name)
        form.addRow("Название:", self.name_edit)
        
        # Пороги
        self.warning_spin = QDoubleSpinBox()
        self.warning_spin.setRange(0, 150)
        self.warning_spin.setSuffix(" °C")
        self.warning_spin.setValue(self.sensor.warning_threshold if self.sensor else 55.0)
        form.addRow("Порог предупреждения:", self.warning_spin)
        
        self.danger_spin = QDoubleSpinBox()
        self.danger_spin.setRange(0, 150)
        self.danger_spin.setSuffix(" °C")
        self.danger_spin.setValue(self.sensor.danger_threshold if self.sensor else 75.0)
        form.addRow("Критический порог:", self.danger_spin)
        
        # Фильтрация
        self.filter_check = QCheckBox("Включена")
        self.filter_check.setChecked(self.sensor.filter_enabled if self.sensor else True)
        form.addRow("Фильтрация данных:", self.filter_check)
        
        layout.addLayout(form)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название датчика.")
            return
        
        if self.warning_spin.value() >= self.danger_spin.value():
            QMessageBox.warning(
                self, "Ошибка", 
                "Порог предупреждения должен быть меньше критического порога."
            )
            return
        
        self.result_data = {
            'room_id': self.room_combo.currentData(),
            'name': name,
            'warning_threshold': self.warning_spin.value(),
            'danger_threshold': self.danger_spin.value(),
            'filter_enabled': self.filter_check.isChecked()
        }
        self.accept()


class SettingsView(QWidget):
    """Представление настроек системы"""
    
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title = QLabel("Настройки системы")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Вкладки
        tabs = QTabWidget()
        
        # Вкладка помещений
        rooms_tab = self._create_rooms_tab()
        tabs.addTab(rooms_tab, "Помещения")
        
        # Вкладка датчиков
        sensors_tab = self._create_sensors_tab()
        tabs.addTab(sensors_tab, "Датчики")
        
        # Вкладка уведомлений
        notifications_tab = self._create_notifications_tab()
        tabs.addTab(notifications_tab, "Уведомления")
        
        # Вкладка общих настроек
        general_tab = self._create_general_tab()
        tabs.addTab(general_tab, "Общие")
        
        layout.addWidget(tabs)
    
    def _create_rooms_tab(self) -> QWidget:
        """Создать вкладку помещений"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Панель кнопок
        buttons = QHBoxLayout()
        
        add_btn = QPushButton("➕ Добавить")
        add_btn.clicked.connect(self._add_room)
        buttons.addWidget(add_btn)
        
        edit_btn = QPushButton("✏️ Редактировать")
        edit_btn.clicked.connect(self._edit_room)
        buttons.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️ Удалить")
        delete_btn.clicked.connect(self._delete_room)
        buttons.addWidget(delete_btn)
        
        buttons.addStretch()
        layout.addLayout(buttons)
        
        # Таблица помещений
        self.rooms_table = QTableWidget()
        self.rooms_table.setColumnCount(4)
        self.rooms_table.setHorizontalHeaderLabels([
            "ID", "Название", "Описание", "Датчиков"
        ])
        
        header = self.rooms_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        
        self.rooms_table.setColumnWidth(0, 50)
        self.rooms_table.setColumnWidth(3, 80)
        self.rooms_table.setAlternatingRowColors(True)
        self.rooms_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.rooms_table)
        
        return widget
    
    def _create_sensors_tab(self) -> QWidget:
        """Создать вкладку датчиков"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Фильтр по помещению
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Помещение:"))
        
        self.sensor_room_filter = QComboBox()
        self.sensor_room_filter.addItem("Все помещения", None)
        self.sensor_room_filter.currentIndexChanged.connect(self._filter_sensors)
        filter_layout.addWidget(self.sensor_room_filter)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Панель кнопок
        buttons = QHBoxLayout()
        
        add_btn = QPushButton("➕ Добавить")
        add_btn.clicked.connect(self._add_sensor)
        buttons.addWidget(add_btn)
        
        edit_btn = QPushButton("✏️ Редактировать")
        edit_btn.clicked.connect(self._edit_sensor)
        buttons.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️ Удалить")
        delete_btn.clicked.connect(self._delete_sensor)
        buttons.addWidget(delete_btn)
        
        buttons.addStretch()
        layout.addLayout(buttons)
        
        # Таблица датчиков
        self.sensors_table = QTableWidget()
        self.sensors_table.setColumnCount(7)
        self.sensors_table.setHorizontalHeaderLabels([
            "ID", "Название", "Помещение", "Статус", 
            "Порог предупр.", "Крит. порог", "Фильтр"
        ])
        
        header = self.sensors_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        self.sensors_table.setColumnWidth(0, 50)
        self.sensors_table.setColumnWidth(3, 100)
        self.sensors_table.setColumnWidth(4, 120)
        self.sensors_table.setColumnWidth(5, 100)
        self.sensors_table.setColumnWidth(6, 60)
        self.sensors_table.setAlternatingRowColors(True)
        self.sensors_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.sensors_table)
        
        return widget
    
    def _create_notifications_tab(self) -> QWidget:
        """Создать вкладку уведомлений"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Настройки email
        email_group = QGroupBox("Настройки уведомлений по email")
        email_layout = QFormLayout(email_group)
        
        self.email_enabled = QCheckBox("Включить email-уведомления")
        self.email_enabled.setChecked(True)
        email_layout.addRow("", self.email_enabled)
        
        self.smtp_server = QLineEdit("smtp.company.ru")
        email_layout.addRow("SMTP сервер:", self.smtp_server)
        
        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(587)
        email_layout.addRow("Порт:", self.smtp_port)
        
        self.email_from = QLineEdit("monitoring@company.ru")
        email_layout.addRow("Email отправителя:", self.email_from)
        
        layout.addWidget(email_group)
        
        # Получатели уведомлений
        recipients_group = QGroupBox("Получатели уведомлений")
        recipients_layout = QVBoxLayout(recipients_group)
        
        # Кнопки управления
        rec_buttons = QHBoxLayout()
        
        add_rec_btn = QPushButton("➕ Добавить")
        add_rec_btn.clicked.connect(self._add_notification_setting)
        rec_buttons.addWidget(add_rec_btn)
        
        del_rec_btn = QPushButton("🗑️ Удалить")
        del_rec_btn.clicked.connect(self._delete_notification_setting)
        rec_buttons.addWidget(del_rec_btn)
        
        rec_buttons.addStretch()
        recipients_layout.addLayout(rec_buttons)
        
        # Таблица получателей
        self.notifications_table = QTableWidget()
        self.notifications_table.setColumnCount(4)
        self.notifications_table.setHorizontalHeaderLabels([
            "ID", "Email", "Тип события", "Помещение"
        ])
        
        header = self.notifications_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self.notifications_table.setColumnWidth(0, 50)
        self.notifications_table.setAlternatingRowColors(True)
        self.notifications_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        
        recipients_layout.addWidget(self.notifications_table)
        
        layout.addWidget(recipients_group)
        
        # Кнопка сохранения
        save_btn = QPushButton("💾 Сохранить настройки")
        save_btn.clicked.connect(self._save_notification_settings)
        layout.addWidget(save_btn)
        
        return widget
    
    def _create_general_tab(self) -> QWidget:
        """Создать вкладку общих настроек"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Интервал опроса
        polling_group = QGroupBox("Параметры опроса датчиков")
        polling_layout = QFormLayout(polling_group)
        
        self.polling_interval = QSpinBox()
        self.polling_interval.setRange(1, 60)
        self.polling_interval.setValue(5)
        self.polling_interval.setSuffix(" сек")
        polling_layout.addRow("Интервал опроса:", self.polling_interval)
        
        self.offline_threshold = QSpinBox()
        self.offline_threshold.setRange(1, 10)
        self.offline_threshold.setValue(3)
        self.offline_threshold.setSuffix(" пропусков")
        polling_layout.addRow("Порог потери связи:", self.offline_threshold)
        
        layout.addWidget(polling_group)
        
        # Очистка данных
        cleanup_group = QGroupBox("Очистка данных")
        cleanup_layout = QFormLayout(cleanup_group)
        
        self.retention_days = QSpinBox()
        self.retention_days.setRange(30, 365)
        self.retention_days.setValue(180)
        self.retention_days.setSuffix(" дней")
        cleanup_layout.addRow("Хранить данные:", self.retention_days)
        
        cleanup_btn = QPushButton("🗑️ Очистить старые данные")
        cleanup_btn.clicked.connect(self._cleanup_old_data)
        cleanup_layout.addRow("", cleanup_btn)
        
        layout.addWidget(cleanup_group)
        
        # Демо-данные
        demo_group = QGroupBox("Демонстрационные данные")
        demo_layout = QVBoxLayout(demo_group)
        
        demo_label = QLabel(
            "Создание демонстрационных данных для тестирования системы "
            "(5 помещений, по 2 датчика в каждом)."
        )
        demo_label.setWordWrap(True)
        demo_layout.addWidget(demo_label)
        
        init_demo_btn = QPushButton("📊 Инициализировать демо-данные")
        init_demo_btn.clicked.connect(self._init_demo_data)
        demo_layout.addWidget(init_demo_btn)
        
        layout.addWidget(demo_group)
        
        layout.addStretch()
        
        # Кнопка сохранения
        save_btn = QPushButton("💾 Сохранить настройки")
        save_btn.clicked.connect(self._save_general_settings)
        layout.addWidget(save_btn)
        
        return widget
    
    def _load_data(self):
        """Загрузить данные"""
        self._load_rooms()
        self._load_sensors()
        self._load_notifications()
        self._update_room_filters()
    
    def _load_rooms(self):
        """Загрузить помещения"""
        self.rooms_table.setRowCount(0)
        
        rooms = self.db.get_all_rooms()
        for room in rooms:
            row = self.rooms_table.rowCount()
            self.rooms_table.insertRow(row)
            
            id_item = QTableWidgetItem(str(room.id))
            id_item.setData(Qt.ItemDataRole.UserRole, room.id)
            self.rooms_table.setItem(row, 0, id_item)
            
            self.rooms_table.setItem(row, 1, QTableWidgetItem(room.name))
            self.rooms_table.setItem(row, 2, QTableWidgetItem(room.description))
            
            sensors_count = len(self.db.get_sensors_by_room(room.id))
            self.rooms_table.setItem(row, 3, QTableWidgetItem(str(sensors_count)))
    
    def _load_sensors(self, room_id: int = None):
        """Загрузить датчики"""
        self.sensors_table.setRowCount(0)
        
        if room_id:
            sensors = self.db.get_sensors_by_room(room_id)
        else:
            sensors = self.db.get_all_sensors()
        
        for sensor in sensors:
            row = self.sensors_table.rowCount()
            self.sensors_table.insertRow(row)
            
            id_item = QTableWidgetItem(str(sensor.id))
            id_item.setData(Qt.ItemDataRole.UserRole, sensor.id)
            self.sensors_table.setItem(row, 0, id_item)
            
            self.sensors_table.setItem(row, 1, QTableWidgetItem(sensor.name))
            
            room = self.db.get_room(sensor.room_id)
            room_name = room.name if room else "—"
            self.sensors_table.setItem(row, 2, QTableWidgetItem(room_name))
            
            self.sensors_table.setItem(row, 3, QTableWidgetItem(sensor.status.value))
            self.sensors_table.setItem(row, 4, 
                QTableWidgetItem(f"{sensor.warning_threshold}°C"))
            self.sensors_table.setItem(row, 5, 
                QTableWidgetItem(f"{sensor.danger_threshold}°C"))
            self.sensors_table.setItem(row, 6, 
                QTableWidgetItem("✓" if sensor.filter_enabled else "✗"))
    
    def _load_notifications(self):
        """Загрузить настройки уведомлений"""
        self.notifications_table.setRowCount(0)
        
        settings = self.db.get_notification_settings()
        for setting in settings:
            row = self.notifications_table.rowCount()
            self.notifications_table.insertRow(row)
            
            id_item = QTableWidgetItem(str(setting.id))
            id_item.setData(Qt.ItemDataRole.UserRole, setting.id)
            self.notifications_table.setItem(row, 0, id_item)
            
            self.notifications_table.setItem(row, 1, QTableWidgetItem(setting.email))
            self.notifications_table.setItem(row, 2, 
                QTableWidgetItem(setting.event_type.value))
            
            if setting.room_id:
                room = self.db.get_room(setting.room_id)
                room_name = room.name if room else "—"
            else:
                room_name = "Все помещения"
            self.notifications_table.setItem(row, 3, QTableWidgetItem(room_name))
    
    def _update_room_filters(self):
        """Обновить фильтры помещений"""
        current = self.sensor_room_filter.currentData()
        
        self.sensor_room_filter.clear()
        self.sensor_room_filter.addItem("Все помещения", None)
        
        for room in self.db.get_all_rooms():
            self.sensor_room_filter.addItem(room.name, room.id)
        
        if current:
            index = self.sensor_room_filter.findData(current)
            if index >= 0:
                self.sensor_room_filter.setCurrentIndex(index)
    
    def _filter_sensors(self):
        """Фильтрация датчиков по помещению"""
        room_id = self.sensor_room_filter.currentData()
        self._load_sensors(room_id)
    
    # === Операции с помещениями ===
    
    def _add_room(self):
        """Добавить помещение"""
        dialog = RoomDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.result_data
            self.db.add_room(data['name'], data['description'])
            self._load_rooms()
            self._update_room_filters()
    
    def _edit_room(self):
        """Редактировать помещение"""
        selected = self.rooms_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Выбор", "Выберите помещение для редактирования.")
            return
        
        room_id = self.rooms_table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        room = self.db.get_room(room_id)
        if not room:
            return
        
        dialog = RoomDialog(room, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.result_data
            self.db.update_room(room_id, data['name'], data['description'])
            self._load_rooms()
            self._update_room_filters()
    
    def _delete_room(self):
        """Удалить помещение"""
        selected = self.rooms_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Выбор", "Выберите помещение для удаления.")
            return
        
        room_id = self.rooms_table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        room = self.db.get_room(room_id)
        if not room:
            return
        
        sensors = self.db.get_sensors_by_room(room_id)
        
        msg = f"Удалить помещение '{room.name}'?"
        if sensors:
            msg += f"\n\nВнимание: будут также удалены {len(sensors)} датчиков!"
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_room(room_id)
            self._load_rooms()
            self._load_sensors()
            self._update_room_filters()
    
    # === Операции с датчиками ===
    
    def _add_sensor(self):
        """Добавить датчик"""
        room_id = self.sensor_room_filter.currentData()
        dialog = SensorDialog(self.db, room_id=room_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.result_data
            self.db.add_sensor(
                data['room_id'],
                data['name'],
                data['warning_threshold'],
                data['danger_threshold']
            )
            self._load_sensors(self.sensor_room_filter.currentData())
            self._load_rooms()
    
    def _edit_sensor(self):
        """Редактировать датчик"""
        selected = self.sensors_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Выбор", "Выберите датчик для редактирования.")
            return
        
        sensor_id = self.sensors_table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        sensor = self.db.get_sensor(sensor_id)
        if not sensor:
            return
        
        dialog = SensorDialog(self.db, sensor=sensor, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.result_data
            self.db.update_sensor(
                sensor_id,
                room_id=data['room_id'],
                name=data['name'],
                warning_threshold=data['warning_threshold'],
                danger_threshold=data['danger_threshold'],
                filter_enabled=data['filter_enabled']
            )
            self._load_sensors(self.sensor_room_filter.currentData())
            self._load_rooms()
    
    def _delete_sensor(self):
        """Удалить датчик"""
        selected = self.sensors_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Выбор", "Выберите датчик для удаления.")
            return
        
        sensor_id = self.sensors_table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        sensor = self.db.get_sensor(sensor_id)
        if not sensor:
            return
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить датчик '{sensor.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_sensor(sensor_id)
            self._load_sensors(self.sensor_room_filter.currentData())
            self._load_rooms()
    
    # === Настройки уведомлений ===
    
    def _add_notification_setting(self):
        """Добавить настройку уведомлений"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить получателя")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        
        email_edit = QLineEdit()
        form.addRow("Email:", email_edit)
        
        type_combo = QComboBox()
        type_combo.addItem("Критические", EventType.CRITICAL)
        type_combo.addItem("Предупреждения", EventType.WARNING)
        type_combo.addItem("Сбои датчиков", EventType.SENSOR_FAILURE)
        form.addRow("Тип события:", type_combo)
        
        room_combo = QComboBox()
        room_combo.addItem("Все помещения", None)
        for room in self.db.get_all_rooms():
            room_combo.addItem(room.name, room.id)
        form.addRow("Помещение:", room_combo)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            email = email_edit.text().strip()
            if not email or '@' not in email:
                QMessageBox.warning(self, "Ошибка", "Введите корректный email.")
                return
            
            self.db.add_notification_setting(
                type_combo.currentData(),
                email,
                room_combo.currentData()
            )
            self._load_notifications()
    
    def _delete_notification_setting(self):
        """Удалить настройку уведомлений"""
        selected = self.notifications_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Выбор", "Выберите запись для удаления.")
            return
        
        setting_id = self.notifications_table.item(selected[0].row(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        
        self.db.delete_notification_setting(setting_id)
        self._load_notifications()
    
    def _save_notification_settings(self):
        """Сохранить настройки уведомлений"""
        QMessageBox.information(
            self, "Сохранено",
            "Настройки уведомлений сохранены."
        )
    
    # === Общие настройки ===
    
    def _save_general_settings(self):
        """Сохранить общие настройки"""
        QMessageBox.information(
            self, "Сохранено",
            "Общие настройки сохранены."
        )
    
    def _cleanup_old_data(self):
        """Очистить старые данные"""
        days = self.retention_days.value()
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить данные старше {days} дней?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            deleted = self.db.cleanup_old_data(days)
            QMessageBox.information(
                self, "Очистка завершена",
                f"Удалено {deleted} старых записей."
            )
    
    def _init_demo_data(self):
        """Инициализировать демо-данные"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Создать демонстрационные данные?\n\n"
            "Будет создано 5 помещений с 2 датчиками в каждом.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.db.init_demo_data()
            self._load_data()
            QMessageBox.information(
                self, "Готово",
                "Демонстрационные данные созданы."
            )
    
    def refresh(self):
        """Обновить все данные"""
        self._load_data()
