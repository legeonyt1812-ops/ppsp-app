import os
import uuid
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image
import cloudinary
import cloudinary.uploader
from config import Config

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_nickname(prefix='obj'):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def save_photo_to_cloudinary(file, folder='ppsp_photos'):
    try:
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            public_id=f"{uuid.uuid4().hex}",
            overwrite=True
        )
        
        thumb = cloudinary.uploader.upload(
            file,
            folder=f"{folder}/thumbs",
            public_id=f"{uuid.uuid4().hex}",
            width=300,
            height=300,
            crop="thumb",
            overwrite=True
        )
        
        return {
            'url': result['secure_url'],
            'thumb': thumb['secure_url'],
            'public_id': result['public_id']
        }
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None

def save_photo_local(file, upload_folder):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        img = Image.open(filepath)
        img.thumbnail((300, 300))
        thumb_path = os.path.join(upload_folder, f"thumb_{filename}")
        img.save(thumb_path)
        
        return {
            'url': f'/static/uploads/{filename}',
            'thumb': f'/static/uploads/thumb_{filename}'
        }
    return None

def save_photo(file):
    if Config.CLOUDINARY_CLOUD_NAME:
        return save_photo_to_cloudinary(file)
    else:
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        return save_photo_local(file, Config.UPLOAD_FOLDER)

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

def format_priority(priority):
    priorities = {
        'high': ('🔴', 'Высокий'),
        'medium': ('🟠', 'Средний'),
        'low': ('🟢', 'Низкий')
    }
    return priorities.get(priority, ('⚪', 'Неизвестно'))

def format_status(status):
    statuses = {
        'active': ('🟡', 'Активен'),
        'in_progress': ('🔵', 'В работе'),
        'completed': ('🟢', 'Завершен'),
        'cancelled': ('⚫', 'Отменен')
    }
    return statuses.get(status, ('⚪', status))