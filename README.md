# Homie - Family Utility App 🏠

A simple, clean family utility app with OIDC authentication for managing household tasks, shopping lists, expiry tracking, and bills.

## Features

- **🛒 Shopping List** - Collaborative shopping list for the family
- **🧹 Chores** - Assign and track household chores
- **📅 Expiry Tracker** - Keep track of food expiration dates
- **💳 Bills** - Monitor recurring bills and due dates
- **🔐 OIDC Authentication** - Secure single sign-on authentication
- **📱 Mobile Friendly** - Responsive design that works on all devices
- **🌙 Dark Mode** - Automatic dark/light theme support

## Quick Setup

### 1. Prerequisites

- Python 3.7+
- OIDC Provider (PocketID, Auth0, etc.)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and configure:

```env
# Flask Configuration
FLASK_SECRET_KEY=your_secret_key_here

# OIDC Configuration
OIDC_CLIENT_ID=your_client_id
OIDC_CLIENT_SECRET=your_client_secret
OIDC_ISSUER=https://auth.camc.xyz
OIDC_REDIRECT_URI=http://localhost:5000/auth/callback

# OIDC Endpoints (PocketID example)
OIDC_AUTHORIZATION_ENDPOINT=https://auth.camc.xyz/authorize
OIDC_TOKEN_ENDPOINT=https://auth.camc.xyz/api/oidc/token
OIDC_USERINFO_ENDPOINT=https://auth.camc.xyz/api/oidc/userinfo
OIDC_END_SESSION_ENDPOINT=https://auth.camc.xyz/api/oidc/end-session

# Access Control
ALLOWED_EMAILS=user1@example.com,user2@example.com
ADMIN_EMAILS=admin@example.com
```

### 4. Run the Application

```bash
python app.py
```

Visit `http://localhost:5000` and sign in with your OIDC provider!

## Access Control

Control who can access your Homie instance:

- **`ALLOWED_EMAILS`** - Comma-separated list of allowed email addresses (leave empty to allow all)
- **`ALLOWED_GROUPS`** - Comma-separated list of allowed OIDC groups (if supported by provider)
- **`ADMIN_EMAILS`** - Comma-separated list of admin users (currently informational)

## OIDC Provider Setup

### PocketID Example

1. Create a new application in PocketID
2. Set **Redirect URIs**: `http://localhost:5000/auth/callback`
3. Set **Grant Types**: Authorization Code
4. Set **Response Types**: Code
5. Set **Scopes**: openid, profile, email

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: SQLite
- **Frontend**: Tailwind CSS, Font Awesome
- **Authentication**: OIDC/OAuth 2.0

## Contributing

This is a simple family utility app. Feel free to fork and customize for your own needs!

## License

MIT License - see LICENSE file for details. - Family Utility App

Homie is a beautiful family utility web application built with Flask and Tailwind CSS. It helps families manage their household together with shared shopping lists, chore tracking, expiry monitoring, and bill management.

## Features

🛒 **Shopping List** - Collaborative shopping list where family members can add items and check them off
🧽 **Chore Tracker** - Assign and track household chores with completion status
📅 **Expiry Tracker** - Monitor food expiration dates with visual calendar and alerts
💰 **Bills Manager** - Track monthly bills with due dates and cost calculations

## Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application:**
   ```bash
   python app.py
   ```

3. **Open your browser and go to:**
   ```
   http://localhost:5000
   ```

4. **Create your first account** using the registration form.

## Key Features

### 🎨 Beautiful UI
- Dark and light theme toggle
- Responsive design that works on all devices
- Modern interface with Tailwind CSS
- Icon-rich interface using Font Awesome

### 👥 User Management
- Local user registration and authentication
- Session-based login system
- Ready for future OIDC integration

### 📱 Mobile Friendly
- Fully responsive design
- Touch-friendly interface
- Works great on phones and tablets

### 🏠 Family Focused
- Multi-user collaboration
- See who added what and when
- Assign tasks to specific family members

## Technology Stack

- **Backend:** Flask (Python)
- **Database:** SQLite
- **Frontend:** HTML5, Tailwind CSS, JavaScript
- **Icons:** Font Awesome
- **Authentication:** Session-based (ready for OIDC)

## Database

The app uses SQLite for simplicity. The database is automatically created when you first run the application with all necessary tables:

- `users` - User accounts
- `shopping_items` - Shopping list items
- `chores` - Household chores
- `expiry_items` - Items with expiration dates
- `bills` - Monthly bills and costs

## Future Enhancements

- OIDC authentication integration
- Email notifications for expiring items
- Recurring chore scheduling
- Bill payment tracking
- Mobile app companion
- Shopping list categories
- Photo attachments for items

## Contributing

This is a personal family utility app, but feel free to fork and customize for your own needs!

## License

MIT License - Feel free to use and modify as needed.

---

Made with ❤️ for family life management