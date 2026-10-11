"""
名人堂设置同步: 登录机器人账号读站内信, 把成员自己选的头衔 / 显示开关写进 dis/config.json.

App 发的信 (Dis 的 HallOfFame.submitIfNeeded):  「[Dis 名人堂] 显示「元老」」/「[Dis 名人堂] 不显示」
- 发信人 uid 取论坛页面上的, 不信消息内容, 别人冒充不了
- 只处理名单里的成员; 头衔必须在公共池或他自己的专属 titles 里
- 每个会话只看最新一条, 重复处理结果不变; 名单没变就不提交
"""
import html, http.cookiejar, json, os, re, sys, urllib.parse, urllib.request

BASE = "https://www.4d4y.com/forum/"
CONFIG = "dis/config.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
MSG = re.compile(r"\[Dis 名人堂\]\s*(?:(不显示)|显示「(.+?)」)")
ITEM = re.compile(r'uid=(\d+)" target="_blank">(.*?)</a></cite>(.*?)</p>.*?summary">\s*(.*?)</div>', re.S)
DEFAULT_POOL = ["名人堂", "元老", "传奇", "开荒者", "老友", "守望者"]

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
opener.addheaders = [("User-Agent", UA)]


def get(path, data=None):
    body = urllib.parse.urlencode(data, encoding="gbk").encode() if data else None   # 论坛是 GBK
    with opener.open(BASE + path, body, timeout=30) as r:
        return r.read().decode("gb18030", errors="replace")


def login(username, password):
    page = get("logging.php?action=login")
    m = re.search(r'formhash" value="([^"]+)"', page)
    if not m:
        sys.exit("登录页没有 formhash")
    res = get("logging.php?action=login&loginsubmit=yes&inajax=1", {
        "loginfield": "username", "username": username, "password": password,
        "questionid": "0", "answer": "", "cookietime": "2592000",
        "referer": BASE + "index.php", "formhash": m.group(1),
    })
    if "欢迎您回来" not in res:
        sys.exit("登录失败: " + re.sub(r"<[^>]+>", "", res)[:200])


def choices():
    """{uid: (hidden: bool, title: str|None)}, 每个会话的最新一条"""
    found = {}
    for page in range(1, 11):
        items = ITEM.findall(get(f"pm.php?filter=privatepm&page={page}"))
        for uid, _, _, summary in items:
            text = html.unescape(re.sub(r"<[^>]+>", "", summary)).strip()
            m = MSG.search(text)
            if m and int(uid) not in found:
                found[int(uid)] = (True, None) if m.group(1) else (False, m.group(2).strip())
        if len(items) < 10:
            break
    return found


def main():
    login(os.environ["FORUM_USERNAME"], os.environ["FORUM_PASSWORD"])
    found = choices()
    print(f"收到 {len(found)} 位的设置")

    with open(CONFIG, encoding="utf-8") as f:
        config = json.load(f)
    hof = config.get("hallOfFame") or {}
    pool = hof.get("titles") or DEFAULT_POOL
    changed = []
    for m in hof.get("members", []):
        uid = int(m.get("uid", 0))
        if uid not in found:
            continue
        hidden, title = found[uid]
        if title is not None and title not in pool + m.get("titles", []):
            print(f"UID {uid}: 头衔「{title}」不在可选范围, 忽略")
            continue
        new = dict(m, hidden=hidden, **({} if hidden else {"current": title}))
        if new != m:
            m.clear(); m.update(new)
            changed.append(f"UID {uid} {'不显示' if hidden else '显示「' + title + '」'}")
    for uid in set(found) - {int(m.get("uid", 0)) for m in hof.get("members", [])}:
        print(f"UID {uid}: 不在名单里, 忽略")

    if not changed:
        print("名单无变化")
        return
    # 和 App 写回时的格式一致 (Apple JSONSerialization prettyPrinted + sortedKeys)
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True, separators=(",", " : ")) + "\n")
    msg = "名人堂: " + ", ".join(changed)
    print(msg)
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
        f.write(f"message={msg}\n")


main()
