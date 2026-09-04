"""
Представление отчётов.
Интерфейс для генерации и экспорта отчётов.
"""

from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QComboBox, QDateEdit, QRadioButton,
    QButtonGroup, QTextEdit, QFileDialog, QMessageBox,
    QProgressBar, QFrame, QCheckBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from database.db_manager import DatabaseManager
from database.models import EventType
from core.reporter import Reporter, ReportPeriod, ExportFormat


class ReportsView(QWidget):
    """Представление для генерации отчётов"""
    
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.reporter = Reporter(db_manager)
        
        self._current_report = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Заголовок
        title = QLabel("Формирование отчётов")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Основной контент
        content_layout = QHBoxLayout()
        
        # Левая панель - параметры отчёта
        params_widget = QWidget()
        params_layout = QVBoxLayout(params_widget)
        params_layout.setContentsMargins(0, 0, 0, 0)
        
        # Тип отчёта
        period_group = QGroupBox("Период отчёта")
        period_layout = QVBoxLayout(period_group)
        
        self.period_group = QButtonGroup(self)
        
        self.daily_radio = QRadioButton("Ежедневный отчёт")
        self.period_group.addButton(self.daily_radio, 0)
        period_layout.addWidget(self.daily_radio)
        
        self.weekly_radio = QRadioButton("Еженедельный отчёт")
        self.period_group.addButton(self.weekly_radio, 1)
        period_layout.addWidget(self.weekly_radio)
        
        self.monthly_radio = QRadioButton("Ежемесячный отчёт")
        self.period_group.addButton(self.monthly_radio, 2)
        period_layout.addWidget(self.monthly_radio)
        
        self.custom_radio = QRadioButton("Произвольный период")
        self.period_group.addButton(self.custom_radio, 3)
        period_layout.addWidget(self.custom_radio)
        
        self.daily_radio.setChecked(True)
        
        # Выбор дат
        dates_layout = QHBoxLayout()
        dates_layout.addWidget(QLabel("С:"))
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addDays(-7))
        self.date_from.setCalendarPopup(True)
        self.date_from.setEnabled(False)
        dates_layout.addWidget(self.date_from)
        
        dates_layout.addWidget(QLabel("По:"))
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setEnabled(False)
        dates_layout.addWidget(self.date_to)
        
        period_layout.addLayout(dates_layout)
        
        self.period_group.idToggled.connect(self._on_period_changed)
        
        params_layout.addWidget(period_group)
        
        # Фильтры
        filters_group = QGroupBox("Фильтры")
        filters_layout = QFormLayout(filters_group)
        
        # Помещение
        self.room_combo = QComboBox()
        self.room_combo.addItem("Все помещения", None)
        for room in self.db.get_all_rooms():
            self.room_combo.addItem(room.name, room.id)
        filters_layout.addRow("Помещение:", self.room_combo)
        
        # Тип события
        self.type_combo = QComboBox()
        self.type_combo.addItem("Все типы", None)
        self.type_combo.addItem("Предупреждения", EventType.WARNING)
        self.type_combo.addItem("Критические", EventType.CRITICAL)
        self.type_combo.addItem("Сбои датчиков", EventType.SENSOR_FAILURE)
        filters_layout.addRow("Тип события:", self.type_combo)
        
        params_layout.addWidget(filters_group)
        
        # Формат экспорта
        format_group = QGroupBox("Формат экспорта")
        format_layout = QVBoxLayout(format_group)
        
        self.format_group = QButtonGroup(self)
        
        self.xlsx_radio = QRadioButton("Excel (.xlsx)")
        self.format_group.addButton(self.xlsx_radio, 0)
        format_layout.addWidget(self.xlsx_radio)
        
        self.pdf_radio = QRadioButton("PDF (.pdf)")
        self.format_group.addButton(self.pdf_radio, 1)
        format_layout.addWidget(self.pdf_radio)
        
        self.xlsx_radio.setChecked(True)
        
        params_layout.addWidget(format_group)
        
        # Опции
        options_group = QGroupBox("Дополнительные опции")
        options_layout = QVBoxLayout(options_group)
        
        self.include_stats = QCheckBox("Включить статистику")
        self.include_stats.setChecked(True)
        options_layout.addWidget(self.include_stats)
        
        self.include_charts = QCheckBox("Включить графики (только PDF)")
        self.include_charts.setChecked(False)
        self.include_charts.setEnabled(False)
        options_layout.addWidget(self.include_charts)
        
        params_layout.addWidget(options_group)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        preview_btn = QPushButton("👁 Предпросмотр")
        preview_btn.clicked.connect(self._preview_report)
        buttons_layout.addWidget(preview_btn)
        
        generate_btn = QPushButton("📄 Сформировать")
        generate_btn.clicked.connect(self._generate_report)
        buttons_layout.addWidget(generate_btn)
        
        params_layout.addLayout(buttons_layout)
        
        params_layout.addStretch()
        
        content_layout.addWidget(params_widget, 1)
        
        # Правая панель - предпросмотр
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        preview_label = QLabel("Предпросмотр отчёта")
        preview_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        preview_layout.addWidget(preview_label)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #ccc;
                font-family: Consolas, monospace;
                font-size: 10pt;
            }
        """)
        preview_layout.addWidget(self.preview_text)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        preview_layout.addWidget(self.progress_bar)
        
        # Кнопки экспорта
        export_layout = QHBoxLayout()
        
        export_btn = QPushButton("💾 Сохранить отчёт")
        export_btn.clicked.connect(self._export_report)
        export_layout.addWidget(export_btn)
        
        open_folder_btn = QPushButton("📁 Открыть папку")
        open_folder_btn.clicked.connect(self._open_reports_folder)
        export_layout.addWidget(open_folder_btn)
        
        preview_layout.addLayout(export_layout)
        
        content_layout.addWidget(preview_widget, 2)
        
        layout.addLayout(content_layout)
    
    def _on_period_changed(self, button_id: int, checked: bool):
        """Обработка изменения периода"""
        if not checked:
            return
        
        custom = button_id == 3
        self.date_from.setEnabled(custom)
        self.date_to.setEnabled(custom)
    
    def _get_report_period(self) -> ReportPeriod:
        """Получить выбранный период"""
        if self.daily_radio.isChecked():
            return ReportPeriod.DAILY
        elif self.weekly_radio.isChecked():
            return ReportPeriod.WEEKLY
        elif self.monthly_radio.isChecked():
            return ReportPeriod.MONTHLY
        else:
            return ReportPeriod.CUSTOM
    
    def _get_date_range(self):
        """Получить диапазон дат"""
        from_date = self.date_from.date()
        to_date = self.date_to.date()
        
        start = datetime(from_date.year(), from_date.month(), from_date.day(), 0, 0, 0)
        end = datetime(to_date.year(), to_date.month(), to_date.day(), 23, 59, 59)
        
        return start, end
    
    def _preview_report(self):
        """Предпросмотр отчёта"""
        try:
            period = self._get_report_period()
            start_date, end_date = self._get_date_range() if period == ReportPeriod.CUSTOM else (None, None)
            room_id = self.room_combo.currentData()
            event_type = self.type_combo.currentData()
            
            self._current_report = self.reporter.generate_report(
                period=period,
                start_date=start_date,
                end_date=end_date,
                room_id=room_id,
                event_type=event_type
            )
            
            self._display_preview()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось сформировать отчёт:\n{str(e)}"
            )
    
    def _display_preview(self):
        """Отобразить предпросмотр отчёта"""
        if not self._current_report:
            return
        
        report = self._current_report
        
        lines = [
            f"{'=' * 60}",
            f"{report.title}",
            f"{'=' * 60}",
            "",
            f"Период: {report.period_start.strftime('%d.%m.%Y %H:%M')} - {report.period_end.strftime('%d.%m.%Y %H:%M')}",
            f"Сформирован: {report.generated_at.strftime('%d.%m.%Y %H:%M:%S')}",
            "",
            f"{'-' * 60}",
            "СВОДКА",
            f"{'-' * 60}",
            report.summary,
            "",
            f"{'-' * 60}",
            "СОБЫТИЯ",
            f"{'-' * 60}",
        ]
        
        if report.events:
            lines.append("")
            lines.append(f"{'№':<4} {'Дата/Время':<18} {'Датчик':<20} {'Тип':<18} {'Статус':<12}")
            lines.append("-" * 75)
            
            for i, event in enumerate(report.events[:20], 1):
                sensor = self.db.get_sensor(event.sensor_id)
                sensor_name = sensor.name[:18] if sensor else f"#{event.sensor_id}"
                
                lines.append(
                    f"{i:<4} "
                    f"{event.start_time.strftime('%d.%m.%Y %H:%M'):<18} "
                    f"{sensor_name:<20} "
                    f"{event.event_type.value[:16]:<18} "
                    f"{event.status.value:<12}"
                )
            
            if len(report.events) > 20:
                lines.append(f"\n... и ещё {len(report.events) - 20} событий")
        else:
            lines.append("\nСобытий за указанный период не найдено.")
        
        self.preview_text.setPlainText("\n".join(lines))
    
    def _generate_report(self):
        """Сформировать и сохранить отчёт"""
        if not self._current_report:
            self._preview_report()
        
        if not self._current_report:
            return
        
        self._export_report()
    
    def _export_report(self):
        """Экспортировать отчёт в файл"""
        if not self._current_report:
            QMessageBox.warning(
                self,
                "Нет данных",
                "Сначала сформируйте отчёт."
            )
            return
        
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(30)
            
            if self.xlsx_radio.isChecked():
                filepath = self.reporter.export_xlsx(self._current_report)
            else:
                filepath = self.reporter.export_pdf(self._current_report)
            
            self.progress_bar.setValue(100)
            
            QMessageBox.information(
                self,
                "Отчёт сохранён",
                f"Отчёт успешно сохранён:\n{filepath}"
            )
            
        except ImportError as e:
            QMessageBox.critical(
                self,
                "Ошибка зависимости",
                f"Для экспорта необходимо установить дополнительные пакеты:\n{str(e)}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка экспорта",
                f"Не удалось экспортировать отчёт:\n{str(e)}"
            )
        finally:
            self.progress_bar.setVisible(False)
    
    def _open_reports_folder(self):
        """Открыть папку с отчётами"""
        import os
        import subprocess
        
        reports_dir = os.path.abspath(self.reporter.reports_dir)
        
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        
        if os.name == 'nt':  # Windows
            os.startfile(reports_dir)
        elif os.name == 'posix':  # Linux/Mac
            subprocess.run(['xdg-open', reports_dir])
    
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
