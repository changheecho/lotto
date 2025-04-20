# app.py
import os
import random
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect('lotto.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS saved_numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        numbers TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    conn.commit()
    conn.close()

# 로그인 필수 데코레이터
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('로그인이 필요합니다.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 로또 번호 추천 함수
def generate_lotto_numbers():
    numbers = random.sample(range(1, 46), 6)
    numbers.sort()
    return numbers

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('lotto.db')
        cursor = conn.cursor()
        
        # 사용자 존재 여부 확인
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            flash('이미 존재하는 사용자입니다.')
            conn.close()
            return redirect(url_for('register'))
        
        # 새 사용자 등록
        hashed_password = generate_password_hash(password)
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', 
                      (username, hashed_password))
        conn.commit()
        conn.close()
        
        flash('회원가입이 완료되었습니다! 로그인해주세요.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('lotto.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, password FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            flash('로그인 성공!')
            return redirect(url_for('dashboard'))
        else:
            flash('아이디 또는 비밀번호가 잘못되었습니다.')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('로그아웃 되었습니다.')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect('lotto.db')
    cursor = conn.cursor()
    cursor.execute('SELECT numbers, created_at FROM saved_numbers WHERE user_id = ? ORDER BY created_at DESC LIMIT 5', 
                  (session['user_id'],))
    saved_numbers = cursor.fetchall()
    conn.close()
    
    history = []
    for numbers, date in saved_numbers:
        numbers_list = [int(n) for n in numbers.split(',')]
        history.append((numbers_list, date))
    
    return render_template('dashboard.html', username=session['username'], history=history)

@app.route('/generate', methods=['POST'])
@login_required
def generate():
    numbers = generate_lotto_numbers()
    
    # 번호 저장
    if request.form.get('save') == 'yes':
        conn = sqlite3.connect('lotto.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO saved_numbers (user_id, numbers) VALUES (?, ?)', 
                     (session['user_id'], ','.join(map(str, numbers))))
        conn.commit()
        conn.close()
        flash('로또 번호가 저장되었습니다!')
    
    return render_template('result.html', numbers=numbers)

@app.route('/history')
@login_required
def history():
    conn = sqlite3.connect('lotto.db')
    cursor = conn.cursor()
    cursor.execute('SELECT numbers, created_at FROM saved_numbers WHERE user_id = ? ORDER BY created_at DESC', 
                  (session['user_id'],))
    saved_numbers = cursor.fetchall()
    conn.close()
    
    history = []
    for numbers, date in saved_numbers:
        numbers_list = [int(n) for n in numbers.split(',')]
        history.append((numbers_list, date))
    
    return render_template('history.html', history=history)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=45000, debug=True)