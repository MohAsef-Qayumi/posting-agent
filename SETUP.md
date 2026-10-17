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

## 3. AI writer key (5 min)

You need **one** of these. Start free, and switch to Claude later by just adding its key — the agent automatically uses the best key it finds (Claude → Gemini → OpenRouter).

| Option | Cost | Get the key | Secret name |
|---|---|---|---|
| **Google Gemini** | Free tier | aistudio.google.com → *Get API key* | `GEMINI_API_KEY` |
| **OpenRouter** | Free models | openrouter.ai → *Keys* | `OPENROUTER_API_KEY` |
| **Claude** (best quality) | ~$1–3/month | console.anthropic.com → Billing (add ~$5) → *API keys* | `ANTHROPIC_API_KEY` |

Tip: start with Gemini and keep an OpenRouter key as backup — if Gemini hits a free limit, delete its secret and OpenRouter takes over.

## 4. Meta developer app — Facebook + Instagram (20–30 min)

1. Go to **developers.facebook.com** → log in with your Facebook account → **My Apps → Create app**.
2. Choose the use cases **"Manage everything on your Page"** and **"Manage messaging & content on Instagram"** (Meta renames these occasionally — pick the Page + Instagram publishing ones). App type: **Business**.
3. In **App settings → Basic**: copy **App ID** and **App Secret**. Also fill *Privacy Policy URL* (any public page works, e.g. a short Google Doc or Notion page that says what the app does), pick a category and an icon → Save.
4. If the wizard shows **"Publishing requirements"** (Business verification + App Review) → just click **Next** and finish creating the app.
   You don't need either one — they're only for apps that access *other people's* accounts. Your app only posts to your own Page and Instagram, and as the app's admin you already have access.
   Leave the app in **Development** mode for now. After your first real post, open your Page in a private/logged-out window: if the post is visible, you're done; if not, switch the app to **Live** (toggle at the top of the app dashboard).
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

1. Create a **private** repository on github.com (e.g. `posting-agent`). Private keeps your drafts and history to yourself; the free plan includes 2,000 Actions minutes/month and this uses under 1,000.
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
   | `GEMINI_API_KEY` / `OPENROUTER_API_KEY` / `ANTHROPIC_API_KEY` (whichever you have) | 3 |
   | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | 2 |
   | `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`, `IG_USER_ID` | 4 |
   | `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_PERSON_URN`, `LINKEDIN_TOKEN_EXPIRES` | 5 |
   | `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN`, `THREADS_TOKEN_EXPIRES` | 8 |
   | `GH_PAT`, `WORKER_URL`, `WORKER_SECRET` (instant mode) | 9 |

4. Repo → **Settings → Actions → General → Workflow permissions** → **Read and write permissions** → Save. (The agent saves its drafts/history back to the repo.)
5. First run: **Actions** tab → **Generate daily draft → Run workflow**. Within ~3 minutes the draft arrives in Telegram.
6. Tap **✅ Approve & post**, then **Actions → Process approvals → Run workflow** (or wait — it runs every hour automatically, or instantly once step 9 is done). You'll get a Telegram message with links to the live posts. 🎉

From now on it runs by itself: a draft every day at **08:00 Pakistan time**.

## 8. Threads (15 min)

Threads uses its own Meta app (Meta keeps the Threads API separate from the Page/Instagram one).

1. **developers.facebook.com → My Apps → Create app** → use case **"Access the Threads API"** → name it (e.g. *posting-agent-threads*) → create.
2. **Use cases → Access the Threads API → Customize**:
   - *Permissions*: add **`threads_content_publish`** (`threads_basic` is already there).
   - *Settings*: in **Redirect Callback URLs**, **Uninstall Callback URL** and **Delete Callback URL**, enter:
     ```
     https://localhost:8765/callback
     ```
     → Save.
3. **App roles → Roles → Add People → Threads Tester** → your Threads username.
   Then in the **Threads app** (phone): **Settings → Account → Website permissions → Invites → Accept**.
4. **App settings → Basic** → copy the **Threads app ID** and **Threads app secret** (not the normal App ID).
5. Run:
   ```
   python tools/threads_auth.py <THREADS_APP_ID> <THREADS_APP_SECRET>
   ```
   Your browser opens → **Allow** → the page then shows *"can't reach this page"* — that's expected. Copy the **whole address** from the address bar and paste it into the terminal.
   → **`THREADS_USER_ID`**, **`THREADS_ACCESS_TOKEN`**, **`THREADS_TOKEN_EXPIRES`** → add to `.env` and GitHub Secrets.

   ⏰ The token lasts 60 days, but with **`GH_PAT`** from step 9 the agent renews it every week by itself. Without it, the bot reminds you a week before it expires.

## 9. Instant mode — Cloudflare worker (20 min, free)

Without this, your taps and messages wait for the hourly run. With it, the bot reacts instantly and posts go live about a minute after you tap ✅.

**a) A random secret** — run:
```
python tools/telegram_webhook.py secret
```
→ **`WORKER_SECRET`**. Add it to `.env`.

**b) A GitHub token** so the worker can start your workflows: **github.com/settings/personal-access-tokens/new** (fine-grained)
- *Token name*: posting-agent · *Expiration*: the longest allowed
- *Repository access*: **Only select repositories → posting-agent**
- *Permissions → Repository*: **Actions: Read and write**, **Secrets: Read and write**
- Generate → copy → **`GH_PAT`** (add it as a GitHub secret too — that's what renews the Threads token).

**c) The worker** — sign up free at **dash.cloudflare.com**, then:
1. **Storage & databases → Workers KV → Create** → name `posting-agent-queue`.
2. **Compute → Workers & Pages → Create → Start with Hello World** → name `posting-agent` → **Deploy**.
3. **Edit code** → delete everything → paste the contents of `worker/worker.js` → **Deploy**.
4. Worker → **Settings → Bindings → Add → KV namespace** → variable name **`QUEUE`** → pick `posting-agent-queue` → Save.
5. Worker → **Settings → Variables and Secrets → Add**:

   | Type | Name | Value |
   |---|---|---|
   | Text | `GH_REPO` | `<your-username>/posting-agent` |
   | Secret | `TELEGRAM_BOT_TOKEN` | same as in `.env` |
   | Secret | `TELEGRAM_CHAT_ID` | same as in `.env` |
   | Secret | `WORKER_SECRET` | from a) |
   | Secret | `GH_PAT` | from b) |

6. Copy the worker's address (e.g. `https://posting-agent.<you>.workers.dev`) → **`WORKER_URL`**. Add it to `.env`.

**d) Connect everything**
1. GitHub secrets: add **`WORKER_URL`**, **`WORKER_SECRET`**, **`GH_PAT`**.
2. Turn it on:
   ```
   python tools/telegram_webhook.py on <WORKER_URL>
   ```
3. `python main.py check` → *Instant mode: worker connected* ✅. Send `/help` to your bot — you'll see 👀 on your message right away and the answer about a minute later.

To go back to hourly mode: `python tools/telegram_webhook.py off` and delete the `WORKER_URL` secret.

---

## Daily use

| In Telegram | What happens |
|---|---|
| ✅ Post · FB English / فارسی / پښتو | Publishes to LinkedIn, Facebook, Instagram and Threads — Facebook in the language you tapped (all three versions are in the preview; the other platforms stay English) |
| 🔁 Regenerate | Writes a different post (new topic) and sends it in a few minutes |
| ❌ Skip | Nothing is posted today |
| 🌐 Write FB in … | Only appears if a translation failed — tries that language again |
| Any idea, e.g. `Freelancers should always sign contracts` | Writes a draft about your idea. Start with a pillar to set the theme: `Career freelancers should…` |
| `/new` or `/new AI` | Creates an extra draft now (optionally on a pillar) |
| `/status` | Lists recent drafts |

Drafts you don't answer expire after 2 days.

## Troubleshooting

- **Something failed?** The bot sends you the error. Full logs: GitHub → **Actions** → the failed run.
- **One platform failed, others posted** → tap **🔁 Retry failed**; only the failed one is retried.
- **LinkedIn 401** → token expired, redo step 5 and update the secrets.
- **Threads errors** → check you accepted the tester invite (step 8.3); token expired → redo step 8.5.
- **Taps not answered instantly** → `python tools/telegram_webhook.py info` shows the last error; `python main.py check` tests the worker.
- **LinkedIn "version" error** → bump `api_versions.linkedin` in `config.yaml` to a recent month (format `YYYYMM`).
- **Meta "permission" errors** → redo step 4.5–4.6 and make sure the Page **and** Instagram account were ticked in the popup.
- **Turn a platform off** → set it to `false` under `platforms:` in `config.yaml`.
