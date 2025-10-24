# auth.py
from functools import wraps
from flask import redirect, url_for, request, session

def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if 'username' not in session:
            return redirect(url_for('login', next=request.path))
        return f(*a, **kw)
    return wrap

def authenticate_user(username, password):
    # Import inside function to avoid circular import
    from database import get_user_by_username
    from werkzeug.security import check_password_hash
    
    user = get_user_by_username(username)
    if user and check_password_hash(user['password_hash'], password):
        return user
    return None