from http.server import BaseHTTPRequestHandler
import json
import re
import html as htmlmod
import urllib.request

URL = "https://online.atletika.cz/vysledky/84981/1330"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def clean(s):
    return htmlmod.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def parse_heights(section):
    m = re.search(r'class="verticalJumps">(.*?)</th>', section, re.DOTALL)
    if not m:
        return []
    return [s.strip() for s in re.findall(r"<span>([^<]+)</span>", m.group(1))]


def parse_results(tbody):
    athletes = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.DOTALL):
        name_m = re.search(r'resultsEanLink"[^>]*>([^<]+)<', row)
        if not name_m:
            continue
        name = htmlmod.unescape(name_m.group(1).strip())
        club_m = re.search(r'athleteclub noprint">([^<]+)</span>', row)
        club = htmlmod.unescape(club_m.group(1).strip()) if club_m else ""
        rank_m = re.search(r"<td[^>]*>\s*(\d+|NM|DSQ|DNS)\s*</td>", row)
        rank = rank_m.group(1).strip() if rank_m else ""
        result_m = re.search(r'class="resultcell[^"]*">(.*?)</td>', row, re.DOTALL)
        result, record = "", ""
        if result_m:
            rec_m = re.search(r'class="record">([^<]+)</span>', result_m.group(1))
            record = rec_m.group(1).strip() if rec_m else ""
            result = re.sub(r"<[^>]+>", "", result_m.group(1)).strip()
        att_m = re.search(r'class="attemptvertical">(.*?)</td>', row, re.DOTALL)
        attempts = []
        if att_m:
            attempts = [s.strip() for s in re.findall(r"<span>([^<]+)</span>", att_m.group(1))]
        athletes.append({"rank": rank, "name": name, "club": club,
                         "result": result, "record": record, "attempts": attempts})
    return athletes


def parse_startlist(tbody):
    athletes = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.DOTALL):
        name_m = re.search(r'resultsEanLink"[^>]*>([^<]+)<', row)
        if not name_m:
            continue
        name = htmlmod.unescape(name_m.group(1).strip())
        club_m = re.search(r'class="noprint">([^<]+)</span>', row)
        club = htmlmod.unescape(club_m.group(1).strip()) if club_m else ""
        decimals = re.findall(r'<td class="aright">(\d+[.,]\d+)</td>', row)
        pb = decimals[0] if len(decimals) > 0 else ""
        sb = decimals[1] if len(decimals) > 1 else ""
        athletes.append({"name": name, "club": club, "pb": pb, "sb": sb})
    return athletes


def fetch_data():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=8) as resp:
        content = resp.read().decode("utf-8", errors="replace")

    match = re.search(r'<h2 class="main-result-header">(?:(?!<h2).)*?-\s*Juniorky\s*<span', content, re.DOTALL)
    if not match:
        return {"error": "Sekce Juniorky nenalezena", "athletes": [], "heights": [], "status": "unknown"}

    start = match.start()
    next_h2 = content.find('<h2 class="main-result-header">', start + 10)
    section = content[start:next_h2] if next_h2 != -1 else content[start:]

    if 'offBadge' in section[:3000]:
        status = "official"
    elif 'class="disabled"' in section[:2000]:
        status = "startlist"
    else:
        status = "live" if 'attemptvertical' in section else "startlist"

    time_m = re.search(r'\(([^)]*\d{2}:\d{2}[^)]*)\)', section[:2000])
    race_time = time_m.group(1).strip() if time_m else ""

    heights = parse_heights(section)
    tbody_m = re.search(r"<tbody>(.*?)(?:</tbody>|</table>)", section, re.DOTALL)
    athletes = []
    if tbody_m:
        tbody = tbody_m.group(1)
        athletes = parse_results(tbody) if heights else parse_startlist(tbody)

    return {"status": status, "race_time": race_time, "heights": heights, "athletes": athletes}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data = fetch_data()
        except Exception as e:
            data = {"error": str(e), "athletes": [], "heights": [], "status": "error"}

        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
