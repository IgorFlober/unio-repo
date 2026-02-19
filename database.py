import sqlite3
from datetime import datetime, timedelta

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('uniobot.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        # Таблица тренеров
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trainers (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE,
                name TEXT,
                phone TEXT,
                specialty TEXT,
                description TEXT,
                photo TEXT,
                subscription_end DATE,
                is_active BOOLEAN DEFAULT 0
            )
        ''')
        # Таблица расписания
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY,
                trainer_id INTEGER,
                day_of_week INTEGER,
                time TEXT,
                max_clients INTEGER DEFAULT 1
            )
        ''')
        # Таблица записей клиентов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY,
                trainer_id INTEGER,
                client_name TEXT,
                client_phone TEXT,
                telegram_id INTEGER,
                booking_date DATE,
                booking_time TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        # Таблица отзывов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                trainer_id INTEGER,
                user_id INTEGER,
                user_name TEXT,
                rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
    
    # ----- Тренеры: регистрация и профиль -----
    def add_trainer(self, user_id, name, phone):
        try:
            self.cursor.execute(
                "INSERT INTO trainers (user_id, name, phone) VALUES (?, ?, ?)",
                (user_id, name, phone)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_trainer_status(self, user_id):
        self.cursor.execute(
            "SELECT name, phone, specialty, description, photo, subscription_end, is_active FROM trainers WHERE user_id = ?",
            (user_id,)
        )
        row = self.cursor.fetchone()
        if not row:
            return None
        return {
            'name': row[0],
            'phone': row[1],
            'specialty': row[2],
            'description': row[3],
            'photo': row[4],
            'subscription_end': row[5],
            'is_active': bool(row[6])
        }
    
    def update_trainer_profile(self, user_id, specialty=None, description=None, photo=None):
        updates = []
        params = []
        if specialty is not None:
            updates.append("specialty = ?")
            params.append(specialty)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if photo is not None:
            updates.append("photo = ?")
            params.append(photo)
        if not updates:
            return
        params.append(user_id)
        self.cursor.execute(f"UPDATE trainers SET {', '.join(updates)} WHERE user_id = ?", params)
        self.conn.commit()
    
    def activate_subscription(self, user_id, days=30):
        end_date = datetime.now() + timedelta(days=days)
        self.cursor.execute(
            "UPDATE trainers SET subscription_end = ?, is_active = 1 WHERE user_id = ?",
            (end_date.strftime('%Y-%m-%d'), user_id)
        )
        self.conn.commit()
    
    def check_subscription(self, user_id):
        self.cursor.execute(
            "SELECT subscription_end FROM trainers WHERE user_id = ?",
            (user_id,)
        )
        result = self.cursor.fetchone()
        if result and result[0]:
            end_date = datetime.strptime(result[0], '%Y-%m-%d').date()
            return end_date >= datetime.now().date()
        return False
    
    # ----- Расписание -----
    def add_schedule(self, trainer_id, day_of_week, time, max_clients=1):
        self.cursor.execute(
            "INSERT INTO schedule (trainer_id, day_of_week, time, max_clients) VALUES (?, ?, ?, ?)",
            (trainer_id, day_of_week, time, max_clients)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_trainer_schedule(self, trainer_id):
        self.cursor.execute(
            "SELECT id, day_of_week, time, max_clients FROM schedule WHERE trainer_id = ? ORDER BY day_of_week, time",
            (trainer_id,)
        )
        return self.cursor.fetchall()
    
    def delete_schedule(self, slot_id):
        self.cursor.execute("DELETE FROM schedule WHERE id = ?", (slot_id,))
        self.conn.commit()
    
    # ----- Записи клиентов для тренера -----
    def get_trainer_bookings(self, trainer_id, date=None):
        if date:
            self.cursor.execute(
                "SELECT id, client_name, client_phone, booking_date, booking_time FROM bookings WHERE trainer_id = ? AND booking_date = ? AND status = 'active'",
                (trainer_id, date)
            )
        else:
            self.cursor.execute(
                "SELECT id, client_name, client_phone, booking_date, booking_time FROM bookings WHERE trainer_id = ? AND status = 'active' ORDER BY booking_date, booking_time",
                (trainer_id,)
            )
        return self.cursor.fetchall()
    
    # ----- Клиентская часть (остаётся) -----
    def get_all_trainers(self, search=None):
        query = "SELECT user_id, name, specialty, photo FROM trainers WHERE is_active = 1"
        params = []
        if search:
            query += " AND (name LIKE ? OR specialty LIKE ?)"
            params.extend([f'%{search}%', f'%{search}%'])
        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()
        trainers = []
        for row in rows:
            trainers.append({
                'user_id': row[0],
                'name': row[1],
                'specialty': row[2],
                'photo': row[3],
                'rating_avg': self.get_trainer_rating_avg(row[0]),
                'review_count': self.get_trainer_review_count(row[0])
            })
        return trainers
    
    def get_trainer_by_id(self, user_id):
        self.cursor.execute(
            "SELECT name, specialty, description, photo FROM trainers WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        row = self.cursor.fetchone()
        if not row:
            return None
        return {
            'name': row[0],
            'specialty': row[1],
            'description': row[2],
            'photo': row[3],
            'rating_avg': self.get_trainer_rating_avg(user_id),
            'review_count': self.get_trainer_review_count(user_id)
        }
    
    def add_booking(self, trainer_id, client_name, client_phone, telegram_id, booking_date, booking_time):
        self.cursor.execute(
            "INSERT INTO bookings (trainer_id, client_name, client_phone, telegram_id, booking_date, booking_time) VALUES (?, ?, ?, ?, ?, ?)",
            (trainer_id, client_name, client_phone, telegram_id, booking_date, booking_time)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_client_bookings(self, telegram_id):
        self.cursor.execute(
            """SELECT b.id, b.trainer_id, t.name, b.booking_date, b.booking_time, b.status 
               FROM bookings b 
               JOIN trainers t ON b.trainer_id = t.user_id 
               WHERE b.telegram_id = ? 
               ORDER BY b.booking_date, b.booking_time""",
            (telegram_id,)
        )
        return self.cursor.fetchall()
    
    def cancel_booking(self, booking_id):
        self.cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
        self.conn.commit()
        self.cursor.execute("SELECT trainer_id FROM bookings WHERE id = ?", (booking_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def add_review(self, trainer_id, user_id, user_name, rating, text):
        self.cursor.execute(
            "INSERT INTO reviews (trainer_id, user_id, user_name, rating, text) VALUES (?, ?, ?, ?, ?)",
            (trainer_id, user_id, user_name, rating, text)
        )
        self.conn.commit()
    
    def get_trainer_reviews(self, trainer_id):
        self.cursor.execute(
            "SELECT user_name, rating, text, created_at FROM reviews WHERE trainer_id = ? ORDER BY created_at DESC",
            (trainer_id,)
        )
        rows = self.cursor.fetchall()
        return [{'user_name': r[0], 'rating': r[1], 'text': r[2], 'created_at': r[3]} for r in rows]
    
    def get_trainer_rating_avg(self, trainer_id):
        self.cursor.execute("SELECT AVG(rating) FROM reviews WHERE trainer_id = ?", (trainer_id,))
        result = self.cursor.fetchone()[0]
        return round(result, 1) if result else 0.0
    
    def get_trainer_review_count(self, trainer_id):
        self.cursor.execute("SELECT COUNT(*) FROM reviews WHERE trainer_id = ?", (trainer_id,))
        return self.cursor.fetchone()[0]