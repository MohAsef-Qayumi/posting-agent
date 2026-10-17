// Posting agent — instant Telegram mode (Cloudflare Worker, free plan).
//
// Telegram sends every tap/message here the moment it happens. The worker:
//   1. answers the tap right away (no more endless loading spinner),
//   2. saves the update in a KV queue,
//   3. starts the "Process approvals" GitHub workflow, which does the real work.
// The workflow reads the queue from GET /queue and removes handled items with POST /queue/ack.
//
// Settings (Worker → Settings → Variables and Secrets):
//   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WORKER_SECRET, GH_PAT  (secrets)
//   GH_REPO  e.g. "MohAsef-Qayumi/posting-agent"                 (text)
// Binding: KV namespace bound as QUEUE.

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    if (pathname === "/telegram" && request.method === "POST") return onTelegram(request, env, ctx);
    if (pathname.startsWith("/queue")) return onQueue(request, env, pathname);
    return new Response("posting-agent worker is running ✓");
  },
};

async function onTelegram(request, env, ctx) {
  if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WORKER_SECRET) {
    return new Response("forbidden", { status: 403 });
  }
  const update = await request.json();
  const cb = update.callback_query;
  const msg = update.message;
  const chat = String(cb?.message?.chat?.id ?? msg?.chat?.id ?? "");
  if (chat !== String(env.TELEGRAM_CHAT_ID)) return new Response("ok"); // only you can control the bot

  const key = `u:${String(update.update_id).padStart(12, "0")}`;
  await env.QUEUE.put(key, JSON.stringify(update), { expirationTtl: 3 * 86400 });

  ctx.waitUntil(Promise.all([
    cb
      ? telegram(env, "answerCallbackQuery", { callback_query_id: cb.id, text: "⏳ Got it — working on it (about a minute)…" })
      : telegram(env, "setMessageReaction", { chat_id: chat, message_id: msg.message_id, reaction: [{ type: "emoji", emoji: "👀" }] }),
    startWorkflow(env, update, chat),
  ]));
  return new Response("ok");
}

async function onQueue(request, env, pathname) {
  if (request.headers.get("Authorization") !== `Bearer ${env.WORKER_SECRET}`) {
    return new Response("forbidden", { status: 403 });
  }
  if (pathname === "/queue" && request.method === "GET") {
    const { keys } = await env.QUEUE.list({ prefix: "u:" });
    const items = await Promise.all(keys.map((k) => env.QUEUE.get(k.name, "json")));
    return Response.json(items.filter(Boolean));
  }
  if (pathname === "/queue/ack" && request.method === "POST") {
    const { ids = [] } = await request.json();
    await Promise.all(ids.map((id) => env.QUEUE.delete(`u:${String(id).padStart(12, "0")}`)));
    return Response.json({ ok: true });
  }
  return new Response("not found", { status: 404 });
}

async function startWorkflow(env, update, chat) {
  const res = await fetch(`https://api.github.com/repos/${env.GH_REPO}/actions/workflows/process.yml/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GH_PAT}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "posting-agent-worker",
    },
    body: JSON.stringify({ ref: "main", inputs: { update: JSON.stringify(update) } }),
  });
  if (!res.ok) {
    const detail = (await res.text()).slice(0, 300);
    await telegram(env, "sendMessage", {
      chat_id: chat,
      text: `⚠️ Couldn't start GitHub (${res.status}): ${detail}\nYour tap is saved and will be handled by the hourly run.`,
    });
  }
}

function telegram(env, method, body) {
  return fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
