# Ask Qwen to write a bid for chosen test jobs, timing each. Run in ~/cf-cache/:
#   python3 qwen_bid.py <n> [<n> ...]  -> qwen-test/bids.json
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qwen_client import ask

SYSTEM = """You write bids on Freelancer.com for a NEW account with zero reviews and no portfolio. The work is done by an AI writer/analyst.

Hard rules (breaking any makes the bid unusable):
- Never claim years of experience, past clients, past projects, a portfolio, native-speaker status, a degree, or being a lawyer/accountant/certified anything.
- Never promise anything that needs a body, a phone, or tools other than documents, spreadsheets, code and text.
- Legal jobs: say it is document preparation or research based on facts the client provides; do not give advice on what the client should do.
- Pine Script jobs: say the client runs it in TradingView and sends back any errors or backtest results.
- WordPress fix jobs: ask for the access needed (hosting/cPanel or wp-admin).

What wins: say things the post did NOT spell out - concrete steps for THIS job, the exact files you will deliver, where this kind of job usually goes wrong, or a contradiction/gap in the post. Ask at most 2 sharp questions. No greeting fluff, no restating the post. 600-1000 characters.

Output format, exactly:
AMOUNT: <number in USD within the client's budget>
DAYS: <integer>
BID:
<bid text>"""

if __name__ == '__main__':
    jobs = json.load(open('qwen-test/jobs.json'))
    out = []
    for n in map(int, sys.argv[1:]):
        j = jobs[n]
        p = f"Title: {j['title']}\nBudget: {j['budget']} ({j['type']})\nDescription: {j['desc']}"
        text, first, total, usage = ask(p, system=SYSTEM, max_tokens=4000, think_budget=1024)
        out.append(dict(n=n, id=j['id'], secs=total, first=first, usage=usage, text=text.strip()))
        print(f"\n######## [{n}] {j['title']} | {j['budget']} | {total:.1f}s first={first or 0:.1f}s out={usage.get('output_tokens')}\n{text.strip()}", flush=True)
    json.dump(out, open('qwen-test/bids.json', 'w'), ensure_ascii=False, indent=1)
