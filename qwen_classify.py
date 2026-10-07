# Ask Qwen to sort each test job into one of the bid groups, one call per job, timing each.
# Run in ~/cf-cache/: python3 qwen_classify.py  -> qwen-test/classify.json
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qwen_client import ask

SYSTEM = """You screen Freelancer.com job posts for an AI writer/analyst that has no body, no license, and no access to design apps like InDesign, Photoshop or video editors. It can only bid on these groups:

wp = FIX a broken/hacked/erroring existing WordPress site (not building a new site, not ongoing maintenance retainers, not new features).
pdf = convert a PDF file into an editable Word document (or plain editable text). EXCLUDE data entry: typing or transcribing into Excel, Google Sheets, forms, templates or databases; re-typing scanned, photographed or printed pages; and any job that forbids OCR or automation. Not design work, not video.
tr = translate documents/text between languages. EXCLUDE if the client requires a certified/sworn/notarized translation.
legal = only: formatting/proofreading legal documents, legal research memos, or letters to companies/platforms (complaints, demand letters). EXCLUDE drafting court filings or lawsuits, contracts for businesses, and anything requiring a licensed attorney or representation.
pine = write or modify TradingView Pine Script indicators/strategies.
kdp = interior formatting of a book into print PDF or EPUB for KDP. EXCLUDE covers, jobs requiring InDesign files, and jobs that need logging into the client's KDP account.
fin = financial models in Excel: forecasts, pro forma, NPV, amortization schedules, valuation, P&L from documents.
grant = write or review a grant proposal, tender or RFP response from information the client provides. EXCLUDE ongoing tender hunting on government portals (GeM, SAM.gov), success-fee work.
grantfind = one-off job: find suitable funders AND write the application/letter. EXCLUDE ongoing or success-fee work.
none = anything else (new websites, video, design, marketing, social media, physical work, data entry of any kind, etc.).

Answer with ONLY a JSON object: {"group": "<code>", "reason": "<one short sentence>"}"""

def prompt(j):
    return f"Title: {j['title']}\nBudget: {j['budget']} ({j['type']})\nDescription: {j['desc']}"

def parse(t):
    t = t.strip()
    a, b = t.find('{'), t.rfind('}')
    try:
        return json.loads(t[a:b+1])
    except Exception:
        return {"group": "PARSE_ERROR", "reason": t[:200]}

if __name__ == '__main__':
    jobs = json.load(open('qwen-test/jobs.json'))
    out = []
    for n, j in enumerate(jobs):
        try:
            text, first, total, usage = ask(prompt(j), system=SYSTEM, max_tokens=2000)
            r = parse(text)
        except Exception as e:
            text, first, total, usage, r = '', None, None, {}, {"group": "ERROR", "reason": repr(e)[:200]}
        r.update(n=n, id=j['id'], secs=total, first=first, usage=usage, raw=text[-400:])
        out.append(r)
        print(n, r['group'], f"{total:.1f}s" if total else '-', usage.get('output_tokens'), flush=True)
    json.dump(out, open('qwen-test/classify.json', 'w'), ensure_ascii=False, indent=1)
