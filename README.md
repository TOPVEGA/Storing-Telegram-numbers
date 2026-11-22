📱 Storing Telegram Numbers

<div align="center">A Telegram Bot Project for Managing Numbers, Users, Wallets, and Transactions

"Python" · "Pyrogram/Kurigram" · "PostgreSQL" · "Redis" · "Flask"

</div>---

📌 About the Project

Storing Telegram Numbers is a Telegram bot project written in Python. It includes a user interface and an administration panel, with features for managing number records, wallets, statistics, transactions, referrals, and rewards.

This document describes the components and functions available in the project files. Documenting a feature does not mean that its use is legal or safe in all circumstances. You must comply with Telegram's Terms of Service, applicable local laws, and obtain explicit consent from account and data owners.

✨ Features

👤 User Interface

- Main menu for accessing bot sections.
- View wallet and balance information.
- View user statistics.
- Transaction history.
- Search and custom requests.
- Referral and daily reward system.
- Support and contact section.
- Subscription channel display.

💳 Wallet and Transactions

- Recording balance movements and transactions.
- Statistics related to user activity.
- Support for deposits and balance management according to the project's logic.
- Generation of transaction IDs.

📊 Admin Panel

- Display bot statistics and reports.
- View user information.
- Manage administrator permissions.
- Manage bans and unbans.
- Manage subscription channels.
- Send broadcast messages.
- Manage balances and review transactions.
- Daily and general reports, country statistics, and seller statistics.

🗄️ Data Management

- PostgreSQL database using "asyncpg".
- Redis caching when configured.
- Functions for recording events and transactions.
- Encryption and decryption functions in the database layer.

🌐 Web Interface

The project includes a Flask application with routes for the dashboard, status checks, and certain statistics, such as the number of users, top sellers, and countries.

🧱 Project Structure

Storing-Telegram-numbers/
│
├── main.py              # Bot entry point, Flask routes, and background tasks
├── config.py            # Project configuration
├── Database.py          # Database operations and encryption
├── requirements.txt     # Required Python libraries
├── README.md            # Project documentation
├── photo.jpg            # Image used within the project
│
└── shop/
    ├── Admin.py         # Administration and administrator functions
    ├── Botpay.py        # Wallet, purchases, statistics, and history
    ├── callbacks.py     # Interactive button handlers
    ├── inform.py        # Country codes and default prices
    └── play.py          # Pyrogram interaction logic

🛠️ Technologies Used

Technology| Usage
Python| Main programming language
Pyrogram / Kurigram| Telegram API interaction
PostgreSQL| Data storage
asyncpg| Asynchronous database connection
Redis| Caching
Flask| Web interface and statistics endpoints
Cryptography| Encryption functions
python-dotenv| Environment configuration management
TgCrypto| Support for encryption operations used with the Telegram library

⚙️ Configuration

Project settings are read from environment variables. According to "config.py", these include Telegram connection credentials, owner ID, database connection details, encryption key, Redis settings, web interface settings, and subscription channels.

Important Security Notice Before Running or Deploying:

- Never place "BOT_TOKEN", "API_HASH", passwords, or encryption keys inside a public repository.
- Review "config.py"; the current file contains sensitive default values and a shared password configuration. Remove insecure default values, generate strong independent secrets, and never use a shared password across accounts.
- Never upload session files, databases, login logs, or verification codes to GitHub.
- Do not store or transfer login codes or two-step verification passwords except through a trusted and authorized process, with the account owner's explicit consent.
- Do not use this project to take control of other people's accounts, trade account access, or bypass Telegram security.
- Before making any web dashboard publicly accessible, review authentication, permissions, and route protection against unauthorized access.

🔐 Privacy and Responsible Use

The project may handle phone numbers, account information, transactions, and sensitive verification information. Therefore, you should:

1. Collect only the minimum necessary data with the owners' consent.
2. Clearly explain the purpose of data collection and the retention period.
3. Restrict data access according to clearly defined permissions.
4. Protect backups, operational logs, and encryption keys.
5. Provide a mechanism for deleting data when it is no longer needed or when requested by its owner, where applicable.
6. Review Telegram's Terms of Service and applicable laws before using any account-related functionality.

⚠️ Notes About the Current Version

This documentation is based on the files included in the archive. It does not include a complete operational audit or testing of every route and function. Therefore, it does not guarantee that the project is free of bugs or vulnerabilities. The presence of a function in the code does not prove that it works successfully in the actual runtime environment.

📄 Copyright and Licensing

Please preserve the copyright and licensing notices included in the project files. Consult the project owner before redistribution, modification, or commercial use. This document does not grant permission to use trademarks, content, or data belonging to third parties.

---

<div align="center">Storing Telegram Numbers

<!-- ═══════════════════════════════════════════════════════════════════════ --><!--                       Copyright | Footer                              --><!-- ═══════════════════════════════════════════════════════════════════════ --><div align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=0:3B82F6,100:0F172A&height=4&width=40%&section=header" />
  <br><br>  <p style="color: #9CA3AF; font-size: 14px;">
    <b style="color: #3B82F6;">Brand:</b> VEGA &amp; Logic &nbsp;|&nbsp;
    <b style="color: #3B82F6;">Copyright:</b> © 2015 - 2025
  </p>
  <p style="color: #6B7280; font-size: 12px;">
  </p>
</div><br><!-- Smooth Gradient Footer Background --><img src="https://capsule-render.vercel.app/api?type=waving&color=0:3B82F6,50:1E3A8A,100:0F172A&height=120&section=footer" width="100%" /></div>
