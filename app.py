from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
import sqlite3
import os
import secrets
import requests
from datetime import datetime, date, timedelta
from functools import wraps
from dotenv import load_dotenv
from urllib.parse import urlencode

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Configuration
app.secret_key = os.getenv('FLASK_SECRET_KEY')

def discover_oidc_endpoints(issuer):
    """Auto-discover OIDC endpoints from issuer's well-known configuration"""
    try:
        well_known_url = f"{issuer}/.well-known/openid-configuration"
        response = requests.get(well_known_url, timeout=10)
        response.raise_for_status()
        config = response.json()
        
        return {
            'authorization_endpoint': config.get('authorization_endpoint'),
            'token_endpoint': config.get('token_endpoint'),
            'userinfo_endpoint': config.get('userinfo_endpoint'),
            'end_session_endpoint': config.get('end_session_endpoint'),
        }
    except Exception as e:
        print(f"Failed to discover OIDC endpoints: {e}")
        # Fallback to manual configuration
        return {
            'authorization_endpoint': os.getenv('OIDC_AUTHORIZATION_ENDPOINT'),
            'token_endpoint': os.getenv('OIDC_TOKEN_ENDPOINT'),
            'userinfo_endpoint': os.getenv('OIDC_USERINFO_ENDPOINT'),
            'end_session_endpoint': os.getenv('OIDC_END_SESSION_ENDPOINT'),
        }

# OIDC Configuration
issuer = os.getenv('OIDC_ISSUER')
oidc_endpoints = discover_oidc_endpoints(issuer) if issuer else {}

OIDC_CONFIG = {
    'client_id': os.getenv('OIDC_CLIENT_ID'),
    'client_secret': os.getenv('OIDC_CLIENT_SECRET'),
    'issuer': issuer,
    'redirect_uri': os.getenv('OIDC_REDIRECT_URI'),
    **oidc_endpoints
}

# Access Control
ALLOWED_EMAILS = [email.strip() for email in os.getenv('ALLOWED_EMAILS', '').split(',') if email.strip()]
# Force reload to pick up template changes
ALLOWED_GROUPS = [group.strip() for group in os.getenv('ALLOWED_GROUPS', '').split(',') if group.strip()]
ADMIN_EMAILS = [email.strip() for email in os.getenv('ADMIN_EMAILS', '').split(',') if email.strip()]

# Database setup
DATABASE = 'homie.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Custom Jinja2 filters
@app.template_filter('title_case')
def title_case_filter(text):
    """Convert text to title case for better UI display"""
    if text:
        return text.title()
    return ''

@app.template_filter('format_date')
def format_date_filter(date_string, format_str='%B %d, %Y'):
    """Format a date string for display"""
    if not date_string:
        return ''
    try:
        # Try parsing as datetime first
        dt = parse_datetime(date_string)
        if dt:
            return dt.strftime(format_str)
        # Try parsing as date only
        d = parse_date(date_string)
        if d:
            return d.strftime(format_str)
        return date_string
    except:
        return date_string

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
    
    # Users table (simplified for OIDC-only)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT,
            is_admin BOOLEAN DEFAULT FALSE,
            oidc_sub TEXT UNIQUE NOT NULL,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP
        )
    ''')
    
    # Shopping list table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS shopping_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            added_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (added_by) REFERENCES users (id)
        )
    ''')
    
    # Chores table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS chores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chore_name TEXT NOT NULL,
            assigned_to INTEGER,
            completed BOOLEAN DEFAULT FALSE,
            added_by INTEGER NOT NULL,
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
    
    # Settings table for app configuration
    conn.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

# Authentication Functions
def is_user_authorized(userinfo):
    """Check if user is authorized based on groups (preferred) or email fallback"""
    email = userinfo.get('email')
    groups = userinfo.get('groups', [])
    
    # If no restrictions are set, allow all authenticated users
    if not ALLOWED_EMAILS and not ALLOWED_GROUPS:
        return True
    
    # Priority 1: Check group allowlist (preferred method)
    if ALLOWED_GROUPS:
        if groups and any(group in ALLOWED_GROUPS for group in groups):
            return True
        # If groups are configured but user has no matching groups, deny access
        return False
    
    # Priority 2: Fallback to email allowlist (legacy method)
    if ALLOWED_EMAILS and email in ALLOWED_EMAILS:
        return True
    
    return False

def create_or_update_user(userinfo):
    """Create or update user from OIDC userinfo"""
    conn = get_db_connection()
    
    # Extract user information
    email = userinfo.get('email')
    username = userinfo.get('preferred_username', email.split('@')[0] if email else 'user')
    full_name = userinfo.get('name', '')
    oidc_sub = userinfo.get('sub')
    is_admin = email in ADMIN_EMAILS if email else False
    
    try:
        # Try to find existing user
        user = conn.execute('''
            SELECT * FROM users WHERE oidc_sub = ?
        ''', (oidc_sub,)).fetchone()
        
        if user:
            # Update existing user
            conn.execute('''
                UPDATE users SET 
                    username = ?, email = ?, full_name = ?, is_admin = ?, last_login = CURRENT_TIMESTAMP
                WHERE oidc_sub = ?
            ''', (username, email, full_name, is_admin, oidc_sub))
        else:
            # Create new user
            conn.execute('''
                INSERT INTO users (username, email, full_name, is_admin, oidc_sub, last_login)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (username, email, full_name, is_admin, oidc_sub))
        
        conn.commit()
        
        # Get the user (updated or created)
        user = conn.execute('''
            SELECT * FROM users WHERE oidc_sub = ?
        ''', (oidc_sub,)).fetchone()
        
        conn.close()
        return user
        
    except Exception as e:
        print(f"Error creating/updating user: {e}")
        conn.close()
        return None

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # Update user activity
        conn = get_db_connection()
        conn.execute('''
            UPDATE users SET last_activity = ? WHERE id = ?
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session['user_id']))
        conn.commit()
        conn.close()
        
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    
    # Get counts for dashboard stats
    shopping_count = conn.execute('SELECT COUNT(*) as count FROM shopping_items WHERE completed = 0 OR completed IS NULL').fetchone()['count']
    chores_count = conn.execute('SELECT COUNT(*) as count FROM chores WHERE completed = 0 OR completed IS NULL').fetchone()['count']
    expiring_count = conn.execute('''
        SELECT COUNT(*) as count FROM expiry_items 
        WHERE expiry_date BETWEEN date('now') AND date('now', '+30 days')
    ''').fetchone()['count']
    
    # Get monthly bills total
    monthly_total = conn.execute('SELECT COALESCE(SUM(amount), 0) as total FROM bills').fetchone()['total']
    
    # Get recent activities for the activity feed
    recent_activities = []
    
    # Recent shopping items
    shopping_items = conn.execute('''
        SELECT 'shopping' as type, si.item_name as title, si.created_at, u.username
        FROM shopping_items si
        LEFT JOIN users u ON si.added_by = u.id
        ORDER BY si.created_at DESC
        LIMIT 3
    ''').fetchall()
    
    # Recent chores
    chores_items = conn.execute('''
        SELECT 'chore' as type, c.chore_name as title, c.created_at, u.username
        FROM chores c
        LEFT JOIN users u ON c.added_by = u.id
        ORDER BY c.created_at DESC
        LIMIT 3
    ''').fetchall()
    
    # Convert to format expected by template
    activities = []
    for item in shopping_items:
        activities.append({
            'icon': 'fa-shopping-cart',
            'description': f"{item['username'] or 'Someone'} added '{item['title']}' to shopping list",
            'time': item['created_at'],
            'created_at': item['created_at']  # For sorting
        })
    
    for item in chores_items:
        activities.append({
            'icon': 'fa-tasks', 
            'description': f"{item['username'] or 'Someone'} added chore '{item['title']}'",
            'time': item['created_at'],
            'created_at': item['created_at']  # For sorting
        })
    
    # Sort by creation time and take latest 5
    recent_activities = sorted(activities, key=lambda x: x['created_at'], reverse=True)[:5]
    
    conn.close()
    
    return render_template('dashboard.html',
                         shopping_count=shopping_count,
                         chores_count=chores_count,
                         expiring_count=expiring_count,
                         monthly_total=monthly_total,
                         recent_activities=recent_activities)

@app.route('/login')
def login():
    """Initiate OIDC login"""
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    
    # Build authorization URL - request groups if available
    params = {
        'client_id': OIDC_CONFIG['client_id'],
        'response_type': 'code',
        'scope': 'openid profile email groups',  # Add groups scope
        'redirect_uri': OIDC_CONFIG['redirect_uri'],
        'state': state
    }
    
    auth_url = f"{OIDC_CONFIG['authorization_endpoint']}?{urlencode(params)}"
    return redirect(auth_url)

@app.route('/auth/callback')
def oidc_callback():
    """Handle OIDC callback"""
    # Verify state parameter
    if request.args.get('state') != session.get('oauth_state'):
        flash('Invalid authentication state. Please try again.', 'error')
        return redirect(url_for('login'))
    
    # Check for error
    if 'error' in request.args:
        error_description = request.args.get('error_description', 'Authentication failed')
        flash(f'Authentication error: {error_description}', 'error')
        return redirect(url_for('login'))
    
    # Get authorization code
    code = request.args.get('code')
    if not code:
        flash('No authorization code received', 'error')
        return redirect(url_for('login'))
    
    try:
        # Exchange code for tokens
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': OIDC_CONFIG['redirect_uri'],
            'client_id': OIDC_CONFIG['client_id'],
            'client_secret': OIDC_CONFIG['client_secret']
        }
        
        token_response = requests.post(
            OIDC_CONFIG['token_endpoint'],
            data=token_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        token_response.raise_for_status()
        tokens = token_response.json()
        
        # Get user info
        userinfo_response = requests.get(
            OIDC_CONFIG['userinfo_endpoint'],
            headers={'Authorization': f'Bearer {tokens["access_token"]}'}
        )
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()
        
        # Debug: Print user info to see what groups are available
        print(f"DEBUG - User info for {userinfo.get('email', 'unknown')}: {userinfo}")
        print(f"DEBUG - Groups: {userinfo.get('groups', 'No groups key found')}")
        
        # Check if user is authorized
        if not is_user_authorized(userinfo):
            # Store user info temporarily for the unauthorized page
            session['temp_userinfo'] = {
                'name': userinfo.get('name'),
                'email': userinfo.get('email'),
                'preferred_username': userinfo.get('preferred_username')
            }
            return redirect(url_for('unauthorized'))
        
        # Create or update user
        user = create_or_update_user(userinfo)
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = bool(user['is_admin'])
            flash(f'Welcome, {user["full_name"] or user["username"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Failed to create user account', 'error')
            
    except Exception as e:
        print(f"OIDC callback error: {e}")
        flash('Authentication failed. Please try again.', 'error')
    
    return redirect(url_for('login'))

@app.route('/unauthorized')
def unauthorized():
    """Show unauthorized access page"""
    # Get user info from session if available
    user_info = session.get('temp_userinfo')
    # Clear temporary user info
    session.pop('temp_userinfo', None)
    return render_template('unauthorized.html', user_info=user_info)

@app.route('/logout')
def logout():
    # Clear local session
    session.clear()
    flash('You have been logged out', 'info')
    
    # Redirect to OIDC logout if available
    if OIDC_CONFIG['end_session_endpoint']:
        logout_params = {
            'post_logout_redirect_uri': request.url_root.rstrip('/') + url_for('login')
        }
        logout_url = f"{OIDC_CONFIG['end_session_endpoint']}?{urlencode(logout_params)}"
        return redirect(logout_url)
    
    return redirect(url_for('login'))

@app.route('/manifest.json')
def manifest():
    """Serve PWA manifest file"""
    return send_from_directory('static', 'manifest.json', mimetype='application/json')

# Shopping List Routes
@app.route('/shopping')
@login_required
def shopping_list():
    conn = get_db_connection()
    
    # Get active (non-completed) items
    items = conn.execute('''
        SELECT si.*, u.username as added_by_username, cu.username as completed_by_username
        FROM shopping_items si
        LEFT JOIN users u ON si.added_by = u.id
        LEFT JOIN users cu ON si.completed_by = cu.id
        WHERE si.completed = 0 OR si.completed IS NULL
        ORDER BY si.created_at DESC
    ''').fetchall()
    
    # Get completed items (last 10)
    completed_items = conn.execute('''
        SELECT si.*, u.username as added_by_username, cu.username as completed_by_username
        FROM shopping_items si
        LEFT JOIN users u ON si.added_by = u.id
        LEFT JOIN users cu ON si.completed_by = cu.id
        WHERE si.completed = 1
        ORDER BY si.completed_at DESC
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    return render_template('shopping_list.html', items=items, completed_items=completed_items)

@app.route('/add_shopping_item', methods=['POST'])
@login_required
def add_shopping_item():
    item_name = request.form['item_name'].strip()
    
    if not item_name:
        flash('Item name is required', 'error')
        return redirect(url_for('shopping_list'))
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO shopping_items (item_name, added_by)
        VALUES (?, ?)
    ''', (item_name, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Item added to shopping list!', 'success')
    return redirect(url_for('shopping_list'))

@app.route('/delete_shopping_item/<int:item_id>')
@login_required
def delete_shopping_item(item_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM shopping_items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    
    flash('Item removed from shopping list', 'success')
    return redirect(url_for('shopping_list'))

@app.route('/delete_shopping/<int:item_id>', methods=['DELETE'])
@login_required  
def delete_shopping_ajax(item_id):
    conn = get_db_connection()
    result = conn.execute('DELETE FROM shopping_items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/toggle_shopping/<int:item_id>', methods=['POST'])
@login_required
def toggle_shopping_item(item_id):
    conn = get_db_connection()
    
    # Get current item
    item = conn.execute('SELECT * FROM shopping_items WHERE id = ?', (item_id,)).fetchone()
    if not item:
        conn.close()
        return jsonify({'success': False, 'error': 'Item not found'}), 404
    
    # Toggle completed status
    new_completed = 0 if item['completed'] else 1
    completed_by = session['user_id'] if new_completed else None
    completed_at = datetime.now().isoformat() if new_completed else None
    
    conn.execute('''
        UPDATE shopping_items 
        SET completed = ?, completed_by = ?, completed_at = ?
        WHERE id = ?
    ''', (new_completed, completed_by, completed_at, item_id))
    conn.commit()
    
    # Get updated item with user information
    updated_item = conn.execute('''
        SELECT si.*, u.username as added_by_username, cu.username as completed_by_username
        FROM shopping_items si
        LEFT JOIN users u ON si.added_by = u.id
        LEFT JOIN users cu ON si.completed_by = cu.id
        WHERE si.id = ?
    ''', (item_id,)).fetchone()
    conn.close()
    
    return jsonify({
        'success': True,
        'item': {
            'id': updated_item['id'],
            'item_name': updated_item['item_name'],
            'completed': updated_item['completed'],
            'completed_at': updated_item['completed_at'],
            'created_at': updated_item['created_at'],
            'added_by_username': updated_item['added_by_username'],
            'completed_by_username': updated_item['completed_by_username']
        }
    })

# Chores Routes
@app.route('/chores')
@login_required
def chores():
    conn = get_db_connection()
    
    # Get all users for assignment dropdown
    users = conn.execute('SELECT id, username, full_name FROM users ORDER BY username').fetchall()
    
    # Get pending chores
    pending_chores = conn.execute('''
        SELECT c.*, 
               added_by_user.username as added_by_username,
               assigned_user.username as assigned_to_username
        FROM chores c
        LEFT JOIN users added_by_user ON c.added_by = added_by_user.id
        LEFT JOIN users assigned_user ON c.assigned_to = assigned_user.id
        WHERE c.completed = 0
        ORDER BY c.created_at DESC
    ''').fetchall()
    
    # Get completed chores (last 10)
    completed_chores = conn.execute('''
        SELECT c.*, 
               added_by_user.username as added_by_username,
               completed_by_user.username as completed_by_username
        FROM chores c
        LEFT JOIN users added_by_user ON c.added_by = added_by_user.id
        LEFT JOIN users completed_by_user ON c.completed_by = completed_by_user.id
        WHERE c.completed = 1
        ORDER BY c.completed_at DESC
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return render_template('chores.html', 
                         users=users,
                         pending_chores=pending_chores,
                         completed_chores=completed_chores)

@app.route('/add_chore', methods=['POST'])
@login_required
def add_chore():
    chore_name = request.form['chore_name'].strip()
    assigned_to = request.form.get('assigned_to') or None
    
    if not chore_name:
        flash('Chore name is required', 'error')
        return redirect(url_for('chores'))
    
    # Convert empty string to None for database
    if assigned_to == '':
        assigned_to = None
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO chores (chore_name, assigned_to, added_by, completed)
        VALUES (?, ?, ?, 0)
    ''', (chore_name, assigned_to, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Chore added successfully!', 'success')
    return redirect(url_for('chores'))

@app.route('/complete_chore/<int:chore_id>')
@login_required
def complete_chore(chore_id):
    conn = get_db_connection()
    conn.execute('''
        UPDATE chores 
        SET completed = 1, completed_by = ?, completed_at = CURRENT_TIMESTAMP
        WHERE id = ? AND completed = 0
    ''', (session['user_id'], chore_id))
    conn.commit()
    conn.close()
    
    flash('Chore marked as completed!', 'success')
    return redirect(url_for('chores'))

@app.route('/delete_chore/<int:chore_id>')
@login_required
def delete_chore(chore_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM chores WHERE id = ?', (chore_id,))
    conn.commit()
    conn.close()
    
    flash('Chore deleted', 'success')
    return redirect(url_for('chores'))

@app.route('/delete_chore/<int:chore_id>', methods=['DELETE'])
@login_required
def delete_chore_ajax(chore_id):
    conn = get_db_connection()
    result = conn.execute('DELETE FROM chores WHERE id = ?', (chore_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/toggle_chore/<int:chore_id>', methods=['POST'])
@login_required
def toggle_chore(chore_id):
    conn = get_db_connection()
    
    # Get current chore
    chore = conn.execute('SELECT * FROM chores WHERE id = ?', (chore_id,)).fetchone()
    if not chore:
        conn.close()
        return jsonify({'success': False, 'error': 'Chore not found'}), 404
    
    # Toggle completed status
    new_completed = 0 if chore['completed'] else 1
    completed_by = session['user_id'] if new_completed else None
    completed_at = datetime.now().isoformat() if new_completed else None
    
    conn.execute('''
        UPDATE chores 
        SET completed = ?, completed_by = ?, completed_at = ?
        WHERE id = ?
    ''', (new_completed, completed_by, completed_at, chore_id))
    conn.commit()
    
    # Get updated chore with user information
    updated_chore = conn.execute('''
        SELECT c.*, 
               added_by_user.username as added_by_username,
               assigned_user.username as assigned_to_username,
               completed_by_user.username as completed_by_username
        FROM chores c
        LEFT JOIN users added_by_user ON c.added_by = added_by_user.id
        LEFT JOIN users assigned_user ON c.assigned_to = assigned_user.id
        LEFT JOIN users completed_by_user ON c.completed_by = completed_by_user.id
        WHERE c.id = ?
    ''', (chore_id,)).fetchone()
    conn.close()
    
    return jsonify({
        'success': True,
        'chore': {
            'id': updated_chore['id'],
            'chore_name': updated_chore['chore_name'],
            'completed': updated_chore['completed'],
            'completed_at': updated_chore['completed_at'],
            'created_at': updated_chore['created_at'],
            'added_by_username': updated_chore['added_by_username'],
            'assigned_to_username': updated_chore['assigned_to_username'],
            'completed_by_username': updated_chore['completed_by_username']
        }
    })

# Expiry Tracker Routes
@app.route('/expiry')
@login_required
def expiry_tracker():
    conn = get_db_connection()
    
    # Get all expiry items, categorized by status
    all_items = conn.execute('''
        SELECT ei.*, u.username as added_by_username
        FROM expiry_items ei
        LEFT JOIN users u ON ei.added_by = u.id
        ORDER BY ei.expiry_date ASC
    ''').fetchall()
    
    today = date.today()
    expired_items = []
    expiring_soon = []
    future_items = []
    
    for item in all_items:
        expiry_date = parse_date(item['expiry_date'])
        if expiry_date:
            days_until_expiry = (expiry_date - today).days
            
            if days_until_expiry < 0:
                expired_items.append(item)
            elif days_until_expiry <= 30:
                expiring_soon.append(item)
            else:
                future_items.append(item)
    
    conn.close()
    
    # Add days_remaining to items for template display
    items_with_days = []
    for item in all_items:
        expiry_date = parse_date(item['expiry_date'])
        if expiry_date:
            days_remaining = (expiry_date - today).days
            items_with_days.append({
                **item,
                'days_remaining': days_remaining
            })
    
    # Get counts for the stats cards
    expired_count = len(expired_items)
    expiring_soon_count = len(expiring_soon)
    
    return render_template('expiry_tracker.html',
                         expired_items=expired_items,
                         expiring_soon=expiring_soon,
                         future_items=future_items,
                         items=items_with_days,
                         expired_count=expired_count,
                         expiring_soon_count=expiring_soon_count)

@app.route('/add_expiry_item', methods=['POST'])
@login_required
def add_expiry_item():
    item_name = request.form['item_name'].strip()
    expiry_date = request.form['expiry_date']
    
    if not item_name or not expiry_date:
        flash('Item name and expiry date are required', 'error')
        return redirect(url_for('expiry_tracker'))
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO expiry_items (item_name, expiry_date, added_by)
        VALUES (?, ?, ?)
    ''', (item_name, expiry_date, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Item added to expiry tracker!', 'success')
    return redirect(url_for('expiry_tracker'))

@app.route('/delete_expiry_item/<int:item_id>')
@login_required
def delete_expiry_item(item_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM expiry_items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    
    flash('Item removed from expiry tracker', 'success')
    return redirect(url_for('expiry_tracker'))

@app.route('/delete_expiry/<int:item_id>', methods=['DELETE'])
@login_required
def delete_expiry_ajax(item_id):
    conn = get_db_connection()
    result = conn.execute('DELETE FROM expiry_items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# Bills Routes
@app.route('/bills')
@login_required
def bills():
    conn = get_db_connection()
    
    bills = conn.execute('''
        SELECT b.*, u.username as added_by_username
        FROM bills b
        LEFT JOIN users u ON b.added_by = u.id
        ORDER BY b.due_day ASC
    ''').fetchall()
    
    conn.close()
    
    # Calculate days until next due date for each bill
    current_day = datetime.now().day
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    bills_with_days = []
    for bill in bills:
        due_day = bill['due_day']
        
        if due_day >= current_day:
            # Due this month
            due_date = date(current_year, current_month, due_day)
        else:
            # Due next month
            if current_month == 12:
                due_date = date(current_year + 1, 1, due_day)
            else:
                due_date = date(current_year, current_month + 1, due_day)
        
        days_until = (due_date - date.today()).days
        bills_with_days.append({
            **bill,
            'due_date': due_date,
            'days_until': days_until
        })
    
    # Calculate monthly total
    monthly_total = sum(bill['amount'] for bill in bills_with_days)
    
    return render_template('bills.html', bills=bills_with_days, monthly_total=monthly_total)

@app.route('/add_bill', methods=['POST'])
@login_required
def add_bill():
    bill_name = request.form['bill_name'].strip()
    amount = request.form['amount']
    due_day = request.form['due_day']
    
    if not bill_name or not amount or not due_day:
        flash('All fields are required', 'error')
        return redirect(url_for('bills'))
    
    try:
        amount = float(amount)
        due_day = int(due_day)
        
        if due_day < 1 or due_day > 31:
            flash('Due day must be between 1 and 31', 'error')
            return redirect(url_for('bills'))
            
    except ValueError:
        flash('Invalid amount or due day', 'error')
        return redirect(url_for('bills'))
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO bills (bill_name, amount, due_day, added_by)
        VALUES (?, ?, ?, ?)
    ''', (bill_name, amount, due_day, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Bill added successfully!', 'success')
    return redirect(url_for('bills'))

@app.route('/edit_bill', methods=['POST'])
@login_required
def edit_bill():
    bill_id = request.form.get('bill_id')
    bill_name = request.form['bill_name'].strip()
    amount = request.form['amount'].strip()
    due_day = request.form['due_day'].strip()
    
    if not bill_name or not amount or not due_day:
        flash('All fields are required', 'error')
        return redirect(url_for('bills'))
    
    try:
        amount = float(amount)
        due_day = int(due_day)
        
        if due_day < 1 or due_day > 31:
            flash('Due day must be between 1 and 31', 'error')
            return redirect(url_for('bills'))
            
    except ValueError:
        flash('Invalid amount or due day', 'error')
        return redirect(url_for('bills'))
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE bills 
        SET bill_name = ?, amount = ?, due_day = ?
        WHERE id = ?
    ''', (bill_name, amount, due_day, bill_id))
    conn.commit()
    conn.close()
    
    flash('Bill updated successfully!', 'success')
    return redirect(url_for('bills'))

@app.route('/delete_bill/<int:bill_id>')
@login_required
def delete_bill(bill_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM bills WHERE id = ?', (bill_id,))
    conn.commit()
    conn.close()
    
    flash('Bill deleted', 'success')
    return redirect(url_for('bills'))

@app.route('/delete_bill/<int:bill_id>', methods=['DELETE'])
@login_required
def delete_bill_ajax(bill_id):
    conn = get_db_connection()
    result = conn.execute('DELETE FROM bills WHERE id = ?', (bill_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
