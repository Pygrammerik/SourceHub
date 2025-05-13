from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file, session, after_this_request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import zipfile
import shutil
import tempfile
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sourcehub.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 минут

# Создаем папку для загрузок, если она не существует
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

migrate = Migrate(app, db)

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    projects = db.relationship('Project', backref='owner', lazy=True)
    avatar = db.Column(db.String(256), default=None)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)    
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issues = db.relationship('Issue', backref='project', lazy=True)
    releases = db.relationship('Release', backref='project', lazy=True)

class Issue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='open')  # open, in_progress, closed
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

class Release(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

# Routes
@app.route('/')
def index():
    projects = Project.query.all()
    return render_template('index.html', projects=projects)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.password_hash = generate_password_hash(password)
        db.session.add(user)
        db.session.commit()
        
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    user_projects_count = Project.query.filter_by(user_id=current_user.id).count()
    user_issues_count = Issue.query.join(Project).filter(Project.user_id == current_user.id).count()
    user_releases_count = Release.query.join(Project).filter(Project.user_id == current_user.id).count()
    return render_template(
        'profile.html',
        user=current_user,
        user_projects_count=user_projects_count,
        user_issues_count=user_issues_count,
        user_releases_count=user_releases_count
    )

@app.route('/project/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        project = Project(name=name, description=description, user_id=current_user.id)
        db.session.add(project)
        db.session.commit()
        return redirect(url_for('project', project_id=project.id))
    return render_template('new_project.html')

@app.route('/project/<int:project_id>')
def project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Получаем список файлов проекта
    project_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(project_id))
    items = []
    if os.path.exists(project_folder):
        def get_directory_contents(path, base_path):
            items = []
            try:
                with os.scandir(path) as entries:
                    for entry in sorted(entries, key=lambda x: (not x.is_dir(), x.name.lower())):
                        if entry.is_dir():
                            items.append({
                                'name': entry.name,
                                'path': os.path.relpath(entry.path, base_path),
                                'type': 'directory',
                                'modified': datetime.fromtimestamp(entry.stat().st_mtime),
                                'contents': get_directory_contents(entry.path, base_path)
                            })
                        else:
                            items.append({
                                'name': entry.name,
                                'path': os.path.relpath(entry.path, base_path),
                                'type': 'file',
                                'size': entry.stat().st_size,
                                'modified': datetime.fromtimestamp(entry.stat().st_mtime)
                            })
            except PermissionError:
                pass
            return items
        
        items = get_directory_contents(project_folder, project_folder)
    
    return render_template('project.html', project=project, items=items)

@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('У вас нет прав для редактирования этого проекта')
        return redirect(url_for('project', project_id=project_id))
    
    if request.method == 'POST':
        project.name = request.form['name']
        project.description = request.form['description']
        db.session.commit()
        flash('Проект успешно обновлен')
        return redirect(url_for('project', project_id=project_id))
    
    return render_template('edit_project.html', project=project)

@app.route('/project/<int:project_id>/upload', methods=['POST'])
@login_required
def upload_code(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('У вас нет прав для загрузки кода в этот проект')
        return redirect(url_for('project', project_id=project_id))
    
    if 'code_files' not in request.files:
        flash('Файлы не выбраны')
        return redirect(url_for('project', project_id=project_id))
    
    files = request.files.getlist('code_files')
    if not files or files[0].filename == '':
        flash('Файлы не выбраны')
        return redirect(url_for('project', project_id=project_id))
    
    # Создаем папку для проекта, если она не существует
    project_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(project_id))
    if not os.path.exists(project_folder):
        os.makedirs(project_folder)
    
    uploaded_files = []
    for file in files:
        if file.filename:
            filename = file.filename
            file_path = os.path.join(project_folder, filename)
            
            # Если это ZIP-архив, распаковываем его
            if filename.endswith('.zip'):
                try:
                    file.save(file_path)
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(project_folder)
                    # Удаляем ZIP-файл после распаковки
                    os.remove(file_path)
                    uploaded_files.append(f"Папка {filename} распакована")
                except zipfile.BadZipFile:
                    flash(f'Ошибка при распаковке архива {filename}')
            else:
                file.save(file_path)
                uploaded_files.append(filename)
    
    if uploaded_files:
        flash(f'Успешно загружено: {", ".join(uploaded_files)}')
    else:
        flash('Не удалось загрузить файлы')
    
    # Сохраняем сессию перед редиректом
    session.modified = True
    return redirect(url_for('project', project_id=project_id))

@app.route('/project/<int:project_id>/files')
@login_required
def view_files(project_id):
    project = Project.query.get_or_404(project_id)
    project_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(project_id))
    
    if not os.path.exists(project_folder):
        return render_template('files.html', project=project, items=[])
    
    def get_directory_contents(path, base_path):
        items = []
        try:
            # Получаем список элементов в текущей директории
            with os.scandir(path) as entries:
                # Сначала добавляем папки
                for entry in sorted(entries, key=lambda x: (not x.is_dir(), x.name.lower())):
                    if entry.is_dir():
                        items.append({
                            'name': entry.name,
                            'path': os.path.relpath(entry.path, base_path),
                            'type': 'directory',
                            'modified': datetime.fromtimestamp(entry.stat().st_mtime),
                            'contents': get_directory_contents(entry.path, base_path)
                        })
                    else:
                        items.append({
                            'name': entry.name,
                            'path': os.path.relpath(entry.path, base_path),
                            'type': 'file',
                            'size': entry.stat().st_size,
                            'modified': datetime.fromtimestamp(entry.stat().st_mtime)
                        })
        except PermissionError:
            pass
        return items
    
    items = get_directory_contents(project_folder, project_folder)
    return render_template('files.html', project=project, items=items)

@app.route('/project/<int:project_id>/files/<path:filename>')
@login_required
def download_file(project_id, filename):
    project = Project.query.get_or_404(project_id)
    project_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(project_id))
    return send_from_directory(project_folder, filename)

@app.route('/project/<int:project_id>/issue/new', methods=['GET', 'POST'])
@login_required
def new_issue(project_id):
    project = Project.query.get_or_404(project_id)
    users = User.query.all()  # Получаем список всех пользователей для назначения

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        status = request.form['status']
        assigned_to = request.form.get('assigned_to', None)

        issue = Issue(
            title=title,
            description=description,
            status=status,
            assigned_to=assigned_to,
            project_id=project_id
        )
        db.session.add(issue)
        db.session.commit()
        flash('Задача успешно создана')
        return redirect(url_for('project', project_id=project_id))

    return render_template('new_issue.html', project=project, users=users)

@app.route('/project/<int:project_id>/release/new', methods=['GET', 'POST'])
@login_required
def new_release(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('У вас нет прав для создания релизов в этом проекте')
        return redirect(url_for('project', project_id=project_id))
    
    if request.method == 'POST':
        version = request.form['version']
        description = request.form['description']
        release = Release(version=version, description=description, project_id=project_id)
        db.session.add(release)
        db.session.commit()
        flash('Релиз успешно создан')
        return redirect(url_for('project', project_id=project_id))
    
    return render_template('new_release.html', project=project)

@app.route('/project/<int:project_id>/files/<path:filename>/delete', methods=['POST'])
@login_required
def delete_file(project_id, filename):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('У вас нет прав для удаления файлов в этом проекте')
        return redirect(url_for('project', project_id=project_id))
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], str(project_id), filename)
    if os.path.exists(file_path):
        try:
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)
            flash('Файл успешно удален')
        except Exception as e:
            flash(f'Ошибка при удалении файла: {str(e)}')
    else:
        flash('Файл не найден')
    
    return redirect(url_for('project', project_id=project_id))

@app.route('/project/<int:project_id>/download')
def download_project(project_id):
    project = Project.query.get_or_404(project_id)
    project_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(project_id))
    
    if not os.path.exists(project_folder):
        flash('В проекте нет файлов для скачивания')
        return redirect(url_for('project', project_id=project_id))
    
    # Создаем временный ZIP-архив
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"{project.name}.zip")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_folder):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, project_folder)
                zipf.write(file_path, arcname)

    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
        return response

    return send_file(
        zip_path,
        as_attachment=True,
        download_name=f"{project.name}.zip",
        mimetype='application/zip'
    )

@app.route('/project/<int:project_id>/issue/<int:issue_id>/delete', methods=['POST'])
@login_required
def delete_issue(project_id, issue_id):
    project = Project.query.get_or_404(project_id)
    issue = Issue.query.get_or_404(issue_id)
    if project.user_id != current_user.id:
        flash('У вас нет прав для удаления этой задачи')
        return redirect(url_for('project', project_id=project_id))
    db.session.delete(issue)
    db.session.commit()
    flash('Задача успешно удалена')
    return redirect(url_for('project', project_id=project_id))

@app.route('/project/<int:project_id>/files/<path:filename>/view')
@login_required
def view_file(project_id, filename):
    project = Project.query.get_or_404(project_id)
    project_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(project_id))
    file_path = os.path.join(project_folder, filename)
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        flash('Файл не найден')
        return redirect(url_for('project', project_id=project_id))
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        content = f'Ошибка при чтении файла: {e}'
    return render_template('view_file.html', project=project, filename=filename, content=content)

@app.route('/project/<int:project_id>/release/<int:release_id>/delete', methods=['POST'])
@login_required
def delete_release(project_id, release_id):
    project = Project.query.get_or_404(project_id)
    release = Release.query.get_or_404(release_id)
    if project.user_id != current_user.id:
        flash('У вас нет прав для удаления релизов в этом проекте')
        return redirect(url_for('project', project_id=project_id))
    db.session.delete(release)
    db.session.commit()
    flash('Релиз успешно удалён')
    return redirect(url_for('project', project_id=project_id))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
