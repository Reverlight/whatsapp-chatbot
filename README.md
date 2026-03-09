# 📬 Maildesk — AI-Powered Customer Support Email Client

Maildesk is a full-stack customer support tool that syncs your Gmail inbox, groups emails into conversation threads, and uses AI to help you analyze and act on customer requests — with direct Shopify integration for order lookups, customer details, and refunds.

---

## ✨ Features

- **Gmail sync** — fetches threads from your inbox including your own sent replies
- **Thread view** — groups messages into conversations, sorted newest first, with chat-style bubbles
- **Reply** — send replies directly from the UI, threaded into the original Gmail conversation
- **AI Assistant** — powered by OpenAI GPT-4o-mini:
  - Summarize a thread in 3–5 sentences
  - Detect relevant Shopify actions (fetch order, fetch customer, refund)
  - Extracts order IDs and emails automatically from the thread content
- **Shopify actions** — clickable action buttons with pre-filled parameters and a confirmation popup before executing
- **HTML email parsing** — strips HTML, tracking URLs, and noise from marketing emails for clean readable text

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Next.js Frontend                   │
│         (React, Node.js, port 3000)                  │
└───────────────────┬─────────────────────────────────┘
                    │ HTTP (rewrites proxy)
┌───────────────────▼─────────────────────────────────┐
│                  FastAPI Backend                      │
│                  (Python, port 8000)                  │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ EmailClient │  │ OpenAIClient │  │ShopifyClient│  │
│  │  (Gmail API)│  │  (GPT-4o-mini│  │ (GraphQL)  │  │
│  └─────────────┘  └──────────────┘  └────────────┘  │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│               PostgreSQL Database                     │
└─────────────────────────────────────────────────────┘
```

---


## 📸 Screenshots

### Inbox & Thread View
![Inbox and thread view](https://raw.githubusercontent.com/Reverlight/email-assistant/main/screenshots/screenshot1.png)

### AI Summary & Action Detection
![AI summary and action detection](https://raw.githubusercontent.com/Reverlight/email-assistant/main/screenshots/screenshot2.png)

### Shopify Action Popup
![Shopify action confirmation popup](https://raw.githubusercontent.com/Reverlight/email-assistant/main/screenshots/screenshot3.png)

### Reply in Thread
![Replying in a thread](https://raw.githubusercontent.com/Reverlight/email-assistant/main/screenshots/screenshot4.png)

## 🚀 Getting Started

### Prerequisites

- Docker & Docker Compose
- A Google Cloud project with Gmail API enabled
- A Shopify store with API access
- An OpenAI API key

### 1. Clone the repo

```bash
git clone https://github.com/Reverlight/email-assistant
cd maildesk
```

### 2. Configure environment

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

```env
# PostgreSQL
POSTGRES_DB=maildesk
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourpassword
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@db:5432/maildesk

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_PROJECT_ID=your_google_project_id

# OpenAI
OPENAI_API_KEY=sk-...

# Shopify
SHOPIFY_SHOP_ID=your-shop
SHOPIFY_CLIENT_ID=your_shopify_client_id
SHOPIFY_CLIENT_SECRET=your_shopify_client_secret

# PgAdmin
PGADMIN_DEFAULT_EMAIL=admin@admin.com
PGADMIN_DEFAULT_PASSWORD=admin
```

### 3. Generate a Gmail token

Run this locally (not in Docker) to authorize Gmail access:

```bash
pip install google-auth-oauthlib python-dotenv
python generate_token.py
```

A browser window will open. Log in with Google and authorize. A `token.json` file will be saved — place it in the project root.

> **Required Gmail scopes:**
> - `https://www.googleapis.com/auth/gmail.readonly`
> - `https://www.googleapis.com/auth/gmail.send`

### 4. Start the stack

```bash
make start-dev
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/docs |
| PgAdmin | http://localhost:8090 |

### 5. Run database migrations

```bash
docker compose run web alembic upgrade head
```

### 6. Run tests

```bash
make start-test
```

