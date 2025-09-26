from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import secrets
from datetime import datetime, date, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = 'ZapJSwLc2gNo8C341iWDFCwIZYGdqpoj'  # Change this in production

# Custom Jinja2 filters
@app.template_filter('title_case')
def title_case_filter(text):
    """Convert text to title case for better UI display"""
    if text:
        return text.title()
    return text

# Database setup
DATABASE = 'homie.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def parse_datetime(date_string):
    """Parse SQLite datetime string to Python datetime object"""
    if date_string is None:
        return None
    try:
        return datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            return datetime.strptime(date_string, '%Y-%m-%d')
        except ValueError:
            return None

def parse_date(date_string):
    """Parse SQLite date string to Python date object"""
    if date_string is None:
        return None
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').date()
    except ValueError:
        return None

def init_db():
    """Initialize the database with required tables"""
    conn = get_db_connection()
    
    # Users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add admin column to existing users table if it doesn't exist
    try:
        conn.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE')
    except:
        pass  # Column already exists
    
    # Add last_login column to existing users table if it doesn't exist
    try:
        conn.execute('ALTER TABLE users ADD COLUMN last_login TIMESTAMP')
    except:
        pass  # Column already exists
    
    # Signup tokens table for admin-generated registration links
    conn.execute('''
        CREATE TABLE IF NOT EXISTS signup_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            created_by INTEGER NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            used_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users (id),
            FOREIGN KEY (used_by) REFERENCES users (id)
        )
    ''')
    
    # Shopping list table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS shopping_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            added_by INTEGER NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            completed_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (added_by) REFERENCES users (id),
            FOREIGN KEY (completed_by) REFERENCES users (id)
        )
    ''')
    
    # Chores table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS chores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chore_name TEXT NOT NULL,
            description TEXT,
            assigned_to INTEGER,
            added_by INTEGER NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            completed_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (assigned_to) REFERENCES users (id),
            FOREIGN KEY (added_by) REFERENCES users (id),
            FOREIGN KEY (completed_by) REFERENCES users (id)
        )
    ''')
    
    # Expiry items table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS expiry_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            expiry_date DATE NOT NULL,
            added_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (added_by) REFERENCES users (id)
        )
    ''')
    
    # Bills table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_name TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            due_day INTEGER NOT NULL,
            added_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (added_by) REFERENCES users (id)
        )
    ''')
    
    # Make 'Cam' or 'cam' an admin if they exist (case insensitive)
    conn.execute("UPDATE users SET is_admin = TRUE WHERE LOWER(username) = 'cam'")
    
    conn.commit()
    conn.close()

def login_required(f):
    """Decorator to require login for certain routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges for certain routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        
        if not user or not user['is_admin']:
            flash('Admin privileges required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get dashboard stats
    shopping_count = conn.execute('SELECT COUNT(*) as count FROM shopping_items WHERE completed = 0').fetchone()['count']
    chores_count = conn.execute('SELECT COUNT(*) as count FROM chores WHERE completed = 0').fetchone()['count']
    
    # Get expiring items (next 30 days)
    expiring_count = conn.execute('''
        SELECT COUNT(*) as count FROM expiry_items 
        WHERE julianday(expiry_date) - julianday('now') BETWEEN 0 AND 30
    ''').fetchone()['count']
    
    # Get monthly bills total
    monthly_total = conn.execute('SELECT SUM(amount) as total FROM bills').fetchone()['total'] or 0
    
    # Get the last activity clear time (create settings table if it doesn't exist)
    try:
        activity_cleared_result = conn.execute('''
            SELECT value FROM settings WHERE key = 'activity_cleared_at'
        ''').fetchone()
        activity_cleared_at = activity_cleared_result['value'] if activity_cleared_result else '1970-01-01 00:00:00'
    except sqlite3.OperationalError:
        # Settings table doesn't exist yet, so no activities have been cleared
        activity_cleared_at = '1970-01-01 00:00:00'
    
    # Get recent activities (last 10)
    recent_activities = []
    
    # Recent shopping items added (after last clear)
    recent_shopping = conn.execute('''
        SELECT si.item_name, si.created_at, u.username
        FROM shopping_items si
        LEFT JOIN users u ON si.added_by = u.id
        WHERE si.created_at > ?
        ORDER BY si.created_at DESC
        LIMIT 3
    ''', (activity_cleared_at,)).fetchall()
    
    for item in recent_shopping:
        recent_activities.append({
            'icon': 'fa-shopping-cart',
            'description': f'{item["username"]} added "{item["item_name"]}" to shopping list',
            'time': item['created_at']
        })
    
    # Recent chores completed (after last clear)
    recent_chores = conn.execute('''
        SELECT c.chore_name, c.completed_at, u.username
        FROM chores c
        LEFT JOIN users u ON c.completed_by = u.id
        WHERE c.completed = 1 AND c.completed_at > ?
        ORDER BY c.completed_at DESC
        LIMIT 3
    ''', (activity_cleared_at,)).fetchall()
    
    for chore in recent_chores:
        recent_activities.append({
            'icon': 'fa-check-circle',
            'description': f'{chore["username"]} completed "{chore["chore_name"]}"',
            'time': chore['completed_at']
        })
    
    # Sort activities by time and take the most recent 5
    recent_activities.sort(key=lambda x: x['time'], reverse=True)
    recent_activities = recent_activities[:5]
    
    # Format times for display
    for activity in recent_activities:
        try:
            activity_time = datetime.strptime(activity['time'], '%Y-%m-%d %H:%M:%S')
            activity['time'] = activity_time.strftime('%B %d at %I:%M %p')
        except:
            activity['time'] = 'Recently'
    
    conn.close()
    
    return render_template('dashboard.html', 
                         shopping_count=shopping_count,
                         chores_count=chores_count,
                         expiring_count=expiring_count,
                         monthly_total=monthly_total,
                         recent_activities=recent_activities)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        # Use case-insensitive username lookup
        user = conn.execute(
            'SELECT * FROM users WHERE LOWER(username) = ?', (username.lower(),)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            # Update last login time and make cam admin if not already
            conn = get_db_connection()
            if user['username'].lower() == 'cam':
                conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP, is_admin = 1 WHERE id = ?', (user['id'],))
            else:
                conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
            conn.commit()
            
            # Get fresh user data to ensure we have the latest is_admin value
            updated_user = conn.execute('SELECT * FROM users WHERE id = ?', (user['id'],)).fetchone()
            conn.close()
            
            session['user_id'] = updated_user['id']
            session['username'] = updated_user['username']
            session['is_admin'] = bool(updated_user['is_admin'])
            flash('Welcome back!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register/<token>', methods=['GET', 'POST'])
def register(token):
    conn = get_db_connection()
    
    # Verify the signup token is valid and not used
    signup_token = conn.execute('''
        SELECT * FROM signup_tokens 
        WHERE token = ? AND used = FALSE AND expires_at > CURRENT_TIMESTAMP
    ''', (token,)).fetchone()
    
    if not signup_token:
        conn.close()
        flash('Invalid or expired registration link.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            conn.close()
            return render_template('register.html', token=token)
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            conn.close()
            return render_template('register.html', token=token)
        
        # Convert username to lowercase for storage
        username_lower = username.lower()
        
        # Check if username or email already exists (case insensitive for username)
        existing_user = conn.execute(
            'SELECT id FROM users WHERE LOWER(username) = ? OR email = ?', (username_lower, email)
        ).fetchone()
        
        if existing_user:
            flash('Username or email already exists', 'error')
            conn.close()
            return render_template('register.html', token=token)
        
        # Create new user (store username in lowercase)
        password_hash = generate_password_hash(password)
        cursor = conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username_lower, email, password_hash)
        )
        new_user_id = cursor.lastrowid
        
        # Mark the signup token as used
        conn.execute(
            'UPDATE signup_tokens SET used = TRUE, used_by = ? WHERE id = ?',
            (new_user_id, signup_token['id'])
        )
        conn.commit()
        
        # Get the new user and log them in
        user = conn.execute(
            'SELECT * FROM users WHERE id = ?', (new_user_id,)
        ).fetchone()
        conn.close()
        
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['is_admin'] = bool(user['is_admin'])
        flash('Account created successfully! Welcome to Homie!', 'success')
        return redirect(url_for('index'))
    
    conn.close()
    return render_template('register.html', token=token)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/shopping')
@login_required
def shopping_list():
    conn = get_db_connection()
    
    # Get pending items
    items_raw = conn.execute('''
        SELECT si.*, u1.username as added_by_username, u2.username as completed_by_username
        FROM shopping_items si
        LEFT JOIN users u1 ON si.added_by = u1.id
        LEFT JOIN users u2 ON si.completed_by = u2.id
        WHERE si.completed = 0
        ORDER BY si.created_at DESC
    ''').fetchall()
    
    # Get recently completed items (last 7 days)
    completed_items_raw = conn.execute('''
        SELECT si.*, u1.username as added_by_username, u2.username as completed_by_username
        FROM shopping_items si
        LEFT JOIN users u1 ON si.added_by = u1.id
        LEFT JOIN users u2 ON si.completed_by = u2.id
        WHERE si.completed = 1 AND si.completed_at > datetime('now', '-7 days')
        ORDER BY si.completed_at DESC
    ''').fetchall()
    
    conn.close()
    
    # Convert to dictionaries and parse dates
    items = []
    for item in items_raw:
        item_dict = dict(item)
        item_dict['created_at'] = parse_datetime(item['created_at'])
        item_dict['completed_at'] = parse_datetime(item['completed_at'])
        items.append(item_dict)
    
    completed_items = []
    for item in completed_items_raw:
        item_dict = dict(item)
        item_dict['created_at'] = parse_datetime(item['created_at'])
        item_dict['completed_at'] = parse_datetime(item['completed_at'])
        completed_items.append(item_dict)
    
    return render_template('shopping_list.html', items=items, completed_items=completed_items)

@app.route('/shopping', methods=['POST'])
@login_required
def add_shopping_item():
    item_name = request.form['item_name'].strip()
    
    if not item_name:
        flash('Please enter an item name', 'error')
        return redirect(url_for('shopping_list'))
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO shopping_items (item_name, added_by) VALUES (?, ?)',
        (item_name, session['user_id'])
    )
    conn.commit()
    conn.close()
    
    flash(f'"{item_name}" added to shopping list', 'success')
    return redirect(url_for('shopping_list'))

@app.route('/toggle_shopping/<int:item_id>', methods=['POST'])
@login_required
def toggle_shopping_item(item_id):
    conn = get_db_connection()
    
    # Get current status
    item = conn.execute('SELECT * FROM shopping_items WHERE id = ?', (item_id,)).fetchone()
    
    if not item:
        return jsonify({'success': False, 'message': 'Item not found'})
    
    # Toggle completion status
    new_status = not item['completed']
    
    if new_status:
        # Mark as completed
        conn.execute(
            'UPDATE shopping_items SET completed = 1, completed_by = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?',
            (session['user_id'], item_id)
        )
    else:
        # Mark as not completed
        conn.execute(
            'UPDATE shopping_items SET completed = 0, completed_by = NULL, completed_at = NULL WHERE id = ?',
            (item_id,)
        )
    
    conn.commit()
    
    # Get updated item with user information
    updated_item = conn.execute('''
        SELECT si.*, 
               added_by_user.username as added_by_username,
               completed_by_user.username as completed_by_username
        FROM shopping_items si
        LEFT JOIN users added_by_user ON si.added_by = added_by_user.id
        LEFT JOIN users completed_by_user ON si.completed_by = completed_by_user.id
        WHERE si.id = ?
    ''', (item_id,)).fetchone()
    
    conn.close()
    
    return jsonify({
        'success': True,
        'item': {
            'id': updated_item['id'],
            'item_name': updated_item['item_name'],
            'completed': bool(updated_item['completed']),
            'added_by_username': updated_item['added_by_username'],
            'completed_by_username': updated_item['completed_by_username'],
            'created_at': updated_item['created_at'],
            'completed_at': updated_item['completed_at']
        }
    })

@app.route('/delete_shopping/<int:item_id>', methods=['DELETE'])
@login_required
def delete_shopping_item(item_id):
    conn = get_db_connection()
    
    # Check if item exists
    item = conn.execute('SELECT * FROM shopping_items WHERE id = ?', (item_id,)).fetchone()
    
    if not item:
        return jsonify({'success': False, 'message': 'Item not found'})
    
    # Delete the item
    conn.execute('DELETE FROM shopping_items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/chores')
@login_required
def chores():
    conn = get_db_connection()
    
    # Get all users for assignment dropdown
    users = conn.execute('SELECT id, username FROM users ORDER BY username').fetchall()
    
    # Get pending chores
    chores_list_raw = conn.execute('''
        SELECT c.*, u1.username as added_by_username, u2.username as assigned_to_username, u3.username as completed_by_username
        FROM chores c
        LEFT JOIN users u1 ON c.added_by = u1.id
        LEFT JOIN users u2 ON c.assigned_to = u2.id
        LEFT JOIN users u3 ON c.completed_by = u3.id
        WHERE c.completed = 0
        ORDER BY c.created_at DESC
    ''').fetchall()
    
    # Get recently completed chores (last 7 days)
    completed_chores_raw = conn.execute('''
        SELECT c.*, u1.username as added_by_username, u2.username as assigned_to_username, u3.username as completed_by_username
        FROM chores c
        LEFT JOIN users u1 ON c.added_by = u1.id
        LEFT JOIN users u2 ON c.assigned_to = u2.id
        LEFT JOIN users u3 ON c.completed_by = u3.id
        WHERE c.completed = 1 AND c.completed_at > datetime('now', '-7 days')
        ORDER BY c.completed_at DESC
    ''').fetchall()
    
    conn.close()
    
    # Convert to dictionaries and parse dates
    chores_list = []
    for chore in chores_list_raw:
        chore_dict = dict(chore)
        chore_dict['created_at'] = parse_datetime(chore['created_at'])
        chore_dict['completed_at'] = parse_datetime(chore['completed_at'])
        chores_list.append(chore_dict)
    
    completed_chores = []
    for chore in completed_chores_raw:
        chore_dict = dict(chore)
        chore_dict['created_at'] = parse_datetime(chore['created_at'])
        chore_dict['completed_at'] = parse_datetime(chore['completed_at'])
        completed_chores.append(chore_dict)
    
    return render_template('chores.html', chores=chores_list, completed_chores=completed_chores, users=users)

@app.route('/chores', methods=['POST'])
@login_required
def add_chore():
    chore_name = request.form['chore_name'].strip()
    description = request.form.get('description', '').strip()
    assigned_to = request.form.get('assigned_to')
    
    if not chore_name:
        flash('Please enter a chore name', 'error')
        return redirect(url_for('chores'))
    
    # Convert empty string to None for database
    assigned_to = int(assigned_to) if assigned_to else None
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO chores (chore_name, description, assigned_to, added_by) VALUES (?, ?, ?, ?)',
        (chore_name, description or None, assigned_to, session['user_id'])
    )
    conn.commit()
    conn.close()
    
    flash(f'Chore "{chore_name}" added successfully', 'success')
    return redirect(url_for('chores'))

@app.route('/toggle_chore/<int:chore_id>', methods=['POST'])
@login_required
def toggle_chore(chore_id):
    conn = get_db_connection()
    
    # Get current status
    chore = conn.execute('SELECT * FROM chores WHERE id = ?', (chore_id,)).fetchone()
    
    if not chore:
        return jsonify({'success': False, 'message': 'Chore not found'})
    
    # Toggle completion status
    new_status = not chore['completed']
    
    if new_status:
        # Mark as completed
        conn.execute(
            'UPDATE chores SET completed = 1, completed_by = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?',
            (session['user_id'], chore_id)
        )
    else:
        # Mark as not completed
        conn.execute(
            'UPDATE chores SET completed = 0, completed_by = NULL, completed_at = NULL WHERE id = ?',
            (chore_id,)
        )
    
    conn.commit()
    
    # Get updated chore with user information
    updated_chore = conn.execute('''
        SELECT c.*, 
               added_by_user.username as added_by_username,
               assigned_to_user.username as assigned_to_username,
               completed_by_user.username as completed_by_username
        FROM chores c
        LEFT JOIN users added_by_user ON c.added_by = added_by_user.id
        LEFT JOIN users assigned_to_user ON c.assigned_to = assigned_to_user.id
        LEFT JOIN users completed_by_user ON c.completed_by = completed_by_user.id
        WHERE c.id = ?
    ''', (chore_id,)).fetchone()
    
    conn.close()
    
    return jsonify({
        'success': True,
        'chore': {
            'id': updated_chore['id'],
            'chore_name': updated_chore['chore_name'],
            'description': updated_chore['description'],
            'completed': bool(updated_chore['completed']),
            'added_by_username': updated_chore['added_by_username'],
            'assigned_to_username': updated_chore['assigned_to_username'],
            'completed_by_username': updated_chore['completed_by_username'],
            'created_at': updated_chore['created_at'],
            'completed_at': updated_chore['completed_at']
        }
    })

@app.route('/delete_chore/<int:chore_id>', methods=['DELETE'])
@login_required
def delete_chore(chore_id):
    conn = get_db_connection()
    
    # Check if chore exists
    chore = conn.execute('SELECT * FROM chores WHERE id = ?', (chore_id,)).fetchone()
    
    if not chore:
        return jsonify({'success': False, 'message': 'Chore not found'})
    
    # Delete the chore
    conn.execute('DELETE FROM chores WHERE id = ?', (chore_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/expiry')
@login_required
def expiry_tracker():
    conn = get_db_connection()
    
    # Get all expiry items with days remaining calculation (rounded to whole days)
    items_raw = conn.execute('''
        SELECT ei.*, u.username as added_by_username,
               ROUND(julianday(ei.expiry_date) - julianday('now')) as days_remaining
        FROM expiry_items ei
        LEFT JOIN users u ON ei.added_by = u.id
        ORDER BY ei.expiry_date ASC
    ''').fetchall()
    
    # Convert to dictionaries and parse dates
    items = []
    for item in items_raw:
        item_dict = dict(item)
        item_dict['expiry_date'] = parse_date(item['expiry_date'])
        items.append(item_dict)
    
    # Count items by status
    expired_count = sum(1 for item in items if item['days_remaining'] < 0)
    expiring_soon_count = sum(1 for item in items if 0 <= item['days_remaining'] <= 30)
    
    conn.close()
    
    return render_template('expiry_tracker.html', 
                         items=items, 
                         expired_count=expired_count,
                         expiring_soon_count=expiring_soon_count)

@app.route('/expiry', methods=['POST'])
@login_required
def add_expiry_item():
    item_name = request.form['item_name'].strip()
    expiry_date = request.form['expiry_date']
    
    if not item_name or not expiry_date:
        flash('Please enter both item name and expiry date', 'error')
        return redirect(url_for('expiry_tracker'))
    
    # Validate date is not in the past
    try:
        expiry_date_obj = datetime.strptime(expiry_date, '%Y-%m-%d').date()
        if expiry_date_obj < date.today():
            flash('Expiry date cannot be in the past', 'error')
            return redirect(url_for('expiry_tracker'))
    except ValueError:
        flash('Invalid date format', 'error')
        return redirect(url_for('expiry_tracker'))
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO expiry_items (item_name, expiry_date, added_by) VALUES (?, ?, ?)',
        (item_name, expiry_date, session['user_id'])
    )
    conn.commit()
    conn.close()
    
    flash(f'"{item_name}" added to expiry tracker', 'success')
    return redirect(url_for('expiry_tracker'))

@app.route('/delete_expiry/<int:item_id>', methods=['DELETE'])
@login_required
def delete_expiry_item(item_id):
    conn = get_db_connection()
    
    # Check if item exists
    item = conn.execute('SELECT * FROM expiry_items WHERE id = ?', (item_id,)).fetchone()
    
    if not item:
        return jsonify({'success': False, 'message': 'Item not found'})
    
    # Delete the item
    conn.execute('DELETE FROM expiry_items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/bills')
@login_required
def bills():
    conn = get_db_connection()
    
    # Get all bills with days until due calculation
    bills_list = conn.execute('''
        SELECT b.*, u.username as added_by_username
        FROM bills b
        LEFT JOIN users u ON b.added_by = u.id
        ORDER BY b.due_day ASC
    ''').fetchall()
    
    # Calculate days until due for each bill
    today = date.today()
    current_day = today.day
    
    bills_with_due_info = []
    monthly_total = 0
    
    for bill in bills_list:
        bill_dict = dict(bill)
        
        # Calculate days until due
        due_day = bill['due_day']
        if due_day >= current_day:
            # Due this month
            due_date = date(today.year, today.month, due_day)
        else:
            # Due next month
            next_month = today.month + 1 if today.month < 12 else 1
            next_year = today.year if today.month < 12 else today.year + 1
            try:
                due_date = date(next_year, next_month, due_day)
            except ValueError:
                # Handle case where due_day doesn't exist in next month (e.g., Feb 30)
                from calendar import monthrange
                last_day = monthrange(next_year, next_month)[1]
                due_date = date(next_year, next_month, min(due_day, last_day))
        
        days_until_due = (due_date - today).days
        bill_dict['days_until_due'] = days_until_due
        
        bills_with_due_info.append(bill_dict)
        monthly_total += float(bill['amount'])
    
    conn.close()
    
    return render_template('bills.html', bills=bills_with_due_info, monthly_total=monthly_total)

@app.route('/bills', methods=['POST'])
@login_required
def add_bill():
    bill_name = request.form['bill_name'].strip()
    amount = request.form['amount']
    due_day = request.form['due_day']
    
    if not bill_name or not amount or not due_day:
        flash('Please fill in all fields', 'error')
        return redirect(url_for('bills'))
    
    try:
        amount = float(amount)
        due_day = int(due_day)
        
        if amount < 0:
            flash('Amount must be positive', 'error')
            return redirect(url_for('bills'))
        
        if due_day < 1 or due_day > 31:
            flash('Due day must be between 1 and 31', 'error')
            return redirect(url_for('bills'))
            
    except ValueError:
        flash('Invalid amount or due day', 'error')
        return redirect(url_for('bills'))
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO bills (bill_name, amount, due_day, added_by) VALUES (?, ?, ?, ?)',
        (bill_name, amount, due_day, session['user_id'])
    )
    conn.commit()
    conn.close()
    
    flash(f'Bill "{bill_name}" added successfully', 'success')
    return redirect(url_for('bills'))

@app.route('/edit_bill', methods=['POST'])
@login_required
def edit_bill():
    bill_id = request.form['bill_id']
    bill_name = request.form['bill_name'].strip()
    amount = request.form['amount']
    due_day = request.form['due_day']
    
    if not bill_name or not amount or not due_day:
        flash('Please fill in all fields', 'error')
        return redirect(url_for('bills'))
    
    try:
        amount = float(amount)
        due_day = int(due_day)
        
        if amount < 0:
            flash('Amount must be positive', 'error')
            return redirect(url_for('bills'))
        
        if due_day < 1 or due_day > 31:
            flash('Due day must be between 1 and 31', 'error')
            return redirect(url_for('bills'))
            
    except ValueError:
        flash('Invalid amount or due day', 'error')
        return redirect(url_for('bills'))
    
    conn = get_db_connection()
    
    # Check if bill exists
    bill = conn.execute('SELECT * FROM bills WHERE id = ?', (bill_id,)).fetchone()
    
    if not bill:
        flash('Bill not found', 'error')
        conn.close()
        return redirect(url_for('bills'))
    
    # Update the bill
    conn.execute(
        'UPDATE bills SET bill_name = ?, amount = ?, due_day = ? WHERE id = ?',
        (bill_name, amount, due_day, bill_id)
    )
    conn.commit()
    conn.close()
    
    flash(f'Bill "{bill_name}" updated successfully', 'success')
    return redirect(url_for('bills'))

@app.route('/delete_bill/<int:bill_id>', methods=['DELETE'])
@login_required
def delete_bill(bill_id):
    conn = get_db_connection()
    
    # Check if bill exists
    bill = conn.execute('SELECT * FROM bills WHERE id = ?', (bill_id,)).fetchone()
    
    if not bill:
        return jsonify({'success': False, 'message': 'Bill not found'})
    
    # Delete the bill
    conn.execute('DELETE FROM bills WHERE id = ?', (bill_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/settings')
@login_required
def settings():
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    return render_template('settings.html', current_user=user)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    username = request.form['username'].strip()
    email = request.form['email'].strip()
    
    if not username or not email:
        flash('Username and email are required.', 'error')
        return redirect(url_for('settings'))
    
    # Convert username to lowercase for storage
    username_lower = username.lower()
    
    conn = get_db_connection()
    
    # Check if username or email already exists (excluding current user, case insensitive for username)
    existing_user = conn.execute(
        'SELECT id FROM users WHERE (LOWER(username) = ? OR email = ?) AND id != ?',
        (username_lower, email, session['user_id'])
    ).fetchone()
    
    if existing_user:
        flash('Username or email already exists.', 'error')
        conn.close()
        return redirect(url_for('settings'))
    
    # Update user profile (store username in lowercase)
    conn.execute(
        'UPDATE users SET username = ?, email = ? WHERE id = ?',
        (username_lower, email, session['user_id'])
    )
    conn.commit()
    conn.close()
    
    # Update session username (store lowercase in session too)
    session['username'] = username_lower
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    
    if not current_password or not new_password or not confirm_password:
        flash('All password fields are required.', 'error')
        return redirect(url_for('settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('settings'))
    
    if len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'error')
        return redirect(url_for('settings'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    if not user or not check_password_hash(user['password_hash'], current_password):
        flash('Current password is incorrect.', 'error')
        conn.close()
        return redirect(url_for('settings'))
    
    # Update password
    new_password_hash = generate_password_hash(new_password)
    conn.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (new_password_hash, session['user_id'])
    )
    conn.commit()
    conn.close()
    
    flash('Password changed successfully!', 'success')
    return redirect(url_for('settings'))

# Admin routes
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    
    # Get active signup tokens
    active_tokens = conn.execute('''
        SELECT st.*, u.username as created_by_username
        FROM signup_tokens st
        LEFT JOIN users u ON st.created_by = u.id
        WHERE st.used = FALSE AND st.expires_at > CURRENT_TIMESTAMP
        ORDER BY st.created_at DESC
    ''').fetchall()
    
    # Get used tokens
    used_tokens = conn.execute('''
        SELECT st.*, 
               created_by_user.username as created_by_username,
               used_by_user.username as used_by_username
        FROM signup_tokens st
        LEFT JOIN users created_by_user ON st.created_by = created_by_user.id
        LEFT JOIN users used_by_user ON st.used_by = used_by_user.id
        WHERE st.used = TRUE
        ORDER BY st.created_at DESC
        LIMIT 10
    ''').fetchall()
    
    # Get all users for user management
    users = conn.execute('''
        SELECT id, username, email, is_admin, last_login, created_at
        FROM users
        ORDER BY created_at DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         active_tokens=active_tokens,
                         used_tokens=used_tokens,
                         users=users)

@app.route('/admin/generate_signup_link', methods=['POST'])
@admin_required
def generate_signup_link():
    # Generate a secure token
    token = secrets.token_urlsafe(32)
    
    # Set expiration to 7 days from now
    expires_at = datetime.now() + timedelta(days=7)
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO signup_tokens (token, created_by, expires_at) VALUES (?, ?, ?)',
        (token, session['user_id'], expires_at)
    )
    conn.commit()
    conn.close()
    
    flash('Signup link generated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_token/<int:token_id>', methods=['POST'])
@admin_required
def delete_signup_token(token_id):
    conn = get_db_connection()
    
    # Check if token exists and is active
    token = conn.execute(
        'SELECT * FROM signup_tokens WHERE id = ? AND used = FALSE',
        (token_id,)
    ).fetchone()
    
    if not token:
        flash('Token not found or already used.', 'error')
        conn.close()
        return redirect(url_for('admin_dashboard'))
    
    # Delete the token
    conn.execute('DELETE FROM signup_tokens WHERE id = ?', (token_id,))
    conn.commit()
    conn.close()
    
    flash('Signup token deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/users')
@admin_required
def admin_users():
    conn = get_db_connection()
    users = conn.execute('''
        SELECT id, username, email, is_admin, last_login, created_at
        FROM users
        ORDER BY created_at DESC
    ''').fetchall()
    conn.close()
    
    return render_template('admin_users.html', users=users)

@app.route('/admin/edit_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_edit_user(user_id):
    username = request.form['username']
    email = request.form['email']
    
    # Convert username to lowercase for storage
    username_lower = username.lower()
    
    conn = get_db_connection()
    
    # Check if username or email already exists (excluding current user, case insensitive for username)
    existing_user = conn.execute(
        'SELECT id FROM users WHERE (LOWER(username) = ? OR email = ?) AND id != ?',
        (username_lower, email, user_id)
    ).fetchone()
    
    if existing_user:
        flash('Username or email already exists.', 'error')
        conn.close()
        return redirect(url_for('admin_dashboard'))
    
    # Update user (store username in lowercase)
    conn.execute(
        'UPDATE users SET username = ?, email = ? WHERE id = ?',
        (username_lower, email, user_id)
    )
    conn.commit()
    conn.close()
    
    flash('User updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reset_password/<int:user_id>', methods=['POST'])
@admin_required
def admin_reset_password(user_id):
    new_password = request.form['new_password']
    
    if len(new_password) < 6:
        flash('Password must be at least 6 characters long.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    conn = get_db_connection()
    password_hash = generate_password_hash(new_password)
    conn.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (password_hash, user_id)
    )
    conn.commit()
    conn.close()
    
    flash('Password reset successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    # Prevent admin from deleting themselves
    if user_id == session['user_id']:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    conn = get_db_connection()
    
    # Check if user exists
    user = conn.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('User not found.', 'error')
        conn.close()
        return redirect(url_for('admin_dashboard'))
    
    # Delete user (this will cascade delete their items due to foreign keys)
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    flash(f'User "{user["username"]}" deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/clear_recent_activity', methods=['POST'])
@admin_required
def clear_recent_activity():
    conn = get_db_connection()
    
    # Create a settings table if it doesn't exist
    conn.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Store the current timestamp as the "cleared" time
    from datetime import datetime
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn.execute('''
        INSERT OR REPLACE INTO settings (key, value, updated_at)
        VALUES ('activity_cleared_at', ?, ?)
    ''', (current_time, current_time))
    
    conn.commit()
    conn.close()
    
    flash('Recent activity cleared successfully.', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)