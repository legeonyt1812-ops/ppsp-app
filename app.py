import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import cloudinary
import cloudinary.api
import json

from config import Config
from models import db, User, Citizen, CriminalRecord, Vehicle, Wanted, Call, ActionLog, Notification
from utils import (
    generate_nickname, save_photo, log_action, create_notification,
    notify_all_users, format_priority, format_status
)

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему'

if Config.CLOUDINARY_CLOUD_NAME:
    cloudinary.config(
        cloud_name=Config.CLOUDINARY_CLOUD_NAME,
        api_key=Config.CLOUDINARY_API_KEY,
        api_secret=Config.CLOUDINARY_API_SECRET
    )

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    
    if not User.query.first():
        users = [
            User(
                badge_number='001',
                nickname='boss',
                full_name='Петров Иван Иванович',
                rank='Лейтенант полиции',
                password=generate_password_hash('password123'),
                department='ОР ППСП'
            ),
            User(
                badge_number='002',
                nickname='patrol1',
                full_name='Сидоров Петр Петрович',
                rank='Старший лейтенант',
                password=generate_password_hash('password123'),
                department='ППСП'
            ),
            User(
                badge_number='003',
                nickname='operator',
                full_name='Иванова Мария Сергеевна',
                rank='Капитан полиции',
                password=generate_password_hash('password123'),
                department='Дежурная часть'
            )
        ]
        db.session.add_all(users)
        db.session.commit()
    
    if not Citizen.query.first():
        citizens = [
            Citizen(
                nickname=f"citizen_{i}",
                last_name=f"Фамилия{i}",
                first_name=f"Имя{i}",
                middle_name=f"Отчество{i}",
                birth_date=f"198{i}-01-01",
                passport_series=f"40{i}1",
                passport_number=f"12345{i}",
                address=f"ул. Ленина, д. {i}",
                phone=f"+7(999){i:03d}-{i:02d}-{i:02d}",
                status='active'
            ) for i in range(1, 11)
        ]
        db.session.add_all(citizens)
        db.session.commit()
    
    if not Call.query.first():
        calls = [
            Call(
                nickname=f"call_{i}",
                kusp_number=f"КУСП-2025-{i:04d}",
                address=f"ул. Тестовая, д. {i}",
                caller_name=f"Заявитель {i}",
                caller_phone=f"+7(999){i:03d}-{i:02d}-{i:02d}",
                description=f"Тестовое описание вызова {i}",
                priority=['high', 'medium', 'low'][i % 3],
                category=['crime', 'administrative', 'accident'][i % 3],
                status='active'
            ) for i in range(1, 6)
        ]
        db.session.add_all(calls)
        db.session.commit()

@app.route('/')
@login_required
def index():
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    
    total_citizens = Citizen.query.count()
    active_wanted = Wanted.query.filter_by(status='active').count()
    active_calls = Call.query.filter_by(status='active').count()
    my_calls = Call.query.filter_by(assigned_to_id=current_user.id, status='active').count()
    
    recent_calls = Call.query.order_by(Call.received_time.desc()).limit(5).all()
    recent_actions = ActionLog.query.order_by(ActionLog.timestamp.desc()).limit(10).all()
    unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    active_users = User.query.filter(User.last_seen > datetime.utcnow() - timedelta(minutes=5)).count()
    
    return render_template('index.html',
                         total_citizens=total_citizens,
                         active_wanted=active_wanted,
                         active_calls=active_calls,
                         my_calls=my_calls,
                         recent_calls=recent_calls,
                         recent_actions=recent_actions,
                         unread_notifications=unread_notifications,
                         active_users=active_users)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        badge = request.form.get('badge_number')
        password = request.form.get('password')
        
        user = User.query.filter_by(badge_number=badge).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            
            log_action(
                user_id=user.id,
                action_type='login',
                target_type='user',
                target_id=user.id,
                target_nickname=user.nickname,
                details={'badge': badge},
                request=request
            )
            
            socketio.emit('user_status', {
                'user': user.nickname,
                'name': user.full_name,
                'status': 'online'
            })
            
            flash(f'Добро пожаловать, {user.rank} {user.full_name}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный табельный номер или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_action(
        user_id=current_user.id,
        action_type='logout',
        target_type='user',
        target_id=current_user.id,
        target_nickname=current_user.nickname,
        request=request
    )
    
    socketio.emit('user_status', {
        'user': current_user.nickname,
        'name': current_user.full_name,
        'status': 'offline'
    })
    
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

@app.route('/api/notifications')
@login_required
def get_notifications():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())\
        .paginate(page=page, per_page=per_page)
    
    return jsonify({
        'notifications': [n.to_dict() for n in notifications.items],
        'total': notifications.total,
        'pages': notifications.pages,
        'current_page': page
    })

@app.route('/api/notifications/read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    notif.is_read = True
    notif.read_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/notifications/read-all', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False)\
        .update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/notifications/unread-count')
@login_required
def unread_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

@app.route('/citizens')
@login_required
def citizens():
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = Config.ITEMS_PER_PAGE
    
    query = Citizen.query
    
    if search_query:
        query = query.filter(
            (Citizen.nickname.contains(search_query)) |
            (Citizen.last_name.contains(search_query)) |
            (Citizen.first_name.contains(search_query)) |
            (Citizen.passport_number.contains(search_query)) |
            (Citizen.address.contains(search_query))
        )
    
    citizens = query.order_by(Citizen.last_name).paginate(page=page, per_page=per_page)
    
    if search_query:
        log_action(
            user_id=current_user.id,
            action_type='search',
            target_type='citizen',
            target_id=0,
            target_nickname='search',
            details={'query': search_query, 'results': citizens.total},
            request=request
        )
    
    return render_template('citizens.html', 
                         citizens=citizens, 
                         search_query=search_query)

@app.route('/citizen/<int:id>')
@login_required
def citizen_detail(id):
    citizen = Citizen.query.get_or_404(id)
    
    log_action(
        user_id=current_user.id,
        action_type='view',
        target_type='citizen',
        target_id=id,
        target_nickname=citizen.nickname,
        request=request
    )
    
    return render_template('citizen_detail.html', citizen=citizen)

@app.route('/citizen/new', methods=['GET', 'POST'])
@login_required
def new_citizen():
    if request.method == 'POST':
        nickname = request.form.get('nickname') or generate_nickname('citizen')
        
        citizen = Citizen(
            nickname=nickname,
            last_name=request.form.get('last_name'),
            first_name=request.form.get('first_name'),
            middle_name=request.form.get('middle_name'),
            birth_date=request.form.get('birth_date'),
            passport_series=request.form.get('passport_series'),
            passport_number=request.form.get('passport_number'),
            address=request.form.get('address'),
            phone=request.form.get('phone'),
            notes=request.form.get('notes'),
            created_by=current_user.id
        )
        
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename:
                photo_data = save_photo(file)
                if photo_data:
                    citizen.photo_url = photo_data.get('url')
                    citizen.photo_thumb = photo_data.get('thumb')
        
        db.session.add(citizen)
        db.session.commit()
        
        log_action(
            user_id=current_user.id,
            action_type='create',
            target_type='citizen',
            target_id=citizen.id,
            target_nickname=citizen.nickname,
            details={'name': citizen.full_name},
            request=request
        )
        
        flash(f'Гражданин {citizen.full_name} добавлен в базу', 'success')
        return redirect(url_for('citizen_detail', id=citizen.id))
    
    return render_template('citizen_form.html', citizen=None)

@app.route('/citizen/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_citizen(id):
    citizen = Citizen.query.get_or_404(id)
    
    if request.method == 'POST':
        old_data = {
            'name': citizen.full_name,
            'address': citizen.address,
            'phone': citizen.phone
        }
        
        citizen.last_name = request.form.get('last_name')
        citizen.first_name = request.form.get('first_name')
        citizen.middle_name = request.form.get('middle_name')
        citizen.birth_date = request.form.get('birth_date')
        citizen.passport_series = request.form.get('passport_series')
        citizen.passport_number = request.form.get('passport_number')
        citizen.address = request.form.get('address')
        citizen.phone = request.form.get('phone')
        citizen.notes = request.form.get('notes')
        citizen.status = request.form.get('status', 'active')
        
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename:
                photo_data = save_photo(file)
                if photo_data:
                    citizen.photo_url = photo_data.get('url')
                    citizen.photo_thumb = photo_data.get('thumb')
        
        db.session.commit()
        
        log_action(
            user_id=current_user.id,
            action_type='update',
            target_type='citizen',
            target_id=id,
            target_nickname=citizen.nickname,
            details={'old': old_data, 'new': {'name': citizen.full_name}},
            request=request
        )
        
        flash('Данные обновлены', 'success')
        return redirect(url_for('citizen_detail', id=id))
    
    return render_template('citizen_form.html', citizen=citizen)

@app.route('/calls')
@login_required
def calls():
    status = request.args.get('status', 'active')
    my_only = request.args.get('my_only', False, type=bool)
    page = request.args.get('page', 1, type=int)
    per_page = Config.ITEMS_PER_PAGE
    
    query = Call.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    if my_only:
        query = query.filter_by(assigned_to_id=current_user.id)
    
    calls = query.order_by(Call.received_time.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('calls.html', 
                         calls=calls, 
                         current_status=status,
                         my_only=my_only)

@app.route('/call/<int:id>')
@login_required
def call_detail(id):
    call = Call.query.get_or_404(id)
    
    log_action(
        user_id=current_user.id,
        action_type='view',
        target_type='call',
        target_id=id,
        target_nickname=call.nickname,
        request=request
    )
    
    return render_template('call_detail.html', call=call)

@app.route('/call/new', methods=['GET', 'POST'])
@login_required
def new_call():
    if request.method == 'POST':
        today = datetime.now().strftime('%Y%m%d')
        last_call = Call.query.filter(Call.kusp_number.like(f'КУСП-{today}-%'))\
            .order_by(Call.id.desc()).first()
        
        if last_call and last_call.kusp_number:
            last_num = int(last_call.kusp_number.split('-')[-1])
            new_num = f"КУСП-{today}-{last_num + 1:04d}"
        else:
            new_num = f"КУСП-{today}-0001"
        
        nickname = request.form.get('nickname') or generate_nickname('call')
        
        call = Call(
            nickname=nickname,
            kusp_number=new_num,
            address=request.form.get('address'),
            caller_name=request.form.get('caller_name'),
            caller_phone=request.form.get('caller_phone'),
            description=request.form.get('description'),
            priority=request.form.get('priority'),
            category=request.form.get('category'),
            created_by_id=current_user.id
        )
        
        db.session.add(call)
        db.session.commit()
        
        log_action(
            user_id=current_user.id,
            action_type='create',
            target_type='call',
            target_id=call.id,
            target_nickname=call.nickname,
            details={'kusp': call.kusp_number, 'address': call.address},
            request=request
        )
        
        notify_all_users(
            notif_type='new_call',
            title='Новый вызов',
            message=f'Поступил новый вызов: {call.address}',
            data={'call_id': call.id, 'kusp': call.kusp_number},
            exclude_user=current_user.id
        )
        
        socketio.emit('new_call', {
            'id': call.id,
            'nickname': call.nickname,
            'kusp': call.kusp_number,
            'address': call.address,
            'priority': call.priority,
            'time': call.received_time
        })
        
        flash(f'Вызов {new_num} создан', 'success')
        return redirect(url_for('calls'))
    
    return render_template('new_call.html')

@app.route('/call/<int:id>/take', methods=['POST'])
@login_required
def take_call(id):
    call = Call.query.get_or_404(id)
    
    if call.assigned_to_id:
        flash('Вызов уже принят другим нарядом', 'warning')
        return redirect(url_for('calls'))
    
    call.assigned_to_id = current_user.id
    call.assigned_at = datetime.utcnow()
    call.status = 'in_progress'
    db.session.commit()
    
    log_action(
        user_id=current_user.id,
        action_type='take',
        target_type='call',
        target_id=id,
        target_nickname=call.nickname,
        request=request
    )
    
    create_notification(
        user_id=current_user.id,
        notif_type='call_assigned',
        title='Вызов принят',
        message=f'Вы приняли вызов {call.kusp_number}',
        data={'call_id': call.id}
    )
    
    socketio.emit('call_taken', {
        'call_id': call.id,
        'call_nickname': call.nickname,
        'user': current_user.nickname
    })
    
    flash(f'Вызов {call.kusp_number} принят', 'success')
    return redirect(url_for('call_detail', id=id))

@app.route('/call/<int:id>/complete', methods=['POST'])
@login_required
def complete_call(id):
    call = Call.query.get_or_404(id)
    
    if call.assigned_to_id != current_user.id:
        flash('Вы не можете завершить чужой вызов', 'danger')
        return redirect(url_for('calls'))
    
    report = request.form.get('report', '')
    
    call.status = 'completed'
    call.completed_at = datetime.utcnow()
    call.completed_by_id = current_user.id
    call.report = report
    db.session.commit()
    
    log_action(
        user_id=current_user.id,
        action_type='complete',
        target_type='call',
        target_id=id,
        target_nickname=call.nickname,
        details={'report': report[:100]},
        request=request
    )
    
    socketio.emit('call_completed', {
        'call_id': call.id,
        'call_nickname': call.nickname,
        'user': current_user.nickname
    })
    
    flash(f'Вызов {call.kusp_number} завершен', 'success')
    return redirect(url_for('calls'))

@app.route('/wanted')
@login_required
def wanted():
    status = request.args.get('status', 'active')
    page = request.args.get('page', 1, type=int)
    per_page = Config.ITEMS_PER_PAGE
    
    query = Wanted.query
    if status != 'all':
        query = query.filter_by(status=status)
    
    wanted_list = query.order_by(Wanted.date_added.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('wanted.html', wanted_list=wanted_list, current_status=status)

@app.route('/wanted/new', methods=['POST'])
@login_required
def new_wanted():
    citizen_id = request.form.get('citizen_id')
    citizen = Citizen.query.get_or_404(citizen_id)
    
    if citizen.wanted:
        flash('Гражданин уже в розыске', 'warning')
        return redirect(url_for('citizen_detail', id=citizen_id))
    
    nickname = generate_nickname('wanted')
    
    wanted = Wanted(
        nickname=nickname,
        citizen_id=citizen_id,
        wanted_type=request.form.get('wanted_type'),
        crime_article=request.form.get('crime_article'),
        crime_description=request.form.get('crime_description'),
        dangerous=bool(request.form.get('dangerous')),
        weapons=request.form.get('weapons'),
        special_marks=request.form.get('special_marks'),
        initiator=request.form.get('initiator'),
        initiator_contact=request.form.get('initiator_contact'),
        created_by=current_user.id
    )
    
    db.session.add(wanted)
    db.session.commit()
    
    log_action(
        user_id=current_user.id,
        action_type='create',
        target_type='wanted',
        target_id=wanted.id,
        target_nickname=wanted.nickname,
        details={'citizen': citizen.full_name, 'article': wanted.crime_article},
        request=request
    )
    
    notify_all_users(
        notif_type='wanted_update',
        title='Новый в розыске',
        message=f'Объявлен в розыск: {citizen.full_name}',
        data={'wanted_id': wanted.id, 'citizen_id': citizen_id}
    )
    
    flash(f'{citizen.full_name} объявлен в розыск', 'success')
    return redirect(url_for('citizen_detail', id=citizen_id))

@app.route('/wanted/<int:id>/capture', methods=['POST'])
@login_required
def capture_wanted(id):
    wanted = Wanted.query.get_or_404(id)
    
    wanted.status = 'captured'
    wanted.capture_date = datetime.now().strftime('%Y-%m-%d')
    wanted.capture_info = request.form.get('capture_info')
    db.session.commit()
    
    log_action(
        user_id=current_user.id,
        action_type='update',
        target_type='wanted',
        target_id=id,
        target_nickname=wanted.nickname,
        details={'action': 'capture'},
        request=request
    )
    
    notify_all_users(
        notif_type='wanted_update',
        title='Задержание',
        message=f'Задержан: {wanted.citizen.full_name}',
        data={'wanted_id': wanted.id}
    )
    
    flash(f'Задержание зарегистрировано', 'success')
    return redirect(url_for('wanted'))

@app.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    user_id = request.args.get('user_id', type=int)
    action_type = request.args.get('action_type')
    target_type = request.args.get('target_type')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = ActionLog.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    if action_type:
        query = query.filter_by(action_type=action_type)
    if target_type:
        query = query.filter_by(target_type=target_type)
    if date_from:
        query = query.filter(ActionLog.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(ActionLog.timestamp <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    
    logs = query.order_by(ActionLog.timestamp.desc()).paginate(page=page, per_page=per_page)
    
    users = User.query.all()
    
    action_stats = db.session.query(
        ActionLog.action_type, db.func.count(ActionLog.id)
    ).group_by(ActionLog.action_type).all()
    
    return render_template('history.html', 
                         logs=logs, 
                         users=users,
                         action_stats=action_stats,
                         filters={
                             'user_id': user_id,
                             'action_type': action_type,
                             'target_type': target_type,
                             'date_from': date_from,
                             'date_to': date_to
                         })

@app.route('/api/search')
@login_required
def api_search():
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'all')
    
    results = {}
    
    if search_type in ['all', 'citizens']:
        citizens = Citizen.query.filter(
            (Citizen.nickname.contains(query)) |
            (Citizen.last_name.contains(query)) |
            (Citizen.first_name.contains(query)) |
            (Citizen.passport_number.contains(query))
        ).limit(10).all()
        
        results['citizens'] = [c.to_dict() for c in citizens]
    
    if search_type in ['all', 'vehicles']:
        vehicles = Vehicle.query.filter(
            (Vehicle.nickname.contains(query)) |
            (Vehicle.plate_number.contains(query)) |
            (Vehicle.vin.contains(query))
        ).limit(10).all()
        
        results['vehicles'] = [v.to_dict() for v in vehicles]
    
    if search_type in ['all', 'calls']:
        calls = Call.query.filter(
            (Call.nickname.contains(query)) |
            (Call.address.contains(query)) |
            (Call.kusp_number.contains(query))
        ).limit(10).all()
        
        results['calls'] = [c.to_dict() for c in calls]
    
    if search_type in ['all', 'wanted']:
        wanted = Wanted.query.filter(
            (Wanted.nickname.contains(query)) |
            (Wanted.crime_article.contains(query))
        ).limit(10).all()
        
        results['wanted'] = [w.to_dict() for w in wanted]
    
    log_action(
        user_id=current_user.id,
        action_type='search',
        target_type='api',
        target_id=0,
        target_nickname='search',
        details={'query': query, 'type': search_type, 'results': results},
        request=request
    )
    
    return jsonify(results)

@app.route('/api/check-person', methods=['POST'])
@login_required
def check_person():
    data = request.json
    passport = data.get('passport')
    last_name = data.get('last_name')
    nickname = data.get('nickname')
    
    query = Citizen.query
    if nickname:
        query = query.filter_by(nickname=nickname)
    elif passport:
        if len(passport) >= 10:
            passport_series = passport[:4]
            passport_number = passport[4:]
            query = query.filter_by(passport_series=passport_series, passport_number=passport_number)
    elif last_name:
        query = query.filter(Citizen.last_name.contains(last_name))
    else:
        return jsonify({'error': 'No search criteria'}), 400
    
    citizen = query.first()
    
    if citizen:
        result = citizen.to_dict()
        result['found'] = True
        result['wanted'] = citizen.wanted.to_dict() if citizen.wanted else None
        result['criminal_record'] = len(citizen.criminal_records) > 0
        result['vehicles'] = [v.to_dict() for v in citizen.vehicles]
    else:
        result = {'found': False}
    
    log_action(
        user_id=current_user.id,
        action_type='check',
        target_type='citizen',
        target_id=citizen.id if citizen else 0,
        target_nickname=citizen.nickname if citizen else None,
        details={'passport': passport, 'found': bool(citizen)},
        request=request
    )
    
    return jsonify(result)

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(f"user_{current_user.id}")
        emit('status', {'msg': f'{current_user.nickname} подключился'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        leave_room(f"user_{current_user.id}")
        emit('status', {'msg': f'{current_user.nickname} отключился'}, broadcast=True)

@socketio.on('join_call_room')
def handle_join_call_room(data):
    call_id = data.get('call_id')
    room = f"call_{call_id}"
    join_room(room)
    emit('joined', {'room': room, 'user': current_user.nickname}, room=room)

@socketio.on('leave_call_room')
def handle_leave_call_room(data):
    call_id = data.get('call_id')
    room = f"call_{call_id}"
    leave_room(room)

@socketio.on('call_message')
def handle_call_message(data):
    call_id = data.get('call_id')
    message = data.get('message')
    room = f"call_{call_id}"
    
    emit('call_message', {
        'user': current_user.nickname,
        'user_name': current_user.full_name,
        'message': message,
        'time': datetime.now().strftime('%H:%M:%S')
    }, room=room)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)