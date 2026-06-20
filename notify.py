"""Notifications via Apprise — fire-and-forget. A failure must never block an API
response or raise into the request path: log and return False."""
import logging

import logic

log = logging.getLogger("chore.notify")


def send(conn, title, message):
    """Best-effort Apprise notification. Returns True on success, never raises."""
    urls_raw = logic.get_setting(conn, "notify_urls", "") or ""
    urls = [u.strip() for u in urls_raw.splitlines() if u.strip()]
    if not urls:
        log.warning("No notification URLs configured; skipping: %s", title)
        return False
    try:
        import apprise
        ap = apprise.Apprise()
        for url in urls:
            ap.add(url)
        result = ap.notify(title=title, body=message)
        if not result:
            log.error("Apprise notify returned False for: %s", title)
        return bool(result)
    except Exception as exc:  # noqa: BLE001 - fire-and-forget by design
        log.error("Notification send failed: %s", exc)
        return False


def send_once(conn, kid_id, ntype, title, message, d):
    """Send only if this (kid, date, type) hasn't been sent — dedup backstop.

    The UNIQUE constraint on notifications_sent makes the claim atomic, so two
    near-simultaneous requests can't both send.
    """
    ds = logic.d2s(d)
    try:
        conn.execute(
            "INSERT INTO notifications_sent (kid_id, notification_date, "
            "notification_type, sent_at) VALUES (?,?,?,?)",
            (kid_id, ds, ntype, logic.now_iso()))
        conn.commit()
    except Exception:
        return False  # already recorded -> already sent (or being sent)
    return send(conn, title, message)
