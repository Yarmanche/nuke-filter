#!/usr/bin/env python3
"""
Telegram bot — send it a photo/video/GIF, get the filtered version back.
Commands: /start, /pos <center|tl|tr|bl|br|ml|mr|mt|mb>, /width <0.1-1.0>

Token: FILTER_BOT_TOKEN env var (legacy NUKE_BOT_TOKEN also accepted),
       set in your environment or in a .env file next to this script.
Run:   python3 nuke_bot.py        (long polling, stays alive)
"""
import os, sys, tempfile, time, re

import config  # loads .env from the project dir (if present)

TOKEN = config.TOKEN
if not TOKEN:
    sys.exit("set FILTER_BOT_TOKEN in your environment or in a .env file next to "
             "this script (get the token from @BotFather)")

import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nuke_vid import run as nuke_run, run_photo

API = f"https://api.telegram.org/bot{TOKEN}"
state = {}  # chat_id -> {"pos": ..., "width": ...}

def tg(method, **kw):
    for attempt in range(3):
        try:
            r = requests.post(f"{API}/{method}", json=kw, timeout=120)
            return r.json()
        except requests.RequestException as e:
            if attempt == 2: print("tg error:", e); return {}
            time.sleep(2)

def handle_update(u):
    msg = u.get("message") or u.get("edited_message") or {}
    chat_id = msg.get("chat", {}).get("id")
    if not chat_id: return
    st = state.setdefault(chat_id, {"pos": "center", "width": config.LOGO_WIDTH})

    text = (msg.get("text") or "").strip()
    if text.startswith("/start"):
        tg("sendMessage", chat_id=chat_id, parse_mode="Markdown",
           text=(f"*{config.APP_NAME}*\nSend me any photo / video / GIF and I'll return it "
                 "grayscaled with the box logo stamped on.\n\n⚠️ *Send GIFs as FILE (attachment), not as inline GIF* — Telegram re-encodes inline animations to 320px trash before I ever see them.\n\n"
                 f"current pos: `{st['pos']}` · width: `{st['width']}`\n"
                 "/pos center — or tl tr bl br ml mr mt mb\n/width 0.55 — logo size (fraction)"))
        return
    m = re.match(r"/pos\s+(\w+)", text)
    if m:
        if m.group(1) in {"center","tl","tr","bl","br","ml","mr","mt","mb"}:
            st["pos"] = m.group(1)
            tg("sendMessage", chat_id=chat_id, text=f"pos → {st['pos']}")
        else:
            tg("sendMessage", chat_id=chat_id, text="unknown pos. tl tr bl br ml mr mt mb center")
        return
    m = re.match(r"/width\s+([\d.]+)", text)
    if m:
        w = max(0.1, min(1.0, float(m.group(1))))
        st["width"] = w
        tg("sendMessage", chat_id=chat_id, text=f"width → {w}")
        return
    if text:
        return  # ignore other chatter

    # media?
    kind = None; file_id = None
    if "photo" in msg: kind, file_id = "photo", msg["photo"][-1]["file_id"]
    elif "video" in msg: kind, file_id = "video", msg["video"]["file_id"]
    elif "animation" in msg: kind, file_id = "gif", msg["animation"]["file_id"]
    elif "document" in msg:
        d = msg["document"]
        n = d.get("file_name", "")
        if re.search(r"\.(gif|mp4|webm|mov|mkv|avi)$", n, re.I):
            kind = "gif" if n.lower().endswith(".gif") else "video"
            file_id = d["file_id"]
    if not file_id:
        tg("sendMessage", chat_id=chat_id, text="send a photo, video or GIF (or /start)")
        return

    tg("sendChatAction", chat_id=chat_id, action="upload_video")
    tmp = tempfile.mkdtemp(prefix="nuketg_")
    print(f"[job] kind={kind} pos={st['pos']} w={st['width']}")
    # download — STREAMED to disk, never in RAM (retry ×3)
    f = {}
    for attempt in range(3):
        f = tg("getFile", file_id=file_id).get("result", {})
        if f.get("file_path"):
            break
        print(f"[job] getFile attempt {attempt+1} failed:", f)
        time.sleep(2)
    if not f.get("file_path"):
        tg("sendMessage", chat_id=chat_id, text="Telegram won't give me the file (getFile failed 3×).\nIf it's over 20MB, that's the bot API hard limit — send a smaller/compressed version."); return
    url = f"https://api.telegram.org/file/bot{TOKEN}/{f['file_path']}"
    inp = os.path.join(tmp, "in" + (os.path.splitext(f["file_path"])[1] or ".bin"))
    with requests.get(url, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        with open(inp, "wb") as fh:
            for chunk in resp.iter_content(1 << 20):
                fh.write(chunk)
    print(f"[job] downloaded {os.path.getsize(inp)/1e6:.1f} MB")
    # process
    out_ext = ".gif" if kind == "gif" else (".jpg" if kind == "photo" else ".mp4")
    out = os.path.join(tmp, "out" + out_ext)
    if kind == "photo":
        r = run_photo(inp, out, pos=st["pos"], width=st["width"])
    else:
        r = nuke_run(inp, out, pos=st["pos"], width=st["width"])
    if r.returncode != 0 or not os.path.exists(out):
        print("[job] ffmpeg failed:", (r.stderr or "")[-300:])
        tg("sendMessage", chat_id=chat_id, text="ffmpeg failed — probably an unsupported codec"); return
    size = os.path.getsize(out)
    print(f"[job] output {size/1e6:.1f} MB — sending")
    # send — stream via file handle (requests multipart with a handle streams)
    if kind == "photo" and size < 9_500_000:
        with open(out, "rb") as fh:
            requests.post(f"{API}/sendPhoto", data={"chat_id": chat_id},
                          files={"photo": ("nuked.jpg", fh)}, timeout=600)
    elif size < 49_000_000:
        method = "sendVideo" if out_ext == ".mp4" else "sendAnimation"
        with open(out, "rb") as fh:
            rr = requests.post(f"{API}/{method}", data={"chat_id": chat_id},
                               files={method[4:].lower(): ("nuked" + out_ext, fh)}, timeout=900)
        print("[job] send:", rr.json().get("ok"))
    else:
        tg("sendMessage", chat_id=chat_id, text=f"result is {size/1e6:.0f}MB — over Telegram's 50MB upload cap")
    print("[job] done")

def main():
    print("bot polling…")
    offset = 0
    while True:
        try:
            updates = tg("getUpdates", offset=offset, timeout=50).get("result", [])
        except Exception as e:
            print("poll error:", e); time.sleep(3); continue
        for u in updates:
            offset = u["update_id"] + 1
            try:
                handle_update(u)
            except Exception as e:
                import traceback
                print("update error:", e)
                traceback.print_exc()
                try:
                    cid = (u.get("message") or u.get("edited_message") or {}).get("chat", {}).get("id")
                    if cid:
                        tg("sendMessage", chat_id=cid, text="something broke processing that — try again")
                except Exception:
                    pass
                time.sleep(1)

if __name__ == "__main__":
    main()
