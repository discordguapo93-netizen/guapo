import asyncio
import sqlite3
from telethon import TelegramClient, events, Button, functions

# ===========================
# 🔹 Configuration API
# ===========================
api_id = 36767235
api_hash = "6a36bf6c4b15e7eecdb20885a13fc2d7"
session_name = "userbot"

client = TelegramClient(session_name, api_id, api_hash)

# ===========================
# 🔹 Base SQLite
# ===========================
conn = sqlite3.connect("tracker.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tracked_users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    track_photo INTEGER DEFAULT 0,
    track_name INTEGER DEFAULT 0,
    track_username INTEGER DEFAULT 0,
    track_phone INTEGER DEFAULT 0,
    track_status INTEGER DEFAULT 0,
    track_bio INTEGER DEFAULT 0,
    last_photo TEXT,
    last_name TEXT,
    last_username TEXT,
    last_phone TEXT,
    last_status TEXT,
    last_bio TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_tracks (
    user_id INTEGER,
    tracker_id INTEGER,
    PRIMARY KEY(user_id, tracker_id)
)
""")
conn.commit()

# ===========================
# 🔹 Fonction boutons dynamiques
# ===========================
def create_buttons(user_row):
    return [
        [Button.inline(f"{'✅' if user_row['track_photo'] else '❌'} Photo", f"photo_{user_row['id']}"),
         Button.inline(f"{'✅' if user_row['track_name'] else '❌'} Nom", f"name_{user_row['id']}")],
        [Button.inline(f"{'✅' if user_row['track_username'] else '❌'} Username", f"username_{user_row['id']}"),
         Button.inline(f"{'✅' if user_row['track_phone'] else '❌'} Numéro", f"phone_{user_row['id']}")],
        [Button.inline(f"{'✅' if user_row['track_status'] else '❌'} Statut", f"status_{user_row['id']}"),
         Button.inline(f"{'✅' if user_row['track_bio'] else '❌'} Bio", f"bio_{user_row['id']}")],
        [Button.inline("✅ Tout", f"all_{user_row['id']}")]
    ]

# ===========================
# 🔹 Commande .track
# ===========================
@client.on(events.NewMessage(pattern=r"\.track (.+)"))
async def track_user(event):
    target = event.pattern_match.group(1)
    tracker_id = event.sender_id
    try:
        user = await client.get_entity(target)
    except Exception as e:
        await event.reply(f"❌ Impossible de trouver `{target}`.\nErreur: {e}")
        return

    cursor.execute("INSERT OR IGNORE INTO tracked_users (id, username) VALUES (?, ?)", (user.id, user.username))
    cursor.execute("INSERT OR IGNORE INTO user_tracks (user_id, tracker_id) VALUES (?, ?)", (user.id, tracker_id))
    conn.commit()

    cursor.execute("SELECT * FROM tracked_users WHERE id=?", (user.id,))
    user_row = dict(cursor.fetchone())
    msg = await client.send_message(tracker_id, f"Que souhaitez-vous suivre pour @{user.username or 'Pas de pseudo'} ?", buttons=create_buttons(user_row))

# ===========================
# 🔹 Boutons dynamiques en MP
# ===========================
@client.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode()
    action, user_id = data.split("_")
    user_id = int(user_id)
    tracker_id = event.sender_id

    cursor.execute("SELECT * FROM tracked_users WHERE id=?", (user_id,))
    user_row = dict(cursor.fetchone())

    mapping = {
        "photo": "track_photo",
        "name": "track_name",
        "username": "track_username",
        "phone": "track_phone",
        "status": "track_status",
        "bio": "track_bio"
    }

    if action == "all":
        for col in mapping.values():
            cursor.execute(f"UPDATE tracked_users SET {col}=1 WHERE id=?", (user_id,))
        conn.commit()
        await event.answer("✅ Tout le suivi est activé !", alert=True)
    else:
        col = mapping.get(action)
        new_val = 0 if user_row[col] else 1
        cursor.execute(f"UPDATE tracked_users SET {col}=? WHERE id=?", (new_val, user_id))
        conn.commit()
        await event.answer(f"🔔 Suivi {col.replace('track_','')} {'activé' if new_val else 'désactivé'} !", alert=True)

    # Actualisation des boutons
    cursor.execute("SELECT * FROM tracked_users WHERE id=?", (user_id,))
    updated_row = dict(cursor.fetchone())
    await event.edit(f"Que souhaitez-vous suivre pour @{updated_row['username'] or 'Pas de pseudo'} ?", buttons=create_buttons(updated_row))

# ===========================
# 🔹 Liste des suivis
# ===========================
@client.on(events.NewMessage(pattern=r"\.list"))
async def list_users(event):
    tracker_id = event.sender_id
    cursor.execute("""
    SELECT u.username,u.id
    FROM tracked_users u
    JOIN user_tracks t ON u.id=t.user_id
    WHERE t.tracker_id=?
    """, (tracker_id,))
    rows = cursor.fetchall()
    if not rows:
        await client.send_message(tracker_id, "Aucun utilisateur suivi.")
        return
    msg = "📋 Comptes suivis :\n" + "\n".join([f"• @{r['username'] or 'Pas de pseudo'} (ID: {r['id']})" for r in rows])
    await client.send_message(tracker_id, msg)

# ===========================
# 🔹 Commande .untrack
# ===========================
@client.on(events.NewMessage(pattern=r"\.untrack (.+)"))
async def untrack_user(event):
    target = event.pattern_match.group(1)
    tracker_id = event.sender_id
    try:
        user = await client.get_entity(target)
        cursor.execute("DELETE FROM user_tracks WHERE user_id=? AND tracker_id=?", (user.id, tracker_id))
        conn.commit()
        await client.send_message(tracker_id, f"❌ Suivi arrêté pour @{user.username or 'Pas de pseudo'}")
    except:
        await client.send_message(tracker_id, f"❌ Impossible de supprimer `{target}`.")

# ===========================
# 🔹 Boucle de surveillance (notifications MP)
# ===========================
async def monitor():
    while True:
        cursor.execute("SELECT * FROM tracked_users")
        users = cursor.fetchall()
        for u in users:
            user_id = u['id']
            cursor.execute("SELECT tracker_id FROM user_tracks WHERE user_id=?", (user_id,))
            trackers = [r['tracker_id'] for r in cursor.fetchall()]

            try:
                user = await client.get_entity(user_id)
            except:
                continue

            # Photo
            if u['track_photo']:
                photos = await client.get_profile_photos(user)
                new_photo = str(photos[0].id) if photos else None
                if new_photo != u['last_photo']:
                    for tracker in trackers:
                        await client.send_message(tracker, f"📷 Nouvelle photo pour @{user.username or 'Pas de pseudo'}")
                    cursor.execute("UPDATE tracked_users SET last_photo=? WHERE id=?", (new_photo, user_id))

            # Nom
            if u['track_name'] and user.first_name != u['last_name']:
                for tracker in trackers:
                    await client.send_message(tracker, f"👤 Nom modifié: {u['last_name']} → {user.first_name}")
                cursor.execute("UPDATE tracked_users SET last_name=? WHERE id=?", (user.first_name, user_id))

            # Username
            if u['track_username'] and (user.username or "") != u['last_username']:
                for tracker in trackers:
                    await client.send_message(tracker, f"🔗 Username modifié: {u['last_username']} → {user.username}")
                cursor.execute("UPDATE tracked_users SET last_username=? WHERE id=?", (user.username or "", user_id))

            # Bio
            if u['track_bio']:
                full = await client(functions.users.GetFullUserRequest(user.id))
                bio_text = full.about or ""
                if bio_text != u['last_bio']:
                    for tracker in trackers:
                        await client.send_message(tracker, f"📝 Bio modifiée pour @{user.username or 'Pas de pseudo'}: {bio_text}")
                    cursor.execute("UPDATE tracked_users SET last_bio=? WHERE id=?", (bio_text, user_id))

            # Statut
            if u['track_status']:
                status = "en ligne" if getattr(user.status, 'was_online', None) is None and getattr(user.status, 'expires', None) is None else "hors ligne"
                if status != u['last_status']:
                    for tracker in trackers:
                        await client.send_message(tracker, f"🟢 Statut changé pour @{user.username or 'Pas de pseudo'}: {status}")
                    cursor.execute("UPDATE tracked_users SET last_status=? WHERE id=?", (status, user_id))

            conn.commit()
            await asyncio.sleep(1)
        await asyncio.sleep(5)

# ===========================
# 🔹 Démarrage
# ===========================
async def main():
    await client.start()
    print("✅ Userbot connecté !")
    client.loop.create_task(monitor())
    await client.run_until_disconnected()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
