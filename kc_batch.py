#!/usr/bin/env python3
"""keelcode 批量注册并发版：线程池并发出号，API 打码优先失败切本地
用法: python3 kc_batch_conc.py <数量> [并发数]
"""
import json, os, sys, time, random, string, subprocess, urllib.request, urllib.parse, re, quopri
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===== 生产配置 =====
API_BASE = os.environ.get("KC_API_BASE", "https://keelcode.ai")
SITEKEY = os.environ.get("KC_SITEKEY", "0x4AAAAAAEDkke8x5GYWpYaB")
SITE_URL = os.environ.get("KC_SITE_URL", "https://keelcode.ai/signup")
PROXY = os.environ.get("KC_PROXY", "")
PASSWORD = os.environ.get("KC_PASSWORD", "KcTest#2026x9z")
NAME = os.environ.get("KC_NAME", "keel")
CREDS_DIR = os.environ.get("KC_CREDS_DIR", "/opt/data/keel-code-switch/credentials")
MAIL_API = os.environ.get("KC_MAIL_API", "")
MAIL_ADMIN = os.environ.get("KC_MAIL_ADMIN_KEY", "")
MAIL_DOMAIN = os.environ.get("KC_MAIL_DOMAIN", "")
SOLVER = os.environ.get("KC_SOLVER_URL", "http://172.17.0.1:5009")
CAPTCHA_BACKEND = os.environ.get("KC_CAPTCHA_BACKEND", "gateway")
YESCAPTCHA_KEY = os.environ.get("KC_YESCAPTCHA_KEY", "")
GATEWAY_URL = os.environ.get("KC_GATEWAY_URL", "https://sub.aixiangshu.com/captcha")
GATEWAY_KEY = os.environ.get("KC_GATEWAY_KEY", "")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

# 并发统计
STATS = {"ok": 0, "fail": 0, "captcha_api": 0, "captcha_local": 0}
LOCK = __import__("threading").Lock()
_logs = []

def log(msg):
    with LOCK:
        _logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        sys.stdout.write(f"\r{msg} {' ' * 20}")
        sys.stdout.flush()

def http_json(url, data=None, headers=None, timeout=30, proxy=None):
    cmd = ["curl", "-s", "-m", str(timeout)]
    if proxy: cmd += ["-x", proxy]
    if data is not None:
        cmd += ["-X", "POST", "-H", "Content-Type: application/json", "-d", json.dumps(data)]
    cmd.append(url)
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {"_raw": r.stdout[:150]}

def create_mailbox():
    name = "kc" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    for _ in range(3):
        d = http_json(f"{MAIL_API}/admin/new_address",
                      {"name": name, "domain": MAIL_DOMAIN, "enablePrefix": True, "enableRandomSubdomain": True},
                      {"x-admin-auth": MAIL_ADMIN, "Referer": f"{MAIL_API}/",
                       "User-Agent": UA})
        if d.get("address"):
            return d["address"]
        time.sleep(2)
    return None

def solve_captcha():
    """打码：gateway（aixiangshu）→ yescaptcha → 本地，逐级降级"""
    if CAPTCHA_BACKEND == "gateway":
        tok = _solve_gateway()
        if tok:
            with LOCK: STATS["captcha_api"] += 1
            return tok
        log("⚠️ gateway 失败，切 yescaptcha")
        tok = _solve_yescaptcha()
        if tok:
            with LOCK: STATS["captcha_api"] += 1
            return tok
        log("⚠️ yescaptcha 失败切本地")
    elif CAPTCHA_BACKEND == "yescaptcha":
        tok = _solve_yescaptcha()
        if tok:
            with LOCK: STATS["captcha_api"] += 1
            return tok
        log("⚠️ yescaptcha 失败切本地")
    tok = _solve_local()
    if tok:
        with LOCK: STATS["captcha_local"] += 1
    return tok

def _solve_gateway():
    """aixiangshu 打码网关（2captcha 兼容，代理必填）"""
    if not GATEWAY_KEY:
        return None
    d = http_json(f"{GATEWAY_URL}/createTask",
                  {"clientKey": GATEWAY_KEY, "task": {
                      "type": "TurnstileTask", "websiteURL": SITE_URL,
                      "websiteKey": SITEKEY, "proxy": PROXY}}, timeout=30)
    tid = d.get("taskId")
    if not tid:
        return None
    for _ in range(24):
        time.sleep(5)
        r = http_json(f"{GATEWAY_URL}/getTaskResult",
                      {"clientKey": GATEWAY_KEY, "taskId": tid}, timeout=30)
        if r.get("status") == "ready":
            return (r.get("solution") or {}).get("cf_turnstile_response")
        if r.get("errorId") not in (0, None):
            return None
    return None

def _solve_yescaptcha():
    d = http_json("https://api.yescaptcha.com/createTask",
                  {"clientKey": YESCAPTCHA_KEY, "task": {
                      "type": "TurnstileTaskProxyless",
                      "websiteURL": SITE_URL, "websiteKey": SITEKEY}}, timeout=30)
    tid = d.get("taskId")
    if not tid:
        return None
    for _ in range(20):
        time.sleep(3)
        r = http_json("https://api.yescaptcha.com/getTaskResult",
                      {"clientKey": YESCAPTCHA_KEY, "taskId": tid}, timeout=30)
        if r.get("status") == "ready":
            return r["solution"]["token"]
        if r.get("errorId") != 0:
            return None
    return None

def _solve_local():
    d = http_json(f"{SOLVER}/turnstile?url={urllib.parse.quote(SITE_URL)}&sitekey={SITEKEY}", timeout=90)
    tid = d.get("taskId")
    if not tid:
        return None
    for _ in range(25):
        time.sleep(5)
        r = http_json(f"{SOLVER}/result?id={tid}")
        tok = (r.get("solution") or {}).get("token") or r.get("token")
        if tok:
            return tok
        if r.get("status") in ("failed", "error"):
            return None
    return None

def register(email, token):
    return http_json(f"{API_BASE}/api/auth/sign-up/email",
                     {"email": email, "password": PASSWORD, "name": NAME, "callbackURL": API_BASE},
                     {"x-captcha-response": token, "Origin": API_BASE, "Referer": f"{API_BASE}/signup"},
                     proxy=PROXY)

def get_verify_link(address):
    for _ in range(12):
        time.sleep(5)
        mails = http_json(f"{MAIL_API}/admin/mails?offset=0&limit=50",
                          headers={"x-admin-auth": MAIL_ADMIN, "Referer": f"{MAIL_API}/", "User-Agent": UA})
        for m in (mails.get("results") or []):
            if m.get("address") == address:
                raw = m.get("raw", "")
                mm = re.search(r"token=3D([A-Za-z0-9=_.\-]+(?:(?:\r?\n)[A-Za-z0-9=_.\-]+)*)", raw)
                if mm:
                    enc = re.sub(r"=\r?\n", "", mm.group(1))
                    return quopri.decodestring(enc.encode()).decode()
    return None

def verify_login(email, token):
    cmd = ["curl", "-s", "-m", "20", "-G", f"{API_BASE}/api/auth/verify-email",
           "--data-urlencode", f"token={token}", "--data-urlencode", "callbackURL=/dashboard",
           "-A", UA, "-o", "/dev/null", "-w", "%{http_code}"]
    code = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    time.sleep(1)
    login_tok = solve_captcha()
    if not login_tok:
        return None
    return http_json(f"{API_BASE}/api/auth/sign-in/email",
                     {"email": email, "password": PASSWORD, "callbackURL": "/dashboard"},
                     {"x-captcha-response": login_tok, "Origin": API_BASE},
                     proxy=PROXY)

def one_account(i):
    addr = create_mailbox()
    if not addr:
        with LOCK: STATS["fail"] += 1
        msg = f"[{i}] 邮箱创建失败"
        log(f"❌ {msg}"); return msg
    tok = solve_captcha()
    if not tok:
        with LOCK: STATS["fail"] += 1
        msg = f"[{i}] 打码失败 {addr}"
        log(f"❌ {msg}"); return msg
    d = register(addr, tok)
    uid = (d.get("user") or {}).get("id")
    if not uid:
        with LOCK: STATS["fail"] += 1
        msg = f"[{i}] 注册失败 {addr}: {str(d)[:90]}"
        log(f"❌ {msg}"); return msg
    vtok = get_verify_link(addr)
    if not vtok:
        with LOCK: STATS["fail"] += 1
        msg = f"[{i}] 邮件未到 {addr}"
        log(f"❌ {msg}"); return msg
    login = verify_login(addr, vtok)
    access = (login or {}).get("token")
    if not access:
        with LOCK: STATS["fail"] += 1
        msg = f"[{i}] 登录失败 {addr}: {str(login)[:70]}"
        log(f"❌ {msg}"); return msg
    # 写凭证
    os.makedirs(CREDS_DIR, exist_ok=True)
    with LOCK:
        n = len([f for f in os.listdir(CREDS_DIR) if f.endswith(".json")]) + 1
        path = f"{CREDS_DIR}/account{n}.json"
    cred = {"schemaVersion": 1, "apiBaseUrl": API_BASE, "accessToken": access,
            "authStyle": "bearer", "expiresAt": "2026-08-10T00:00:00.000Z",
            "user": {"name": NAME, "email": addr}}
    with open(path, "w") as f:
        json.dump(cred, f)
    with LOCK:
        STATS["ok"] += 1
        done = STATS["ok"] + STATS["fail"]
    log(f"✅ {STATS['ok']}/{done} {addr}")
    return f"[{i}] OK {addr}"

def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    t0 = time.time()
    print(f"🚀 并发注册 {count} 个号，workers={workers}")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one_account, i) for i in range(count)]
        for f in as_completed(futs):
            f.result()
    dt = time.time() - t0
    print(f"\n=== 完成: 成功 {STATS['ok']} / 失败 {STATS['fail']} / 耗时 {dt:.0f}s "
          f"({count/dt:.1f} 号/秒) | API打码 {STATS['captcha_api']} 本地打码 {STATS['captcha_local']} ===")
    # 失败明细
    fails = [l for l in _logs if "❌" in l]
    if fails:
        print("--- 失败明细 ---")
        for fl in fails:
            print(fl)

if __name__ == "__main__":
    main()
