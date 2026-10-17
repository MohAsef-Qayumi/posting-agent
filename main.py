"""Posting agent CLI.

  python main.py generate [--pillar AI] [--replace ID] [--idea TEXT]   create a draft and send it to Telegram
  python main.py process                                               handle Telegram taps, publish approved drafts
  python main.py preview  [--pillar AI] [--sample]             generate + render locally only (no Telegram)
  python main.py check                                         verify every credential works
"""
import argparse
import sys

sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily social posting agent")
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--pillar", default="")
    g.add_argument("--replace", default="")
    g.add_argument("--idea", default="")
    sub.add_parser("process")
    pv = sub.add_parser("preview")
    pv.add_argument("--pillar", default="")
    pv.add_argument("--sample", action="store_true", help="render built-in sample slides (no API key needed)")
    sub.add_parser("check")
    args = parser.parse_args()

    if args.command == "generate":
        from agent.pipeline import create_draft

        draft = create_draft(pillar=args.pillar or None, replace=args.replace or None, idea=args.idea or None)
        print(f"Draft {draft['id']} sent to Telegram: {draft['topic']}")

    elif args.command == "process":
        from agent.pipeline import process_updates, run_dispatch

        run_dispatch(process_updates())

    elif args.command == "preview":
        from agent.preview import preview

        preview(args.pillar or None, sample=args.sample)

    elif args.command == "check":
        from agent.check import check

        sys.exit(0 if check() else 1)


if __name__ == "__main__":
    main()
