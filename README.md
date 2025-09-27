# Homie 🏠

A simple family utility app for managing household tasks with OIDC authentication.

## Features

- 🛒 **Shopping List** - Collaborative family shopping
- 🧹 **Chores** - Track household tasks  
- 📅 **Expiry Tracker** - Monitor food expiration dates (30-day alerts)
- 💳 **Bills** - Manage monthly bills and costs
- 🔐 **OIDC Auth** - Group-based access control
- 📱 **Mobile Friendly** - Responsive design

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   Copy `.env.example` to `.env` and update:
   ```env
   FLASK_SECRET_KEY=your_secret_key
   OIDC_CLIENT_ID=your_client_id
   OIDC_CLIENT_SECRET=your_client_secret
   OIDC_ISSUER=https://your-provider.com
   OIDC_REDIRECT_URI=http://localhost:5000/auth/callback
   ALLOWED_GROUPS=family
   ```

3. **Run:**
   ```bash
   python app.py
   ```

4. **Visit:** `http://localhost:5000`

## Docker Deployment

```bash
docker-compose up -d
```

## Technology

- Flask + SQLite
- Tailwind CSS
- OIDC Authentication
- Group-based access control

---

Made for family life! 🏠