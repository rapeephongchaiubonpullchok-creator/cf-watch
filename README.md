# cf-watch

Watches new Freelancer.com listings, asks a Qwen model whether each one fits a fixed set of job
groups, drafts a bid for every match and sends it to a phone through ntfy. A person reads each
draft and submits it by hand; nothing here logs in to Freelancer.com.

- `watch.py` — the loop (`--once` for a single pass, `--state DIR` for where the seen-list lives)
- `qwen_classify.py`, `qwen_bid.py` — the two prompts, each also runnable on a fixed test set
- `qwen_client.py` — streaming client for the gateway; settings come from the environment
- `.github/workflows/watch.yml` — runs the loop around the clock
