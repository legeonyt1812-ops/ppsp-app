#!/usr/bin/env python3
"""Скрипт для инициализации базы данных"""

from app import app
from models import db, User, Citizen, Call, Wanted, Vehicle
from werkzeug.security import generate_password_hash
from datetime import datetime
import uuid

def init_db():
    """Создает базу данных и заполняет тестовыми данными"""
    with app.app_context():
        # Создаем таблицы
        db.drop_all()
        db.create_all()
        
        print("Создание тестовых пользователей...")
        users = [
            User(
                badge_number='001',
                nickname='boss',
                full_name='Петров Иван Иванович',
                rank='Лейтенант полиции',
                position='Начальник ОР ППСП',
                password=generate_password_hash('password123'),
                role='admin'
            ),
            User(
                badge_number='002',
                nickname='patrol1',
                full_name='Сидоров Петр Петрович',
                rank='Старший лейтенант',
                position='Командир отделения',
                password=generate_password_hash('password123'),
                role='supervisor'
            ),
            User(
                badge_number='003',
                nickname='operator',
                full_name='Иванова Мария Сергеевна',
                rank='Капитан полиции',
                position='Старший оперативный дежурный',
                password=generate_password_hash('password123'),
                role='admin'
            ),
            User(
                badge_number='004',
                nickname='patrol2',
                full_name='Козлов Андрей Николаевич',
                rank='Сержант полиции',
                position='Полицейский',
                password=generate_password_hash('password123'),
                role='user'
            ),
            User(
                badge_number='005',
                nickname='patrol3',
                full_name='Соколова Елена Владимировна',
                rank='Лейтенант полиции',
                position='Полицейский',
                password=generate_password_hash('password123'),
                role='user'
            )
        ]
        db.session.add_all(users)
        db.session.commit()
        
        print("Создание тестовых граждан...")
        citizens = []
        for i in range(1, 21):
            citizen = Citizen(
                nickname=f"citizen_{i}",
                last_name=f"Иванов{i}",
                first_name=f"Петр{i}",
                middle_name=f"Сидорович{i}" if i % 2 == 0 else None,
                birth_date=f"198{i:02d}-01-01" if i < 10 else f"199{i-10:02d}-01-01",
                passport_series=f"40{i:02d}"[:4],
                passport_number=f"12345{i:06d}"[:6],
                address_registration=f"ул. Ленина, д. {i}, кв. {i*10}",
                phone=f"+7(999){i:03d}-{i:02d}-{i:02d}",
                status='active'
            )
            citizens.append(citizen)
        
        # Добавляем одного в розыск
        wanted_citizen = Citizen(
            nickname="wanted_criminal",
            last_name="Сидоров",
            first_name="Алексей",
            middle_name="Петрович",
            birth_date="1975-05-15",
            passport_series="4015",
            passport_number="123456",
            address_registration="ул. Преступная, д. 1",
            phone="+7(999)555-55-55",
            danger_level='high',
            status='active'
        )
        citizens.append(wanted_citizen)
        
        db.session.add_all(citizens)
        db.session.commit()
        
        print("Создание тестовых вызовов...")
        calls = []
        priorities = ['high', 'medium', 'low']
        categories = ['crime', 'administrative', 'accident', 'check']
        
        for i in range(1, 11):
            call = Call(
                nickname=f"call_{i}",
                kusp_number=f"КУСП-2025-{i:04d}",
                address=f"ул. Тестовая, д. {i}",
                district="Центральный",
                caller_name=f"Заявитель {i}",
                caller_phone=f"+7(999){i:03d}-{i:02d}-{i:02d}",
                description=f"Тестовое описание вызова {i}. Необходима проверка.",
                priority=priorities[i % 3],
                category=categories[i % 4],
                status='active' if i < 8 else 'completed',
                created_by_id=users[0].id
            )
            calls.append(call)
        
        db.session.add_all(calls)
        db.session.commit()
        
        print("Создание тестового розыска...")
        wanted = Wanted(
            nickname="wanted_001",
            citizen_id=wanted_citizen.id,
            wanted_type='federal',
            crime_article="105 УК РФ",
            crime_description="Убийство",
            dangerous=True,
            weapons="Пистолет Макарова",
            initiator="СУ СК России",
            status='active',
            created_by=users[0].id
        )
        db.session.add(wanted)
        db.session.commit()
        
        print("Создание тестового транспорта...")
        vehicles = [
            Vehicle(
                nickname="car_001",
                plate_number="А001АА78",
                brand="Toyota",
                model="Camry",
                year=2020,
                color="Черный",
                owner_id=citizens[0].id
            ),
            Vehicle(
                nickname="stolen_car",
                plate_number="В777ВВ78",
                brand="BMW",
                model="X5",
                year=2022,
                color="Белый",
                is_stolen=True,
                stolen_date="2025-01-15",
                stolen_place="ул. Парковая, д. 10"
            )
        ]
        db.session.add_all(vehicles)
        db.session.commit()
        
        print("✅ База данных успешно инициализирована!")
        print("\nТестовые пользователи:")
        print("  Админ: 001 / password123")
        print("  Супервайзер: 002 / password123")
        print("  Оператор: 003 / password123")
        print("  Патрульный: 004 / password123")
        print("  Патрульный: 005 / password123")

if __name__ == '__main__':
    init_db()
