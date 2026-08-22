#!/usr/bin/env python3
"""Web API cho TFS report (Vue frontend): login -> pick items -> tạo report.

Chạy:  python3 backend/server.py   ->  http://127.0.0.1:8765
Sessions lưu in-memory (không ghi disk), mật khẩu không persist.
Report trả về trong JSON, không ghi disk.
"""

import base64
import datetime
import hashlib
import http.server
import json
import os
import sys
import time
import urllib.parse

import requests
from cryptography.fernet import Fernet, InvalidToken
from requests_ntlm import HttpNtlmAuth

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
# giá trị mặc định cho mọi key — nền của load_config
DEFAULTS_PATH = os.path.join(BASE_DIR, "default.json")
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


def load_config():
    """Nối tầng giá trị: default.json (nền) <- config.json (user lưu từ Cài
    đặt) <- env (serverless). Key null trong config.json coi như không set —
    rơi về default. Thiếu/rác thêm 1 lần nữa vẫn coerce về default an toàn."""
    try:
        with open(DEFAULTS_PATH, encoding="utf-8") as fh:
            defaults = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        defaults = {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        cfg = {}
    out = dict(defaults)
    out.update({k: v for k, v in cfg.items() if v is not None})
    # Serverless (Vercel) không nên giữ cấu hình trong file; ưu tiên env.
    out["server"] = os.environ.get("TFS_SERVER") or out.get("server", "")
    out["fullname"] = os.environ.get("TFS_FULLNAME") or out.get("fullname", "")
    # default.json thiếu/rác vẫn phải ra giá trị hợp lệ — coerce như cũ
    if out.get("percent_mode") not in ("work", "state"):
        out["percent_mode"] = "work"
    if not isinstance(out.get("fullname_fallback_user"), bool):
        out["fullname_fallback_user"] = True
    return out


CFG = load_config()


def update_config(fields):
    """Cập nhật field trong config.json (server/org/fullname/token...).
    Value None = XÓA key khỏi config (dọn key cũ không dùng nữa).
    File này vốn chứa thông tin nhạy cảm (README đã ghi chú chmod 600), nên giữ
    nguyên pattern. Serverless FS có thể read-only -> lỗi chỉ log, không fatal.
    Trả True nếu ghi thành công."""
    try:
        try:
            with open(CONFIG_PATH, encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            cfg = {}
        for k, v in fields.items():
            if v is None:
                cfg.pop(k, None)
            else:
                cfg[k] = v
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        return True
    except OSError as e:
        print(f"[update_config] không ghi được config: {e}", file=sys.stderr)
        return False


def save_config_token(token):
    """Lưu/xóa PAT trong config.json khi login bằng token. token rỗng -> xóa."""
    update_config({"token": token})


# --- session: token mã hóa trong cookie (stateless, dùng được trên serverless) ---
SESSION_COOKIE = "session"
SESSION_TTL = 12 * 3600          # đăng nhập thường
SESSION_TTL_REMEMBER = 30 * 86400  # "ghi nhớ đăng nhập"


def _fernet():
    """Khóa mã hóa cookie. Bắt buộc set SESSION_SECRET trên Vercel (Fernet key);
    fallback local khóa suy từ server URL — chỉ tiện dev, không an toàn."""
    secret = os.environ.get("SESSION_SECRET", "")
    if not secret:
        digest = hashlib.sha256(("pineapple-local:" + CFG.get("server", "")).encode()).digest()
        secret = base64.urlsafe_b64encode(digest).decode()
    return Fernet(secret.encode())


def make_session_token(creds):
    payload = dict(creds)
    payload["exp"] = int(time.time()) + (SESSION_TTL_REMEMBER if creds.get("remember") else SESSION_TTL)
    return _fernet().encrypt(json.dumps(payload).encode()).decode()


def read_session_token(token):
    try:
        payload = json.loads(_fernet().decrypt(token.encode()))
    except (InvalidToken, ValueError):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload


def tfs_request(creds, url, body=None):
    """Gọi TFS API qua requests (không cần binary curl). Trả (ok, text).
    Nếu creds có "token" (PAT) thì dùng Basic auth, ngược lại NTLM user/password."""
    headers = {"Accept": "application/json"}
    if creds.get("token"):
        # PAT: Basic với username rỗng -> "Authorization: Basic base64(':' + pat)"
        auth = ("", creds["token"])
    else:
        auth = HttpNtlmAuth(creds["user"], creds["password"])
    try:
        if body is None:
            r = requests.get(url, auth=auth, headers=headers, timeout=60)
        else:
            # TFS từ chối POST thiếu Content-Type: trả 415 với message
            # "Content-Type of ... not supported. Valid ... application/json".
            headers["Content-Type"] = "application/json"
            r = requests.post(url, auth=auth, headers=headers,
                              data=json.dumps(body), timeout=60)
        if 200 <= r.status_code < 300:
            return True, r.text
        # Kèm status để phân biệt 401 (auth), 404 (api-version sai), 415...
        return False, f"HTTP {r.status_code}: {r.text}"
    except requests.RequestException as e:
        return False, f"Lỗi kết nối TFS: {e}"


def connection_data_candidates(creds):
    """Danh sách (url, kind) connectionData/profile theo thứ tự thử.
    Collection-scope trước: TFS on-prem có thể ch PAT ở server-scope.
    Endpoint này cần api-version=7.1-preview (7.1 stable bị từ chối)."""
    collection = creds.get("collection") or CFG.get("org", "")
    quoted = urllib.parse.quote(collection, safe="") if collection else ""
    out = []
    if quoted:
        out.append((f"{CFG['server']}/{quoted}/_apis/connectionData?api-version=7.1-preview", "connection"))
        out.append((f"{CFG['server']}/{quoted}/_apis/profile/profiles/me", "profile"))
    out.append((f"{CFG['server']}/_apis/connectionData", "connection"))
    out.append((f"{CFG['server']}/_apis/profile/profiles/me", "profile"))
    return out


def fetch_fullname(creds):
    """Lấy display name thật của user đang đăng nhập từ TFS. Thử nhiều endpoint
    + nhiều field vì TFS version khác nhau trả shape khác nhau (Azure DevOps
    Server vs TFS cũ, connectionData vs profile API)."""
    for url, kind in connection_data_candidates(creds):
        ok, text = tfs_request(creds, url)
        if not ok:
            print(f"[fetch_fullname] {url} -> fail: {text[:200]}", file=sys.stderr)
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            print(f"[fetch_fullname] {url} -> non-JSON: {text[:200]}", file=sys.stderr)
            continue
        # connectionData: authenticatedUser.{customDisplayName, providerDisplayName,
        # properties.DisplayName.$value}
        user = data.get("authenticatedUser") if kind == "connection" else None
        if user is None:
            # profile API: top-level displayName
            name = data.get("displayName") or ""
            if name:
                return name
            continue
        properties = user.get("properties") or {}
        display_name_prop = properties.get("DisplayName") or {}
        # ConnectionData có khi bọc value trong $value (typed property); có khi
        # lại là string thẳng.
        if isinstance(display_name_prop, dict):
            prop_value = display_name_prop.get("$value") or ""
        else:
            prop_value = display_name_prop
        # Một số phiên bản TFS đặt name dưới key khác (Account, FullName, etc.).
        for key in ("Account", "FullName", "Name"):
            v = properties.get(key)
            if isinstance(v, dict):
                v = v.get("$value", "")
            if v and isinstance(v, str):
                prop_value = prop_value or v
        name = (
            user.get("customDisplayName")
            or user.get("providerDisplayName")
            or prop_value
            or (user.get("identity") or {}).get("DisplayName")
            or ""
        )
        if name:
            return name
    return ""


def fetch_account(creds):
    """Lấy account (DOMAIN\\user hoặc email) của user đăng nhập từ connectionData.
    Dùng khi login bằng PAT: token không kèm username nên phải hỏi TFS."""
    for url, kind in connection_data_candidates(creds):
        if kind != "connection":
            continue
        ok, text = tfs_request(creds, url)
        if not ok:
            print(f"[fetch_account] {url} -> fail: {text[:200]}", file=sys.stderr)
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            print(f"[fetch_account] {url} -> non-JSON: {text[:200]}", file=sys.stderr)
            continue
        return _parse_account(data)
    return ""


def _parse_account(data):
    try:
        user = data.get("authenticatedUser") or {}
        props = user.get("properties") or {}
        for key in ("Account", "LoginName", "Username"):
            v = props.get(key)
            if isinstance(v, dict):
                v = v.get("$value", "")
            if v and isinstance(v, str):
                return v
        return (user.get("identity") or {}).get("directoryAlias", "") or user.get("providerDisplayName", "")
    except AttributeError:
        return ""


def api_url(path, scope="project", project=None, collection=None):
    org = urllib.parse.quote(collection or CFG.get("org", ""), safe="")
    server = CFG.get("server", "")
    if scope == "server":
        return f"{server}/{path}"
    if scope == "collection":
        return f"{server}/{org}/{path}"
    proj = urllib.parse.quote(project or CFG.get("project", ""), safe="")
    return f"{server}/{org}/{proj}/{path}"


def login_ok(creds):
    """Kiểm tra credentials. Với PAT ưu tiên endpoint collection-scope: một số
    TFS on-prem ch PAT ở server-scope (root app IIS chỉ nhận Windows auth)
    nhưng nhận ở collection-scope. Trả (ok, text) để endpoint login hiển thị
    lý do TFS từ chối (401 scope, 404 version...)."""
    collection = creds.get("collection") or CFG.get("org", "")
    if creds.get("token") and collection:
        return tfs_request(creds, api_url(f"_apis/projects?api-version={API}", "collection", collection=collection))
    return tfs_request(creds, api_url(f"_apis/projectcollections?api-version={API}", "server"))


def fetch_collections(creds):
    """List collection của server TFS: {server}/_apis/projectcollections"""
    ok, text = tfs_request(creds, api_url(f"_apis/projectcollections?api-version={API}", "server"))
    if not ok:
        raise RuntimeError(text[:300])
    return json.loads(text).get("value", [])


def fetch_projects(creds, collection):
    """List project trong một collection: {server}/{collection}/_apis/projects"""
    ok, text = tfs_request(creds, api_url(f"_apis/projects?api-version={API}", "collection", collection=collection))
    if not ok:
        raise RuntimeError(text[:300])
    return json.loads(text).get("value", [])


def cur_collection(creds):
    return creds.get("collection", "")


def cur_project(creds):
    return creds.get("project", "")


def fetch_workitem_types(creds):
    """Danh sách work item type của project hiện tại:
    _apis/wit/workitemtypes -> [name].
    TFS version khác nhau nhận api-version khác nhau (states nhận 5.0-preview.1
    nhưng list types thì 404) -> thử lần lượt."""
    collection = cur_collection(creds)
    project = cur_project(creds)
    last = ""
    for ver in ("4.1", "5.0-preview.2", "5.0-preview", "4.1-preview", "5.1-preview", "6.0-preview", "7.0-preview"):
        ok, text = tfs_request(creds, api_url(f"_apis/wit/workitemtypes?api-version={ver}", project=project, collection=collection))
        if not ok:
            last = text[:300]
            continue
        try:
            value = json.loads(text).get("value", [])
        except json.JSONDecodeError:
            continue
        return [t.get("name", "") for t in value if t.get("name")]
    raise RuntimeError(last or "TFS không trả được work item types")


def fetch_states_of_type(creds, wtype):
    """State của 1 work item type: _apis/wit/workitemtypes/{type}/states
    -> list state thô của TFS ([{name, color, ...}])."""
    collection = cur_collection(creds)
    project = cur_project(creds)
    url = api_url(f"_apis/wit/workitemtypes/{urllib.parse.quote(wtype)}/states?api-version=5.0-preview.1", project=project, collection=collection)
    ok, text = tfs_request(creds, url)
    if not ok:
        raise RuntimeError(text[:300])
    return json.loads(text).get("value", [])


def fetch_state_colors(creds, wtypes=("Epic", "User Story", "Task", "Bug")):
    """Lấy màu state thật từ TFS: _apis/wit/workitemtypes/{type}/states -> {state: '#rrggbb'}"""
    colors = {}
    for wtype in wtypes:
        try:
            value = fetch_states_of_type(creds, wtype)
        except (RuntimeError, json.JSONDecodeError):
            continue
        for st in value:
            name, color = st.get("name", ""), st.get("color", "")
            if name and color:
                colors.setdefault(name, "#" + color.lstrip("#").zfill(6))
    return colors


def fetch_items(creds):
    collection = cur_collection(creds)
    project = cur_project(creds)
    ok, text = tfs_request(creds, api_url(f"_apis/wit/wiql?api-version={API}", project=project, collection=collection), {
        "query": "SELECT [System.Id] FROM WorkItems WHERE [System.AssignedTo] = @me ORDER BY [System.ChangedDate] DESC"
    })
    if not ok:
        raise RuntimeError(text[:300])
    ids = [w["id"] for w in json.loads(text).get("workItems", [])]
    items = []
    for i in range(0, len(ids), 200):
        chunk = ids[i : i + 200]
        ok, text = tfs_request(creds, api_url(f"_apis/wit/workitemsbatch?api-version={API}", project=project, collection=collection),
                     {"ids": chunk, "fields": FIELDS})
        if not ok:
            raise RuntimeError(text[:300])
        items.extend(json.loads(text).get("value", []))
    return items


def map_items_payload(creds, items):
    """raw workitemsbatch (FIELDS) -> list shape /api/items, kèm parentTitle
    (fetch riêng title parent còn thiếu)."""
    collection = cur_collection(creds)
    project = cur_project(creds)
    known = {it["id"] for it in items}
    parent_titles = {it["id"]: it["fields"].get("System.Title", "") for it in items}
    missing = [p for p in (it["fields"].get("System.Parent") for it in items) if p and p not in known]
    for pid in dict.fromkeys(missing):
        ok, text = tfs_request(creds, api_url(f"_apis/wit/workitems/{pid}?api-version={API}&fields=System.Id,System.Title", project=project, collection=collection))
        if not ok:
            continue
        try:
            parent_titles[pid] = json.loads(text).get("fields", {}).get("System.Title", "")
        except json.JSONDecodeError:
            continue
    return [
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
            # % hoàn thành theo percent_mode (work ưu tiên / state) — chat report
            "percent": compute_percent(it["fields"]),
        }
        for it in items
    ]


def _local_date(iso):
    """Chuyển timestamp UTC của TFS sang ngày theo giờ local của server.
    TFS trả "2026-08-20T17:23:46Z" — PR tạo 00:23 sáng 21/08 giờ VN.
    Cắt chuỗi thẳng sẽ ra ngày 20/08, lệch với ngày hiển thị trên web TFS.
    Lưu ý: server phải chạy chung múi giờ với người dùng (local dev)."""
    if not iso:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _wi_pr_links(creds):
    """Toàn bộ link WI <-> pull request của user đang login.

    Duyệt từ phía WI (batch relations) thay vì phía PR list: bỏ chuỗi call
    workitems theo từng PR. Trả (wi_ids, links, pr_repos):
    - links: wi_id -> set(pr_number)
    - pr_repos: pr_number -> repo guid (để fetch chi tiết PR).
    URL relation: vstfs:///Git/PullRequestId/{projGuid}%2F{repoGuid}%2F{prNumber}."""
    collection = cur_collection(creds)
    project = cur_project(creds)
    ok, text = tfs_request(creds, api_url(f"_apis/wit/wiql?api-version={API}", project=project, collection=collection),
        {"query": "SELECT [System.Id] FROM WorkItems WHERE [System.AssignedTo] = @me ORDER BY [System.ChangedDate] DESC"})
    if not ok:
        raise RuntimeError(text[:300])
    wi_ids = [w["id"] for w in json.loads(text).get("workItems", [])]

    links = {}
    pr_repos = {}
    for i in range(0, len(wi_ids), 200):
        chunk = wi_ids[i : i + 200]
        ok, text = tfs_request(creds, api_url(f"_apis/wit/workitemsbatch?api-version={API}", project=project, collection=collection),
                     {"ids": chunk, "$expand": "relations"})
        if not ok:
            raise RuntimeError(text[:300])
        for wi in json.loads(text).get("value", []):
            for rel in wi.get("relations", []):
                attrs = rel.get("attributes") or {}
                if rel.get("rel") != "ArtifactLink" or attrs.get("name") != "Pull Request":
                    continue
                # tách projGuid/repoGuid/prNumber khỏi url artifact (đã unquote)
                parts = urllib.parse.unquote(rel.get("url", "")).split("/")
                try:
                    repo_guid, pr_number = parts[-2], int(parts[-1])
                except (IndexError, ValueError):
                    continue
                links.setdefault(wi["id"], set()).add(pr_number)
                pr_repos[pr_number] = repo_guid
    return wi_ids, links, pr_repos


def fetch_pr_workitems(creds, date_from, date_to=None):
    """Work item của user thuộc pull request ĐƯỢC TẠO (bởi chính user) trong
    khoảng ngày [from, to]. Với mỗi PR có link từ WI của user, lấy chi tiết PR
    (repo guid có sẵn trong url relation) rồi check creationDate + createdBy.
    Trả (wi_ids, pr_numbers)."""
    date_to = date_to or date_from
    collection = cur_collection(creds)
    user = (creds.get("user") or "").split("\\")[-1].strip().lower()

    _, links, pr_repos = _wi_pr_links(creds)

    # PR tạo trong range + đúng creator
    ok_prs = set()
    for pr_number, repo_guid in pr_repos.items():
        url = api_url(f"_apis/git/repositories/{repo_guid}/pullrequests/{pr_number}?api-version={API}",
                      "collection", collection=collection)
        ok, text = tfs_request(creds, url)
        if not ok:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        local = _local_date(data.get("creationDate"))
        cb = data.get("createdBy") or {}
        uname = (cb.get("uniqueName") if isinstance(cb, dict) else "") or ""
        if local and date_from <= local <= date_to and uname.split("\\")[-1].strip().lower() == user:
            ok_prs.add(pr_number)

    ids = {wi for wi, prs in links.items() if prs & ok_prs}
    return sorted(ids), sorted(ok_prs)


# cache danh sách PR theo (collection, project, creator) — tránh gọi TFS chuỗi
# call mỗi lần MultiSelect lazy load trang tiếp
_PR_CACHE = {}
_PR_CACHE_TTL = 60  # giây
_PR_PAGE = 1000     # $top mỗi call TFS


def fetch_user_id(creds):
    """GUID của user đăng nhập (từ connectionData) — searchCriteria.creatorId
    của pull requests yêu cầu id, không nhận username."""
    for url, kind in connection_data_candidates(creds):
        if kind != "connection":
            continue
        ok, text = tfs_request(creds, url)
        if not ok:
            continue
        try:
            return (json.loads(text).get("authenticatedUser") or {}).get("id", "")
        except json.JSONDecodeError:
            continue
    return ""


def _fetch_prs_all(creds):
    """Pull request active + completed của project DO CHÍNH user đăng nhập
    tạo (bỏ abandoned + PR người khác), mới nhất trước. TFS không nhận nhiều
    status trong 1 call nên fetch từng status, $skip/$top hết trang; merge +
    sort lại. Kết quả cache theo TTL."""
    collection = cur_collection(creds)
    project = cur_project(creds)
    creator = fetch_user_id(creds)
    user = (creds.get("user") or "").split("\\")[-1].strip().lower()
    key = (collection, project, creator or user)
    cached = _PR_CACHE.get(key)
    if cached and time.time() - cached["ts"] < _PR_CACHE_TTL:
        return cached["prs"]

    creator_q = f"&searchCriteria.creatorId={creator}" if creator else ""
    raw = {}
    for status in ("active", "completed"):
        skip = 0
        while True:
            url = api_url(f"_apis/git/pullrequests?api-version={API}&searchCriteria.status={status}{creator_q}&$top={_PR_PAGE}&$skip={skip}",
                          project=project, collection=collection)
            ok, text = tfs_request(creds, url)
            if not ok:
                raise RuntimeError(text[:300])
            page = json.loads(text).get("value", [])
            for p in page:
                pid = p.get("pullRequestId")
                if pid is None:
                    continue
                # không lấy được creatorId thì lọc createdBy sau fetch
                if not creator_q:
                    cb = p.get("createdBy") or {}
                    uname = (cb.get("uniqueName") if isinstance(cb, dict) else "") or ""
                    if uname.split("\\")[-1].strip().lower() != user:
                        continue
                raw[pid] = p
            if len(page) < _PR_PAGE:
                break
            skip += _PR_PAGE
    out = []
    for p in sorted(raw.values(), key=lambda x: x.get("creationDate") or "", reverse=True):
        local = _local_date(p.get("creationDate"))
        day = f"{local[8:10]}/{local[5:7]}/{local[:4]}" if local else "Không rõ ngày"
        title = (p.get("title") or "").strip()
        # iso (yyyy-mm-dd) để filter theo ngày tạo PR; day chỉ để hiển thị
        out.append({"value": p["pullRequestId"], "label": f"#{p['pullRequestId']} | {title}", "day": day, "iso": local,
                    "repo": (p.get("repository") or {}).get("id", "")})
    _PR_CACHE[key] = {"ts": time.time(), "prs": out}
    return out


def fetch_pullrequests(creds, skip=0, top=50, date_from="", date_to=""):
    """Trang [skip, skip+top) của danh sách PR active + completed đã sort.
    from/to (yyyy-mm-dd, tùy chọn) lọc theo ngày tạo PR."""
    prs = _fetch_prs_all(creds)
    if date_from:
        prs = [p for p in prs if p.get("iso") and p["iso"] >= date_from]
    if date_to:
        prs = [p for p in prs if p.get("iso") and p["iso"] <= date_to]
    return prs[skip : skip + top]


def fetch_items_by_prs(creds, pr_numbers):
    """Work item ĐƯỢC ADD vào các pull request trong pr_numbers — lấy phía PR
    (repo-scoped workitems endpoint) nên gồm cả item KHÔNG gán cho user
    (User Story người khác...), khác với _wi_pr_links chỉ thấy WI của user.
    Repo guid lấy từ cache danh sách PR. Trả (wi_ids, raw_items)."""
    wanted = set(pr_numbers)
    collection = cur_collection(creds)
    project = cur_project(creds)
    pr_repos = {p["value"]: p["repo"] for p in _fetch_prs_all(creds) if p.get("repo")}

    ids = set()
    for pr in sorted(wanted):
        repo_guid = pr_repos.get(pr)
        if not repo_guid:
            continue
        url = api_url(f"_apis/git/repositories/{repo_guid}/pullrequests/{pr}/workitems?api-version={API}",
                      "collection", collection=collection)
        ok, text = tfs_request(creds, url)
        if not ok:
            continue
        try:
            for w in json.loads(text).get("value", []):
                ids.add(int(w["id"]))
        except json.JSONDecodeError:
            continue

    items = []
    ordered = sorted(ids)
    for i in range(0, len(ordered), 200):
        chunk = ordered[i : i + 200]
        ok, text = tfs_request(creds, api_url(f"_apis/wit/workitemsbatch?api-version={API}", project=project, collection=collection),
                     {"ids": chunk, "fields": FIELDS})
        if not ok:
            continue
        items.extend(json.loads(text).get("value", []))
    return ordered, items


def _norm_rules(raw):
    """Chuẩn hóa list rule: {"type", "state", "by", "pick"}.
    type rỗng = mọi loại; by = list con của ("me", "other") — ai chuyển state
    mới được tính ngày (rỗng = cả hai); pick = "first" (lần đầu vào state) hay
    "last" (lần cuối — item active nhiều lần)."""
    out = []
    if isinstance(raw, list):
        for r in raw:
            if not isinstance(r, dict):
                continue
            t = str(r.get("type") or "").strip()
            s = str(r.get("state") or "").strip()
            if not s:
                continue
            by = [x for x in (r.get("by") or []) if x in ("me", "other")]
            pick = "last" if r.get("pick") == "last" else "first"
            out.append({"type": t, "state": s, "by": by or ["me", "other"], "pick": pick})
    return out


def lark_start_rules():
    """Rules trạng thái bắt đầu từ config (xem _norm_rules). lark_state cũ
    (1 state cho mọi type) tự nâng cấp thành 1 rule type rỗng."""
    rules = _norm_rules(CFG.get("lark_rules"))
    if not rules:
        legacy = (CFG.get("lark_state") or "").strip()
        if legacy:
            rules = [{"type": "", "state": legacy, "by": ["me", "other"], "pick": "first"}]
    return rules


def lark_end_rules():
    """Rules trạng thái kết thúc: End date bảng Lark = ngày item vào state.
    Cùng shape với lark_start_rules; chưa có dạng cũ để nâng cấp."""
    return _norm_rules(CFG.get("lark_end_rules"))


def default_settings():
    """Trạng thái Cài đặt dựng từ default.json (cho nút Reset). Cùng shape
    với GET /api/settings; thiếu/rác file thì về mặc định code."""
    try:
        with open(DEFAULTS_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        d = {}
    if d.get("percent_mode") not in ("work", "state"):
        d["percent_mode"] = "work"
    if not isinstance(d.get("fullname_fallback_user"), bool):
        d["fullname_fallback_user"] = True
    rules = _norm_rules(d.get("lark_rules"))
    if not rules and (d.get("lark_state") or "").strip():
        rules = [{"type": "", "state": d["lark_state"].strip(), "by": ["me", "other"], "pick": "first"}]
    return {
        "server": d.get("server", ""),
        "org": d.get("org", ""),
        "fullname": d.get("fullname", ""),
        "larkRules": rules,
        "larkEndRules": _norm_rules(d.get("lark_end_rules")),
        "percentMode": d["percent_mode"],
        "fullnameFallbackUser": d["fullname_fallback_user"],
    }


def _changed_by_user(cb, user):
    """ChangedBy field từ TFS có thể là dict (uniqueName) hoặc string.
    So username bỏ domain (DOMAIN\\user), case-insensitive."""
    if isinstance(cb, dict):
        u = str(cb.get("uniqueName") or cb.get("displayName") or "")
    else:
        u = str(cb or "")
    u = u.split("\\")[-1].strip().lower()
    me = str(user or "").split("\\")[-1].strip().lower()
    return bool(u) and bool(me) and u == me


def fetch_dates_for_rules(creds, ids, rules):
    """id -> ngày (yyyy-mm-dd) item vào state khớp RULES.

    rules: [{"type", "state", "by", "pick"}] (type rỗng áp mọi type; by = ai
    chuyển state mới được tính; pick = "first"/"last" — lần đầu hay lần cuối
    vào state). Mỗi item: lấy type (1 call workitemsbatch cho cả list), lọc
    rule khớp type; quét revisions, mỗi rule lấy match theo pick của nó; giữa
    nhiều rule khớp thì revision sớm nhất thắng. Ngày theo giờ local.
    Item lỗi / không khớp rule thì không có trong kết quả — caller tự fallback."""
    if not rules or not ids:
        return {}
    collection = cur_collection(creds)
    project = cur_project(creds)
    # type từng item để chọn rule theo type
    id_types = {}
    for i in range(0, len(ids), 200):
        chunk = ids[i : i + 200]
        ok, text = tfs_request(creds, api_url(f"_apis/wit/workitemsbatch?api-version={API}", project=project, collection=collection),
                     {"ids": chunk, "fields": ["System.Id", "System.WorkItemType"]})
        if not ok:
            continue
        try:
            value = json.loads(text).get("value", [])
        except json.JSONDecodeError:
            continue
        for it in value:
            id_types[it["id"]] = it["fields"].get("System.WorkItemType", "")
    out = {}
    for wid in ids:
        itype = id_types.get(wid, "")
        applicable = [r for r in rules if not r.get("type") or r.get("type") == itype]
        if not applicable:
            continue
        ok, text = tfs_request(creds, api_url(f"_apis/wit/workitems/{wid}/revisions?api-version={API}",
                                              project=project, collection=collection))
        if not ok:
            continue
        try:
            revs = json.loads(text).get("value", [])
        except json.JSONDecodeError:
            continue
        # mỗi rule: list (rev_index, ngày) khớp state + by; rồi chọn theo pick
        candidates = []
        for r in applicable:
            hits = []
            prev = None
            for idx, rev in enumerate(revs):  # revisions theo thứ tự thời gian
                f = rev.get("fields") or {}
                st = f.get("System.State")
                # chỉ tính revision CHUYỂN sang state rule (prev khác state) —
                # revision sau đó chỉ sửa field khác, state giữ nguyên, không tính
                if st != prev and st == r["state"]:
                    is_me = _changed_by_user(f.get("System.ChangedBy"), creds.get("user"))
                    if ("me" in r["by"] and is_me) or ("other" in r["by"] and not is_me):
                        local = _local_date(f.get("System.ChangedDate"))
                        if local:
                            hits.append((idx, local))
                prev = st
            if hits:
                candidates.append(hits[-1] if r.get("pick") == "last" else hits[0])
        if candidates:
            out[wid] = min(candidates)[1]
    return out


def cell(s):
    return str(s or "").replace("|", "\\|").replace("\n", " ").strip()


# trạng thái coi là hoàn tất khi tính % theo trạng thái
DONE_STATES = {"closed", "done", "completed", "resolved", "removed", "finished", "finish"}


def _state_percent(state):
    """% theo trạng thái: trạng thái kết thúc = 100%, còn lại 0%."""
    return 100 if str(state or "").strip().lower() in DONE_STATES else 0


def _work_percent(f):
    """% theo Remaining/Completed work. Trả None khi item không có số work
    (cả 2 field null) — caller fallback sang trạng thái."""
    completed = f.get("Microsoft.VSTS.Scheduling.CompletedWork")
    remaining = f.get("Microsoft.VSTS.Scheduling.RemainingWork")
    if completed is None and remaining is None:
        return None
    if completed is None:
        return 0
    total = (completed or 0) + (remaining or 0)
    return round(completed / total * 100) if total > 0 else 100


def compute_percent(f):
    """% hoàn thành của 1 item (fields dict) hiển thị trong report.
    percent_mode = "work": ưu tiên Remaining/Completed work, item không có số
    work thì theo trạng thái; "state": luôn theo trạng thái."""
    state = f.get("System.State")
    if CFG.get("percent_mode", "work") == "state":
        return _state_percent(state)
    work = _work_percent(f)
    return work if work is not None else _state_percent(state)


def render_chat(today_items, next_items, report_date, fullname, user):
    """Phần chat — format theo applications/public/templetes/"""
    lines = [
        f"*Báo cáo nhân sự* {report_date.strftime('%d/%m/%Y')}",
        f"*Nhân sự:* {fullname or (user if CFG.get('fullname_fallback_user', True) else '')}",
        "*Công việc:*",
    ]
    for it in today_items:
        f = it["fields"]
        lines.append(f"- {cell(f.get('System.WorkItemType'))} {it['id']}: {cell(f.get('System.Title'))} ({compute_percent(f)}%)")
    if not today_items:
        lines.append("- ...")
    lines.append("*Công việc ngày tiếp theo:*")
    for it in next_items:
        f = it["fields"]
        lines.append(f"- {cell(f.get('System.WorkItemType'))} {it['id']}: {cell(f.get('System.Title'))} ({compute_percent(f)}%)")
    if not next_items:
        lines.append("- ...")
    lines += ["*Vấn đề:*", "- None"]
    return "\n".join(lines)


def render_lark(items, report_date, collection, project, next_ids=None, start_dates=None, end_dates=None):
    """Phần lark — format theo applications/public/templetes/"""
    # Start/End date Lark theo format yyyy-mm-dd
    today_str = report_date.strftime("%Y-%m-%d")
    next_str = (report_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    next_ids = next_ids or set()
    # start/end_dates: {id: "yyyy-mm-dd"} từ fetch_dates_for_rules theo rules
    # cấu hình. Ưu tiên ngày thật item vào trạng thái; không có thì fallback
    # logic cũ (start), end để trống.
    start_dates = start_dates or {}
    end_dates = end_dates or {}
    lines = [
        "| Status | Start date | End date | OT | Note | Type | Task ID | Task Name | Task Link |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    base = f"{CFG['server']}/{collection}/{project}/_workitems/edit/"

    for it in items:
        f = it["fields"]
        real = start_dates.get(it["id"])
        if real:
            start = real  # đã là yyyy-mm-dd
        # Item "mới" (chọn cho ngày tiếp theo) chưa có start date hôm nay —
        # ghi ngày mai để Lark không trùng hàng với today_items.
        else:
            start = next_str if it["id"] in next_ids else today_str
        end = end_dates.get(it["id"]) or ""
        lines.append(
            f"| {cell(f.get('System.State'))} | {start} | {end} |  |  "
            f"| {cell(f.get('System.WorkItemType'))} | {it['id']} "
            f"| {cell(f.get('System.Title'))} | {base}{it['id']} |"
        )
    return "\n".join(lines)


def render_report(today_items, next_items, report_date, fullname, user, collection, project, start_dates=None, end_dates=None):
    # lark: hợp nhất 2 nhóm, bỏ lặp item
    seen, merged = set(), []
    for it in today_items + next_items:
        if it["id"] not in seen:
            seen.add(it["id"])
            merged.append(it)
    # next_ids để render_lark phân biệt item mới (start = ngày mai) vs today (start = hôm nay)
    next_ids = {it["id"] for it in next_items}
    return render_chat(today_items, next_items, report_date, fullname, user) + "\n\n" + render_lark(merged, report_date, collection, project, next_ids=next_ids, start_dates=start_dates, end_dates=end_dates) + "\n"


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
            if k == SESSION_COOKIE and v:
                return read_session_token(v)
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
                "fullname": creds.get("fullname") or CFG.get("fullname", ""),
                "collection": cur_collection(creds),
                "project": cur_project(creds),
            })
        elif self.path == "/api/whoami-debug":
            # Debug endpoint: trả raw response từ TFS connectionData để xem shape thật.
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            ok, text = tfs_request(creds, connection_data_candidates(creds)[0][0])
            self._send({"ok": ok, "raw": text[:2000], "creds_fullname": creds.get("fullname", "")})
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
            except RuntimeError as e:
                # PAT trên TFS on-prem bị chặn server-scope -> trả collection đã biết
                known = creds.get("collection") or CFG.get("org", "")
                if not known:
                    self._send({"error": str(e)}, 502)
                    return
                collections = [{"id": known, "name": known}]
            self._send({"collections": collections})
        elif self.path == "/api/ui-settings":
            # Không yêu cầu đăng nhập: prefs chỉ là whitelist key UI, không nhạy
            # cảm — user đổi dark mode ở trang login cũng cần lưu được.
            self._send(CFG.get("ui") or {})
        elif self.path == "/api/settings":
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            self._send({
                "server": CFG.get("server", ""),
                "org": CFG.get("org", ""),
                "fullname": CFG.get("fullname", ""),
                "larkRules": lark_start_rules(),
                "larkEndRules": lark_end_rules(),
                # cách tính % trong report: "work" / "state"
                "percentMode": CFG.get("percent_mode", "work"),
                # report thiếu display name thì dùng username thay thế?
                "fullnameFallbackUser": bool(CFG.get("fullname_fallback_user", True)),
                # PAT không trả về client — chỉ báo có/không
                "hasToken": bool((CFG.get("token") or "").strip()),
                # trạng thái mặc định từ default.json — cho nút Reset
                "defaults": default_settings(),
            })
        elif self.path.startswith("/api/workitemtypes"):
            # Danh sách work item type của project hiện tại (cho Cài đặt)
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            if not cur_collection(creds) or not cur_project(creds):
                self._send({"error": "Chưa chọn dự án"}, 400)
                return
            try:
                types = fetch_workitem_types(creds)
            except RuntimeError as e:
                print(f"[workitemtypes] {e}", file=sys.stderr)
                self._send({"error": str(e)}, 502)
                return
            self._send({"types": types})
        elif self.path.startswith("/api/workitemstates"):
            # Danh sách state của 1 work item type (cho Cài đặt)
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            if not cur_collection(creds) or not cur_project(creds):
                self._send({"error": "Chưa chọn dự án"}, 400)
                return
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            wtype = (qs.get("type") or [""])[0].strip()
            if not wtype:
                self._send({"error": "Thiếu tham số type"}, 400)
                return
            try:
                raw = fetch_states_of_type(creds, wtype)
            except RuntimeError as e:
                print(f"[workitemstates] {e}", file=sys.stderr)
                self._send({"error": str(e)}, 502)
                return
            except json.JSONDecodeError:
                self._send({"error": "TFS trả dữ liệu không hợp lệ"}, 502)
                return
            self._send({"states": [s.get("name", "") for s in raw if s.get("name")]})
        elif self.path.startswith("/api/state-dates"):
            # Start date bảng Lark theo trạng thái cấu hình (lark_state):
            # trả ngày item vào trạng thái đó cho các id được chọn.
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            start_rules = lark_start_rules()
            end_rules = lark_end_rules()
            if not start_rules and not end_rules:
                self._send({"startDates": {}, "endDates": {}})
                return
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            raw = (qs.get("ids") or [""])[0]
            try:
                ids = [int(x) for x in raw.split(",") if x.strip()]
            except ValueError:
                self._send({"error": "ids không hợp lệ (danh sách số, phân tách dấu phẩy)"}, 400)
                return
            if not ids:
                self._send({"startDates": {}, "endDates": {}})
                return
            try:
                start_d = fetch_dates_for_rules(creds, ids, start_rules) if start_rules else {}
                end_d = fetch_dates_for_rules(creds, ids, end_rules) if end_rules else {}
            except RuntimeError as e:
                self._send({"error": str(e)}, 502)
                return
            # key JSON phải là string
            self._send({
                "startDates": {str(k): v for k, v in start_d.items()},
                "endDates": {str(k): v for k, v in end_d.items()},
            })
        elif self.path.startswith("/api/prs"):
            # Danh sách PR cho MultiSelect "Item theo PR": phân trang skip/top
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            if not cur_collection(creds) or not cur_project(creds):
                self._send({"error": "Chưa chọn dự án"}, 400)
                return
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                skip = max(0, int((qs.get("skip") or ["0"])[0]))
                top = min(200, max(1, int((qs.get("top") or ["50"])[0])))
            except ValueError:
                self._send({"error": "skip/top không hợp lệ"}, 400)
                return
            # from/to (yyyy-mm-dd, tùy chọn): lọc option PR theo ngày tạo
            date_from = (qs.get("from") or [""])[0].strip()
            date_to = (qs.get("to") or [""])[0].strip()
            if date_from or date_to:
                try:
                    datetime.datetime.strptime(date_from or date_to, "%Y-%m-%d").date()
                    datetime.datetime.strptime(date_to or date_from, "%Y-%m-%d").date()
                except ValueError:
                    self._send({"error": "Ngày không hợp lệ (yyyy-mm-dd)"}, 400)
                    return
            try:
                prs = fetch_pullrequests(creds, skip, top, date_from, date_to)
            except RuntimeError as e:
                self._send({"error": str(e)}, 502)
                return
            # fewer than top = hết trang — frontend dừng lazy load
            self._send({"prs": prs, "hasMore": len(prs) >= top})
        elif self.path.startswith("/api/pr-items"):
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            if not cur_collection(creds) or not cur_project(creds):
                self._send({"error": "Chưa chọn dự án"}, 400)
                return
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            # prs = danh sách số PR (comma): item theo PR (bỏ qua ngày)
            prs_raw = (qs.get("prs") or [""])[0].strip()
            if prs_raw:
                try:
                    pr_numbers = [int(x) for x in prs_raw.split(",") if x.strip()]
                except ValueError:
                    self._send({"error": "Danh sách PR không hợp lệ"}, 400)
                    return
                if not pr_numbers:
                    self._send({"error": "Danh sách PR rỗng"}, 400)
                    return
                try:
                    ids, raw_items = fetch_items_by_prs(creds, pr_numbers)
                except RuntimeError as e:
                    self._send({"error": str(e)}, 502)
                    return
                # items đầy đủ field để frontend hiển thị cả WI không gán user
                self._send({"ids": ids, "prs": pr_numbers, "items": map_items_payload(creds, raw_items)})
                return
            # from/to = khoảng ngày; date = dạng cũ (1 ngày) giữ tương thích
            date_from = (qs.get("from") or [""])[0].strip() or (qs.get("date") or [""])[0].strip()
            date_to = (qs.get("to") or [""])[0].strip() or date_from
            try:
                datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
                datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
            except ValueError:
                self._send({"error": "Ngày không hợp lệ (yyyy-mm-dd)"}, 400)
                return
            try:
                ids, prs = fetch_pr_workitems(creds, date_from, date_to)
            except RuntimeError as e:
                self._send({"error": str(e)}, 502)
                return
            self._send({"ids": ids, "prs": prs})
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
                out = map_items_payload(creds, items)
                self._send({
                    "items": out,
                    "fullname": creds.get("fullname") or CFG.get("fullname", ""),
                    # report thiếu display name thì dùng username thay thế?
                    "fullnameFallbackUser": bool(CFG.get("fullname_fallback_user", True)),
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
            token = (body.get("token") or "").strip()
            remember = bool(body.get("remember"))
            if token:
                # PAT: username không cần — TFS tự nhận diện từ token. Cần biết
                # collection (form hoặc config) vì server-scope thường ch PAT.
                collection = (body.get("collection") or "").strip() or CFG.get("org", "")
                creds = {"user": "", "password": "", "token": token, "collection": collection}
                ok, text = login_ok(creds)
                if not ok:
                    # text là phản hồi lỗi gốc từ TFS (401/404/...) — giúp phân biệt
                    # token sai vs server không nhận Basic auth.
                    print(f"[login:token] TFS từ chối: {text[:300]}", file=sys.stderr)
                    hint = "" if collection else " — thử điền tên Collection"
                    self._send({"error": f"TFS từ chối token: {text[:200]}{hint}"}, 401)
                    return
                user = fetch_account(creds) or CFG.get("user", "")
                creds["user"] = user
                # "Ghi nhớ đăng nhập": lưu PAT vào config để các lần sau dùng lại;
                # bỏ tick -> xóa PAT cũ nếu có (đối xứng với remember của password).
                save_config_token(token if remember else "")
            else:
                creds = {"user": user, "password": password, "token": ""}
                if not user or not password or not login_ok(creds)[0]:
                    self._send({"error": "Sai username hoặc mật khẩu"}, 401)
                    return
            creds["remember"] = remember
            # Lấy display name thật từ TFS; fallback về config nếu endpoint lỗi.
            # Lưu vào creds để /api/me và report sau này dùng lại.
            creds["fullname"] = fetch_fullname(creds) or CFG.get("fullname", "")
            if not creds["fullname"]:
                # Log khi không lấy được — dev xem stderr để biết TFS trả shape gì.
                print(f"[login] fetch_fullname rỗng cho user={user!r}", file=sys.stderr)
            token = make_session_token(creds)
            cookie = f"{SESSION_COOKIE}={token}; HttpOnly; Path=/; SameSite=Lax"
            if creds["remember"]:
                cookie += f"; Max-Age={SESSION_TTL_REMEMBER}"
            self._send({"ok": True, "user": user, "fullname": creds["fullname"]}, set_cookie=cookie)
        elif parsed.path == "/api/logout":
            self._send({"ok": True}, set_cookie=f"{SESSION_COOKIE}=; HttpOnly; Path=/; Max-Age=0")
        elif parsed.path == "/api/settings":
            creds = self._session()
            if not creds:
                self._send({"error": "Chưa đăng nhập"}, 401)
                return
            body = self._body()
            server = (body.get("server") or "").strip().rstrip("/")
            org = (body.get("org") or "").strip()
            fullname = (body.get("fullname") or "").strip()
            lark_state = (body.get("larkState") or "").strip()
            lark_type = (body.get("larkType") or "").strip()
            # larkRules/larkEndRules: list {"type", "state", "by"} từ list box
            lark_rules = _norm_rules(body.get("larkRules"))
            lark_end_rules_v = _norm_rules(body.get("larkEndRules"))
            # trạng thái bắt đầu và kết thúc của cùng 1 loại phải khác nhau
            # (type rỗng "Mọi loại" coi như trùng với mọi loại)
            conflict = None
            for s in lark_rules:
                for e in lark_end_rules_v:
                    if s["state"] == e["state"] and (not s["type"] or not e["type"] or s["type"] == e["type"]):
                        conflict = s["type"] or e["type"] or "Mọi loại"
                        break
                if conflict:
                    break
            if conflict:
                self._send({"error": f"Trạng thái bắt đầu và kết thúc của \"{conflict}\" trùng nhau — phải khác nhau"}, 400)
                return
            if not server.startswith(("http://", "https://")):
                self._send({"error": "Server URL phải bắt đầu bằng http:// hoặc https://"}, 400)
                return
            # cách tính %: "work" (ưu tiên Remaining/Completed) hay "state"
            percent_mode = body.get("percentMode") or "work"
            if percent_mode not in ("work", "state"):
                self._send({"error": "percentMode không hợp lệ (work/state)"}, 400)
                return
            # thiếu display name thì report dùng username thay thế?
            fallback_user = bool(body.get("fullnameFallbackUser", True))
            fields = {
                "server": server, "org": org, "fullname": fullname,
                # có list rules thì xóa key cũ để không áp 2 lần; key global
                # changed_by cũ không dùng nữa — rule tự mang "by"
                "lark_rules": lark_rules, "lark_state": "", "lark_type": "",
                "lark_end_rules": lark_end_rules_v,
                "lark_start_changed_by": None, "lark_end_changed_by": None,
                "percent_mode": percent_mode,
                "fullname_fallback_user": fallback_user,
            }
            if not update_config(fields):
                self._send({"error": "Không ghi được file config"}, 500)
                return
            CFG.update({k: v for k, v in fields.items() if v is not None})
            self._send({"ok": True, **{k: v for k, v in fields.items() if v is not None}})
        elif parsed.path == "/api/ui-settings":
            # Không yêu cầu đăng nhập (xem lý do ở GET /api/ui-settings)
            body = self._body()
            if not isinstance(body, dict):
                self._send({"error": "Body phải là object"}, 400)
                return
            # Chỉ giữ key dạng UI pref, bỏ key lạ
            allowed = {"ripple", "darkTheme", "inputStyle", "menuMode", "theme", "scale"}
            ui = {k: v for k, v in body.items() if k in allowed}
            if not ui:
                self._send({"error": "Không có field hợp lệ"}, 400)
                return
            merged = dict(CFG.get("ui") or {})
            merged.update(ui)
            if not update_config({"ui": merged}):
                self._send({"error": "Không ghi được file config"}, 500)
                return
            CFG["ui"] = merged
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
            # Collection list có thể không lấy được khi PAT bị chặn server-scope
            # -> bỏ qua validate collection, chỉ validate project (collection-scope).
            try:
                valid_collections = {c.get("name") for c in fetch_collections(creds)}
            except RuntimeError:
                valid_collections = None
            if valid_collections is not None and collection not in valid_collections:
                self._send({"error": "Collection không hợp lệ"}, 400)
                return
            try:
                valid_projects = {p.get("name") for p in fetch_projects(creds, collection)}
            except RuntimeError as e:
                self._send({"error": str(e)}, 502)
                return
            if project not in valid_projects:
                self._send({"error": "Dự án không hợp lệ"}, 400)
                return
            creds["collection"] = collection
            creds["project"] = project
            # Re-issue cookie vì session stateless: collection/project nằm trong token
            token = make_session_token(creds)
            cookie = f"{SESSION_COOKIE}={token}; HttpOnly; Path=/; SameSite=Lax"
            if creds.get("remember"):
                cookie += f"; Max-Age={SESSION_TTL_REMEMBER}"
            self._send({"ok": True, "collection": collection, "project": project}, set_cookie=cookie)
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
            # rules start/end cấu hình -> Start/End date = ngày item vào trạng thái khớp
            all_ids = sorted(ids | next_ids)
            start_dates = fetch_dates_for_rules(creds, all_ids, lark_start_rules())
            end_dates = fetch_dates_for_rules(creds, all_ids, lark_end_rules())
            report = render_report(today_items, next_items, report_date, body.get("fullname"), creds["user"], collection, project, start_dates=start_dates, end_dates=end_dates)
            # Không ghi disk: trả report trong JSON, frontend tự copy/tải file.
            self._send({"ok": True, "count": len(today_items) + len(next_items), "report": report})
        else:
            self._send({"error": "not found"}, 404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    host = os.environ.get("HOST", "127.0.0.1")
    url = f"http://{host}:{port}"
    print(f"Web UI: {url}   (Ctrl+C để dừng)")
    http.server.ThreadingHTTPServer((host, port), Handler).serve_forever()