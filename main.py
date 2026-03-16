import asyncio
import sqlite3
from telethon import TelegramClient, events, functions

api_id = 36767235
api_hash = "6a36bf6c4b15e7eecdb20885a13fc2d7"
session_name = "userbot"

client = TelegramClient(session_name, api_id, api_hash)

# Base de données
conn = sqlite3.connect("tracker.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS tracked_users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    track_photo INTEGER,
    track_name INTEGER,
    track_username INTEGER,
    track_phone INTEGER,
    track_status INTEGER,
    track_bio INTEGER,
    last_photo TEXT,
    last_name TEXT,
    last_username TEXT,
    last_phone TEXT,
    last_status TEXT,
    last_bio TEXT
)
""")
conn.commit()

# ===========================
# DM d'accueil
# ===========================
@client.on(events.NewMessage(incoming=True))
async def welcome_dm(event):
    if event.is_private and not event.message.message.startswith("."):
        await event.reply(
            "👋 Salut ! Je suis ton Userbot Telegram.\n\n"
            "📌 Commandes disponibles :\n"
            ".track @username ou ID → Commence le suivi automatique.\n"
            ".untrack @username ou ID → Arrête le suivi.\n"
            ".list → Affiche les utilisateurs suivis.\n\n"
            "⚡ Tout est suivi automatiquement dès que tu fais `.track`."
        )

# ===========================
# Commande .track
# ===========================
@client.on(events.NewMessage(pattern=r"\.track (.+)"))
async def track_user(event):
    target = event.pattern_match.group(1)
    try:
        user = await client.get_entity(target)
    except Exception as e:
        await event.reply(f"❌ Impossible de trouver l’utilisateur `{target}`.\nErreur : {e}")
        return

    cursor.execute("""
    INSERT OR REPLACE INTO tracked_users
    (id, username, track_photo, track_name, track_username, track_phone, track_status, track_bio,
     last_photo, last_name, last_username, last_phone, last_status, last_bio)
    VALUES (?, ?, 1,1,1,1,1,1,"","","","","","")
    """, (user.id, user.username or ""))
    conn.commit()

    await event.reply(
        f"✅ Utilisateur @{user.username or 'Pas de pseudo'} (ID: {user.id}) est maintenant suivi.\n"
        "Tout (photo, nom, username, bio, statut, numéro public) sera automatiquement surveillé."
    )

# ===========================
# Commande .untrack
# ===========================
@client.on(events.NewMessage(pattern=r"\.untrack (.+)"))
async def untrack_user(event):
    target = event.pattern_match.group(1)
    try:
        user = await client.get_entity(target)
        cursor.execute("DELETE FROM tracked_users WHERE id=?", (user.id,))
        conn.commit()
        await event.reply(f"❌ Suivi arrêté pour @{user.username or 'Pas de pseudo'} (ID : {user.id})")
    except:
        await event.reply(f"❌ Impossible de supprimer `{target}`. Vérifie que c’est correct.")

# ===========================
# Commande .list
# ===========================
@client.on(events.NewMessage(pattern=r"\.list"))
async def list_users(event):
    cursor.execute("SELECT username,id FROM tracked_users")
    rows = cursor.fetchall()
    if not rows:
        await event.reply("Aucun utilisateur suivi.")
        return
    msg = "📋 Comptes suivis :\n"
    for r in rows:
        msg += f"• @{r[0] or 'Pas de pseudo'} (ID : {r[1]})\n"
    await event.reply(msg)

# ===========================
# Surveillance en temps réel
# ===========================
async def monitor_users():
    await client.start()
    while True:
        cursor.execute("SELECT * FROM tracked_users")
        users = cursor.fetchall()
        for u in users:
            user_id, username, tp, tn, tu, tph, ts, tb, last_photo, last_name, last_username, last_phone, last_status, last_bio = u
            try:
                user = await client.get_entity(user_id)
            except:
                continue

            # Photo
            if tp:
                photos = await client.get_profile_photos(user)
                new_photo_id = photos[0].id if photos else None
                if str(new_photo_id) != last_photo:
                    if photos:
                        await client.send_file("me", photos[0], caption=f"📷 Nouvelle photo pour @{user.username or 'Pas de pseudo'}")
                    else:
                        await client.send_message("me", f"📷 Photo supprimée pour @{user.username or 'Pas de pseudo'}")
                    cursor.execute("UPDATE tracked_users SET last_photo=? WHERE id=?", (str(new_photo_id), user_id))

            # Nom
            if tn and user.first_name != last_name:
                await client.send_message("me", f"👤 Nom modifié pour @{user.username or 'Pas de pseudo'} : {last_name} → {user.first_name}")
                cursor.execute("UPDATE tracked_users SET last_name=? WHERE id=?", (user.first_name, user_id))

            # Username
            if tu and (user.username or "") != last_username:
                await client.send_message("me", f"🔗 Username modifié pour @{user.username or 'Pas de pseudo'} : {last_username} → {user.username or ''}")
                cursor.execute("UPDATE tracked_users SET last_username=? WHERE id=?", (user.username or "", user_id))

            # Bio
            if tb:
                full = await client(functions.users.GetFullUserRequest(user.id))
                bio_text = full.about or ""
                if bio_text != last_bio:
                    await client.send_message("me", f"📝 Bio modifiée pour @{user.username or 'Pas de pseudo'} : {bio_text}")
                    cursor.execute("UPDATE tracked_users SET last_bio=? WHERE id=?", (bio_text, user_id))

            # Statut
            if ts:
                status = "en ligne" if getattr(user.status, 'was_online', None) is None and getattr(user.status, 'expires', None) is None else "hors ligne"
                if status != last_status:
                    await client.send_message("me", f"🟢 Statut changé pour @{user.username or 'Pas de pseudo'} : {status}")
                    cursor.execute("UPDATE tracked_users SET last_status=? WHERE id=?", (status, user_id))

            # Numéro public
            if tph:
                full = await client(functions.users.GetFullUserRequest(user.id))
                phone = full.user.phone or ""
                if phone != last_phone:
                    await client.send_message("me", f"📱 Numéro rendu public pour @{user.username or 'Pas de pseudo'} : {phone}")
                    cursor.execute("UPDATE tracked_users SET last_phone=? WHERE id=?", (phone, user_id))

            conn.commit()
        await asyncio.sleep(5)  # pause entre chaque cycle

# ===========================
# Lancement parallèle
# ===========================
async def main():
    await client.start()
    await asyncio.gather(
        monitor_users(),
        client.run_until_disconnected()
    )

asyncio.run(main())
