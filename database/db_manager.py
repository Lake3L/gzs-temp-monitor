"""
Менеджер базы данных SQLite для системы учёта сигналов о превышении температуры.
Обеспечивает создание таблиц, CRUD операции и работу с данными.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from contextlib import contextmanager
import os

from .models import (
    Room, Sensor, Reading, Event, SuspiciousReading,
    NotificationLog, AuditLog, NotificationSettings,
    SensorStatus, EventType, EventStatus
)


class DatabaseManager:
    """Менеджер базы данных"""
    
    def __init__(self, db_path: str = "temperature_monitoring.db"):
        """
        Инициализация менеджера БД.
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для соединения с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _format_datetime(self, dt: datetime) -> str:
        """Форматировать datetime для SQLite (используем пробел вместо T)"""
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    def _init_database(self):
        """Создание таблиц базы данных"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица помещений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица датчиков
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT DEFAULT 'в сети',
                    warning_threshold REAL DEFAULT 60.0,
                    danger_threshold REAL DEFAULT 80.0,
                    filter_enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                )
            ''')
            
            # Таблица показаний температуры
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_id INTEGER NOT NULL,
                    temperature REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sensor_status TEXT DEFAULT 'в сети',
                    FOREIGN KEY (sensor_id) REFERENCES sensors(id) ON DELETE CASCADE
                )
            ''')
            
            # Индекс для быстрого поиска по времени
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_readings_timestamp 
                ON readings(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_readings_sensor 
                ON readings(sensor_id, timestamp)
            ''')
            
            # Таблица событий превышения
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT DEFAULT 'Активно',
                    temperature REAL NOT NULL,
                    threshold_exceeded REAL NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    acknowledged_by TEXT,
                    acknowledged_at TIMESTAMP,
                    notes TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    action_taken TEXT DEFAULT '',
                    FOREIGN KEY (sensor_id) REFERENCES sensors(id) ON DELETE CASCADE
                )
            ''')
            
            # Таблица подозрительных показаний
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS suspicious_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_id INTEGER NOT NULL,
                    temperature REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reason TEXT DEFAULT '',
                    FOREIGN KEY (sensor_id) REFERENCES sensors(id) ON DELETE CASCADE
                )
            ''')
            
            # Журнал уведомлений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notification_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'sent',
                    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                )
            ''')
            
            # Журнал аудита
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id INTEGER,
                    old_value TEXT,
                    new_value TEXT,
                    user TEXT DEFAULT 'operator',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Настройки уведомлений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notification_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER,
                    event_type TEXT NOT NULL,
                    email TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                )
            ''')
    
    # ==================== ПОМЕЩЕНИЯ ====================
    
    def add_room(self, name: str, description: str = "") -> int:
        """Добавить помещение"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO rooms (name, description) VALUES (?, ?)",
                (name, description)
            )
            room_id = cursor.lastrowid
            
            # Аудит
            self._log_audit(conn, "CREATE", "room", room_id, "", f"name={name}")
            
            return room_id
    
    def get_room(self, room_id: int) -> Optional[Room]:
        """Получить помещение по ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
            row = cursor.fetchone()
            if row:
                return Room(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now()
                )
            return None
    
    def get_all_rooms(self) -> List[Room]:
        """Получить все помещения"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rooms ORDER BY name")
            rows = cursor.fetchall()
            return [
                Room(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now()
                )
                for row in rows
            ]
    
    def update_room(self, room_id: int, name: str, description: str = "") -> bool:
        """Обновить помещение"""
        old_room = self.get_room(room_id)
        if not old_room:
            return False
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE rooms SET name = ?, description = ? WHERE id = ?",
                (name, description, room_id)
            )
            
            self._log_audit(
                conn, "UPDATE", "room", room_id,
                f"name={old_room.name}", f"name={name}"
            )
            
            return cursor.rowcount > 0
    
    def delete_room(self, room_id: int) -> bool:
        """Удалить помещение"""
        old_room = self.get_room(room_id)
        if not old_room:
            return False
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
            
            self._log_audit(
                conn, "DELETE", "room", room_id,
                f"name={old_room.name}", ""
            )
            
            return cursor.rowcount > 0
    
    # ==================== ДАТЧИКИ ====================
    
    def add_sensor(self, room_id: int, name: str, 
                   warning_threshold: float = 60.0,
                   danger_threshold: float = 80.0) -> int:
        """Добавить датчик"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO sensors 
                   (room_id, name, warning_threshold, danger_threshold) 
                   VALUES (?, ?, ?, ?)""",
                (room_id, name, warning_threshold, danger_threshold)
            )
            sensor_id = cursor.lastrowid
            
            self._log_audit(
                conn, "CREATE", "sensor", sensor_id, "",
                f"name={name}, room_id={room_id}"
            )
            
            return sensor_id
    
    def get_sensor(self, sensor_id: int) -> Optional[Sensor]:
        """Получить датчик по ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sensors WHERE id = ?", (sensor_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_sensor(row)
            return None
    
    def get_sensors_by_room(self, room_id: int) -> List[Sensor]:
        """Получить датчики по помещению"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM sensors WHERE room_id = ? ORDER BY name",
                (room_id,)
            )
            return [self._row_to_sensor(row) for row in cursor.fetchall()]
    
    def get_all_sensors(self) -> List[Sensor]:
        """Получить все датчики"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sensors ORDER BY room_id, name")
            return [self._row_to_sensor(row) for row in cursor.fetchall()]
    
    def update_sensor(self, sensor_id: int, **kwargs) -> bool:
        """Обновить датчик"""
        old_sensor = self.get_sensor(sensor_id)
        if not old_sensor:
            return False
        
        allowed_fields = ['name', 'status', 'warning_threshold', 
                          'danger_threshold', 'filter_enabled', 'room_id']
        
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                if key == 'status' and isinstance(value, SensorStatus):
                    values.append(value.value)
                else:
                    values.append(value)
        
        if not updates:
            return False
        
        values.append(sensor_id)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE sensors SET {', '.join(updates)} WHERE id = ?",
                values
            )
            
            self._log_audit(
                conn, "UPDATE", "sensor", sensor_id,
                str(kwargs), str(kwargs)
            )
            
            return cursor.rowcount > 0
    
    def update_sensor_status(self, sensor_id: int, status: SensorStatus) -> bool:
        """Обновить статус датчика"""
        return self.update_sensor(sensor_id, status=status)
    
    def delete_sensor(self, sensor_id: int) -> bool:
        """Удалить датчик"""
        old_sensor = self.get_sensor(sensor_id)
        if not old_sensor:
            return False
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sensors WHERE id = ?", (sensor_id,))
            
            self._log_audit(
                conn, "DELETE", "sensor", sensor_id,
                f"name={old_sensor.name}", ""
            )
            
            return cursor.rowcount > 0
    
    def _row_to_sensor(self, row) -> Sensor:
        """Преобразовать строку БД в объект Sensor"""
        status_map = {
            'в сети': SensorStatus.ONLINE,
            'потеря связи': SensorStatus.OFFLINE,
            'ошибка': SensorStatus.ERROR
        }
        return Sensor(
            id=row['id'],
            room_id=row['room_id'],
            name=row['name'],
            status=status_map.get(row['status'], SensorStatus.ONLINE),
            warning_threshold=row['warning_threshold'],
            danger_threshold=row['danger_threshold'],
            filter_enabled=bool(row['filter_enabled']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now()
        )
    
    # ==================== ПОКАЗАНИЯ ====================
    
    def add_reading(self, sensor_id: int, temperature: float,
                    sensor_status: SensorStatus = SensorStatus.ONLINE,
                    timestamp: datetime = None) -> int:
        """Добавить показание температуры"""
        if timestamp is None:
            timestamp = datetime.now()
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO readings 
                   (sensor_id, temperature, timestamp, sensor_status) 
                   VALUES (?, ?, ?, ?)""",
                (sensor_id, temperature, self._format_datetime(timestamp), sensor_status.value)
            )
            return cursor.lastrowid
    
    def get_readings(self, sensor_id: int, 
                     start_time: datetime = None,
                     end_time: datetime = None,
                     limit: int = None) -> List[Reading]:
        """Получить показания датчика за период"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM readings WHERE sensor_id = ?"
            params = [sensor_id]
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(self._format_datetime(start_time))
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(self._format_datetime(end_time))
            
            query += " ORDER BY timestamp DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query, params)
            return [self._row_to_reading(row) for row in cursor.fetchall()]
    
    def get_latest_reading(self, sensor_id: int) -> Optional[Reading]:
        """Получить последнее показание датчика"""
        readings = self.get_readings(sensor_id, limit=1)
        return readings[0] if readings else None
    
    def get_all_latest_readings(self) -> dict:
        """Получить последние показания всех датчиков"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.* FROM readings r
                INNER JOIN (
                    SELECT sensor_id, MAX(timestamp) as max_time
                    FROM readings
                    GROUP BY sensor_id
                ) latest ON r.sensor_id = latest.sensor_id 
                    AND r.timestamp = latest.max_time
            ''')
            
            result = {}
            for row in cursor.fetchall():
                reading = self._row_to_reading(row)
                result[reading.sensor_id] = reading
            return result
    
    def _row_to_reading(self, row) -> Reading:
        """Преобразовать строку БД в объект Reading"""
        status_map = {
            'в сети': SensorStatus.ONLINE,
            'потеря связи': SensorStatus.OFFLINE,
            'ошибка': SensorStatus.ERROR
        }
        return Reading(
            id=row['id'],
            sensor_id=row['sensor_id'],
            temperature=row['temperature'],
            timestamp=datetime.fromisoformat(row['timestamp']) if row['timestamp'] else datetime.now(),
            sensor_status=status_map.get(row['sensor_status'], SensorStatus.ONLINE)
        )
    
    # ==================== СОБЫТИЯ ====================
    
    def add_event(self, sensor_id: int, event_type: EventType,
                  temperature: float, threshold_exceeded: float,
                  description: str = "") -> int:
        """Добавить событие превышения"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO events 
                   (sensor_id, event_type, temperature, threshold_exceeded, description) 
                   VALUES (?, ?, ?, ?, ?)""",
                (sensor_id, event_type.value, temperature, threshold_exceeded, description)
            )
            return cursor.lastrowid
    
    def get_event(self, event_id: int) -> Optional[Event]:
        """Получить событие по ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_event(row)
            return None
    
    def get_active_events(self) -> List[Event]:
        """Получить активные события"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM events WHERE status = 'Активно' ORDER BY start_time DESC"
            )
            return [self._row_to_event(row) for row in cursor.fetchall()]
    
    def get_events(self, start_time: datetime = None,
                   end_time: datetime = None,
                   sensor_id: int = None,
                   room_id: int = None,
                   event_type: EventType = None,
                   status: EventStatus = None,
                   limit: int = None) -> List[Event]:
        """Получить события с фильтрацией"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT e.* FROM events e"
            params = []
            conditions = []
            
            if room_id:
                query += " JOIN sensors s ON e.sensor_id = s.id"
                conditions.append("s.room_id = ?")
                params.append(room_id)
            
            if start_time:
                conditions.append("e.start_time >= ?")
                params.append(self._format_datetime(start_time))
            
            if end_time:
                conditions.append("e.start_time <= ?")
                params.append(self._format_datetime(end_time))
            
            if sensor_id:
                conditions.append("e.sensor_id = ?")
                params.append(sensor_id)
            
            if event_type:
                conditions.append("e.event_type = ?")
                params.append(event_type.value)
            
            if status:
                conditions.append("e.status = ?")
                params.append(status.value)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY e.start_time DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query, params)
            return [self._row_to_event(row) for row in cursor.fetchall()]
    
    def update_event_status(self, event_id: int, status: EventStatus,
                            acknowledged_by: str = None, notes: str = None,
                            action_taken: str = None) -> bool:
        """Обновить статус события"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            updates = ["status = ?"]
            params = [status.value]
            
            if status == EventStatus.ACKNOWLEDGED and acknowledged_by:
                updates.append("acknowledged_by = ?")
                updates.append("acknowledged_at = ?")
                params.extend([acknowledged_by, self._format_datetime(datetime.now())])
            
            if status == EventStatus.RESOLVED:
                updates.append("end_time = ?")
                params.append(self._format_datetime(datetime.now()))
            
            if notes:
                updates.append("notes = ?")
                params.append(notes)
            
            if action_taken:
                updates.append("action_taken = ?")
                params.append(action_taken)
            
            params.append(event_id)
            
            cursor.execute(
                f"UPDATE events SET {', '.join(updates)} WHERE id = ?",
                params
            )
            
            self._log_audit(
                conn, "UPDATE", "event", event_id,
                "", f"status={status.value}"
            )
            
            return cursor.rowcount > 0
    
    def close_event(self, event_id: int) -> bool:
        """Закрыть событие (температура вернулась в норму)"""
        return self.update_event_status(event_id, EventStatus.RESOLVED)
    
    def get_active_event_for_sensor(self, sensor_id: int) -> Optional[Event]:
        """Получить активное событие для датчика"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM events 
                   WHERE sensor_id = ? AND status = 'Активно' 
                   ORDER BY start_time DESC LIMIT 1""",
                (sensor_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_event(row)
            return None
    
    def _row_to_event(self, row) -> Event:
        """Преобразовать строку БД в объект Event"""
        type_map = {
            'Предупреждение': EventType.WARNING,
            'Критическая ситуация': EventType.CRITICAL,
            'Сбой датчика': EventType.SENSOR_FAILURE
        }
        status_map = {
            'Активно': EventStatus.ACTIVE,
            'Подтверждено': EventStatus.ACKNOWLEDGED,
            'Разрешено': EventStatus.RESOLVED
        }
        return Event(
            id=row['id'],
            sensor_id=row['sensor_id'],
            event_type=type_map.get(row['event_type'], EventType.WARNING),
            status=status_map.get(row['status'], EventStatus.ACTIVE),
            temperature=row['temperature'],
            threshold_exceeded=row['threshold_exceeded'],
            start_time=datetime.fromisoformat(row['start_time']) if row['start_time'] else datetime.now(),
            end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
            acknowledged_by=row['acknowledged_by'],
            acknowledged_at=datetime.fromisoformat(row['acknowledged_at']) if row['acknowledged_at'] else None,
            notes=row['notes'] or "",
            description=row['description'] if 'description' in row.keys() else "",
            action_taken=row['action_taken'] if 'action_taken' in row.keys() else ""
        )
    
    # ==================== ПОДОЗРИТЕЛЬНЫЕ ПОКАЗАНИЯ ====================
    
    def add_suspicious_reading(self, sensor_id: int, temperature: float, reason: str) -> int:
        """Добавить подозрительное показание"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO suspicious_readings 
                   (sensor_id, temperature, reason) 
                   VALUES (?, ?, ?)""",
                (sensor_id, temperature, reason)
            )
            return cursor.lastrowid
    
    def get_suspicious_readings(self, sensor_id: int = None, 
                                 limit: int = 100) -> List[SuspiciousReading]:
        """Получить подозрительные показания"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if sensor_id:
                cursor.execute(
                    """SELECT * FROM suspicious_readings 
                       WHERE sensor_id = ? 
                       ORDER BY timestamp DESC LIMIT ?""",
                    (sensor_id, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM suspicious_readings ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
            
            return [
                SuspiciousReading(
                    id=row['id'],
                    sensor_id=row['sensor_id'],
                    temperature=row['temperature'],
                    timestamp=datetime.fromisoformat(row['timestamp']) if row['timestamp'] else datetime.now(),
                    reason=row['reason']
                )
                for row in cursor.fetchall()
            ]
    
    # ==================== ЖУРНАЛ УВЕДОМЛЕНИЙ ====================
    
    def add_notification(self, event_id: int, channel: str,
                         recipient: str, message: str,
                         status: str = "sent") -> int:
        """Добавить запись в журнал уведомлений"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO notification_log 
                   (event_id, channel, recipient, message, status) 
                   VALUES (?, ?, ?, ?, ?)""",
                (event_id, channel, recipient, message, status)
            )
            return cursor.lastrowid
    
    def get_notifications(self, event_id: int = None,
                          limit: int = 100) -> List[NotificationLog]:
        """Получить журнал уведомлений"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if event_id:
                cursor.execute(
                    """SELECT * FROM notification_log 
                       WHERE event_id = ? 
                       ORDER BY sent_at DESC LIMIT ?""",
                    (event_id, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM notification_log ORDER BY sent_at DESC LIMIT ?",
                    (limit,)
                )
            
            return [
                NotificationLog(
                    id=row['id'],
                    event_id=row['event_id'],
                    channel=row['channel'],
                    recipient=row['recipient'],
                    message=row['message'],
                    sent_at=datetime.fromisoformat(row['sent_at']) if row['sent_at'] else datetime.now(),
                    status=row['status']
                )
                for row in cursor.fetchall()
            ]
    
    # ==================== НАСТРОЙКИ УВЕДОМЛЕНИЙ ====================
    
    def add_notification_setting(self, event_type: EventType, email: str,
                                  room_id: int = None) -> int:
        """Добавить настройку уведомлений"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO notification_settings 
                   (room_id, event_type, email) 
                   VALUES (?, ?, ?)""",
                (room_id, event_type.value, email)
            )
            return cursor.lastrowid
    
    def get_notification_settings(self, room_id: int = None,
                                   event_type: EventType = None) -> List[NotificationSettings]:
        """Получить настройки уведомлений"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM notification_settings WHERE enabled = 1"
            params = []
            
            if room_id is not None:
                query += " AND (room_id = ? OR room_id IS NULL)"
                params.append(room_id)
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)
            
            cursor.execute(query, params)
            
            type_map = {
                'Предупреждение': EventType.WARNING,
                'Критическая ситуация': EventType.CRITICAL,
                'Сбой датчика': EventType.SENSOR_FAILURE
            }
            
            return [
                NotificationSettings(
                    id=row['id'],
                    room_id=row['room_id'],
                    event_type=type_map.get(row['event_type'], EventType.CRITICAL),
                    email=row['email'],
                    enabled=bool(row['enabled'])
                )
                for row in cursor.fetchall()
            ]
    
    def delete_notification_setting(self, setting_id: int) -> bool:
        """Удалить настройку уведомлений"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM notification_settings WHERE id = ?",
                (setting_id,)
            )
            return cursor.rowcount > 0
    
    # ==================== ЖУРНАЛ АУДИТА ====================
    
    def _log_audit(self, conn, action: str, entity_type: str,
                   entity_id: int, old_value: str, new_value: str,
                   user: str = "operator"):
        """Записать в журнал аудита"""
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO audit_log 
               (action, entity_type, entity_id, old_value, new_value, user) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (action, entity_type, entity_id, old_value, new_value, user)
        )
    
    def get_audit_log(self, entity_type: str = None,
                      entity_id: int = None,
                      limit: int = 100) -> List[AuditLog]:
        """Получить журнал аудита"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM audit_log"
            params = []
            conditions = []
            
            if entity_type:
                conditions.append("entity_type = ?")
                params.append(entity_type)
            
            if entity_id:
                conditions.append("entity_id = ?")
                params.append(entity_id)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += f" ORDER BY timestamp DESC LIMIT {limit}"
            
            cursor.execute(query, params)
            
            return [
                AuditLog(
                    id=row['id'],
                    action=row['action'],
                    entity_type=row['entity_type'],
                    entity_id=row['entity_id'],
                    old_value=row['old_value'] or "",
                    new_value=row['new_value'] or "",
                    user=row['user'],
                    timestamp=datetime.fromisoformat(row['timestamp']) if row['timestamp'] else datetime.now()
                )
                for row in cursor.fetchall()
            ]
    
    # ==================== СТАТИСТИКА ====================
    
    def get_statistics(self, start_time: datetime = None,
                       end_time: datetime = None) -> dict:
        """Получить статистику по событиям"""
        if not start_time:
            start_time = datetime.now() - timedelta(days=30)
        if not end_time:
            end_time = datetime.now()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Общее количество событий по типам
            cursor.execute('''
                SELECT event_type, COUNT(*) as count
                FROM events
                WHERE start_time >= ? AND start_time <= ?
                GROUP BY event_type
            ''', (self._format_datetime(start_time), self._format_datetime(end_time)))
            
            events_by_type = {row['event_type']: row['count'] for row in cursor.fetchall()}
            
            # События по датчикам
            cursor.execute('''
                SELECT s.name as sensor_name, r.name as room_name, COUNT(e.id) as count
                FROM events e
                JOIN sensors s ON e.sensor_id = s.id
                JOIN rooms r ON s.room_id = r.id
                WHERE e.start_time >= ? AND e.start_time <= ?
                GROUP BY e.sensor_id
                ORDER BY count DESC
            ''', (self._format_datetime(start_time), self._format_datetime(end_time)))
            
            events_by_sensor = [
                {
                    'sensor': row['sensor_name'],
                    'room': row['room_name'],
                    'count': row['count']
                }
                for row in cursor.fetchall()
            ]
            
            # Средняя температура по датчикам
            cursor.execute('''
                SELECT s.id, s.name, r.name as room_name,
                       AVG(rd.temperature) as avg_temp,
                       MAX(rd.temperature) as max_temp,
                       MIN(rd.temperature) as min_temp
                FROM sensors s
                JOIN rooms r ON s.room_id = r.id
                LEFT JOIN readings rd ON s.id = rd.sensor_id
                    AND rd.timestamp >= ? AND rd.timestamp <= ?
                GROUP BY s.id
            ''', (self._format_datetime(start_time), self._format_datetime(end_time)))
            
            temp_stats = [
                {
                    'sensor_id': row['id'],
                    'sensor': row['name'],
                    'room': row['room_name'],
                    'avg_temp': round(row['avg_temp'], 1) if row['avg_temp'] else None,
                    'max_temp': round(row['max_temp'], 1) if row['max_temp'] else None,
                    'min_temp': round(row['min_temp'], 1) if row['min_temp'] else None
                }
                for row in cursor.fetchall()
            ]
            
            return {
                'period': {
                    'start': start_time,
                    'end': end_time
                },
                'events_by_type': events_by_type,
                'events_by_sensor': events_by_sensor,
                'temperature_stats': temp_stats
            }
    
    # ==================== ИНИЦИАЛИЗАЦИЯ ДЕМО-ДАННЫХ ====================
    
    def init_demo_data(self):
        """Инициализация демонстрационных данных (5 помещений, по 2 датчика)"""
        # Проверяем, есть ли уже данные
        if self.get_all_rooms():
            return
        
        rooms_data = [
            ("Серверная", "Помещение с серверным оборудованием"),
            ("Склад", "Основной складской зал"),
            ("Офис", "Рабочее пространство сотрудников"),
            ("Электрощитовая", "Помещение с электрооборудованием"),
            ("Архив", "Хранилище документов"),
        ]
        
        for room_name, description in rooms_data:
            room_id = self.add_room(room_name, description)
            
            # Добавляем 2 датчика на помещение
            self.add_sensor(room_id, f"Датчик {room_name}-1", 
                           warning_threshold=55.0, danger_threshold=75.0)
            self.add_sensor(room_id, f"Датчик {room_name}-2",
                           warning_threshold=55.0, danger_threshold=75.0)
        
        # Добавляем настройки уведомлений по умолчанию
        self.add_notification_setting(EventType.CRITICAL, "admin@company.ru")
        self.add_notification_setting(EventType.CRITICAL, "security@company.ru")
        self.add_notification_setting(EventType.SENSOR_FAILURE, "tech@company.ru")
    
    def cleanup_old_data(self, days: int = 180):
        """Очистка данных старше указанного количества дней"""
        cutoff = datetime.now() - timedelta(days=days)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Удаляем старые показания
            cursor.execute(
                "DELETE FROM readings WHERE timestamp < ?",
                (self._format_datetime(cutoff),)
            )
            readings_deleted = cursor.rowcount
            
            # Удаляем старые подозрительные показания
            cursor.execute(
                "DELETE FROM suspicious_readings WHERE timestamp < ?",
                (self._format_datetime(cutoff),)
            )
            
            return readings_deleted
