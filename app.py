from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# File upload configuration
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'txt', 'docx'}

# Database setup
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tasks.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime, nullable=True)
    done = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    file_name = db.Column(db.String(200))  # new column for file

# Initialize DB (if needed)
with app.app_context():
    db.create_all()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))
        db.session.add(User(username=username, password=password))
        db.session.commit()
        flash('Registered! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('index'))
        flash('Invalid login.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out!')
    return redirect(url_for('login'))

@app.route('/tasks')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    tasks = Task.query.filter_by(user_id=session['user_id']).order_by(Task.due_date).all()
    total = len(tasks)
    completed = len([t for t in tasks if t.done])
    pending = total - completed
    current_time = datetime.now()
    return render_template('index.html', tasks=tasks, username=session['username'],
                           total=total, completed=completed, pending=pending, current_time=current_time)

@app.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    task_name = request.form['task']
    description = request.form.get('description')
    due_date_str = request.form.get('due_date')
    due_date = datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M") if due_date_str else None

    file = request.files.get('file')
    file_name = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        file_name = filename

    new_task = Task(name=task_name, description=description, due_date=due_date,
                    user_id=session['user_id'], file_name=file_name)
    db.session.add(new_task)
    db.session.commit()
    flash('Task added.')
    return redirect(url_for('index'))

@app.route('/complete/<int:task_id>')
def complete(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != session['user_id']:
        return redirect(url_for('index'))
    task.done = True
    db.session.commit()
    flash('Task marked as complete.')
    return redirect(url_for('index'))

@app.route('/delete/<int:task_id>')
def delete(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != session['user_id']:
        return redirect(url_for('index'))
    
    # Delete attached file if it exists
    if task.file_name:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], task.file_name)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.')
    return redirect(url_for('index'))

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != session['user_id']:
        return redirect(url_for('index'))
    if request.method == 'POST':
        task.name = request.form['task']
        task.description = request.form.get('description')
        due_date_str = request.form.get('due_date')
        task.due_date = datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M") if due_date_str else None
        db.session.commit()
        flash('Task updated.')
        return redirect(url_for('index'))
    return render_template('edit_task.html', task=task)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
