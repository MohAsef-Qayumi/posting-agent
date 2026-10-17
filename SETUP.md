# Setup guide

Do these once, in order. Total time: about 1–1.5 hours. Each step ends with the values you need to save — keep them in a notepad until step 7.

> 🔒 Every token below is a password to your accounts. Never share it, never post it, never commit it to git. They only go in your local `.env` file (which git ignores) and in GitHub Secrets.

---

## 1. Facebook Page + Instagram (10 min)

1. Create the Page: **facebook.com/pages/create** → name (e.g. *Asef Qayumi – Dev & Tech*), category *Software Company* or *Digital Creator* → add your photo and cover.
2. Instagram app → **Settings → Account type and tools → Switch to professional account → Creator** → category *Software Developer* (or similar).
3. Link them: on the Facebook Page → **Settings → Linked accounts → Instagram → Connect** → log in to Instagram.

## 2. Telegram approval bot (5 min)

1. In Telegram open **@BotFather** → send `/newbot` → pick a name and a username ending in `bot`.
2. Copy the token it gives you → **`TELEGRAM_BOT_TOKEN`**.
3. Open your new bot and send it `hi`.
4. In this folder run:
   ```
   python tools/telegram_chat_id.py <TELEGRAM_BOT_TOKEN>
   ```
   → **`TELEGRAM_CHAT_ID`**. (The bot only obeys this chat id, so nobody else can approve posts.)

## 3. Claude API key (5 min)

1. Go to **console.anthropic.com** → sign up → **Billing** → add ~$5 credit (lasts months; daily posts cost roughly $1–3/month).
2. **API keys → Create key** → **`ANTHROPIC_API_KEY`**.

## 4. Meta developer app — Facebook + Instagram (20–30 min)

1. Go to **developers.facebook.com** → log in with your Facebook account → **My Apps → Create app**.
2. Choose the use cases **"Manage everything on your Page"** and **"Manage messaging & content on Instagram"** (Meta renames these occasionally — pick the Page + Instagram publishing ones). App type: **Business**.
3. In **App settings → Basic**: copy **App ID** and **App Secret**. Also fill *Privacy Policy URL* (any public page works, e.g. a short Google Doc or Notion page that says what the app does), pick a category and an icon → Save.
4. Set the app to **Live / Published** (toggle at the top). Posts made by an app in development mode may only be visible to you.
   You don't need App Review — the app only posts to your own Page, and you're its admin.
5. Open **developers.facebook.com/tools/explorer** (Graph API Explorer):
   - *Meta App*: your app · *User or Page*: **Get User Access Token**
   - Add these permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`, `business_management`
   - Click **Generate Access Token** → in the popup, **select your new Page and your Instagram account** → allow.
   - Copy the token (it expires in ~1 hour, so do the next step right away).
6. Run:
   ```
   python tools/meta_tokens.py <APP_ID> <APP_SECRET> <TOKEN_FROM_EXPLORER>
   ```
   → **`FB_PAGE_ID`**, **`FB_PAGE_ACCESS_TOKEN`** (it should say *expires: never ✨*), **`IG_USER_ID`**.

## 5. LinkedIn developer app (15 min)

1. LinkedIn requires every app to belong to a LinkedIn **Company Page**. If you don't have one, create a free one for your startup: **linkedin.com/company/setup/new**.
2. Go to **linkedin.com/developers/apps → Create app** → name, your company page, logo → create.
3. **Products** tab → request **"Share on LinkedIn"** and **"Sign In with LinkedIn using OpenID Connect"** (both are approved instantly).
4. **Auth** tab → copy **Client ID** and **Client Secret** → under *Authorized redirect URLs* add:
   ```
   http://localhost:8765/callback
   ```
5. Run (your browser opens, click **Allow**):
   ```
   python tools/linkedin_auth.py <CLIENT_ID> <CLIENT_SECRET>
   ```
   → **`LINKEDIN_ACCESS_TOKEN`**, **`LINKEDIN_PERSON_URN`**, **`LINKEDIN_TOKEN_EXPIRES`**.

   ⏰ LinkedIn tokens last **60 days**. The Telegram bot warns you a week before; just re-run this command and update the two secrets.

## 6. Test on your PC (10 min)

```
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env        # then paste all your values into .env
python main.py check          # every line should be ✅
python main.py preview        # writes a real post + renders slides into preview/ (nothing is published)
```

Open the `preview/…` folder to see the slides. Want a different style or tone? Edit `config.yaml` (voice, rotation, feeds) or `agent/templates/carousel.html` (design).

## 7. Put it on GitHub Actions (15 min)

1. Create a **private** repository on github.com (e.g. `posting-agent`). Private keeps your drafts and history to yourself; the free plan includes 2,000 Actions minutes/month and this uses about 1,200.
2. Push this folder:
   ```
   git init
   git add .
   git commit -m "Posting agent"
   git branch -M main
   git remote add origin https://github.com/<your-username>/posting-agent.git
   git push -u origin main
   ```
3. Repo → **Settings → Secrets and variables → Actions → New repository secret** — add each one:

   | Secret | From step |
   |---|---|
   | `ANTHROPIC_API_KEY` | 3 |
   | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | 2 |
   | `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`, `IG_USER_ID` | 4 |
   | `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_PERSON_URN`, `LINKEDIN_TOKEN_EXPIRES` | 5 |

4. Repo → **Settings → Actions → General → Workflow permissions** → **Read and write permissions** → Save. (The agent saves its drafts/history back to the repo.)
5. First run: **Actions** tab → **Generate daily draft → Run workflow**. Within ~3 minutes the draft arrives in Telegram.
6. Tap **✅ Approve & post**, then **Actions → Process approvals → Run workflow** (or wait — it runs every 30 min automatically). You'll get a Telegram message with links to the live posts. 🎉

From now on it runs by itself: a draft every day at **08:00 Herat time**, published within 30 minutes of your approval.

---

## Daily use

| In Telegram | What happens |
|---|---|
| ✅ Approve & post | Publishes to LinkedIn, Facebook and Instagram |
| 🔁 Regenerate | Writes a different post (new topic) and sends it in a few minutes |
| ❌ Skip | Nothing is posted today |
| `/new` or `/new AI` | Creates an extra draft now (optionally on a pillar) |
| `/status` | Lists recent drafts |

Drafts you don't answer expire after 2 days.

## Troubleshooting

- **Something failed?** The bot sends you the error. Full logs: GitHub → **Actions** → the failed run.
- **One platform failed, others posted** → tap **🔁 Retry failed**; only the failed one is retried.
- **LinkedIn 401** → token expired, redo step 5 and update the secrets.
- **LinkedIn "version" error** → bump `api_versions.linkedin` in `config.yaml` to a recent month (format `YYYYMM`).
- **Meta "permission" errors** → redo step 4.5–4.6 and make sure the Page **and** Instagram account were ticked in the popup.
- **Turn a platform off** → set it to `false` under `platforms:` in `config.yaml`.
