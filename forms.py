from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField, DateField, FileField, BooleanField, IntegerField, FloatField
from wtforms.validators import DataRequired, Length, Email, Optional, ValidationError
from flask_wtf.file import FileAllowed
from datetime import datetime

# Форма входа
class LoginForm(FlaskForm):
    badge_number = StringField('Табельный номер', validators=[DataRequired(), Length(min=3, max=20)])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember = BooleanField('Запомнить меня')

# Форма гражданина
class CitizenForm(FlaskForm):
    nickname = StringField('Никнейм', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Фамилия', validators=[DataRequired(), Length(min=2, max=50)])
    first_name = StringField('Имя', validators=[DataRequired(), Length(min=2, max=50)])
    middle_name = StringField('Отчество', validators=[Optional(), Length(max=50)])
    birth_date = StringField('Дата рождения', validators=[Optional(), Length(max=10)])
    birth_place = StringField('Место рождения', validators=[Optional(), Length(max=200)])
    
    passport_series = StringField('Серия паспорта', validators=[Optional(), Length(min=4, max=4)])
    passport_number = StringField('Номер паспорта', validators=[Optional(), Length(min=6, max=6)])
    passport_issued_by = StringField('Кем выдан', validators=[Optional(), Length(max=200)])
    passport_issued_date = StringField('Дата выдачи', validators=[Optional(), Length(max=10)])
    passport_code = StringField('Код подразделения', validators=[Optional(), Length(max=7)])
    
    address_registration = StringField('Адрес регистрации', validators=[Optional(), Length(max=200)])
    address_residence = StringField('Адрес проживания', validators=[Optional(), Length(max=200)])
    
    phone = StringField('Телефон', validators=[Optional(), Length(max=20)])
    phone2 = StringField('Доп. телефон', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email()])
    
    workplace = StringField('Место работы', validators=[Optional(), Length(max=200)])
    position = StringField('Должность', validators=[Optional(), Length(max=100)])
    
    photo = FileField('Фотография', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Только изображения!')])
    
    status = SelectField('Статус', choices=[
        ('active', 'Активен'),
        ('deceased', 'Умер'),
        ('emigrated', 'Уехал'),
        ('arrested', 'Арестован')
    ], default='active')
    
    danger_level = SelectField('Уровень опасности', choices=[
        ('none', 'Не опасен'),
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий')
    ], default='none')
    
    special_marks = TextAreaField('Особые приметы', validators=[Optional()])
    notes = TextAreaField('Дополнительная информация', validators=[Optional()])

# Форма вызова
class CallForm(FlaskForm):
    nickname = StringField('Никнейм вызова', validators=[DataRequired(), Length(min=2, max=50)])
    address = StringField('Адрес', validators=[DataRequired(), Length(max=200)])
    district = StringField('Район', validators=[Optional(), Length(max=50)])
    
    caller_name = StringField('ФИО заявителя', validators=[Optional(), Length(max=100)])
    caller_phone = StringField('Телефон заявителя', validators=[Optional(), Length(max=20)])
    caller_address = StringField('Адрес заявителя', validators=[Optional(), Length(max=200)])
    
    description = TextAreaField('Описание происшествия', validators=[DataRequired()])
    
    category = SelectField('Категория', choices=[
        ('crime', 'Преступление'),
        ('administrative', 'Административное'),
        ('accident', 'ДТП'),
        ('check', 'Проверка')
    ], default='crime')
    
    subcategory = StringField('Подкатегория', validators=[Optional(), Length(max=50)])
    
    priority = SelectField('Приоритет', choices=[
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий')
    ], default='medium')
    
    notes = TextAreaField('Примечания', validators=[Optional()])

# Форма розыска
class WantedForm(FlaskForm):
    nickname = StringField('Никнейм розыска', validators=[DataRequired(), Length(min=2, max=50)])
    
    wanted_type = SelectField('Тип розыска', choices=[
        ('local', 'Местный'),
        ('federal', 'Федеральный'),
        ('international', 'Международный')
    ], default='local')
    
    crime_article = StringField('Статья', validators=[DataRequired(), Length(max=100)])
    crime_description = TextAreaField('Описание преступления', validators=[DataRequired()])
    crime_date = StringField('Дата преступления', validators=[Optional(), Length(max=10)])
    
    dangerous = BooleanField('Вооружен и особо опасен')
    weapons = StringField('Если вооружен, чем', validators=[Optional(), Length(max=200)])
    special_marks = TextAreaField('Особые приметы', validators=[Optional()])
    
    initiator = StringField('Инициатор розыска', validators=[DataRequired(), Length(max=100)])
    initiator_department = StringField('Подразделение', validators=[Optional(), Length(max=100)])
    initiator_contact = StringField('Контакты', validators=[Optional(), Length(max=100)])

# Форма транспорта
class VehicleForm(FlaskForm):
    nickname = StringField('Никнейм ТС', validators=[DataRequired(), Length(min=2, max=50)])
    plate_number = StringField('Госномер', validators=[DataRequired(), Length(min=6, max=15)])
    vin = StringField('VIN', validators=[Optional(), Length(min=17, max=17)])
    
    brand = StringField('Марка', validators=[DataRequired(), Length(max=50)])
    model = StringField('Модель', validators=[DataRequired(), Length(max=50)])
    year = IntegerField('Год выпуска', validators=[Optional()])
    color = StringField('Цвет', validators=[Optional(), Length(max=30)])
    
    is_stolen = BooleanField('В угоне')
    stolen_date = StringField('Дата угона', validators=[Optional(), Length(max=10)])
    stolen_place = StringField('Место угона', validators=[Optional(), Length(max=200)])

# Форма поиска
class SearchForm(FlaskForm):
    query = StringField('Поиск', validators=[DataRequired()])
    search_type = SelectField('Тип', choices=[
        ('all', 'Всё'),
        ('citizens', 'Граждане'),
        ('calls', 'Вызовы'),
        ('wanted', 'Розыск'),
        ('vehicles', 'Транспорт')
    ], default='all')
