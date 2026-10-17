# Posting Agent

Writes a post every day with Claude, renders a branded dark-tech Instagram carousel, sends it to you on Telegram for approval, then publishes to **LinkedIn**, a **Facebook Page** and **Instagram**. Runs free on GitHub Actions.

```
08:00 daily ── generate.yml ── Claude writes the post ─ slides rendered ─▶ Telegram preview
                                                                              │ ✅ / 🔁 / ❌
every 30 min ─ process.yml ── reads your taps ─▶ LinkedIn + Facebook Page + Instagram
```

**Setup:** follow [SETUP.md](SETUP.md).

## Weekly content mix
Mon AI · Tue Career · Wed Tech · Thu Startup · Fri Code · Sat Engagement · Sun Mindset — edit `rotation` in `config.yaml`.

## Project layout
| Path | What it does |
|---|---|
| `config.yaml` | Your voice, startup info, weekly rotation, news feeds, platform on/off |
| `agent/content.py` | Claude prompt + structured output |
| `agent/templates/carousel.html` | Slide design (1080×1350, dark tech theme) |
| `agent/render.py` | Renders slides to JPEG with headless Chromium |
| `agent/pipeline.py` | Drafts, Telegram approval flow, publishing |
| `agent/publishers/` | LinkedIn (Posts API) and Meta (Facebook Page + Instagram Graph API) |
| `tools/` | One-time helpers to get your tokens |
| `state/` | Drafts and history — committed by the workflows, don't edit by hand |

## Commands
```
python main.py preview [--pillar AI] [--sample]   # local preview, nothing published
python main.py generate [--pillar AI]             # create draft → Telegram
python main.py process                            # handle taps, publish approved drafts
python main.py check                              # verify all credentials
```

## Adding your startup
Fill in `startup:` in `config.yaml` — Thursday posts use only those facts.
