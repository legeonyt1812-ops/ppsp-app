from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()

# Модель пользователя (сотрудника)
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    badge_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    rank = db.Column(db.String(50), nullable=False)
    position = db.Column(db.String(100), nullable=False, default='Полицейский')
    department = db.Column(db.String(100), default="ОР ППСП")
    division = db.Column(db.String(100), default="Провинциальный район")
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    avatar = db.Column(db.String(500))
    role = db.Column(db.String(20), default='user')  # admin, supervisor, user
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    last_ip = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    actions = db.relationship('ActionLog', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    created_citizens = db.relationship('Citizen', backref='creator', foreign_keys='Citizen.created_by', lazy='dynamic')
    updated_citizens = db.relationship('Citizen', backref='updater', foreign_keys='Citizen.updated_by', lazy='dynamic')
    created_calls = db.relationship('Call', backref='creator', foreign_keys='Call.created_by_id', lazy='dynamic')
    assigned_calls = db.relationship('Call', backref='assignee', foreign_keys='Call.assigned_to_id', lazy='dynamic')
    created_wanted = db.relationship('Wanted', backref='creator', foreign_keys='Wanted.created_by', lazy='dynamic')
    
    def get_id(self):
        return str(self.id)
    
    def has_role(self, role):
        return self.role == role or self.role == 'admin'
    
    def to_dict(self):
        return {
            'id': self.id,
            'badge': self.badge_number,
            'nickname': self.nickname,
            'name': self.full_name,
            'rank': self.rank,
            'role': self.role,
            'last_seen': self.last_login.strftime('%Y-%m-%d %H:%M') if self.last_login else None
        }

# Модель гражданина
class Citizen(db.Model):
    __tablename__ = 'citizens'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False, index=True)
    last_name = db.Column(db.String(50), nullable=False, index=True)
    first_name = db.Column(db.String(50), nullable=False, index=True)
    middle_name = db.Column(db.String(50))
    birth_date = db.Column(db.String(10))
    birth_place = db.Column(db.String(200))
    
    # Паспорт РФ
    passport_series = db.Column(db.String(4))
    passport_number = db.Column(db.String(6))
    passport_issued_by = db.Column(db.String(200))
    passport_issued_date = db.Column(db.String(10))
    passport_code = db.Column(db.String(7))
    
    # Адрес
    address_registration = db.Column(db.String(200))
    address_residence = db.Column(db.String(200))
    
    # Контакты
    phone = db.Column(db.String(20))
    phone2 = db.Column(db.String(20))
    email = db.Column(db.String(100))
    
    # Работа
    workplace = db.Column(db.String(200))
    position = db.Column(db.String(100))
    
    # Фото
    photo_url = db.Column(db.String(500))
    photo_thumb = db.Column(db.String(500))
    
    # Статус
    status = db.Column(db.String(20), default='active')  # active, deceased, emigrated, arrested
    danger_level = db.Column(db.String(20), default='none')  # none, low, medium, high
    special_marks = db.Column(db.Text)
    notes = db.Column(db.Text)
    
    # Метаданные
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    criminal_records = db.relationship('CriminalRecord', backref='citizen', lazy='dynamic', cascade='all, delete-orphan')
    vehicles = db.relationship('Vehicle', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    wanted = db.relationship('Wanted', backref='citizen', uselist=False, cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='citizen', lazy='dynamic', cascade='all, delete-orphan')
    relatives = db.relationship('Relative', backref='citizen', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name} {self.middle_name or ''}".strip()
    
    @property
    def full_name_short(self):
        if self.middle_name:
            return f"{self.last_name} {self.first_name[0]}.{self.middle_name[0]}."
        return f"{self.last_name} {self.first_name[0]}."
    
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
    
    @property
    def passport_full(self):
        if self.passport_series and self.passport_number:
            return f"{self.passport_series} {self.passport_number}"
        return None
    
    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'full_name': self.full_name,
            'birth_date': self.birth_date,
            'age': self.age,
            'passport': self.passport_full,
            'address': self.address_registration,
            'phone': self.phone,
            'photo': self.photo_thumb or self.photo_url,
            'status': self.status,
            'danger': self.danger_level,
            'wanted': bool(self.wanted and self.wanted.status == 'active')
        }

# Модель судимости
class CriminalRecord(db.Model):
    __tablename__ = 'criminal_records'
    
    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey('citizens.id'), nullable=False, index=True)
    
    # Информация о деле
    case_number = db.Column(db.String(50))
    article = db.Column(db.String(50), nullable=False)
    article_text = db.Column(db.String(500))
    crime_date = db.Column(db.String(10))
    crime_place = db.Column(db.String(200))
    
    # Приговор
    sentence_date = db.Column(db.String(10))
    sentence = db.Column(db.String(200))
    sentence_years = db.Column(db.Float)
    prison = db.Column(db.String(200))
    
    # Статус
    status = db.Column(db.String(20), default='active')  # active, served, appealed
    release_date = db.Column(db.String(10))
    
    # Метаданные
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    creator = db.relationship('User', foreign_keys=[created_by])

# Модель транспорта
class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Регистрационные данные
    plate_number = db.Column(db.String(15), unique=True, nullable=False, index=True)
    vin = db.Column(db.String(17), unique=True)
    sts_number = db.Column(db.String(20))  # СТС
    pts_number = db.Column(db.String(20))  # ПТС
    
    # Характеристики
    brand = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer)
    color = db.Column(db.String(30))
    color2 = db.Column(db.String(30))
    body_type = db.Column(db.String(30))  # sedan, hatchback, suv, etc
    engine_type = db.Column(db.String(20))  # petrol, diesel, electric
    engine_capacity = db.Column(db.Float)
    power = db.Column(db.Integer)
    
    # Владелец
    owner_id = db.Column(db.Integer, db.ForeignKey('citizens.id'), index=True)
    
    # Розыск
    is_stolen = db.Column(db.Boolean, default=False, index=True)
    stolen_date = db.Column(db.String(10))
    stolen_place = db.Column(db.String(200))
    stolen_report = db.Column(db.String(200))
    
    # Ограничения
    is_wanted = db.Column(db.Boolean, default=False)
    restrictions = db.Column(db.Text)  # арест, запрет регистрации и т.д.
    
    # Метаданные
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'plate': self.plate_number,
            'model': f"{self.brand} {self.model}",
            'color': self.color,
            'year': self.year,
            'owner': self.owner.full_name if self.owner else None,
            'stolen': self.is_stolen,
            'wanted': self.is_wanted
        }

# Модель розыска
class Wanted(db.Model):
    __tablename__ = 'wanted'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Кто в розыске
    citizen_id = db.Column(db.Integer, db.ForeignKey('citizens.id'), unique=True, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), unique=True)
    
    # Тип розыска
    wanted_type = db.Column(db.String(20), nullable=False)  # federal, local, international
    category = db.Column(db.String(20))  # person, vehicle, weapon, item
    
    # Преступление
    crime_article = db.Column(db.String(100))
    crime_description = db.Column(db.Text)
    crime_date = db.Column(db.String(10))
    
    # Опасность
    dangerous = db.Column(db.Boolean, default=False)
    weapons = db.Column(db.String(200))
    special_marks = db.Column(db.Text)
    
    # Инициатор
    initiator = db.Column(db.String(100))
    initiator_department = db.Column(db.String(100))
    initiator_contact = db.Column(db.String(100))
    
    # Даты
    date_added = db.Column(db.String(10), default=lambda: datetime.now().strftime('%Y-%m-%d'))
    date_updated = db.Column(db.String(10), default=lambda: datetime.now().strftime('%Y-%m-%d'))
    
    # Статус
    status = db.Column(db.String(20), default='active', index=True)  # active, captured, cancelled
    capture_date = db.Column(db.String(10))
    capture_info = db.Column(db.Text)
    capture_place = db.Column(db.String(200))
    
    # Метаданные
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    citizen = db.relationship('Citizen', foreign_keys=[citizen_id])
    vehicle = db.relationship('Vehicle', foreign_keys=[vehicle_id])
    
    def to_dict(self):
        if self.citizen:
            name = self.citizen.full_name
            photo = self.citizen.photo_thumb
        elif self.vehicle:
            name = f"{self.vehicle.brand} {self.vehicle.model} {self.vehicle.plate_number}"
            photo = None
        else:
            name = "Неизвестно"
            photo = None
            
        return {
            'id': self.id,
            'nickname': self.nickname,
            'name': name,
            'type': self.wanted_type,
            'category': self.category,
            'article': self.crime_article,
            'dangerous': self.dangerous,
            'status': self.status,
            'date': self.date_added,
            'photo': photo
        }

# Модель вызова
class Call(db.Model):
    __tablename__ = 'calls'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Номер КУСП
    kusp_number = db.Column(db.String(20), unique=True, index=True)
    
    # Время
    received_time = db.Column(db.String(19), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    received_date = db.Column(db.String(10), default=lambda: datetime.now().strftime('%Y-%m-%d'))
    
    # Место
    address = db.Column(db.String(200), nullable=False)
    district = db.Column(db.String(50))
    coordinates = db.Column(db.String(50))  # широта,долгота
    
    # Заявитель
    caller_name = db.Column(db.String(100))
    caller_phone = db.Column(db.String(20))
    caller_address = db.Column(db.String(200))
    
    # Описание
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), index=True)  # crime, administrative, accident, check
    subcategory = db.Column(db.String(50))
    
    # Приоритет и статус
    priority = db.Column(db.String(20), default='medium', index=True)  # high, medium, low
    status = db.Column(db.String(20), default='active', index=True)  # active, in_progress, completed, cancelled
    
    # Кто принял
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_to_name = db.Column(db.String(100))
    assigned_at = db.Column(db.DateTime)
    
    # Кто создал
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Завершение
    completed_at = db.Column(db.DateTime)
    completed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    report = db.Column(db.Text)  # рапорт
    
    # Дополнительно
    participants = db.Column(db.Text)  # JSON с участниками
    evidence = db.Column(db.Text)  # JSON с вещдоками
    notes = db.Column(db.Text)
    
    # Связи
    assignee = db.relationship('User', foreign_keys=[assigned_to_id])
    completed_by = db.relationship('User', foreign_keys=[completed_by_id])
    creator = db.relationship('User', foreign_keys=[created_by_id])
    
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

# Модель документа
class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False)
    
    citizen_id = db.Column(db.Integer, db.ForeignKey('citizens.id'), index=True)
    
    doc_type = db.Column(db.String(50))  # passport, driver_license, etc
    doc_series = db.Column(db.String(20))
    doc_number = db.Column(db.String(20))
    doc_issued_by = db.Column(db.String(200))
    doc_issued_date = db.Column(db.String(10))
    doc_expiry_date = db.Column(db.String(10))
    
    file_url = db.Column(db.String(500))  # скан документа
    notes = db.Column(db.Text)
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Модель родственника
class Relative(db.Model):
    __tablename__ = 'relatives'
    
    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey('citizens.id'), index=True)
    relative_id = db.Column(db.Integer, db.ForeignKey('citizens.id'), index=True)
    
    relation_type = db.Column(db.String(50))  # father, mother, brother, etc
    notes = db.Column(db.Text)
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    citizen = db.relationship('Citizen', foreign_keys=[citizen_id])
    relative = db.relationship('Citizen', foreign_keys=[relative_id])

# Модель логов
class ActionLog(db.Model):
    __tablename__ = 'action_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    action_type = db.Column(db.String(50), index=True)  # login, logout, create, update, delete, search, view
    target_type = db.Column(db.String(50), index=True)  # citizen, wanted, call, vehicle, user
    target_id = db.Column(db.Integer)
    target_nickname = db.Column(db.String(50))
    
    details = db.Column(db.Text)  # JSON
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(200))
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
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

# Модель уведомлений
class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    type = db.Column(db.String(50), index=True)  # new_call, call_assigned, wanted_update, system
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    data = db.Column(db.Text)  # JSON
    
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'data': json.loads(self.data) if self.data else {},
            'is_read': self.is_read,
            'time': self.created_at.strftime('%H:%M'),
            'date': self.created_at.strftime('%Y-%m-%d')
        }

# Модель статистики
class Statistics(db.Model):
    __tablename__ = 'statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), unique=True, index=True)
    
    citizens_total = db.Column(db.Integer, default=0)
    citizens_added_today = db.Column(db.Integer, default=0)
    
    wanted_active = db.Column(db.Integer, default=0)
    wanted_captured_today = db.Column(db.Integer, default=0)
    
    calls_total = db.Column(db.Integer, default=0)
    calls_active = db.Column(db.Integer, default=0)
    calls_completed_today = db.Column(db.Integer, default=0)
    
    vehicles_stolen = db.Column(db.Integer, default=0)
    
    users_active = db.Column(db.Integer, default=0)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
