"""RDFX Telegram channel bot.

Usage:  python bot.py news | calendar | poll | quiz | challenge | announce "text"
Needs two environment variables: BOT_TOKEN and CHAT_ID
"""
import html
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
API = f"https://api.telegram.org/bot{TOKEN}"
LONDON = ZoneInfo("Europe/London")
UA = {"User-Agent": "Mozilla/5.0 (RDFX bot)"}

# ---------------------------------------------------------------- EDIT ME
NEWS_FEEDS = [
    "https://www.fxstreet.com/rss/news",
    "https://www.fxstreet.com/rss/analysis",
]
# keywords used to sort headlines into each section
SECTIONS = [
    ("🇺🇸 USD", ["usd", "dollar", "fed", "fomc", "powell", "treasury", "cpi", "nfp", "payroll"]),
    ("🥇 GOLD", ["gold", "xau", "bullion"]),
    ("🇬🇧 GBP", ["gbp", "pound", "sterling", "boe", "bank of england", "uk "]),
]
FALLBACKS = {
    "🇺🇸 USD": "No major headline yet. Keep an eye on US data and Fed speakers.",
    "🥇 GOLD": "No major headline yet. Gold usually reacts to USD and yields.",
    "🇬🇧 GBP": "No major headline yet. Watch UK data and BoE commentary.",
}
CALENDAR_COUNTRIES = {"USD": "🇺🇸", "GBP": "🇬🇧", "EUR": "🇪🇺"}
CALENDAR_IMPACT = {"High"}  # add "Medium" to see more events
CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

POLLS = [
    ("What's your biggest struggle with trading right now?",
     ["Finding good entries", "Understanding market structure", "Risk management",
      "Staying disciplined", "Being consistent"]),
    ("How do you handle high-impact news?",
     ["Avoid trading it", "Trade the reaction after", "Trade before it", "I forget to check"]),
    ("What risk per trade do you use?",
     ["Under 0.5%", "0.5% – 1%", "1% – 2%", "Over 2%"]),
    ("Which session do you trade most?",
     ["Asian", "London", "New York", "Whenever I can"]),
    ("What's holding back your consistency?",
     ["Overtrading", "Moving my stop loss", "No clear plan", "Emotions after a loss"]),
]
# (question, options, index of correct answer starting at 0, explanation)
QUIZZES = [
    ("What does NFP stand for?",
     ["Net Forex Profit", "Non-Farm Payrolls", "National Fed Policy", "New Funding Period"],
     1, "Non-Farm Payrolls is the monthly US jobs report and moves USD hard."),
    ("Which usually has the biggest impact on spreads?",
     ["A quiet Asian session", "High-impact news", "Weekend close", "A bank holiday lunch"],
     1, "Spreads widen around high-impact news. Plan for it."),
    ("If you risk 1% on a £10,000 account, how much is that?",
     ["£10", "£100", "£1,000", "£50"], 1, "1% of £10,000 = £100."),
    ("A higher-than-expected CPI usually tends to push rate expectations...",
     ["Higher", "Lower", "No change", "Negative"], 0,
     "Hot inflation tends to raise rate expectations, which often supports the currency."),
]
CHALLENGES = [
    "🏆 <b>RDFX WEEKLY CHALLENGE</b>\n\nThis week: <b>no revenge trades.</b>\nAfter a loss, step away for 30 minutes. Reply with how many times you stuck to it.",
    "🏆 <b>RDFX WEEKLY CHALLENGE</b>\n\nThis week: <b>journal every trade.</b>\nEntry, reason, risk, result. Screenshot your best journal entry and share it.",
    "🏆 <b>RDFX WEEKLY CHALLENGE</b>\n\nThis week: <b>max 2 trades a day.</b>\nQuality over quantity. Tell us how it felt.",
    "🏆 <b>RDFX WEEKLY CHALLENGE</b>\n\nThis week: <b>risk 1% or less on every trade.</b>\nNo exceptions. Report back on Friday.",
]
# ---------------------------------------------------------------------------


def tg(method, **payload):
    r = requests.post(f"{API}/{method}", json={"chat_id": CHAT_ID, **payload}, timeout=30)
    if not r.ok:
        print("Telegram error:", r.text)
        r.raise_for_status()


def send(text):
    tg("sendMessage", text=text, parse_mode="HTML", disable_web_page_preview=True)


def rotate(items):
    """Pick a different item each day."""
    return items[datetime.now(LONDON).timetuple().tm_yday % len(items)]


def fetch_headlines():
    items = []
    for url in NEWS_FEEDS:
        try:
            root = ET.fromstring(requests.get(url, headers=UA, timeout=20).content)
            for it in root.iter("item"):
                title = (it.findtext("title") or "").strip()
                if title:
                    items.append(title)
        except Exception as e:  # a dead feed must not stop the post
            print("Feed failed:", url, e)
    return items


def post_news():
    headlines = fetch_headlines()
    used, lines = set(), []
    for label, words in SECTIONS:
        match = next((h for h in headlines
                      if h not in used and any(w in h.lower() for w in words)), None)
        if match:
            used.add(match)
            lines.append(f"{label}: {html.escape(match)}")
        else:
            lines.append(f"{label}: {FALLBACKS[label]}")
    body = "\n".join(lines)
    send(
        "<b>RDFX | DAILY MARKET NEWS</b>\n"
        "🌍 <b>What's moving the markets?</b>\n\n"
        "Good morning, team.\nHere's your latest market news briefing:\n\n"
        f"{body}\n\n"
        "<b>What to watch today:</b>\n"
        "Keep an eye on today's major economic releases and potential volatility.\n\n"
        "Stay informed, manage your risk and don't rush into trades."
    )


def post_calendar():
    data = requests.get(CALENDAR_URL, headers=UA, timeout=20).json()
    today = datetime.now(LONDON).date()
    events = []
    for e in data:
        if e.get("country") not in CALENDAR_COUNTRIES or e.get("impact") not in CALENDAR_IMPACT:
            continue
        when = datetime.fromisoformat(e["date"]).astimezone(LONDON)
        if when.date() == today:
            events.append((when, e))
    if not events:
        print("No qualifying events today, nothing posted.")
        return
    events.sort(key=lambda x: x[0])
    lines = []
    for when, e in events:
        flag = CALENDAR_COUNTRIES[e["country"]]
        extra = []
        if e.get("forecast"):
            extra.append(f"Forecast {html.escape(e['forecast'])}")
        if e.get("previous"):
            extra.append(f"Previous {html.escape(e['previous'])}")
        extra_txt = " · " + " · ".join(extra) if extra else ""
        lines.append(f"{flag} <b>{html.escape(e['title'])}</b>\n{when:%H:%M} UK time{extra_txt}")
    send(
        "📅 <b>RDFX | ECONOMIC CALENDAR</b>\n"
        "<b>Today's important events</b>\n\n" + "\n\n".join(lines) +
        "\n\nRemember: High-impact news can increase spreads, volatility and slippage."
    )


def post_poll():
    q, opts = rotate(POLLS)
    tg("sendPoll", question=q, options=opts, is_anonymous=True)


def post_quiz():
    q, opts, correct, why = rotate(QUIZZES)
    tg("sendPoll", question=q, options=opts, type="quiz",
       correct_option_id=correct, explanation=why, is_anonymous=True)


def post_challenge():
    week = datetime.now(LONDON).isocalendar()[1]
    send(CHALLENGES[week % len(CHALLENGES)])


def post_announce(text):
    send("📢 <b>RDFX ANNOUNCEMENT</b>\n\n" + html.escape(text))


if __name__ == "__main__":
    if not TOKEN or not CHAT_ID:
        sys.exit("Set BOT_TOKEN and CHAT_ID first.")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    actions = {"news": post_news, "calendar": post_calendar, "poll": post_poll,
               "quiz": post_quiz, "challenge": post_challenge}
    if cmd == "announce":
        post_announce(" ".join(sys.argv[2:]))
    elif cmd in actions:
        actions[cmd]()
    else:
        sys.exit("Use: news | calendar | poll | quiz | challenge | announce \"text\"")
