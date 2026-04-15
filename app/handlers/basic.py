"""Start, help, and a tiny ping."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.config import settings

router = Router(name="basic")


def _brand(line: str = "") -> str:
    name = f"{settings.bot_brand_emoji} <b>{settings.bot_display_name}</b>".strip()
    return f"{name}\n{line}" if line else name


@router.message(CommandStart())
async def start(msg: Message) -> None:
    text = (
        f"{_brand(settings.bot_short_description)}\n\n"
        "I help you <b>catch up on group chats</b> and <b>set reminders</b>.\n\n"
        "<b>Catch-up</b>\n"
        "• /markread — set your checkpoint here\n"
        "• /catchup — summarize new messages since checkpoint\n"
        "• /catchup_short  /catchup_detailed\n"
        "• /autosummary on|off\n\n"
        "<b>Reminders</b>\n"
        "• /remind in 30 minutes water plants\n"
        "• /remind tomorrow 9am submit report\n"
        "• /remind every monday 8:00 team sync\n"
        "• /list_reminders   /delete_reminder &lt;id&gt;\n"
        "• /set_timezone Europe/Berlin\n\n"
        "Type /help for the command list, or /tutorials for worked examples."
    )
    await msg.answer(text)


@router.message(Command("tutorials"))
async def tutorials(msg: Message) -> None:
    text = (
        f"{_brand('Step-by-step examples')}\n\n"

        "<b>1️⃣ Catch up on a group</b>\n"
        "Step 1 — set your checkpoint:\n"
        "  <code>/markread</code>\n"
        "Step 2 — wait for new messages from others.\n"
        "Step 3 — get a summary:\n"
        "  <code>/catchup</code>            (medium)\n"
        "  <code>/catchup_short</code>      (one-glance)\n"
        "  <code>/catchup_detailed</code>   (full digest)\n"
        "<i>Tip:</i> when <b>you</b> send a message in the group, your checkpoint "
        "auto-advances to that message — so /catchup means \"since I last spoke.\"\n\n"

        "<b>2️⃣ One-time reminders</b>\n"
        "  <code>/remind in 30 minutes water plants</code>\n"
        "  <code>/remind in 2 hours check server</code>\n"
        "  <code>/remind today 18:00 call mom</code>\n"
        "  <code>/remind tomorrow 9am submit report</code>\n"
        "  <code>/remind monday 8:00 deploy</code>\n"
        "  <code>/remind on 2026-04-20 09:00 doctor</code>\n\n"

        "<b>3️⃣ Recurring reminders</b>\n"
        "  <code>/remind every day 9:00 take vitamins</code>\n"
        "  <code>/remind every monday 8:00 team sync</code>\n"
        "  <code>/remind every 2 hours stand up</code>\n\n"

        "<b>4️⃣ Manage reminders</b>\n"
        "  <code>/list_reminders</code>      — see your active reminders\n"
        "  <code>/delete_reminder 7</code>   — cancel reminder #7\n\n"

        "<b>5️⃣ Personal settings</b>\n"
        "  <code>/set_timezone Asia/Ho_Chi_Minh</code>\n"
        "  <code>/set_timezone Europe/Berlin</code>\n"
        "  <code>/autosummary on</code>      <code>/autosummary off</code>\n\n"

        "<b>6️⃣ Ask the AI anything</b> (needs LLM_API_KEY)\n"
        "  <code>/ask viết email xin nghỉ phép 2 ngày</code>\n"
        "  <code>/ask giải thích Docker volume cho người mới</code>\n"
        "  <code>/ask tóm tắt sự kiện ngày 30/4/1975</code>\n"
        "<i>Tip:</i> set <code>SUMMARY_LANGUAGE=Vietnamese</code> in env to force "
        "all AI replies in Vietnamese, even when the input is mixed.\n\n"

        "<b>7️⃣ Use me in a group</b>\n"
        "• Add me to the group (Add member → search my username).\n"
        "• Ask the admin: in BotFather → my bot → Bot Settings → "
        "Group Privacy → <b>Disable</b>, then re-add me.\n"
        "• Anyone can run /markread and /catchup — checkpoints are per-user.\n\n"

        "<b>If a time is ambiguous</b> (e.g. <code>/remind tomorrow buy bread</code>), "
        "I assume <b>09:00 in your timezone</b> and ask you to confirm with buttons.\n\n"

        "Need the full reference? → /help"
    )
    await msg.answer(text)


@router.message(Command("help"))
async def help_cmd(msg: Message) -> None:
    text = (
        f"{_brand()}\n\n"
        "<b>Limitations to know</b>\n"
        "• Telegram does not tell bots what you've read. /catchup uses an explicit "
        "<b>checkpoint</b> you set with /markread.\n"
        "• In groups, I can only summarize messages I actually saw. Ask the admin to "
        "disable <b>Privacy Mode</b> in BotFather and add me to the group so I can read messages.\n"
        "• I cannot fetch messages from before I joined.\n\n"
        "<b>Commands</b>\n"
        "/start, /help, /tutorials\n"
        "/markread — set your catch-up checkpoint in this chat\n"
        "/catchup, /catchup_short, /catchup_detailed\n"
        "/autosummary on|off — daily DM digest of this group (best-effort)\n"
        "/remind &lt;when&gt; &lt;text&gt;\n"
        "/list_reminders\n"
        "/delete_reminder &lt;id&gt;\n"
        "/set_timezone &lt;IANA tz&gt;  e.g. <code>Europe/Berlin</code>\n"
        "/ask &lt;question&gt; — free-form Q&amp;A (requires LLM_API_KEY)\n"
    )
    await msg.answer(text)


@router.message(Command("ping"))
async def ping(msg: Message) -> None:
    await msg.answer("pong")
