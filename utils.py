import os
import uuid
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from config import Config

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Проверяет разрешен ли тип файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_nickname(prefix='obj'):
    """Генерирует уникальный никнейм"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def save_photo(file):
    """Сохраняет фото без обработки (без Pillow)"""
    if file and allowed_file(file.filename):
        try:
            # Создаем безопасное имя файла
            filename = secure_filename(file.filename)
            name, ext = os.path.splitext(filename)
            new_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
            
            # Путь для сохранения
            filepath = os.path.join(Config.UPLOAD_FOLDER, new_filename)
            
            # Создаем папку если её нет
            os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
            
            # Сохраняем файл
            file.save(filepath)
            
            # Возвращаем URL (оригинал и превью - одно и то же)
            return {
                'url': f'/static/uploads/{new_filename}',
                'thumb': f'/static/uploads/{new_filename}'
            }
        except Exception as e:
            print(f"Ошибка сохранения фото: {e}")
            return None
    return None

def log_action(user_id, action_type, target_type, target_id, target_nickname=None, details=None, request=None):
    """Логирует действие пользователя"""
    from models import ActionLog, db
    
    log = ActionLog(
        user_id=user_id,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        target_nickname=target_nickname,
        details=json.dumps(details, ensure_ascii=False, default=str) if details else None,
        ip_address=request.remote_addr if request else None,
        user_agent=request.user_agent.string if request and request.user_agent else None
    )
    db.session.add(log)
    db.session.commit()
    return log

def create_notification(user_id, notif_type, title, message, data=None):
    """Создает уведомление для пользователя"""
    from models import Notification, db
    
    notif = Notification(
        nickname=generate_nickname('notif'),
        user_id=user_id,
        type=notif_type,
        title=title,
        message=message,
        data=json.dumps(data, ensure_ascii=False, default=str) if data else None
    )
    db.session.add(notif)
    db.session.commit()
    return notif

def notify_all_users(notif_type, title, message, data=None, exclude_user=None):
    """Отправляет уведомление всем пользователям"""
    from models import User, Notification, db
    
    users = User.query.filter_by(is_active=True)
    if exclude_user:
        users = users.filter(User.id != exclude_user)
    
    notifications = []
    for user in users:
        notif = Notification(
            nickname=generate_nickname('notif'),
            user_id=user.id,
            type=notif_type,
            title=title,
            message=message,
            data=json.dumps(data, ensure_ascii=False, default=str) if data else None
        )
        notifications.append(notif)
    
    if notifications:
        db.session.bulk_save_objects(notifications)
        db.session.commit()
    
    return notifications

def format_priority(priority):
    """Форматирует приоритет для отображения"""
    priorities = {
        'high': ('🔴', 'Высокий'),
        'medium': ('🟠', 'Средний'),
        'low': ('🟢', 'Низкий')
    }
    return priorities.get(priority, ('⚪', 'Неизвестно'))

def format_status(status):
    """Форматирует статус для отображения"""
    statuses = {
        'active': ('🟡', 'Активен'),
        'in_progress': ('🔵', 'В работе'),
        'completed': ('🟢', 'Завершен'),
        'cancelled': ('⚫', 'Отменен')
    }
    return statuses.get(status, ('⚪', status))
