"""
Главное окно приложения.
Содержит навигацию и основные компоненты интерфейса.
"""

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QFrame,
    QMessageBox, QApplication, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon, QAction

from database.db_manager import DatabaseManager
from simulator.sensor_simulator import SensorSimulator
from core.data_collector import DataCollector
from core.analyzer import TemperatureAnalyzer
from core.reporter import Reporter

from ui.dashboard import DashboardView
from ui.events_view import EventsView
from ui.reports_view import ReportsView
from ui.settings_view import SettingsView


class NavButton(QPushButton):
    """Кнопка навигации в боковой панели"""
    
    def __init__(self, text: str, icon_text: str = "", parent=None):
        super().__init__(parent)
        
        self.setText(f"{icon_text}  {text}" if icon_text else text)
        self.setCheckable(True)
        self.setMinimumHeight(50)
        self.setFont(QFont("Segoe UI", 11))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
                text-align: left;
                color: #333;
            }
            QPushButton:hover {
                background-color: #e8f0fe;
            }
            QPushButton:checked {
                background-color: #1a73e8;
                color: white;
            }
        """)


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Система учёта сигналов о превышении температуры")
        self.setMinimumSize(1200, 800)
        
        # Инициализация компонентов системы
        self._init_components()
        
        # Настройка интерфейса
        self._setup_ui()
        self._setup_menu()
        
        # Подключение сигналов
        self._connect_signals()
        
        # Инициализация демо-данных если БД пустая
        self._check_demo_data()
    
    def _init_components(self):
        """Инициализация компонентов системы"""
        # База данных
        self.db = DatabaseManager()
        
        # Симулятор датчиков
        self.simulator = SensorSimulator()
        
        # Сборщик данных
        self.collector = DataCollector(self.db, self.simulator, interval=5000)
        
        # Анализатор температур
        self.analyzer = TemperatureAnalyzer(self.db)
        
        # Генератор отчётов
        self.reporter = Reporter(self.db)
    
    def _setup_ui(self):
        """Настройка интерфейса"""
        # Центральный виджет
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === Боковая панель навигации ===
        nav_panel = QFrame()
        nav_panel.setFixedWidth(220)
        nav_panel.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-right: 1px solid #e0e0e0;
            }
        """)
        
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(10, 15, 10, 15)
        nav_layout.setSpacing(5)
        
        # Логотип/заголовок
        logo_label = QLabel("🌡️ ТемпМонитор")
        logo_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("color: #1a73e8; padding: 10px;")
        nav_layout.addWidget(logo_label)
        
        nav_layout.addSpacing(20)
        
        # Кнопки навигации
        self.nav_buttons = []
        
        self.dashboard_btn = NavButton("Мониторинг", "📊")
        self.dashboard_btn.setChecked(True)
        self.dashboard_btn.clicked.connect(lambda: self._switch_view(0))
        nav_layout.addWidget(self.dashboard_btn)
        self.nav_buttons.append(self.dashboard_btn)
        
        self.events_btn = NavButton("События", "🔔")
        self.events_btn.clicked.connect(lambda: self._switch_view(1))
        nav_layout.addWidget(self.events_btn)
        self.nav_buttons.append(self.events_btn)
        
        self.reports_btn = NavButton("Отчёты", "📋")
        self.reports_btn.clicked.connect(lambda: self._switch_view(2))
        nav_layout.addWidget(self.reports_btn)
        self.nav_buttons.append(self.reports_btn)
        
        self.settings_btn = NavButton("Настройки", "⚙️")
        self.settings_btn.clicked.connect(lambda: self._switch_view(3))
        nav_layout.addWidget(self.settings_btn)
        self.nav_buttons.append(self.settings_btn)
        
        nav_layout.addStretch()
        
        # Статус системы
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet("""
            QFrame {
                background-color: #e8f5e9;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        status_layout = QVBoxLayout(self.status_frame)
        status_layout.setContentsMargins(10, 10, 10, 10)
        
        self.status_label = QLabel("Система готова")
        self.status_label.setFont(QFont("Segoe UI", 9))
        status_layout.addWidget(self.status_label)
        
        self.active_events_label = QLabel("Активных событий: 0")
        self.active_events_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        status_layout.addWidget(self.active_events_label)
        
        nav_layout.addWidget(self.status_frame)
        
        main_layout.addWidget(nav_panel)
        
        # === Область контента ===
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background-color: white;")
        
        # Создаём представления
        self.dashboard_view = DashboardView(
            self.db, self.simulator, self.collector, self.analyzer
        )
        self.content_stack.addWidget(self.dashboard_view)
        
        self.events_view = EventsView(self.db)
        self.content_stack.addWidget(self.events_view)
        
        self.reports_view = ReportsView(self.db)
        self.content_stack.addWidget(self.reports_view)
        
        self.settings_view = SettingsView(self.db)
        self.content_stack.addWidget(self.settings_view)
        
        main_layout.addWidget(self.content_stack, 1)
    
    def _setup_menu(self):
        """Настройка меню"""
        menubar = self.menuBar()
        
        # Меню "Файл"
        file_menu = menubar.addMenu("Файл")
        
        export_action = QAction("Экспорт данных...", self)
        export_action.triggered.connect(self._export_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню "Вид"
        view_menu = menubar.addMenu("Вид")
        
        dashboard_action = QAction("Мониторинг", self)
        dashboard_action.setShortcut("Ctrl+1")
        dashboard_action.triggered.connect(lambda: self._switch_view(0))
        view_menu.addAction(dashboard_action)
        
        events_action = QAction("События", self)
        events_action.setShortcut("Ctrl+2")
        events_action.triggered.connect(lambda: self._switch_view(1))
        view_menu.addAction(events_action)
        
        reports_action = QAction("Отчёты", self)
        reports_action.setShortcut("Ctrl+3")
        reports_action.triggered.connect(lambda: self._switch_view(2))
        view_menu.addAction(reports_action)
        
        settings_action = QAction("Настройки", self)
        settings_action.setShortcut("Ctrl+4")
        settings_action.triggered.connect(lambda: self._switch_view(3))
        view_menu.addAction(settings_action)
        
        # Меню "Справка"
        help_menu = menubar.addMenu("Справка")
        
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _connect_signals(self):
        """Подключение сигналов"""
        # Обновление счётчика активных событий
        self.analyzer.event_created.connect(self._update_event_count)
        self.analyzer.event_closed.connect(self._update_event_count)
    
    def _switch_view(self, index: int):
        """Переключение представления"""
        self.content_stack.setCurrentIndex(index)
        
        # Обновляем состояние кнопок навигации
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        
        # Обновляем данные при переключении
        if index == 1:
            self.events_view.refresh()
        elif index == 2:
            self.reports_view.refresh()
        elif index == 3:
            self.settings_view.refresh()
    
    def _update_event_count(self, *args):
        """Обновление счётчика активных событий"""
        events = self.analyzer.get_active_events()
        count = len(events)
        
        self.active_events_label.setText(f"Активных событий: {count}")
        
        if count > 0:
            critical = sum(1 for e in events if e.event_type.value == "Критическая ситуация")
            if critical > 0:
                self.status_frame.setStyleSheet("""
                    QFrame {
                        background-color: #ffebee;
                        border-radius: 8px;
                        padding: 10px;
                    }
                """)
                self.status_label.setText("⚠️ Внимание!")
            else:
                self.status_frame.setStyleSheet("""
                    QFrame {
                        background-color: #fff3e0;
                        border-radius: 8px;
                        padding: 10px;
                    }
                """)
                self.status_label.setText("Есть предупреждения")
        else:
            self.status_frame.setStyleSheet("""
                QFrame {
                    background-color: #e8f5e9;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
            self.status_label.setText("Система в норме")
    
    def _check_demo_data(self):
        """Проверка и инициализация демо-данных"""
        if not self.db.get_all_rooms():
            reply = QMessageBox.question(
                self,
                "Инициализация",
                "База данных пуста. Создать демонстрационные данные?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.db.init_demo_data()
                # Обновляем дашборд
                self.dashboard_view._load_sensors()
    
    def _export_data(self):
        """Экспорт данных"""
        self._switch_view(2)  # Переключаемся на отчёты
    
    def _show_about(self):
        """Показать информацию о программе"""
        QMessageBox.about(
            self,
            "О программе",
            "<h3>Система учёта сигналов о превышении температуры</h3>"
            "<p>Версия 1.0</p>"
            "<p>Система мониторинга температуры в промышленных помещениях "
            "с автоматическим оповещением о превышении пороговых значений.</p>"
            "<p><b>Возможности:</b></p>"
            "<ul>"
            "<li>Мониторинг температуры в реальном времени</li>"
            "<li>Автоматическое создание событий при превышении порогов</li>"
            "<li>Журнал событий с возможностью фильтрации</li>"
            "<li>Формирование отчётов в форматах Excel и PDF</li>"
            "<li>Настройка уведомлений по email</li>"
            "</ul>"
            "<p>© 2025</p>"
        )
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        # Останавливаем сбор данных
        if self.collector.is_running():
            self.collector.stop()
        
        event.accept()


def main():
    """Точка входа в приложение"""
    app = QApplication(sys.argv)
    
    # Устанавливаем стиль
    app.setStyle("Fusion")
    
    # Создаём и показываем главное окно
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
