# Homie - Family Utility App

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