import os
import uuid
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from config import Config
from PIL import Image

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_nickname(prefix='obj'):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def save_photo(file):
    """Сохраняет фото локально"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
        
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Создаем миниатюру
        try:
            img = Image.open(filepath)
            img.thumbnail((300, 300))
            thumb_path = os.path.join(Config.UPLOAD_FOLDER, f"thumb_{filename}")
            img.save(thumb_path)
            
            return {
                'url': f'/static/uploads/{filename}',
                'thumb': f'/static/uploads/thumb_{filename}'
            }
        except Exception as e:
            print(f"Image processing error: {e}")
            return {
                'url': f'/static/uploads/{filename}',
                'thumb': f'/static/uploads/{filename}'
            }
    return None

def log_action(user_id, action_type, target_type, target_id, target_nickname=None, details=None, request=None):
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
    
    db.session.bulk_save_objects(notifications)
    db.session.commit()
    
    return notifications
