# 📱 Storing Telegram Numbers

<div align="center">

**A Telegram bot project for managing number listings, users, balances, and transactions.**

`Python` · `Kurigram / Pyrogram` · `PostgreSQL` · `Redis` · `Flask`

</div>

---

## 📌 About the Project

**Storing Telegram Numbers** is a Telegram bot project built with Python. It includes user-facing bot features, administrative tools, database management, and a small Flask web dashboard.

The codebase includes functionality for managing number listings, user balances, transactions, reservations, reviews, referrals, support tickets, and administrative operations.

> This README describes functionality found in the supplied source files. It does not certify that every feature has been tested or is safe for production use.

## ✨ Features

### 👤 User Features
- Main menu and interactive bot keyboards.
- View wallet balance and account statistics.
- View transaction history.
- Browse available listings by country.
- View listing details and submit ratings.
- Create and manage purchase-related requests.
- Referral tracking and rewards.
- Daily bonus-related settings.
- Support ticket and communication functionality.
- Subscription-channel checks.

### 💳 Wallet and Transactions
- User balance tracking.
- Transaction records with unique transaction identifiers.
- Deposit records and status tracking.
- Purchase and reservation-related records.
- Ratings and reviews associated with transactions/listings.
- Coupon records and usage tracking.

### 🛠️ Administration
- Admin and staff permission checks.
- User information lookup.
- Ban and unban controls.
- Balance adjustment tools.
- Admin management.
- Subscription-channel management.
- Broadcast messaging options.
- Daily and general reports.
- Top-seller and country statistics.
- Listing-management and maintenance controls.

### 📊 Web Dashboard and API
The project includes a Flask application with routes for:
- Main dashboard.
- Application health status.
- Database health status.
- General statistics.
- User count.
- Top sellers.
- Top countries.

### 🗄️ Database and Background Tasks
- PostgreSQL database integration through `asyncpg`.
- Database tables created by the application.
- Optional Redis cache integration.
- Audit-log functionality.
- Request rate-limiting helper.
- Background cleanup tasks for expired reservations and stale listings.
- Automatic refund scheduler.
- Graceful shutdown handling.

## 🧱 Project Structure

```text
Storing-Telegram-numbers/
│
├── main.py              # Application entry point, Flask routes, and background tasks
├── config.py            # Project configuration
├── Database.py          # Database access, data models, and encryption helpers
├── requirements.txt     # Python dependencies
├── README.md            # Project documentation
├── photo.jpg            # Project image asset
│
└── shop/
    ├── Admin.py         # Admin commands and management tools
    ├── Botpay.py        # Wallet, statistics, history, and purchase handlers
    ├── callbacks.py     # Inline button and callback handlers
    ├── inform.py        # Country detection and default pricing helpers
    └── play.py          # Main bot interactions and account-related logic
```

## 🛠️ Technologies

| Technology | Purpose |
|---|---|
| Python | Main programming language |
| Kurigram / Pyrogram | Telegram client and bot interaction |
| PostgreSQL | Persistent data storage |
| asyncpg | Asynchronous PostgreSQL driver |
| Redis | Optional caching |
| Flask | Web dashboard and statistics endpoints |
| Cryptography (Fernet) | Encryption helper functions |
| python-dotenv | Environment configuration support |
| TgCrypto | Cryptographic support for Telegram libraries |
| aiohttp | Asynchronous HTTP client/server utilities |

## ⚙️ Configuration

The application settings are defined in `config.py`. They include Telegram connection settings, owner/admin configuration, database connection details, encryption settings, Redis configuration, and application limits.

Before running or deploying the project:

- Keep bot tokens, API credentials, database passwords, and encryption keys out of source control.
- Replace insecure defaults and use unique, strong secrets.
- Store secrets in environment variables or a protected configuration system.
- Do not publish Telegram session files, authentication codes, database dumps, or private user information.
- Restrict access to the dashboard and administrative endpoints.
- Use separate credentials for development and production.

## 🔐 Security and Privacy

This project may process phone numbers, Telegram session-related information, account metadata, and transaction records. Such information must be handled carefully.

- Use the project only with explicit authorization from the account and data owners.
- Never collect or use another person's login codes, passwords, or session credentials without their informed consent.
- Do not use the software to gain unauthorized access to accounts or bypass Telegram security.
- Collect only the information required for a clearly explained purpose.
- Apply strict access controls and protect database backups and encryption keys.
- Define a retention policy and delete data when it is no longer needed.
- Review Telegram's terms and all applicable laws before deployment.

**Important:** The source includes account-session and two-step-verification-related routines. These areas require a thorough security review before any use. Avoid storing shared or hard-coded verification passwords; each account owner must remain in control of their own credentials and security settings.

## ⚠️ Project Status and Limitations

This documentation is based on inspection of the files included in the supplied archive. It is not a complete runtime test, security audit, or guarantee that every route and feature works in a production environment.

Dependencies, Telegram API behavior, database availability, and configuration values can affect runtime behavior. Review and test the project in a controlled environment before deployment.

## 📄 License and Credits

Please retain the copyright and license notices present in the source files. Obtain permission from the relevant rights holders before redistributing, modifying, or using the project commercially.

---

<div align="center">

**Storing Telegram Numbers**

<!-- ═══════════════════════════════════════════════════════════════════════ --><!--                       Copyright | Footer                              --><!-- ═══════════════════════════════════════════════════════════════════════ --><div align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=0:3B82F6,100:0F172A&height=4&width=40%&section=header" />
  <br><br>  <p style="color: #9CA3AF; font-size: 14px;">
    <b style="color: #3B82F6;">Brand:</b> VEGA &amp; Logic &nbsp;|&nbsp;
    <b style="color: #3B82F6;">Copyright:</b> © 2015 - 2025
  </p>
  <p style="color: #6B7280; font-size: 12px;">
  </p>
</div><br><!-- Smooth Gradient Footer Background --><img src="https://capsule-render.vercel.app/api?type=waving&color=0:3B82F6,50:1E3A8A,100:0F172A&height=120&section=footer" width="100%" /></div>