"""
Модуль ui - пользовательский интерфейс.
"""

from .dashboard import DashboardView
from .events_view import EventsView
from .reports_view import ReportsView
from .settings_view import SettingsView
from .main_window import MainWindow

__all__ = [
    'MainWindow',
    'DashboardView', 'EventsView', 'ReportsView', 'SettingsView'
]
