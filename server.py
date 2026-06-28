#!/usr/bin/env python3
"""
Live dashboard - MČR juniorů 2026, Skok o tyč - Juniorky
Spuštění: python server.py
Dashboard: http://localhost:8765
"""
import re
import html as htmlmod
import json
import urllib.request
import threading
import time
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

URL = "https://online.atletika.cz/vysledky/84981/1330"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}
PORT = 8765

_cache = {"data": None, "updated": 0}
_lock = threading.Lock()


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

        # PB a SB jsou desetinna cisla v aright cells (SČ je cele cislo - nematchi)
        decimals = re.findall(r'<td class="aright">(\d+[.,]\d+)</td>', row)
        pb = decimals[0] if len(decimals) > 0 else ""
        sb = decimals[1] if len(decimals) > 1 else ""

        athletes.append({"name": name, "club": club, "pb": pb, "sb": sb})
    return athletes


def fetch_data():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode("utf-8", errors="replace")

    # Najdi sekci Juniorky (ne Junioři)
    match = re.search(r'<h2 class="main-result-header">(?:(?!<h2).)*?-\s*Juniorky\s*<span', content, re.DOTALL)
    if not match:
        return {"error": "Sekce Juniorky nenalezena", "athletes": [], "heights": [], "status": "unknown"}

    start = match.start()
    next_h2 = content.find('<h2 class="main-result-header">', start + 10)
    section = content[start:next_h2] if next_h2 != -1 else content[start:]

    # Status detekce
    if 'offBadge' in section[:3000]:
        status = "official"
    elif re.search(r'class="liveBadge"|class="inprogress"|live', section[:3000], re.IGNORECASE):
        status = "live"
    elif 'class="disabled"' in section[:2000]:
        status = "startlist"
    else:
        # Pokud jsou attemptvertical bunky, probiha nebo skoncilo
        status = "live" if 'attemptvertical' in section else "startlist"

    # Cas zavodu
    time_m = re.search(r'\(([^)]*\d{2}:\d{2}[^)]*)\)', section[:2000])
    race_time = time_m.group(1).strip() if time_m else ""

    heights = parse_heights(section)

    # Startlist ma <tbody> bez uzaviracího </tbody> tag - hledame obsah az po </table>
    tbody_m = re.search(r"<tbody>(.*?)(?:</tbody>|</table>)", section, re.DOTALL)
    athletes = []
    if tbody_m:
        tbody = tbody_m.group(1)
        athletes = parse_results(tbody) if heights else parse_startlist(tbody)

    return {
        "status": status,
        "race_time": race_time,
        "heights": heights,
        "athletes": athletes,
    }


def get_data():
    with _lock:
        now = time.time()
        if now - _cache["updated"] > 55:
            try:
                _cache["data"] = fetch_data()
                _cache["updated"] = now
                print(f"[{time.strftime('%H:%M:%S')}] Data obnovena, status: {_cache['data'].get('status')}, "
                      f"atletky: {len(_cache['data'].get('athletes', []))}")
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Chyba: {e}")
                if _cache["data"] is None:
                    _cache["data"] = {"error": str(e), "athletes": [], "heights": [], "status": "error"}
        return _cache["data"]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/api/data":
            data = get_data()
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        else:
            html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
            try:
                with open(html_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()


if __name__ == "__main__":
    print("Načítám data...")
    threading.Thread(target=lambda: get_data(), daemon=True).start()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Dashboard: http://localhost:{PORT}")
    print("Ctrl+C pro zastavení\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer zastaven")
