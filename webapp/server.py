#!/usr/bin/env python3
"""Web UI cho TFS report: login -> pick items -> tạo report.

Chạy:  python3 webapp/server.py   ->  http://127.0.0.1:8765
Sessions lưu in-memory (không ghi disk), mật khẩu không persist.
Report ghi vào <cwd>/<yyyy>/<m>/<d>.md cùng quy tắc CLI.
"""

import datetime
import http.server
import json
import os
import subprocess
import sys
import urllib.parse
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")
API = "7.1"
FIELDS = [
    "System.Id",
    "System.WorkItemType",
    "System.Title",
    "System.State",
    "System.IterationPath",
    "System.CreatedDate",
    "System.ChangedDate",
    "Microsoft.VSTS.Common.Priority",
    "Microsoft.VSTS.Scheduling.RemainingWork",
]
SESSIONS = {}  # token -> {"user": ..., "password": ...}


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


CFG = load_config()


def tfs_curl(creds, url, body=None, head_only=False):
    cmd = [
        "curl", "-s", "--fail-with-body", "--max-time", "60", "--ntlm",
        "-u", f"{creds['user']}:{creds['password']}",
        "-H", "Accept: application/json",
    ]
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        cmd += ["-H", "Content-Type: application/json", "--data-binary", "@-"]
    if head_only:
        cmd = [c for c in cmd if c != "--fail-with-body"] + ["-o", "/dev/null", "-w", "%{http_code}"]
    cmd.append(url)
    return subprocess.run(cmd, input=data, capture_output=True)


def api_url(path, scope="project"):
    base = f"{CFG['server']}/{CFG['org']}" if scope == "collection" else \
        f"{CFG['server']}/{CFG['org']}/{CFG['project']}"
    return f"{base}/{path}"


def login_ok(user, password):
    creds = {"user": user, "password": password}
    p = tfs_curl(creds, api_url(f"_apis/projects?api-version={API}", "collection"), head_only=True)
    return p.stdout.decode(errors="replace").strip() == "200"


def fetch_items(creds):
    p = tfs_curl(creds, api_url(f"_apis/wit/wiql?api-version={API}"), {
        "query": "SELECT [System.Id] FROM WorkItems WHERE [System.AssignedTo] = @me ORDER BY [System.ChangedDate] DESC"
    })
    if p.returncode != 0:
        raise RuntimeError(p.stdout.decode(errors="replace")[:300])
    ids = [w["id"] for w in json.loads(p.stdout).get("workItems", [])]
    items = []
    for i in range(0, len(ids), 200):
        chunk = ids[i : i + 200]
        r = tfs_curl(creds, api_url(f"_apis/wit/workitemsbatch?api-version={API}"),
                     {"ids": chunk, "fields": FIELDS})
        if r.returncode != 0:
            raise RuntimeError(r.stdout.decode(errors="replace")[:300])
        items.extend(json.loads(r.stdout).get("value", []))
    return items


def cell(s):
    return str(s or "").replace("|", "\\|").replace("\n", " ").strip()


def render_chat(today_items, next_items, report_date, fullname, user):
    """Phần chat — format theo templetes/templete.md"""
    lines = [
        f"*Báo cáo nhân sự* {report_date.strftime('%d/%m/%Y')}",
        f"*Nhân sự:* {fullname or user}",
        "*Công việc:*",
    ]
    for it in today_items:
        f = it["fields"]
        lines.append(f"- {cell(f.get('System.WorkItemType'))} {it['id']}: {cell(f.get('System.Title'))} (100%)")
    if not today_items:
        lines.append("- ...")
    lines.append("*Công việc ngày tiếp theo:*")
    for it in next_items:
        f = it["fields"]
        lines.append(f"- {cell(f.get('System.WorkItemType'))} {it['id']}: {cell(f.get('System.Title'))}")
    if not next_items:
        lines.append("- ...")
    lines += ["*Vấn đề:*", "- None"]
    return "\n".join(lines)


def render_lark(items, report_date):
    """Phần lark — format theo templetes/templete.md"""
    date_str = report_date.strftime("%d/%m/%Y")
    lines = [
        "| Status | Start date | End date | Note | Type | Task ID | Task Name | Task Link |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    base = f"{CFG['server']}/{CFG['org']}/{CFG['project']}/_workitems/edit/"
    for it in items:
        f = it["fields"]
        lines.append(
            f"| {cell(f.get('System.State'))} | {date_str} | <none> | <none> "
            f"| {cell(f.get('System.WorkItemType'))} | {it['id']} "
            f"| {cell(f.get('System.Title'))} | {base}{it['id']} |"
        )
    return "\n".join(lines)


def render_report(today_items, next_items, report_date, fullname, user):
    # lark: hợp nhất 2 nhóm, bỏ lặp item
    seen, merged = set(), []
    for it in today_items + next_items:
        if it["id"] not in seen:
            seen.add(it["id"])
            merged.append(it)
    return render_chat(today_items, next_items, report_date, fullname, user) + "\n\n" + render_lark(merged, report_date) + "\n"


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, ctype="application/json; charset=utf-8", set_cookie=None):
        body = obj.encode() if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(body)

    def _session(self):
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "session" and v in SESSIONS:
                return SESSIONS[v]
        return None

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(BASE_DIR, "index.html"), "rb") as fh:
                self._send(fh.read().decode(), ctype="text/html; charset=utf-8")
        elif self.path == "/api/items":
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            try:
                items = fetch_items(creds)
                out = [
                    {
                        "id": it["id"],
                        "type": it["fields"].get("System.WorkItemType", ""),
                        "title": it["fields"].get("System.Title", ""),
                        "state": it["fields"].get("System.State", ""),
                        "iteration": it["fields"].get("System.IterationPath", ""),
                        "changed": (it["fields"].get("System.ChangedDate") or "")[:10],
                    }
                    for it in items
                ]
                self._send({
                    "items": out,
                    "fullname": CFG.get("fullname", ""),
                    "taskBase": f"{CFG['server']}/{CFG['org']}/{CFG['project']}/_workitems/edit/",
                })
            except RuntimeError as e:
                self._send({"error": str(e)}, 502)
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/login":
            body = self._body()
            user = (body.get("user") or "").strip()
            password = body.get("password") or ""
            if not user or not password or not login_ok(user, password):
                self._send({"error": "Sai username hoặc mật khẩu"}, 401)
                return
            token = uuid.uuid4().hex
            SESSIONS[token] = {"user": user, "password": password}
            self._send({"ok": True}, set_cookie=f"session={token}; HttpOnly; Path=/")
        elif parsed.path == "/api/logout":
            cookie = self.headers.get("Cookie", "")
            for part in cookie.split(";"):
                k, _, v = part.strip().partition("=")
                if k == "session":
                    SESSIONS.pop(v, None)
            self._send({"ok": True})
        elif parsed.path == "/api/report":
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            body = self._body()
            try:
                report_date = datetime.datetime.strptime(body.get("date") or "", "%d/%m/%Y").date()
            except ValueError:
                self._send({"error": "Ngày không hợp lệ (dd/mm/yyyy)"}, 400)
                return
            try:
                all_items = fetch_items(creds)
            except RuntimeError as e:
                self._send({"error": str(e)}, 502)
                return
            ids = {int(x) for x in body.get("ids") or []}
            next_ids = {int(x) for x in body.get("next_ids") or []}
            today_items = [it for it in all_items if it["id"] in ids] if ids else all_items
            next_items = [it for it in all_items if it["id"] in next_ids]
            if not today_items and not next_items:
                self._send({"error": "Không chọn item nào"}, 400)
                return
            report = render_report(today_items, next_items, report_date, body.get("fullname"), creds["user"])
            out_path = os.path.join(str(report_date.year), str(report_date.month), f"{report_date.day}.md")
            existed = os.path.exists(out_path)
            if existed:
                with open(out_path, "a", encoding="utf-8") as fh:
                    fh.write("\n---\n\n" + report)
            else:
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as fh:
                    fh.write(report)
            self._send({"ok": True, "path": out_path, "appended": existed, "count": len(today_items) + len(next_items), "report": report})
        else:
            self._send({"error": "not found"}, 404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    url = f"http://127.0.0.1:{port}"
    print(f"Web UI: {url}   (Ctrl+C để dừng)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
