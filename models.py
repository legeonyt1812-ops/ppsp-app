from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    badge_number = db.Column(db.String(20), unique=True, nullable=False)
    nickname = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    rank = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(100), default="ОР ППСП Провинциальный район")
    avatar = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    actions = db.relationship('ActionLog', backref='user', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    created_citizens = db.relationship('Citizen', backref='creator', foreign_keys='Citizen.created_by')
    created_calls = db.relationship('Call', backref='creator', foreign_keys='Call.created_by_id')
    assigned_calls = db.relationship('Call', backref='assignee', foreign_keys='Call.assigned_to_id')

class Citizen(db.Model):
    __tablename__ = 'citizens'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50))
    birth_date = db.Column(db.String(10))
    passport_series = db.Column(db.String(4))
    passport_number = db.Column(db.String(6))
    address = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    photo_url = db.Column(db.String(500))
    photo_thumb = db.Column(db.String(500))
    status = db.Column(db.String(20), default='active')
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    criminal_records = db.relationship('CriminalRecord', backref='citizen', lazy=True, cascade='all, delete-orphan')
    vehicles = db.relationship('Vehicle', backref='owner', lazy=True, cascade='all, delete-orphan')
    wanted = db.relationship('Wanted', backref='citizen', uselist=False, cascade='all, delete-orphan')
    
    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name} {self.middle_name or ''}".strip()
    
    @property
    def age(self):
        if self.birth_date:
            try:
                born = datetime.strptime(self.birth_date, '%Y-%m-%d')
                today = datetime.today()
                return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            except:
                return None
        return None
    
    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'full_name': self.full_name,
            'birth_date': self.birth_date,
            'age': self.age,
            'passport': f"{self.passport_series} {self.passport_number}" if self.passport_series else None,
            'address': self.address,
            'phone': self.phone,
            'photo': self.photo_thumb or self.photo_url,
            'status': self.status
        }

class CriminalRecord(db.Model):
    __tablename__ = 'criminal_records'
    
    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey('citizens.id'), nullable=False)
    article = db.Column(db.String(50))
    article_text = db.Column(db.String(500))
    sentence_date = db.Column(db.String(10))
    sentence = db.Column(db.String(200))
    prison = db.Column(db.String(100))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    creator = db.relationship('User', foreign_keys=[created_by])

class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False)
    plate_number = db.Column(db.String(15), unique=True, nullable=False)
    brand = db.Column(db.String(50))
    model = db.Column(db.String(50))
    color = db.Column(db.String(30))
    year = db.Column(db.Integer)
    vin = db.Column(db.String(17))
    owner_id = db.Column(db.Integer, db.ForeignKey('citizens.id'))
    is_stolen = db.Column(db.Boolean, default=False)
    stolen_date = db.Column(db.String(10))
    stolen_report = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'plate': self.plate_number,
            'model': f"{self.brand} {self.model}",
            'color': self.color,
            'year': self.year,
            'owner': self.owner.full_name if self.owner else None,
            'stolen': self.is_stolen
        }

class Wanted(db.Model):
    __tablename__ = 'wanted'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False)
    citizen_id = db.Column(db.Integer, db.ForeignKey('citizens.id'), unique=True)
    wanted_type = db.Column(db.String(20))
    crime_article = db.Column(db.String(100))
    crime_description = db.Column(db.Text)
    dangerous = db.Column(db.Boolean, default=False)
    weapons = db.Column(db.String(200))
    special_marks = db.Column(db.Text)
    initiator = db.Column(db.String(100))
    initiator_contact = db.Column(db.String(100))
    date_added = db.Column(db.String(10), default=lambda: datetime.now().strftime('%Y-%m-%d'))
    date_updated = db.Column(db.String(10), default=lambda: datetime.now().strftime('%Y-%m-%d'))
    status = db.Column(db.String(20), default='active')
    capture_date = db.Column(db.String(10))
    capture_info = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'citizen': self.citizen.full_name if self.citizen else None,
            'type': self.wanted_type,
            'article': self.crime_article,
            'dangerous': self.dangerous,
            'status': self.status,
            'date': self.date_added
        }

class Call(db.Model):
    __tablename__ = 'calls'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False)
    kusp_number = db.Column(db.String(20), unique=True)
    received_time = db.Column(db.String(19), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    address = db.Column(db.String(200), nullable=False)
    caller_name = db.Column(db.String(100))
    caller_phone = db.Column(db.String(20))
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='medium')
    status = db.Column(db.String(20), default='active')
    category = db.Column(db.String(50))
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_at = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    completed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    report = db.Column(db.Text)
    
    completed_by = db.relationship('User', foreign_keys=[completed_by_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'kusp': self.kusp_number,
            'time': self.received_time,
            'address': self.address,
            'priority': self.priority,
            'status': self.status,
            'category': self.category,
            'assigned_to': self.assignee.nickname if self.assignee else None
        }

class ActionLog(db.Model):
    __tablename__ = 'action_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action_type = db.Column(db.String(50))
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    target_nickname = db.Column(db.String(50))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user': self.user.nickname if self.user else 'system',
            'user_name': self.user.full_name if self.user else 'Система',
            'action': self.action_type,
            'target': self.target_type,
            'target_nick': self.target_nickname,
            'details': json.loads(self.details) if self.details else {},
            'time': self.timestamp.strftime('%H:%M:%S'),
            'date': self.timestamp.strftime('%Y-%m-%d')
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50))
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    data = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'data': json.loads(self.data) if self.data else {},
            'is_read': self.is_read,
            'time': self.created_at.strftime('%H:%M:%S'),
            'date': self.created_at.strftime('%Y-%m-%d')
        }