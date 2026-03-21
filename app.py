import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json
import uuid

from config import Config
from models import db, User, Citizen, CriminalRecord, Vehicle, Wanted, Call, ActionLog, Notification, Document, Relative, Statistics
from forms import LoginForm, CitizenForm, CallForm, WantedForm, VehicleForm, SearchForm
from utils import generate_nickname, save_photo, log_action, create_notification, notify_all_users, format_priority, format_status, get_statistics

# Инициализация приложения
app = Flask(__name__)
app.config.from_object(Config)

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему'
login_manager.login_message_category = 'warning'

socketio = SocketIO(app, cors_allowed_origins="*")

# Создаем папки
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Контекстный процессор для передачи данных во все шаблоны
@app.context_processor
def inject_now():
    return {
        'now': datetime.utcnow(),
        'app_name': Config.APP_NAME,
        'app_version': Config.APP_VERSION,
        'unread_count': lambda: Notification.query.filter_by(user_id=current_user.id, is_read=False).count() if current_user.is_authenticated else 0
    }

# Обработчики ошибок
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

# ==================== АУТЕНТИФИКАЦИЯ ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(badge_number=form.badge_number.data).first()
        
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            
            # Обновляем информацию о входе
            user.last_login = datetime.utcnow()
            user.last_ip = request.remote_addr
            db.session.commit()
            
            # Логируем вход
            log_action(
                user_id=user.id,
                action_type='login',
                target_type='user',
                target_id=user.id,
                target_nickname=user.nickname,
                details={'badge': form.badge_number.data},
                request=request
            )
            
            # Уведомляем о входе
            socketio.emit('user_status', {
                'user': user.nickname,
                'name': user.full_name,
                'status': 'online'
            })
            
            flash(f'Добро пожаловать, {user.rank} {user.full_name}!', 'success')
            
            # Перенаправление на запрошенную страницу
            next_page = request.args.get('next')
            if next_page and next_page != '/logout':
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Неверный табельный номер или пароль', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    # Логируем выход
    log_action(
        user_id=current_user.id,
        action_type='logout',
        target_type='user',
        target_id=current_user.id,
        target_nickname=current_user.nickname,
        request=request
    )
    
    # Уведомляем о выходе
    socketio.emit('user_status', {
        'user': current_user.nickname,
        'name': current_user.full_name,
        'status': 'offline'
    })
    
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.email = request.form.get('email')
        current_user.phone = request.form.get('phone')
        
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename:
                photo_data = save_photo(file)
                if photo_data:
                    current_user.avatar = photo_data.get('url')
        
        db.session.commit()
        flash('Профиль обновлен', 'success')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html', user=current_user)

# ==================== ГЛАВНАЯ ====================

@app.route('/')
@login_required
def index():
    # Обновляем время последнего визита
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    
    # Получаем статистику
    stats = get_statistics()
    
    # Последние события
    recent_calls = Call.query.order_by(Call.received_time.desc()).limit(5).all()
    recent_actions = ActionLog.query.order_by(ActionLog.timestamp.desc()).limit(10).all()
    recent_wanted = Wanted.query.filter_by(status='active').order_by(Wanted.date_added.desc()).limit(5).all()
    
    # Активные пользователи
    active_users = User.query.filter(User.last_login > datetime.utcnow() - timedelta(minutes=15)).count()
    
    return render_template('index.html',
                         stats=stats,
                         recent_calls=recent_calls,
                         recent_actions=recent_actions,
                         recent_wanted=recent_wanted,
                         active_users=active_users)

# ==================== ГРАЖДАНЕ ====================

@app.route('/citizens')
@login_required
def citizens():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    danger = request.args.get('danger', '')
    
    query = Citizen.query
    
    if search:
        query = query.filter(
            (Citizen.nickname.contains(search)) |
            (Citizen.last_name.contains(search)) |
            (Citizen.first_name.contains(search)) |
            (Citizen.middle_name.contains(search)) |
            (Citizen.passport_series.contains(search)) |
            (Citizen.passport_number.contains(search)) |
            (Citizen.address_registration.contains(search)) |
            (Citizen.phone.contains(search))
        )
        
        # Логируем поиск
        log_action(
            user_id=current_user.id,
            action_type='search',
            target_type='citizen',
            target_id=0,
            details={'query': search},
            request=request
        )
    
    if status:
        query = query.filter_by(status=status)
    
    if danger:
        query = query.filter_by(danger_level=danger)
    
    citizens = query.order_by(Citizen.last_name).paginate(page=page, per_page=Config.ITEMS_PER_PAGE)
    
    return render_template('citizens/list.html', 
                         citizens=citizens, 
                         search=search,
                         current_status=status,
                         current_danger=danger)

@app.route('/citizen/<int:id>')
@login_required
def citizen_detail(id):
    citizen = Citizen.query.get_or_404(id)
    
    # Логируем просмотр
    log_action(
        user_id=current_user.id,
        action_type='view',
        target_type='citizen',
        target_id=id,
        target_nickname=citizen.nickname,
        request=request
    )
    
    criminal_records = citizen.criminal_records.all()
    vehicles = citizen.vehicles.all()
    documents = citizen.documents.all()
    relatives = citizen.relatives.all()
    
    return render_template('citizens/detail.html',
                         citizen=citizen,
                         criminal_records=criminal_records,
                         vehicles=vehicles,
                         documents=documents,
                         relatives=relatives)

@app.route('/citizen/new', methods=['GET', 'POST'])
@login_required
def new_citizen():
    form = CitizenForm()
    
    if form.validate_on_submit():
        # Проверяем уникальность никнейма
        if Citizen.query.filter_by(nickname=form.nickname.data).first():
            flash('Гражданин с таким никнеймом уже существует', 'danger')
            return render_template('citizens/form.html', form=form)
        
        citizen = Citizen(
            nickname=form.nickname.data,
            last_name=form.last_name.data,
            first_name=form.first_name.data,
            middle_name=form.middle_name.data,
            birth_date=form.birth_date.data,
            birth_place=form.birth_place.data,
            passport_series=form.passport_series.data,
            passport_number=form.passport_number.data,
            passport_issued_by=form.passport_issued_by.data,
            passport_issued_date=form.passport_issued_date.data,
            passport_code=form.passport_code.data,
            address_registration=form.address_registration.data,
            address_residence=form.address_residence.data,
            phone=form.phone.data,
            phone2=form.phone2.data,
            email=form.email.data,
            workplace=form.workplace.data,
            position=form.position.data,
            status=form.status.data,
            danger_level=form.danger_level.data,
            special_marks=form.special_marks.data,
            notes=form.notes.data,
            created_by=current_user.id
        )
        
        # Обработка фото
        if form.photo.data:
            photo_data = save_photo(form.photo.data)
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
    
    return render_template('citizens/form.html', form=form, citizen=None)

@app.route('/citizen/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_citizen(id):
    citizen = Citizen.query.get_or_404(id)
    form = CitizenForm(obj=citizen)
    
    if form.validate_on_submit():
        # Проверяем уникальность никнейма (если изменился)
        if form.nickname.data != citizen.nickname:
            if Citizen.query.filter_by(nickname=form.nickname.data).first():
                flash('Гражданин с таким никнеймом уже существует', 'danger')
                return render_template('citizens/form.html', form=form, citizen=citizen)
        
        old_data = {
            'nickname': citizen.nickname,
            'name': citizen.full_name,
            'address': citizen.address_registration
        }
        
        citizen.nickname = form.nickname.data
        citizen.last_name = form.last_name.data
        citizen.first_name = form.first_name.data
        citizen.middle_name = form.middle_name.data
        citizen.birth_date = form.birth_date.data
        citizen.birth_place = form.birth_place.data
        citizen.passport_series = form.passport_series.data
        citizen.passport_number = form.passport_number.data
        citizen.passport_issued_by = form.passport_issued_by.data
        citizen.passport_issued_date = form.passport_issued_date.data
        citizen.passport_code = form.passport_code.data
        citizen.address_registration = form.address_registration.data
        citizen.address_residence = form.address_residence.data
        citizen.phone = form.phone.data
        citizen.phone2 = form.phone2.data
        citizen.email = form.email.data
        citizen.workplace = form.workplace.data
        citizen.position = form.position.data
        citizen.status = form.status.data
        citizen.danger_level = form.danger_level.data
        citizen.special_marks = form.special_marks.data
        citizen.notes = form.notes.data
        citizen.updated_by = current_user.id
        
        if form.photo.data:
            photo_data = save_photo(form.photo.data)
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
            details={'old': old_data, 'new': {'nickname': citizen.nickname}},
            request=request
        )
        
        flash('Данные обновлены', 'success')
        return redirect(url_for('citizen_detail', id=id))
    
    return render_template('citizens/form.html', form=form, citizen=citizen)

@app.route('/citizen/<int:id>/delete', methods=['POST'])
@login_required
def delete_citizen(id):
    citizen = Citizen.query.get_or_404(id)
    
    if current_user.role != 'admin':
        flash('Только администратор может удалять записи', 'danger')
        return redirect(url_for('citizen_detail', id=id))
    
    nickname = citizen.nickname
    name = citizen.full_name
    
    db.session.delete(citizen)
    db.session.commit()
    
    log_action(
        user_id=current_user.id,
        action_type='delete',
        target_type='citizen',
        target_id=id,
        target_nickname=nickname,
        details={'name': name},
        request=request
    )
    
    flash(f'Гражданин {name} удален', 'success')
    return redirect(url_for('citizens'))

# ==================== ВЫЗОВЫ ====================

@app.route('/calls')
@login_required
def calls():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'active')
    my_only = request.args.get('my_only', False, type=bool)
    priority = request.args.get('priority', '')
    category = request.args.get('category', '')
    
    query = Call.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    if my_only:
        query = query.filter_by(assigned_to_id=current_user.id)
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(category=category)
    
    calls = query.order_by(Call.received_time.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE)
    
    # Статистика для фильтров
    stats = {
        'active': Call.query.filter_by(status='active').count(),
        'in_progress': Call.query.filter_by(status='in_progress').count(),
        'completed': Call.query.filter_by(status='completed').count(),
        'my': Call.query.filter_by(assigned_to_id=current_user.id, status='active').count()
    }
    
    return render_template('calls/list.html', 
                         calls=calls, 
                         current_status=status,
                         my_only=my_only,
                         current_priority=priority,
                         current_category=category,
                         stats=stats)

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
    
    return render_template('calls/detail.html', call=call)

@app.route('/call/new', methods=['GET', 'POST'])
@login_required
def new_call():
    form = CallForm()
    
    if form.validate_on_submit():
        # Проверяем никнейм
        if Call.query.filter_by(nickname=form.nickname.data).first():
            flash('Вызов с таким никнеймом уже существует', 'danger')
            return render_template('calls/form.html', form=form)
        
        # Генерация номера КУСП
        today = datetime.now().strftime('%Y%m%d')
        last_call = Call.query.filter(Call.kusp_number.like(f'КУСП-{today}-%'))\
            .order_by(Call.id.desc()).first()
        
        if last_call and last_call.kusp_number:
            last_num = int(last_call.kusp_number.split('-')[-1])
            new_num = f"КУСП-{today}-{last_num + 1:04d}"
        else:
            new_num = f"КУСП-{today}-0001"
        
        call = Call(
            nickname=form.nickname.data,
            kusp_number=new_num,
            address=form.address.data,
            district=form.district.data,
            caller_name=form.caller_name.data,
            caller_phone=form.caller_phone.data,
            caller_address=form.caller_address.data,
            description=form.description.data,
            category=form.category.data,
            subcategory=form.subcategory.data,
            priority=form.priority.data,
            notes=form.notes.data,
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
        
        # Уведомляем всех
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
    
    return render_template('calls/form.html', form=form)

@app.route('/call/<int:id>/take', methods=['POST'])
@login_required
def take_call(id):
    call = Call.query.get_or_404(id)
    
    if call.assigned_to_id:
        flash('Вызов уже принят другим нарядом', 'warning')
        return redirect(url_for('calls'))
    
    call.assigned_to_id = current_user.id
    call.assigned_to_name = current_user.full_name
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
    
    # Уведомление для взявшего
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

# ==================== РОЗЫСК ====================

@app.route('/wanted')
@login_required
def wanted():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'active')
    wanted_type = request.args.get('type', '')
    
    query = Wanted.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    if wanted_type:
        query = query.filter_by(wanted_type=wanted_type)
    
    wanted_list = query.order_by(Wanted.date_added.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE)
    
    stats = {
        'active': Wanted.query.filter_by(status='active').count(),
        'federal': Wanted.query.filter_by(wanted_type='federal', status='active').count(),
        'local': Wanted.query.filter_by(wanted_type='local', status='active').count(),
        'dangerous': Wanted.query.filter_by(dangerous=True, status='active').count()
    }
    
    return render_template('wanted/list.html', 
                         wanted_list=wanted_list, 
                         current_status=status,
                         current_type=wanted_type,
                         stats=stats)

@app.route('/wanted/<int:id>')
@login_required
def wanted_detail(id):
    wanted = Wanted.query.get_or_404(id)
    return render_template('wanted/detail.html', wanted=wanted)

@app.route('/wanted/new', methods=['POST'])
@login_required
def new_wanted():
    citizen_id = request.form.get('citizen_id')
    citizen = Citizen.query.get_or_404(citizen_id)
    
    if citizen.wanted:
        flash('Гражданин уже в розыске', 'warning')
        return redirect(url_for('citizen_detail', id=citizen_id))
    
    nickname = request.form.get('nickname')
    if not nickname:
        nickname = f"wanted_{citizen.nickname}"
    
    wanted = Wanted(
        nickname=nickname,
        citizen_id=citizen_id,
        wanted_type=request.form.get('wanted_type'),
        crime_article=request.form.get('crime_article'),
        crime_description=request.form.get('crime_description'),
        crime_date=request.form.get('crime_date'),
        dangerous=bool(request.form.get('dangerous')),
        weapons=request.form.get('weapons'),
        special_marks=request.form.get('special_marks'),
        initiator=request.form.get('initiator'),
        initiator_department=request.form.get('initiator_department'),
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
    
    # Уведомление всем
    notify_all_users(
        notif_type='wanted_update',
        title='Новый в розыске',
        message=f'Объявлен в розыск: {citizen.full_name}',
        data={'wanted_id': wanted.id, 'citizen_id': citizen_id}
    )
    
    socketio.emit('wanted_update', {
        'id': wanted.id,
        'name': citizen.full_name,
        'dangerous': wanted.dangerous
    })
    
    flash(f'{citizen.full_name} объявлен в розыск', 'success')
    return redirect(url_for('citizen_detail', id=citizen_id))

@app.route('/wanted/<int:id>/capture', methods=['POST'])
@login_required
def capture_wanted(id):
    wanted = Wanted.query.get_or_404(id)
    
    wanted.status = 'captured'
    wanted.capture_date = datetime.now().strftime('%Y-%m-%d')
    wanted.capture_info = request.form.get('capture_info')
    wanted.capture_place = request.form.get('capture_place')
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
    
    # Уведомление
    name = wanted.citizen.full_name if wanted.citizen else 'Неизвестно'
    notify_all_users(
        notif_type='wanted_update',
        title='Задержание',
        message=f'Задержан: {name}',
        data={'wanted_id': wanted.id}
    )
    
    socketio.emit('wanted_captured', {
        'id': wanted.id,
        'name': name
    })
    
    flash('Задержание зарегистрировано', 'success')
    return redirect(url_for('wanted'))

# ==================== ТРАНСПОРТ ====================

@app.route('/vehicles')
@login_required
def vehicles():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    stolen_only = request.args.get('stolen', False, type=bool)
    
    query = Vehicle.query
    
    if search:
        query = query.filter(
            (Vehicle.plate_number.contains(search)) |
            (Vehicle.vin.contains(search)) |
            (Vehicle.brand.contains(search)) |
            (Vehicle.model.contains(search))
        )
    
    if stolen_only:
        query = query.filter_by(is_stolen=True)
    
    vehicles = query.order_by(Vehicle.created_at.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE)
    
    stats = {
        'total': Vehicle.query.count(),
        'stolen': Vehicle.query.filter_by(is_stolen=True).count(),
        'wanted': Vehicle.query.filter_by(is_wanted=True).count()
    }
    
    return render_template('vehicles/list.html', vehicles=vehicles, search=search, stolen_only=stolen_only, stats=stats)

@app.route('/vehicle/<int:id>')
@login_required
def vehicle_detail(id):
    vehicle = Vehicle.query.get_or_404(id)
    return render_template('vehicles/detail.html', vehicle=vehicle)

@app.route('/vehicle/new', methods=['GET', 'POST'])
@login_required
def new_vehicle():
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        if not nickname:
            flash('Никнейм обязателен', 'danger')
            return redirect(url_for('new_vehicle'))
        
        if Vehicle.query.filter_by(nickname=nickname).first():
            flash('Транспорт с таким никнеймом уже существует', 'danger')
            return redirect(url_for('new_vehicle'))
        
        vehicle = Vehicle(
            nickname=nickname,
            plate_number=request.form.get('plate_number'),
            vin=request.form.get('vin'),
            brand=request.form.get('brand'),
            model=request.form.get('model'),
            year=request.form.get('year', type=int),
            color=request.form.get('color'),
            owner_id=request.form.get('owner_id', type=int) or None,
            is_stolen=bool(request.form.get('is_stolen')),
            stolen_date=request.form.get('stolen_date'),
            stolen_place=request.form.get('stolen_place'),
            created_by=current_user.id
        )
        
        db.session.add(vehicle)
        db.session.commit()
        
        log_action(
            user_id=current_user.id,
            action_type='create',
            target_type='vehicle',
            target_id=vehicle.id,
            target_nickname=vehicle.nickname,
            details={'plate': vehicle.plate_number},
            request=request
        )
        
        flash(f'Транспорт {vehicle.brand} {vehicle.model} добавлен', 'success')
        return redirect(url_for('vehicle_detail', id=vehicle.id))
    
    citizens = Citizen.query.order_by(Citizen.last_name).all()
    return render_template('vehicles/form.html', citizens=citizens)

# ==================== ИСТОРИЯ ====================

@app.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Фильтры
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
    
    # Список пользователей для фильтра
    users = User.query.all()
    
    # Статистика действий
    action_stats = db.session.query(
        ActionLog.action_type, db.func.count(ActionLog.id)
    ).group_by(ActionLog.action_type).all()
    
    return render_template('history/index.html', 
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

# ==================== УВЕДОМЛЕНИЯ ====================

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

# ==================== ПОИСК ====================

@app.route('/api/search')
@login_required
def api_search():
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'all')
    
    if not query or len(query) < 2:
        return jsonify({'error': 'Query too short'}), 400
    
    results = {}
    
    if search_type in ['all', 'citizens']:
        citizens = Citizen.query.filter(
            (Citizen.nickname.contains(query)) |
            (Citizen.last_name.contains(query)) |
            (Citizen.first_name.contains(query)) |
            (Citizen.passport_number.contains(query)) |
            (Citizen.phone.contains(query))
        ).limit(10).all()
        
        results['citizens'] = [c.to_dict() for c in citizens]
    
    if search_type in ['all', 'calls']:
        calls = Call.query.filter(
            (Call.nickname.contains(query)) |
            (Call.address.contains(query)) |
            (Call.kusp_number.contains(query)) |
            (Call.caller_name.contains(query))
        ).limit(10).all()
        
        results['calls'] = [c.to_dict() for c in calls]
    
    if search_type in ['all', 'vehicles']:
        vehicles = Vehicle.query.filter(
            (Vehicle.nickname.contains(query)) |
            (Vehicle.plate_number.contains(query)) |
            (Vehicle.vin.contains(query)) |
            (Vehicle.brand.contains(query))
        ).limit(10).all()
        
        results['vehicles'] = [v.to_dict() for v in vehicles]
    
    if search_type in ['all', 'wanted']:
        wanted = Wanted.query.filter(
            (Wanted.nickname.contains(query)) |
            (Wanted.crime_article.contains(query))
        ).limit(10).all()
        
        results['wanted'] = [w.to_dict() for w in wanted]
    
    # Логируем поиск
    log_action(
        user_id=current_user.id,
        action_type='search',
        target_type='api',
        target_id=0,
        target_nickname='search',
        details={'query': query, 'type': search_type, 'results_count': sum(len(v) for v in results.values())},
        request=request
    )
    
    return jsonify(results)

@app.route('/api/check-person', methods=['POST'])
@login_required
def check_person():
    """Быстрая проверка гражданина"""
    data = request.json
    passport = data.get('passport')
    last_name = data.get('last_name')
    nickname = data.get('nickname')
    plate = data.get('plate')
    
    result = {'found': False}
    
    # Поиск по гражданам
    if passport or last_name or nickname:
        query = Citizen.query
        if nickname:
            query = query.filter_by(nickname=nickname)
        elif passport:
            if len(passport) >= 10:
                passport_series = passport[:4]
                passport_number = passport[4:10]
                query = query.filter_by(passport_series=passport_series, passport_number=passport_number)
        elif last_name:
            query = query.filter(Citizen.last_name.contains(last_name))
        
        citizen = query.first()
        
        if citizen:
            result = citizen.to_dict()
            result['found'] = True
            result['wanted'] = citizen.wanted.to_dict() if citizen.wanted else None
            result['criminal_record'] = citizen.criminal_records.count() > 0
    
    # Поиск по транспорту
    if plate:
        vehicle = Vehicle.query.filter_by(plate_number=plate).first()
        if vehicle:
            result['vehicle'] = vehicle.to_dict()
            result['found'] = True
    
    # Логируем проверку
    log_action(
        user_id=current_user.id,
        action_type='check',
        target_type='citizen',
        target_id=citizen.id if 'citizen' in locals() and citizen else 0,
        target_nickname=citizen.nickname if 'citizen' in locals() and citizen else None,
        details={'passport': passport, 'plate': plate, 'found': result['found']},
        request=request
    )
    
    return jsonify(result)

# ==================== СТАТИСТИКА И ОТЧЕТЫ ====================

@app.route('/reports')
@login_required
def reports():
    return render_template('reports/index.html')

@app.route('/api/stats')
@login_required
def api_stats():
    """API для статистики"""
    period = request.args.get('period', 'day')
    
    if period == 'day':
        date = datetime.now().strftime('%Y-%m-%d')
        calls = Call.query.filter_by(received_date=date).count()
        citizens = Citizen.query.filter(Citizen.created_at >= date).count()
    elif period == 'week':
        week_ago = datetime.now() - timedelta(days=7)
        calls = Call.query.filter(Call.created_at >= week_ago).count()
        citizens = Citizen.query.filter(Citizen.created_at >= week_ago).count()
    else:
        calls = Call.query.count()
        citizens = Citizen.query.count()
    
    return jsonify({
        'calls': calls,
        'citizens': citizens,
        'wanted': Wanted.query.filter_by(status='active').count(),
        'vehicles_stolen': Vehicle.query.filter_by(is_stolen=True).count(),
        'users_active': User.query.filter(User.last_login >= datetime.now() - timedelta(minutes=15)).count()
    })

# ==================== WEBSOCKET ====================

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

# ==================== СТАТИЧЕСКИЕ ФАЙЛЫ ====================

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# ==================== ЗАПУСК ====================

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
