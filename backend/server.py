#!/usr/bin/env python3
"""Web API cho TFS report (Vue frontend): login -> pick items -> tạo report.

Chạy:  python3 backend/server.py   ->  http://127.0.0.1:8765
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

import json
from http.server import BaseHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
API = "7.1"
FIELDS = [
    "System.Id",
    "System.WorkItemType",
    "System.Title",
    "System.State",
    "System.BoardColumn",
    "System.IterationPath",
    "System.Parent",
    "System.CreatedDate",
    "System.ChangedDate",
    "Microsoft.VSTS.Common.Priority",
    "Microsoft.VSTS.Scheduling.RemainingWork",
    "Microsoft.VSTS.Scheduling.CompletedWork",
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


def api_url(path, scope="project", project=None, collection=None):
    org = urllib.parse.quote(collection or CFG["org"], safe="")
    if scope == "server":
        return f"{CFG['server']}/{path}"
    if scope == "collection":
        return f"{CFG['server']}/{org}/{path}"
    proj = urllib.parse.quote(project or CFG["project"], safe="")
    return f"{CFG['server']}/{org}/{proj}/{path}"


def login_ok(user, password):
    creds = {"user": user, "password": password}
    p = tfs_curl(creds, api_url(f"_apis/projects?api-version={API}", "collection"), head_only=True)
    return p.stdout.decode(errors="replace").strip() == "200"


def fetch_collections(creds):
    """List collection của server TFS: {server}/_apis/projectcollections"""
    p = tfs_curl(creds, api_url(f"_apis/projectcollections?api-version={API}", "server"))
    if p.returncode != 0:
        raise RuntimeError(p.stdout.decode(errors="replace")[:300])
    return json.loads(p.stdout).get("value", [])


def fetch_projects(creds, collection):
    """List project trong một collection: {server}/{collection}/_apis/projects"""
    p = tfs_curl(creds, api_url(f"_apis/projects?api-version={API}", "collection", collection=collection))
    if p.returncode != 0:
        raise RuntimeError(p.stdout.decode(errors="replace")[:300])
    return json.loads(p.stdout).get("value", [])


def cur_collection(creds):
    return creds.get("collection", "")


def cur_project(creds):
    return creds.get("project", "")


def fetch_state_colors(creds, wtypes=("Epic", "User Story", "Task", "Bug")):
    """Lấy màu state thật từ TFS: _apis/wit/workitemtypes/{type}/states -> {state: '#rrggbb'}"""
    collection = cur_collection(creds)
    project = cur_project(creds)
    colors = {}
    for wtype in wtypes:
        url = api_url(f"_apis/wit/workitemtypes/{urllib.parse.quote(wtype)}/states?api-version=5.0-preview.1", project=project, collection=collection)
        p = tfs_curl(creds, url)
        if p.returncode != 0:
            continue
        try:
            value = json.loads(p.stdout).get("value", [])
        except json.JSONDecodeError:
            continue
        for st in value:
            name, color = st.get("name", ""), st.get("color", "")
            if name and color:
                colors.setdefault(name, "#" + color.lstrip("#").zfill(6))
    return colors


def fetch_items(creds):
    collection = cur_collection(creds)
    project = cur_project(creds)
    p = tfs_curl(creds, api_url(f"_apis/wit/wiql?api-version={API}", project=project, collection=collection), {
        "query": "SELECT [System.Id] FROM WorkItems WHERE [System.AssignedTo] = @me ORDER BY [System.ChangedDate] DESC"
    })
    if p.returncode != 0:
        raise RuntimeError(p.stdout.decode(errors="replace")[:300])
    ids = [w["id"] for w in json.loads(p.stdout).get("workItems", [])]
    items = []
    for i in range(0, len(ids), 200):
        chunk = ids[i : i + 200]
        r = tfs_curl(creds, api_url(f"_apis/wit/workitemsbatch?api-version={API}", project=project, collection=collection),
                     {"ids": chunk, "fields": FIELDS})
        if r.returncode != 0:
            raise RuntimeError(r.stdout.decode(errors="replace")[:300])
        items.extend(json.loads(r.stdout).get("value", []))
    return items


def cell(s):
    return str(s or "").replace("|", "\\|").replace("\n", " ").strip()


def render_chat(today_items, next_items, report_date, fullname, user):
    """Phần chat — format theo applications/public/templetes/"""
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


def render_lark(items, report_date, collection, project):
    """Phần lark — format theo applications/public/templetes/"""
    date_str = report_date.strftime("%d/%m/%Y")
    lines = [
        "| Status | Start date | End date | Note | Type | Task ID | Task Name | Task Link |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    base = f"{CFG['server']}/{collection}/{project}/_workitems/edit/"
    for it in items:
        f = it["fields"]
        lines.append(
            f"| {cell(f.get('System.State'))} | {date_str} |  |  "
            f"| {cell(f.get('System.WorkItemType'))} | {it['id']} "
            f"| {cell(f.get('System.Title'))} | {base}{it['id']} |"
        )
    return "\n".join(lines)


def render_report(today_items, next_items, report_date, fullname, user, collection, project):
    # lark: hợp nhất 2 nhóm, bỏ lặp item
    seen, merged = set(), []
    for it in today_items + next_items:
        if it["id"] not in seen:
            seen.add(it["id"])
            merged.append(it)
    return render_chat(today_items, next_items, report_date, fullname, user) + "\n\n" + render_lark(merged, report_date, collection, project) + "\n"


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
        if self.path == "/api/me":
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            self._send({
                "user": creds["user"],
                "fullname": CFG.get("fullname", ""),
                "collection": cur_collection(creds),
                "project": cur_project(creds),
            })
        elif self.path == "/api/collections":
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            try:
                raw = fetch_collections(creds)
                collections = [
                    {"id": c.get("id", ""), "name": c.get("name", "")}
                    for c in raw
                ]
                self._send({"collections": collections})
            except RuntimeError as e:
                self._send({"error": str(e)}, 502)
        elif self.path.startswith("/api/projects"):
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            collection = (qs.get("collection") or [""])[0].strip()
            if not collection:
                self._send({"error": "Thiếu tham số collection"}, 400)
                return
            try:
                raw = fetch_projects(creds, collection)
                projects = [
                    {
                        "id": p.get("id", ""),
                        "name": p.get("name", ""),
                        "description": p.get("description") or "",
                        "state": p.get("state", ""),
                    }
                    for p in raw
                ]
                self._send({"collection": collection, "projects": projects})
            except RuntimeError as e:
                self._send({"error": str(e)}, 502)
        elif self.path == "/api/items":
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            collection = cur_collection(creds)
            project = cur_project(creds)
            if not collection or not project:
                self._send({"error": "Chưa chọn dự án"}, 400)
                return
            try:
                items = fetch_items(creds)
                # parent ids chưa có trong danh sách -> fetch title riêng
                known = {it["id"] for it in items}
                parent_titles = {it["id"]: it["fields"].get("System.Title", "") for it in items}
                missing = [p for p in (it["fields"].get("System.Parent") for it in items) if p and p not in known]
                for pid in dict.fromkeys(missing):
                    r = tfs_curl(creds, api_url(f"_apis/wit/workitems/{pid}?api-version={API}&fields=System.Id,System.Title", project=project, collection=collection))
                    if r.returncode != 0:
                        continue
                    try:
                        parent_titles[pid] = json.loads(r.stdout).get("fields", {}).get("System.Title", "")
                    except json.JSONDecodeError:
                        continue
                out = [
                    {
                        "id": it["id"],
                        "type": it["fields"].get("System.WorkItemType", ""),
                        "title": it["fields"].get("System.Title", ""),
                        "state": it["fields"].get("System.State", ""),
                        "board": it["fields"].get("System.BoardColumn") or it["fields"].get("System.State", ""),
                        "iteration": it["fields"].get("System.IterationPath", ""),
                        "parent": it["fields"].get("System.Parent"),
                        "parentTitle": parent_titles.get(it["fields"].get("System.Parent"), ""),
                        "changed": it["fields"].get("System.ChangedDate") or "",
                        "remaining": it["fields"].get("Microsoft.VSTS.Scheduling.RemainingWork"),
                        "completed": it["fields"].get("Microsoft.VSTS.Scheduling.CompletedWork"),
                    }
                    for it in items
                ]
                self._send({
                    "items": out,
                    "fullname": CFG.get("fullname", ""),
                    "collection": collection,
                    "project": project,
                    "taskBase": f"{CFG['server']}/{collection}/{project}/_workitems/edit/",
                    "stateColors": fetch_state_colors(creds),
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
            cookie = f"session={token}; HttpOnly; Path=/"
            if body.get("remember"):
                cookie += "; Max-Age=2592000"  # 30 ngày
            self._send({"ok": True, "user": user, "fullname": CFG.get("fullname", "")}, set_cookie=cookie)
        elif parsed.path == "/api/logout":
            cookie = self.headers.get("Cookie", "")
            for part in cookie.split(";"):
                k, _, v = part.strip().partition("=")
                if k == "session":
                    SESSIONS.pop(v, None)
            self._send({"ok": True})
        elif parsed.path == "/api/select-project":
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            body = self._body()
            collection = (body.get("collection") or "").strip()
            project = (body.get("project") or "").strip()
            if not collection or not project:
                self._send({"error": "Thiếu collection hoặc project"}, 400)
                return
            try:
                valid_collections = {c.get("name") for c in fetch_collections(creds)}
                if collection not in valid_collections:
                    self._send({"error": "Collection không hợp lệ"}, 400)
                    return
                valid_projects = {p.get("name") for p in fetch_projects(creds, collection)}
                if project not in valid_projects:
                    self._send({"error": "Dự án không hợp lệ"}, 400)
                    return
            except RuntimeError as e:
                self._send({"error": str(e)}, 502)
                return
            creds["collection"] = collection
            creds["project"] = project
            self._send({"ok": True, "collection": collection, "project": project})
        elif parsed.path == "/api/report":
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            collection = cur_collection(creds)
            project = cur_project(creds)
            if not collection or not project:
                self._send({"error": "Chưa chọn dự án"}, 400)
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
            report = render_report(today_items, next_items, report_date, body.get("fullname"), creds["user"], collection, project)
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


# Adapter để Vercel Serverless Function gọi đến Handler của bạn
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Tái sử dụng lại logic của Handler cũ
        h = Handler(self.request, self.client_address, self.server)
        
    def do_POST(self):
        h = Handler(self.request, self.client_address, self.server)

# Nếu chạy local bằng lệnh python3 backend/server.py thì vẫn giữ nguyên tính năng dev local
if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    url = f"http://127.0.0.1:{port}"
    print(f"Web UI: {url}   (Ctrl+C để dừng)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()