# make_a_ton
 ## User Authentication Module

Secure signup, login and logout for the Subscription Management System. Every page of the site is locked until the user is logged in.

### Features

- Signup with name, email and password
- Strict password rules: at least 8 characters, one uppercase letter, one lowercase letter and one special character
- Live password checklist on the signup page, with the same rules checked again on the server
- Login with an optional "Keep me logged in" box
- Logout button in the navigation bar
- All pages except signup and login redirect to the login page when the user is not logged in
- Duplicate emails are blocked, and emails are stored in lowercase

### Routes

| Route | Method | Purpose |
|---|---|---|
| `/signup` | GET, POST | Create an account |
| `/login` | GET, POST | Log in |
| `/logout` | POST | Log out |

### Security

- Passwords are never stored in plain text. Only a salted hash is saved (Werkzeug).
- Every form carries a CSRF token, and the server rejects forms without a valid one.
- After login, redirects are limited to pages inside this site, which blocks open-redirect attacks.
- Login errors use one generic message, so attackers cannot tell whether an email exists.

### Files

| File | What it does |
|---|---|
| `auth.py` | Signup, login and logout routes |
| `models_auth.py` | `User` table and the password rules |
| `extensions.py` | Shared database and login manager |
| `templates/auth_base.html` | Layout for the login and signup pages |
| `templates/login.html`, `templates/signup.html` | The login and signup pages |
| `static/auth.css` | Styling for the auth pages |

### Tech stack

Python, Flask, Flask-Login, Flask-SQLAlchemy, SQLite, Bootstrap 5.

### How to run

Requires Python 3.10 or newer.

```
git clone https://github.com/semafathima/make_a_ton.git
cd make_a_ton
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 and click **Sign up** to create an account. The database file is created automatically in the `instance` folder.

### Known limitations and next steps

- Email verification and "forgot password" are not built yet
- No limit on failed login attempts yet
- The `role` field (customer / admin) exists but is not enforced yet
- The subscription pages and the billing dashboard use separate data, so linking them is planned
- Set a real `SECRET_KEY` environment variable before any real deployment
