# Minimal streaming client for the Qwen gateway (Anthropic Messages API shape).
# Reads base/key/model from the environment (GitHub Actions secrets) or else from
# ~/.config/fm-grading.env at run time; never prints the key.
import json, os, time, urllib.request

def _env():
    if os.environ.get("FM_CLAUDE_KEY"):
        return {k: os.environ[k] for k in ("FM_CLAUDE_BASE", "FM_CLAUDE_KEY", "FM_CLAUDE_MODEL")}
    cfg = {}
    for line in open(os.path.expanduser("~/.config/fm-grading.env")):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            cfg[k] = v.strip().strip('"')
    return cfg

CFG = _env()
MODEL = CFG["FM_CLAUDE_MODEL"]

def ask(prompt, system=None, max_tokens=1024, timeout=600, think_budget=None):
    """Returns (text, seconds_to_first_token, seconds_total, usage)."""
    body = {"model": MODEL, "max_tokens": max_tokens, "stream": True,
            "messages": [{"role": "user", "content": prompt}]}
    if system:
        body["system"] = system
    if think_budget:  # without a budget Qwen can think until max_tokens and return no text
        body["thinking"] = {"type": "enabled", "budget_tokens": think_budget}
    req = urllib.request.Request(
        CFG["FM_CLAUDE_BASE"].rstrip("/") + "/v1/messages", data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "x-api-key": CFG["FM_CLAUDE_KEY"],
                 "authorization": "Bearer " + CFG["FM_CLAUDE_KEY"], "anthropic-version": "2023-06-01", "user-agent": "claude-cli/2.0 (external, cli)"})
    t0 = time.time(); first = None; out = []; usage = {}
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            if ev.get("type") == "content_block_delta":
                d = ev["delta"]
                if d.get("type") == "text_delta":
                    if first is None:
                        first = time.time() - t0
                    out.append(d["text"])
                elif d.get("type") == "thinking_delta":
                    usage["thinking_chars"] = usage.get("thinking_chars", 0) + len(d.get("thinking", ""))
            elif ev.get("type") == "message_delta":
                usage.update(ev.get("usage", {}))
            elif ev.get("type") == "message_start":
                usage.update(ev["message"].get("usage", {}))
    return "".join(out), first, time.time() - t0, usage

if __name__ == "__main__":
    t, f, tot, u = ask("Reply with exactly: pong", max_tokens=50)
    print(repr(t), f, round(tot, 1), u)
