from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime
import requests
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

app = Flask(__name__)
CORS(app)

DATABASE = 'uniobot.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_telegram_file_url(file_id):
    if not file_id:
        return None
    try:
        resp = requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getFile', params={'file_id': file_id})
        if resp.status_code == 200:
            file_path = resp.json().get('result', {}).get('file_path')
            if file_path:
                return f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}'
    except:
        pass
    return None

from database import Database
db_helper = Database()

# ========== Эндпоинты для тренеров ==========
@app.route('/api/trainer/status', methods=['GET'])
def trainer_status():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400
    try:
        user_id = int(user_id)
    except:
        return jsonify({'error': 'Invalid user_id'}), 400
    status = db_helper.get_trainer_status(user_id)
    if status is None:
        return jsonify({'registered': False})
    # Добавляем photo_url
    if status['photo']:
        status['photo_url'] = get_telegram_file_url(status['photo'])
    else:
        status['photo_url'] = None
    status['registered'] = True
    return jsonify(status)

@app.route('/api/trainer/register', methods=['POST'])
def trainer_register():
    data = request.get_json()
    user_id = data.get('user_id')
    name = data.get('name')
    phone = data.get('phone')
    if not all([user_id, name, phone]):
        return jsonify({'error': 'Missing fields'}), 400
    try:
        user_id = int(user_id)
    except:
        return jsonify({'error': 'Invalid user_id'}), 400
    success = db_helper.add_trainer(user_id, name, phone)
    if success:
        return jsonify({'status': 'registered'})
    else:
        return jsonify({'error': 'User already registered'}), 409

@app.route('/api/trainer/subscribe', methods=['POST'])
def trainer_subscribe():
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400
    try:
        user_id = int(user_id)
    except:
        return jsonify({'error': 'Invalid user_id'}), 400
    # Тестовая активация на 30 дней
    db_helper.activate_subscription(user_id, days=30)
    return jsonify({'status': 'subscribed', 'days': 30})

@app.route('/api/trainer/schedule', methods=['GET'])
def trainer_schedule():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400
    try:
        user_id = int(user_id)
    except:
        return jsonify({'error': 'Invalid user_id'}), 400
    schedule = db_helper.get_trainer_schedule(user_id)
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    result = []
    for s in schedule:
        result.append({
            'id': s[0],
            'day': s[1],
            'day_name': days[s[1]-1] if 1 <= s[1] <= 7 else '',
            'time': s[2],
            'max_clients': s[3]
        })
    return jsonify(result)

@app.route('/api/trainer/schedule', methods=['POST'])
def trainer_add_slot():
    data = request.get_json()
    user_id = data.get('user_id')
    day = data.get('day')
    time = data.get('time')
    max_clients = data.get('max_clients', 1)
    if not all([user_id, day, time]):
        return jsonify({'error': 'Missing fields'}), 400
    try:
        user_id = int(user_id)
        day = int(day)
        max_clients = int(max_clients)
    except:
        return jsonify({'error': 'Invalid data'}), 400
    slot_id = db_helper.add_schedule(user_id, day, time, max_clients)
    return jsonify({'status': 'added', 'id': slot_id})

@app.route('/api/trainer/schedule/<int:slot_id>', methods=['DELETE'])
def trainer_delete_slot(slot_id):
    db_helper.delete_schedule(slot_id)
    return jsonify({'status': 'deleted'})

@app.route('/api/trainer/bookings', methods=['GET'])
def trainer_bookings():
    user_id = request.args.get('user_id')
    date = request.args.get('date')  # опционально
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400
    try:
        user_id = int(user_id)
    except:
        return jsonify({'error': 'Invalid user_id'}), 400
    bookings = db_helper.get_trainer_bookings(user_id, date)
    result = []
    for b in bookings:
        result.append({
            'id': b[0],
            'client_name': b[1],
            'client_phone': b[2],
            'date': b[3],
            'time': b[4]
        })
    return jsonify(result)

@app.route('/api/trainer/profile', methods=['PUT'])
def trainer_update_profile():
    data = request.get_json()
    user_id = data.get('user_id')
    specialty = data.get('specialty')
    description = data.get('description')
    photo = data.get('photo')  # file_id
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400
    try:
        user_id = int(user_id)
    except:
        return jsonify({'error': 'Invalid user_id'}), 400
    db_helper.update_trainer_profile(user_id, specialty, description, photo)
    return jsonify({'status': 'updated'})

# ========== Клиентские эндпоинты (остаются) ==========
@app.route('/api/trainers', methods=['GET'])
def get_trainers():
    search = request.args.get('search', '')
    trainers = db_helper.get_all_trainers(search if search else None)
    for t in trainers:
        if t['photo']:
            t['photo_url'] = get_telegram_file_url(t['photo'])
        else:
            t['photo_url'] = None
    return jsonify(trainers)

@app.route('/api/trainers/<int:user_id>', methods=['GET'])
def get_trainer(user_id):
    trainer = db_helper.get_trainer_by_id(user_id)
    if not trainer:
        return jsonify({'error': 'Trainer not found'}), 404
    if trainer['photo']:
        trainer['photo_url'] = get_telegram_file_url(trainer['photo'])
    else:
        trainer['photo_url'] = None
    return jsonify(trainer)

@app.route('/api/schedule/<int:trainer_id>/<date>', methods=['GET'])
def get_schedule(trainer_id, date):
    conn = get_db()
    cursor = conn.cursor()
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        day_of_week = date_obj.isoweekday()
    except:
        conn.close()
        return jsonify({'error': 'Invalid date'}), 400
    cursor.execute(
        "SELECT id, time, max_clients FROM schedule WHERE trainer_id = ? AND day_of_week = ?",
        (trainer_id, day_of_week)
    )
    slots = cursor.fetchall()
    result = []
    for slot in slots:
        cursor.execute(
            "SELECT COUNT(*) FROM bookings WHERE trainer_id = ? AND booking_date = ? AND booking_time = ? AND status='active'",
            (trainer_id, date, slot['time'])
        )
        booked = cursor.fetchone()[0]
        free = slot['max_clients'] - booked
        if free > 0:
            result.append({
                'id': slot['id'],
                'time': slot['time'],
                'free': free
            })
    conn.close()
    return jsonify(result)

@app.route('/api/book', methods=['POST'])
def book():
    data = request.get_json()
    trainer_id = data.get('trainer_id')
    date = data.get('date')
    time = data.get('time')
    client_name = data.get('client_name')
    client_phone = data.get('client_phone')
    telegram_id = data.get('telegram_id')
    if not all([trainer_id, date, time, client_name, client_phone]):
        return jsonify({'error': 'Missing fields'}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        day_of_week = date_obj.isoweekday()
    except:
        conn.close()
        return jsonify({'error': 'Invalid date'}), 400
    cursor.execute(
        "SELECT max_clients FROM schedule WHERE trainer_id = ? AND day_of_week = ? AND time = ?",
        (trainer_id, day_of_week, time)
    )
    slot = cursor.fetchone()
    if not slot:
        conn.close()
        return jsonify({'error': 'Slot not found'}), 404
    cursor.execute(
        "SELECT COUNT(*) FROM bookings WHERE trainer_id = ? AND booking_date = ? AND booking_time = ? AND status='active'",
        (trainer_id, date, time)
    )
    booked = cursor.fetchone()[0]
    if booked >= slot['max_clients']:
        conn.close()
        return jsonify({'error': 'No free slots'}), 409
    cursor.execute(
        "INSERT INTO bookings (trainer_id, client_name, client_phone, telegram_id, booking_date, booking_time) VALUES (?, ?, ?, ?, ?, ?)",
        (trainer_id, client_name, client_phone, telegram_id, date, time)
    )
    conn.commit()
    booking_id = cursor.lastrowid
    conn.close()
    return jsonify({'status': 'success', 'booking_id': booking_id})

@app.route('/api/client_bookings/<int:telegram_id>', methods=['GET'])
def client_bookings(telegram_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.id, b.trainer_id, t.name, b.booking_date, b.booking_time, b.status 
        FROM bookings b 
        JOIN trainers t ON b.trainer_id = t.user_id 
        WHERE b.telegram_id = ? 
        ORDER BY b.booking_date, b.booking_time
    """, (telegram_id,))
    bookings = cursor.fetchall()
    conn.close()
    return jsonify([dict(b) for b in bookings])

@app.route('/api/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'cancelled'})

@app.route('/api/reviews/<int:trainer_id>', methods=['GET'])
def get_reviews(trainer_id):
    reviews = db_helper.get_trainer_reviews(trainer_id)
    return jsonify(reviews)

@app.route('/api/reviews', methods=['POST'])
def add_review():
    data = request.get_json()
    trainer_id = data.get('trainer_id')
    user_id = data.get('user_id')
    user_name = data.get('user_name', 'Аноним')
    rating = data.get('rating')
    text = data.get('text', '')
    if not all([trainer_id, user_id, rating]):
        return jsonify({'error': 'Missing fields'}), 400
    if rating < 1 or rating > 5:
        return jsonify({'error': 'Rating must be 1-5'}), 400
    db_helper.add_review(trainer_id, user_id, user_name, rating, text)
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)