# Watch new Freelancer.com listings, let Qwen pick the bid group, draft a bid for every match,
# and push each draft to the user's phone through ntfy. The user reads the draft and submits it
# by hand; nothing here logs in or touches the Freelancer account.
#
#   python3 watch.py [--once] [--max-seconds N] [--state DIR]
#
# NTFY_TOPIC unset -> drafts only go to DIR/drafts.jsonl (handy for local tests).
# The repo is public, so stdout (the Actions log) never carries bid text or the topic name.
import argparse, json, os, re, sys, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qwen_client import ask
from qwen_classify import SYSTEM as CLASSIFY, parse
from qwen_bid import SYSTEM as BID

FEED = ('https://www.freelancer.com/api/projects/0.1/projects/active/'
        '?limit=50&full_description=true&job_details=true&compact=true&sort_field=submitdate')
POLL = 30              # seconds between feed reads; 50 listings cover about an hour
FRESH = 15 * 60        # with no saved state, only handle listings younger than this
QWEN_DEAD = 10         # this many Qwen failures in a row -> exit red so GitHub emails
FEED_DEAD = 30 * 60    # feed failing this long -> exit red
NAMES = {'wp': 'แก้ WordPress', 'pdf': 'PDF เป็น Word', 'tr': 'แปล', 'legal': 'กฎหมาย', 'pine': 'Pine Script',
         'kdp': 'จัดหน้าหนังสือ', 'fin': 'โมเดลการเงิน', 'grant': 'ขอทุน/tender', 'grantfind': 'หาแหล่งทุน'}
URGENT = {'wp'}        # the first ten bids land within ~2.5 minutes

def fetch():
    req = urllib.request.Request(FEED, headers={'user-agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)['result']['projects']

def job(p):
    bu, rate = p['budget'], p['currency']['exchange_rate']
    return {'id': p['id'], 'title': p['title'], 'type': p['type'],
            'budget': f"${(bu.get('minimum') or 0)*rate:.0f}-{(bu.get('maximum') or 0)*rate:.0f}",
            'desc': re.sub(r'\s+', ' ', p.get('description') or '')[:2500],
            'url': 'https://www.freelancer.com/projects/' + p['seo_url'], 'posted': p['submitdate']}

def prompt(j):
    return f"Title: {j['title']}\nBudget: {j['budget']} ({j['type']})\nDescription: {j['desc']}"

def draft(j):
    text, _, secs, _ = ask(prompt(j), system=BID, max_tokens=4000, think_budget=1024)
    m = re.search(r'AMOUNT:\s*\$?([\d.,]+).*?DAYS:\s*(\d+).*?BID:\s*(.*)', text, re.S)
    if not m:
        return {'raw': text.strip()}, secs
    return {'amount': m[1], 'days': m[2], 'bid': m[3].strip()}, secs

def notify(rec):
    """Title carries everything but the bid, so the message body is the bid alone and copies clean."""
    topic = os.environ.get('NTFY_TOPIC')
    if not topic:
        return
    j, b, g = rec['job'], rec['draft'], rec['group']
    age = (time.time() - j['posted']) / 60
    title = (f"[{NAMES[g]}] ${b.get('amount', '?')} · {b.get('days', '?')} วัน · งบ {j['budget']} "
             f"· อายุ {age:.0f} นาที · {j['title']}")
    body = {'topic': topic, 'title': title[:250], 'message': (b.get('bid') or b.get('raw') or '')[:3900],
            'click': j['url'], 'priority': 5 if g in URGENT else 3,
            'actions': [{'action': 'view', 'label': 'เปิดประกาศ', 'url': j['url']}]}
    req = urllib.request.Request('https://ntfy.sh/', data=json.dumps(body).encode(),
                                 headers={'content-type': 'application/json'})
    for wait in (0, 5, 20):
        time.sleep(wait)
        try:
            urllib.request.urlopen(req, timeout=20).read(); return
        except Exception as e:
            print(f"  ntfy error: {type(e).__name__}", flush=True)

class Watch:
    def __init__(self, state):
        self.state = state
        os.makedirs(state, exist_ok=True)
        self.sf = os.path.join(state, 'seen.json')
        self.seen = set(json.load(open(self.sf))) if os.path.exists(self.sf) else set()
        self.qwen_fails = 0

    def handle(self, p):
        """True when the listing is done with; False to retry it on the next poll."""
        j = job(p)
        try:
            text, _, secs, _ = ask(prompt(j), system=CLASSIFY, max_tokens=2000)
            c = parse(text)
            g = c.get('group')
            if g not in NAMES:
                print(f"{time.strftime('%H:%M:%S')} {j['id']} {g} {secs:.1f}s", flush=True)
                self.qwen_fails = 0
                return True
            b, bsecs = draft(j)
        except Exception as e:
            self.qwen_fails += 1
            print(f"  qwen error #{self.qwen_fails} on {j['id']}: {type(e).__name__}", flush=True)
            return False
        self.qwen_fails = 0
        rec = {'at': int(time.time()), 'group': g, 'reason': c.get('reason', ''), 'job': j, 'draft': b,
               'secs': bsecs}
        with open(os.path.join(self.state, 'drafts.jsonl'), 'a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        notify(rec)
        print(f"{time.strftime('%H:%M:%S')} {j['id']} {g} {secs:.1f}s DRAFT {bsecs:.0f}s "
              f"age {(time.time() - j['posted']) / 60:.1f} min", flush=True)
        return True

    def run(self, once, max_seconds):
        start = last_ok = time.time()
        boot = not self.seen
        while time.time() - start < max_seconds:
            try:
                projects = fetch(); last_ok = time.time()
            except (urllib.error.URLError, OSError, ValueError) as e:
                print(f"feed error: {type(e).__name__} {getattr(e, 'code', '')}", flush=True)
                if time.time() - last_ok > FEED_DEAD:
                    sys.exit('feed down for 30 minutes')
                time.sleep(POLL * 4); continue
            # newest first, so a fresh WordPress fix is not stuck behind older listings
            for p in sorted(projects, key=lambda p: -p['submitdate']):
                if p['id'] in self.seen:
                    continue
                if boot and not once and start - p['submitdate'] > FRESH:
                    self.seen.add(p['id']); continue
                if self.handle(p):
                    self.seen.add(p['id'])
                if self.qwen_fails >= QWEN_DEAD:
                    self.save(); sys.exit('Qwen failed 10 times in a row')
            boot = False
            self.save()
            if once:
                return
            time.sleep(POLL)

    def save(self):
        json.dump(sorted(self.seen)[-5000:], open(self.sf, 'w'))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--max-seconds', type=int, default=10 ** 9)
    ap.add_argument('--state', default=os.path.expanduser('~/cf-cache/watch'))
    a = ap.parse_args()
    Watch(a.state).run(a.once, a.max_seconds)
