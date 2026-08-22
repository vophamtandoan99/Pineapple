#!/usr/bin/env python3
"""Interactive TFS work item report.

Flow: load config -> ask user/pass if not saved -> login -> list all my work
items -> user picks IDs -> write report to <yyyy>/<m>/<d>.md.

Setup:    run report init     (asks fullname, server, user/pass, saves config.json)
Daily:    run report          (uses config; asks password only if not saved)

Config lives next to this script as config.json (chmod 600).
Saving the password is optional — it is stored in PLAINTEXT.
"""

import datetime
import getpass
import json
import os
import subprocess
import sys

try:
    import termios
    import tty
    HAS_TTY = True
except ImportError:
    HAS_TTY = False


def menu(title, options):
    """Arrow-key menu: ↑/↓ move, Enter/digit select. Returns index.
    Falls back to numeric prompt when stdin is not a TTY."""
    if not HAS_TTY or not sys.stdin.isatty():
        print(title)
        for i, o in enumerate(options, 1):
            print(f"{i}. {o}")
        while True:
            raw = input("Chọn: ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return int(raw) - 1
            print(f"Chọn 1-{len(options)}.")
    idx = 0
    print(title)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)

    def draw(first):
        if not first:
            sys.stdout.write(f"\x1b[{len(options)}F")  # cursor back to first option
        for i, o in enumerate(options):
            mark = "❯" if i == idx else " "
            sys.stdout.write(f"\r\x1b[2K {mark} {o}\n")
        sys.stdout.flush()

    try:
        tty.setraw(fd)
        draw(True)
        while True:
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    idx = (idx - 1) % len(options)
                elif seq == "[B":
                    idx = (idx + 1) % len(options)
            elif ch in ("\r", "\n"):
                break
            elif ch == "\x03":
                raise KeyboardInterrupt
            elif ch.isdigit() and 1 <= int(ch) <= len(options):
                idx = int(ch) - 1
                break
            draw(False)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    print(f"→ {options[idx]}")
    return idx

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
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


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
    os.chmod(CONFIG_PATH, 0o600)


def init():
    print("=== Thiết lập ban đầu (config.json) ===\n")
    cfg = load_config() or {}
    cfg["fullname"] = input(f'Họ tên đầy đủ [{cfg.get("fullname","")}]: ').strip() or cfg.get("fullname", "")
    cfg["server"] = (input(f'TFS server [{cfg.get("server","https://tfs.tmtco.dev")}]: ').strip()
                     or cfg.get("server", "https://tfs.tmtco.dev")).rstrip("/")
    cfg["org"] = input(f'Collection/Org [{cfg.get("org","TMTAICollection")}]: ').strip() or cfg.get("org", "TMTAICollection")
    cfg["project"] = input(f'Project [{cfg.get("project","Team_AI")}]: ').strip() or cfg.get("project", "Team_AI")
    cfg["user"] = input(f'Username [{cfg.get("user","")}]: ').strip() or cfg.get("user", "")
    save_pass = input("Lưu mật khẩu vào config (plaintext,Enter = không lưu)? [y/N]: ").strip().lower() == "y"
    if save_pass:
        cfg["password"] = getpass.getpass("Mật khẩu: ")
    else:
        cfg.pop("password", None)
    save_config(cfg)
    print(f"\nĐã lưu: {CONFIG_PATH}")
    if not save_pass:
        print("Mật khẩu sẽ được hỏi mỗi lần chạy.")


def logout():
    cfg = load_config() or {}
    removed = False
    if cfg.pop("password", None) is not None:
        save_config(cfg)
        removed = True
        print("Đã xóa mật khẩu khỏi config.json.")
    else:
        print("Config không lưu mật khẩu.")
    if os.environ.pop("TFS_PASS", None):
        print("Đã xóa TFS_PASS khỏi env.")
    if not removed:
        print("(Không có gì cần xóa trong config.)")


CFG = load_config() or {}
USER = None
PASSWORD = None


def login_ok():
    url = f'{CFG["server"]}/{CFG["org"]}/_apis/projects?api-version={API}'
    cmd = [
        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
        "--max-time", "30", "--ntlm", "-u", f"{USER}:{PASSWORD}", url,
    ]
    return subprocess.run(cmd, capture_output=True).stdout.decode().strip() == "200"


def ensure_credentials():
    global USER, PASSWORD
    USER = CFG.get("user") or os.environ.get("TFS_USER") or input("Username: ")
    for attempt in range(1, 4):
        PASSWORD = CFG.get("password") or os.environ.get("TFS_PASS") or getpass.getpass("Password: ")
        if login_ok():
            print(f"Login OK: {USER}")
            return
        # wrong password: drop the bad source so next round prompts fresh
        if CFG.get("password"):
            print("Mật khẩu đã lưu trong config sai — bỏ qua, hỏi lại.")
            CFG.pop("password", None)
        if os.environ.get("TFS_PASS"):
            print("TFS_PASS sai — bỏ qua, hỏi lại.")
            os.environ.pop("TFS_PASS", None)
        if attempt < 3:
            print(f"Sai mật khẩu. Nhập lại (còn {3 - attempt} lần):")
    sys.exit("Sai mật khẩu 3 lần — thoát.")


def api(path, body=None, scope="project"):
    base = f'{CFG["server"]}/{CFG["org"]}' if scope == "collection" else f'{CFG["server"]}/{CFG["org"]}/{CFG["project"]}'
    cmd = [
        "curl", "-s", "--fail-with-body", "--max-time", "60", "--ntlm",
        "-u", f"{USER}:{PASSWORD}",
        "-H", "Accept: application/json",
    ]
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        cmd += ["-H", "Content-Type: application/json", "--data-binary", "@-"]
    cmd.append(f"{base}/{path}")
    p = subprocess.run(cmd, input=data, capture_output=True)
    if p.returncode != 0:
        sys.exit(f"Request failed ({p.returncode}): {p.stdout.decode(errors='replace')[:300]}")
    return json.loads(p.stdout)


def batch(ids):
    out = []
    for i in range(0, len(ids), 200):
        res = api(f"_apis/wit/workitemsbatch?api-version={API}", {"ids": ids[i : i + 200], "fields": FIELDS})
        out.extend(res.get("value", []))
    return out


def cell(s):
    return str(s or "").replace("|", "\\|").replace("\n", " ").strip()


def render_chat(today_items, next_items, today):
    who = CFG.get("fullname") or USER
    lines = [
        f"*Báo cáo nhân sự* {today.strftime('%d/%m/%Y')}",
        f"*Nhân sự:* {who}",
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
        lines.append(f"- {cell(f.get('System.WorkItemType'))} {it['id']}: {cell(f.get('System.Title'))} (0%)")
    if not next_items:
        lines.append("- ...")
    lines += ["*Vấn đề:*", "- None"]
    return lines


def render_lark(items, today, next_ids=None):
    today_str = today.strftime("%Y-%m-%d")
    next_str = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    next_ids = next_ids or set()
    lines = [
        "| Status | Start date | End date | OT | Note | Type | Task ID | Task Name | Task Link |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    base = f'{CFG["server"]}/{CFG["org"]}/{CFG["project"]}/_workitems/edit/'
    for it in items:
        f = it["fields"]
        # Item "mới" (chọn cho ngày tiếp theo) chưa có start date hôm nay —
        # ghi ngày mai để Lark không trùng hàng với today_items.
        start = next_str if it["id"] in next_ids else today_str
        lines.append(
            f"| {cell(f.get('System.State'))} | {start} |  |  |  "
            f"| {cell(f.get('System.WorkItemType'))} | {it['id']} "
            f"| {cell(f.get('System.Title'))} | {base}{it['id']} |"
        )
    return lines


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "logout":
        logout()
        return

    for key in ("server", "org", "project"):
        if not CFG.get(key):
            sys.exit(f"Chưa có cấu hình. Chạy: run report init")
    ensure_credentials()  # login check with retry

    choice = menu("Chọn kiểu report:", ["Report hôm nay", "Report ngày cũ"])
    if choice == 0:
        report_date = datetime.date.today()
    else:
        while True:
            date_str = input("Nhập ngày (dd/mm/yyyy): ").strip()
            try:
                report_date = datetime.datetime.strptime(date_str, "%d/%m/%Y").date()
                break
            except ValueError:
                print("Ngày không hợp lệ — đúng dạng dd/mm/yyyy, ví dụ 19/08/2026. Nhập lại.")
    out_path = os.path.join(str(report_date.year), str(report_date.month), f"{report_date.day}.md")
    print(f"Report sẽ ghi vào: {out_path}" + (" (file đã có — sẽ update)" if os.path.exists(out_path) else " (tạo mới)"))

    wiql = api(
        f"_apis/wit/wiql?api-version={API}",
        {"query": "SELECT [System.Id] FROM WorkItems WHERE [System.AssignedTo] = @me ORDER BY [System.ChangedDate] DESC"},
    )
    ids = [w["id"] for w in wiql.get("workItems", [])]
    if not ids:
        sys.exit("No work items assigned to you.")
    items = batch(ids)

    # stats table instead of full list
    def counts(key):
        out = {}
        for it in items:
            k = cell(it["fields"].get(key)) or "?"
            out[k] = out.get(k, 0) + 1
        return out

    print(f"\nWork items của bạn: {len(items)}\n")
    by_state, by_type = counts("System.State"), counts("System.WorkItemType")
    print("| Type           | Count |")
    print("|----------------|------:|")
    for k in sorted(by_type):
        print(f"| {k:<14} | {by_type[k]:>5} |")
    print()
    print("| State         | Count |")
    print("|---------------|------:|")
    for k in sorted(by_state):
        print(f"| {k:<13} | {by_state[k]:>5} |")

    def print_full_list():
        print(f'\n{"#":<4}{"ID":<7}{"Type":<22}{"State":<12}{"Changed":<12}Title')
        for i, it in enumerate(sorted(items, key=lambda x: x["fields"].get("System.ChangedDate", ""), reverse=True), 1):
            f = it["fields"]
            print(f"{i:<4}{it['id']:<7}{cell(f.get('System.WorkItemType')):<22}{cell(f.get('System.State')):<12}{f.get('System.ChangedDate','')[:10]:<12}{cell(f.get('System.Title'))[:70]}")

    sorted_items = sorted(items, key=lambda x: x["fields"].get("System.ChangedDate", ""), reverse=True)

    def parse_ints(text, max_n):
        if not text: return None
        try:
            return {n for n in (int(x) for x in text.replace(";", ",").split(",") if x.strip())
                    if 1 <= n <= max_n}
        except ValueError:
            return None

    chosen = None
    while chosen is None:
        opt = menu("Chọn item để report:", ["Tất cả (all)", "Xem danh sách + chọn số (list)", "Nhập ID trực tiếp (ids)", "Thoát (quit)"])
        if opt == 3:
            sys.exit(0)
        if opt == 0:
            chosen = set(range(len(sorted_items)))
        elif opt == 1:
            print_full_list()
            pick = input("Nhập STT (phẩy cách, Enter = all): ").strip()
            if not pick:
                chosen = set(range(len(sorted_items)))
            else:
                idxs = parse_ints(pick, len(sorted_items))
                if idxs is None:
                    print("STT không hợp lệ.")
                else:
                    chosen = idxs
        elif opt == 2:
            pick = input("Nhập ID (phẩy cách, Enter = all): ").strip()
            if not pick:
                chosen = set(range(len(sorted_items)))
            else:
                try:
                    ids_set = {int(x) for x in pick.replace(";", ",").split(",") if x.strip()}
                    chosen = {i for i, it in enumerate(sorted_items) if it["id"] in ids_set}
                    if not chosen:
                        print("Không khớp ID nào.")
                except ValueError:
                    print("ID không hợp lệ.")
    today_items = [sorted_items[i] for i in sorted(chosen)]
    today_items.sort(key=lambda x: x["fields"].get("System.ChangedDate", ""))

    # Pick riêng cho "Công việc ngày tiếp theo" (Enter = bỏ trống)
    print(f"\nĐã chọn hôm nay: {len(today_items)} item.")
    print_full_list()
    next_set = None
    while next_set is None:
        pick = input("IDs cho 'Công việc ngày tiếp theo' (ID hoặc STT, Enter = bỏ trống): ").strip()
        if not pick:
            next_set = set()
            break
        try:
            ids_set = {int(x) for x in pick.replace(";", ",").split(",") if x.strip()}
        except ValueError:
            ids_set = None
        if ids_set is not None:
            next_set = {i for i, it in enumerate(sorted_items) if it["id"] in ids_set}
            if not next_set:
                print("Không khớp ID nào. Thử lại hoặc Enter để bỏ trống.")
                next_set = None
        else:
            idxs = parse_ints(pick, len(sorted_items))
            if idxs is None:
                print("Không hợp lệ. Nhập ID (vd 7939) hoặc STT (vd 1,3), Enter = bỏ trống.")
            else:
                next_set = idxs
    next_items = [sorted_items[i] for i in sorted(next_set)]
    next_items.sort(key=lambda x: x["fields"].get("System.ChangedDate", ""))

    seen, merged = set(), []
    for it in today_items + next_items:
        if it["id"] not in seen:
            seen.add(it["id"])
            merged.append(it)
    report = "\n".join(render_chat(today_items, next_items, report_date) + [""] + render_lark(merged, report_date, next_ids={it["id"] for it in next_items}) + [""])
    if os.path.exists(out_path):
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write("\n---\n\n" + report)
        print(f"File đã có — đã update (append): {out_path}")
    else:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"Tạo mới: {out_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã thoát.")
        sys.exit(130)
