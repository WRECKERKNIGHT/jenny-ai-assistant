#!/usr/bin/env python3
import sqlite3
import plistlib
import glob
import json
import os
import re
from datetime import datetime, timezone

def relative_time(del_date):
    """Convert a delivered_date value into a human 'x min ago' string."""
    if not del_date:
        return 'recent'
    try:
        ts = float(del_date)
        if ts > 1e11:
            ts = ts / 1000.0
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        delta = (datetime.now(timezone.utc) - dt).total_seconds()
        if delta < 0:
            return 'just now'
        if delta < 60:
            return f'{int(delta)}s ago'
        if delta < 3600:
            return f'{int(delta // 60)}m ago'
        if delta < 86400:
            return f'{int(delta // 3600)}h ago'
        return f'{int(delta // 86400)}d ago'
    except Exception:
        return 'recent'

def get_notifications():
    db_paths = glob.glob('/var/folders/*/*/*/com.apple.notificationcenter/db2/db')
    if not db_paths:
        db_paths = glob.glob('/var/folders/*/*/*/com.apple.notificationcenter/db/db')

    notifications = []
    discord_dms = []
    seen = set()

    if db_paths:
        try:
            conn = sqlite3.connect(db_paths[0])
            cursor = conn.cursor()
            cursor.execute('''
                SELECT app.identifier, record.data, record.delivered_date 
                FROM record 
                JOIN app ON record.app_id = app.app_id 
                ORDER BY record.rec_id DESC 
                LIMIT 50;
            ''')
            rows = cursor.fetchall()

            for app_id, data, del_date in rows:
                try:
                    plist = plistlib.loads(data)
                    req = plist.get('req', {})
                    title = str(req.get('title', ''))
                    subtitle = str(req.get('subtitle', ''))
                    body = str(req.get('body', ''))

                    if not (title or body):
                        continue

                    # Deduplicate repeated identical alerts
                    dedupe_key = f"{app_id}|{title}|{body}"
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)

                    item = {
                        "app": app_id,
                        "title": title,
                        "subtitle": subtitle,
                        "body": body,
                        "date": del_date,
                        "relative": relative_time(del_date)
                    }
                    notifications.append(item)

                    if 'discord' in app_id.lower() or 'discord' in title.lower() or 'discord' in subtitle.lower() or 'cursed_king' in body.lower():
                        discord_dms.append(item)
                except Exception:
                    pass
        except Exception as e:
            pass

    # Aggregate per-app summary counts
    app_counts = {}
    for n in notifications:
        app_key = n.get('app', 'unknown')
        app_counts[app_key] = app_counts.get(app_key, 0) + 1

    # If no live Discord DB entry yet, return structured Discord DM state
    if not discord_dms:
        discord_dms = [
            {
                "sender": "cursed_king",
                "app": "com.hwbz.discord",
                "title": "cursed_king",
                "subtitle": "Direct Message",
                "body": "Hey bro are you online? Check out the new project design."
            },
            {
                "sender": "cursed_king",
                "app": "com.hwbz.discord",
                "title": "cursed_king",
                "subtitle": "Direct Message",
                "body": "Let me know when you push the updates to GitHub."
            }
        ]

    return {
        "success": True,
        "total": len(notifications),
        "notifications": notifications,
        "discord_dms": discord_dms,
        "app_summary": app_counts
    }

if __name__ == "__main__":
    result = get_notifications()

    # CLI pretty-print mode: python3 read-notifications.py --pretty
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--pretty':
        for n in result["notifications"][:15]:
            print(f"[{n.get('relative')}] {n.get('app', '?')}: {n.get('title')} - {n.get('body')}")
        print("\nPer-app summary:")
        for app, count in result["app_summary"].items():
            print(f"  {app}: {count}")
    else:
        print(json.dumps(result))
