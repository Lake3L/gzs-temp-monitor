"""
Представление событий и журнала.
Отображает историю событий превышения температуры.
"""

from datetime import datetime, timedelta
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QComboBox, QDateEdit, QGroupBox, QFormLayout,
    QLineEdit, QTextEdit, QDialog, QDialogButtonBox, QHeaderView,
    QMessageBox, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from database.db_manager import DatabaseManager
from database.models import Event, EventType, EventStatus


class EventDetailsDialog(QDialog):
    """Диалог деталей события"""
    
    def __init__(self, event: Event, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.event = event
        self.db = db_manager
        
        self.setWindowTitle(f"Событие #{event.id}")
        self.setMinimumSize(500, 400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Информация о событии
        info_group = QGroupBox("Информация о событии")
        info_layout = QFormLayout(info_group)
        
        # Датчик
        sensor = self.db.get_sensor(self.event.sensor_id)
        sensor_name = sensor.name if sensor else f"#{self.event.sensor_id}"
        room = self.db.get_room(sensor.room_id) if sensor else None
        room_name = room.name if room else "Неизвестно"
        
        info_layout.addRow("Датчик:", QLabel(sensor_name))
        info_layout.addRow("Помещение:", QLabel(room_name))
        
        # Тип события
        type_label = QLabel(self.event.event_type.value)
        if self.event.event_type == EventType.CRITICAL:
            type_label.setStyleSheet("color: red; font-weight: bold;")
        elif self.event.event_type == EventType.WARNING:
            type_label.setStyleSheet("color: orange; font-weight: bold;")
        info_layout.addRow("Тип:", type_label)
        
        # Температура
        info_layout.addRow("Температура:", 
            QLabel(f"{self.event.temperature:.1f}°C"))
        info_layout.addRow("Превышенный порог:", 
            QLabel(f"{self.event.threshold_exceeded:.1f}°C"))
        
        # Время
        info_layout.addRow("Начало:", 
            QLabel(self.event.start_time.strftime("%d.%m.%Y %H:%M:%S")))
        
        if self.event.end_time:
            info_layout.addRow("Окончание:", 
                QLabel(self.event.end_time.strftime("%d.%m.%Y %H:%M:%S")))
            duration = self.event.end_time - self.event.start_time
            info_layout.addRow("Длительность:", 
                QLabel(str(duration).split('.')[0]))
        
        # Статус
        status_label = QLabel(self.event.status.value)
        if self.event.status == EventStatus.ACTIVE:
            status_label.setStyleSheet("color: red;")
        elif self.event.status == EventStatus.ACKNOWLEDGED:
            status_label.setStyleSheet("color: orange;")
        else:
            status_label.setStyleSheet("color: green;")
        info_layout.addRow("Статус:", status_label)
        
        if self.event.acknowledged_by:
            info_layout.addRow("Подтверждено:", 
                QLabel(f"{self.event.acknowledged_by} ({self.event.acknowledged_at.strftime('%d.%m.%Y %H:%M') if self.event.acknowledged_at else ''})"))
        
        layout.addWidget(info_group)
        
        # Описание
        if self.event.description:
            desc_group = QGroupBox("Описание")
            desc_layout = QVBoxLayout(desc_group)
            desc_text = QLabel(self.event.description)
            desc_text.setWordWrap(True)
            desc_layout.addWidget(desc_text)
            layout.addWidget(desc_group)
        
        # Действия и примечания
        action_group = QGroupBox("Действия и примечания")
        action_layout = QFormLayout(action_group)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(self.event.notes or "")
        self.notes_edit.setMaximumHeight(80)
        action_layout.addRow("Примечания:", self.notes_edit)
        
        self.action_edit = QLineEdit()
        self.action_edit.setText(self.event.action_taken or "")
        action_layout.addRow("Принятые меры:", self.action_edit)
        
        layout.addWidget(action_group)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        if self.event.status == EventStatus.ACTIVE:
            ack_btn = QPushButton("Подтвердить")
            ack_btn.clicked.connect(self._acknowledge)
            buttons_layout.addWidget(ack_btn)
        
        if self.event.status != EventStatus.RESOLVED:
            resolve_btn = QPushButton("Разрешить")
            resolve_btn.clicked.connect(self._resolve)
            buttons_layout.addWidget(resolve_btn)
        
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self._save)
        buttons_layout.addWidget(save_btn)
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
    
    def _acknowledge(self):
        """Подтвердить событие"""
        notes = self.notes_edit.toPlainText()
        self.db.update_event_status(
            self.event.id,
            EventStatus.ACKNOWLEDGED,
            acknowledged_by="operator",
            notes=notes
        )
        self.accept()
    
    def _resolve(self):
        """Разрешить событие"""
        notes = self.notes_edit.toPlainText()
        action = self.action_edit.text()
        self.db.update_event_status(
            self.event.id,
            EventStatus.RESOLVED,
            notes=notes,
            action_taken=action
        )
        self.accept()
    
    def _save(self):
        """Сохранить примечания"""
        notes = self.notes_edit.toPlainText()
        action = self.action_edit.text()
        self.db.update_event_status(
            self.event.id,
            self.event.status,
            notes=notes,
            action_taken=action
        )
        QMessageBox.information(self, "Сохранено", "Изменения сохранены.")


class EventsView(QWidget):
    """Представление журнала событий"""
    
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        
        self._setup_ui()
        self._load_events()
    
    def _setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title = QLabel("Журнал событий")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Фильтры
        filter_group = QGroupBox("Фильтры")
        filter_layout = QHBoxLayout(filter_group)
        
        # Период
        filter_layout.addWidget(QLabel("Период:"))
        
        self.period_combo = QComboBox()
        self.period_combo.addItems([
            "Сегодня", "Вчера", "Последние 7 дней", 
            "Последние 30 дней", "Произвольный"
        ])
        self.period_combo.currentTextChanged.connect(self._on_period_changed)
        filter_layout.addWidget(self.period_combo)
        
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addDays(-7))
        self.date_from.setCalendarPopup(True)
        self.date_from.setEnabled(False)
        filter_layout.addWidget(QLabel("С:"))
        filter_layout.addWidget(self.date_from)
        
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setEnabled(False)
        filter_layout.addWidget(QLabel("По:"))
        filter_layout.addWidget(self.date_to)
        
        filter_layout.addSpacing(20)
        
        # Тип события
        filter_layout.addWidget(QLabel("Тип:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("Все типы", None)
        self.type_combo.addItem("Предупреждение", EventType.WARNING)
        self.type_combo.addItem("Критическая ситуация", EventType.CRITICAL)
        self.type_combo.addItem("Сбой датчика", EventType.SENSOR_FAILURE)
        filter_layout.addWidget(self.type_combo)
        
        # Статус
        filter_layout.addWidget(QLabel("Статус:"))
        self.status_combo = QComboBox()
        self.status_combo.addItem("Все статусы", None)
        self.status_combo.addItem("Активно", EventStatus.ACTIVE)
        self.status_combo.addItem("Подтверждено", EventStatus.ACKNOWLEDGED)
        self.status_combo.addItem("Разрешено", EventStatus.RESOLVED)
        filter_layout.addWidget(self.status_combo)
        
        # Помещение
        filter_layout.addWidget(QLabel("Помещение:"))
        self.room_combo = QComboBox()
        self.room_combo.addItem("Все помещения", None)
        for room in self.db.get_all_rooms():
            self.room_combo.addItem(room.name, room.id)
        filter_layout.addWidget(self.room_combo)
        
        filter_layout.addStretch()
        
        # Кнопка применения фильтра
        apply_btn = QPushButton("Применить")
        apply_btn.clicked.connect(self._load_events)
        filter_layout.addWidget(apply_btn)
        
        layout.addWidget(filter_group)
        
        # Таблица событий
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(8)
        self.events_table.setHorizontalHeaderLabels([
            "ID", "Дата/Время", "Помещение", "Датчик", 
            "Тип", "Температура", "Статус", "Действия"
        ])
        
        # Настройка заголовков
        header = self.events_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        
        self.events_table.setColumnWidth(0, 50)
        self.events_table.setColumnWidth(1, 140)
        self.events_table.setColumnWidth(4, 150)
        self.events_table.setColumnWidth(5, 100)
        self.events_table.setColumnWidth(6, 120)
        self.events_table.setColumnWidth(7, 100)
        
        self.events_table.setAlternatingRowColors(True)
        self.events_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.events_table.doubleClicked.connect(self._on_row_double_click)
        
        layout.addWidget(self.events_table)
        
        # Нижняя панель
        bottom_layout = QHBoxLayout()
        
        self.count_label = QLabel("Всего событий: 0")
        bottom_layout.addWidget(self.count_label)
        
        bottom_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self._load_events)
        bottom_layout.addWidget(refresh_btn)
        
        export_btn = QPushButton("📤 Экспорт")
        export_btn.clicked.connect(self._export_events)
        bottom_layout.addWidget(export_btn)
        
        layout.addLayout(bottom_layout)
    
    def _on_period_changed(self, period_text: str):
        """Обработка изменения периода"""
        custom = period_text == "Произвольный"
        self.date_from.setEnabled(custom)
        self.date_to.setEnabled(custom)
        
        if not custom:
            today = QDate.currentDate()
            
            if period_text == "Сегодня":
                self.date_from.setDate(today)
                self.date_to.setDate(today)
            elif period_text == "Вчера":
                yesterday = today.addDays(-1)
                self.date_from.setDate(yesterday)
                self.date_to.setDate(yesterday)
            elif period_text == "Последние 7 дней":
                self.date_from.setDate(today.addDays(-7))
                self.date_to.setDate(today)
            elif period_text == "Последние 30 дней":
                self.date_from.setDate(today.addDays(-30))
                self.date_to.setDate(today)
    
    def _get_filter_dates(self):
        """Получить даты фильтра"""
        from_date = self.date_from.date()
        to_date = self.date_to.date()
        
        start = datetime(from_date.year(), from_date.month(), from_date.day(), 0, 0, 0)
        end = datetime(to_date.year(), to_date.month(), to_date.day(), 23, 59, 59)
        
        return start, end
    
    def _load_events(self):
        """Загрузка событий с учётом фильтров"""
        self.events_table.setRowCount(0)
        
        # Получаем параметры фильтра
        start_time, end_time = self._get_filter_dates()
        event_type = self.type_combo.currentData()
        status = self.status_combo.currentData()
        room_id = self.room_combo.currentData()
        
        # Получаем события
        events = self.db.get_events(
            start_time=start_time,
            end_time=end_time,
            event_type=event_type,
            status=status,
            room_id=room_id
        )
        
        for event in events:
            self._add_event_row(event)
        
        self.count_label.setText(f"Всего событий: {len(events)}")
    
    def _add_event_row(self, event: Event):
        """Добавить строку события"""
        row = self.events_table.rowCount()
        self.events_table.insertRow(row)
        
        # ID
        id_item = QTableWidgetItem(str(event.id))
        id_item.setData(Qt.ItemDataRole.UserRole, event.id)
        self.events_table.setItem(row, 0, id_item)
        
        # Дата/время
        self.events_table.setItem(row, 1, 
            QTableWidgetItem(event.start_time.strftime("%d.%m.%Y %H:%M")))
        
        # Помещение и датчик
        sensor = self.db.get_sensor(event.sensor_id)
        if sensor:
            room = self.db.get_room(sensor.room_id)
            self.events_table.setItem(row, 2, 
                QTableWidgetItem(room.name if room else "—"))
            self.events_table.setItem(row, 3, 
                QTableWidgetItem(sensor.name))
        else:
            self.events_table.setItem(row, 2, QTableWidgetItem("—"))
            self.events_table.setItem(row, 3, 
                QTableWidgetItem(f"#{event.sensor_id}"))
        
        # Тип события
        type_item = QTableWidgetItem(event.event_type.value)
        if event.event_type == EventType.CRITICAL:
            type_item.setBackground(QColor("#ffcccc"))
        elif event.event_type == EventType.WARNING:
            type_item.setBackground(QColor("#fff3cd"))
        elif event.event_type == EventType.SENSOR_FAILURE:
            type_item.setBackground(QColor("#e0e0e0"))
        self.events_table.setItem(row, 4, type_item)
        
        # Температура
        temp_text = f"{event.temperature:.1f}°C" if event.temperature else "—"
        self.events_table.setItem(row, 5, QTableWidgetItem(temp_text))
        
        # Статус
        status_item = QTableWidgetItem(event.status.value)
        if event.status == EventStatus.ACTIVE:
            status_item.setBackground(QColor("#f8d7da"))
        elif event.status == EventStatus.ACKNOWLEDGED:
            status_item.setBackground(QColor("#fff3cd"))
        else:
            status_item.setBackground(QColor("#d4edda"))
        self.events_table.setItem(row, 6, status_item)
        
        # Кнопка действий
        details_btn = QPushButton("Детали")
        details_btn.clicked.connect(lambda checked, eid=event.id: self._show_details(eid))
        self.events_table.setCellWidget(row, 7, details_btn)
    
    def _on_row_double_click(self, index):
        """Двойной клик по строке"""
        row = index.row()
        event_id = self.events_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self._show_details(event_id)
    
    def _show_details(self, event_id: int):
        """Показать детали события"""
        event = self.db.get_event(event_id)
        if not event:
            return
        
        dialog = EventDetailsDialog(event, self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_events()
    
    def _export_events(self):
        """Экспорт событий"""
        # Реализация экспорта через Reporter
        from core.reporter import Reporter, ReportPeriod
        
        try:
            reporter = Reporter(self.db)
            
            start_time, end_time = self._get_filter_dates()
            event_type = self.type_combo.currentData()
            room_id = self.room_combo.currentData()
            
            report_data = reporter.generate_report(
                ReportPeriod.CUSTOM,
                start_date=start_time,
                end_date=end_time,
                room_id=room_id,
                event_type=event_type
            )
            
            filepath = reporter.export_xlsx(report_data)
            
            QMessageBox.information(
                self,
                "Экспорт завершён",
                f"Отчёт сохранён:\n{filepath}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка экспорта",
                f"Не удалось экспортировать данные:\n{str(e)}"
            )
    
    def refresh(self):
        """Обновить данные"""
        # Обновляем список помещений
        current_room = self.room_combo.currentData()
        self.room_combo.clear()
        self.room_combo.addItem("Все помещения", None)
        for room in self.db.get_all_rooms():
            self.room_combo.addItem(room.name, room.id)
        
        # Восстанавливаем выбор
        if current_room:
            index = self.room_combo.findData(current_room)
            if index >= 0:
                self.room_combo.setCurrentIndex(index)
        
        # Обновляем таблицу
        self._load_events()
