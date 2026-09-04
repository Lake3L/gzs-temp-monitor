#!/usr/bin/env python3
"""
Система учёта сигналов о превышении температуры.

Точка входа в приложение.
Запуск: python main.py
"""

import sys
import os

# Добавляем корневую директорию в путь поиска модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow


def main():
    """Главная функция запуска приложения"""
    # Создаём приложение
    app = QApplication(sys.argv)
    
    # Настройки приложения
    app.setApplicationName("ТемпМонитор")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Курсовая работа")
    
    # Устанавливаем стиль Fusion для кроссплатформенного вида
    app.setStyle("Fusion")
    
    # Включаем поддержку высокого DPI
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # Создаём и показываем главное окно
    window = MainWindow()
    window.show()
    
    # Запускаем цикл обработки событий
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
