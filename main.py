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
# 🔹 Message automatique DM
# ===========================
@client.on(events.NewMessage(incoming=True))
async def auto_dm(event):
    if event.is_private and not event.message.message.startswith("."):
        await event.reply(
            """👋 Salut ! Je suis ton Userbot Telegram. Voici les commandes disponibles :

📌 **Commandes principales :**

.track @username ou ID
→ Commence à suivre un utilisateur.  
→ Après, un menu interactif te permettra de choisir ce que tu veux suivre :  
   • 📷 Photo de profil  
   • 👤 Nom  
   • 🔗 Username  
   • 📝 Bio  
   • 🟢 Statut en ligne  
   • 📱 Numéro public  
   • ✅ Tout sélectionner (active tout le suivi)

.untrack @username ou ID
→ Arrête le suivi de cet utilisateur.

.list
→ Affiche la liste de tous les utilisateurs suivis.

⚡ **Notes importantes :**
- Le suivi est basé sur l’ID de l’utilisateur → même s’il change de pseudo, il sera toujours suivi.  
- Les notifications apparaissent **en temps quasi réel** pour les modifications de photo, pseudo, bio, statut, etc.  
- Tu peux cliquer sur les boutons du menu pour activer/désactiver le suivi pour chaque élément individuellement.

Pour commencer, tape simplement `.track @username` ou `.track ID` pour l’utilisateur que tu veux suivre."""
        )

# ===========================
# 🔹 Commande .track avec menu interactif
# ===========================
@client.on(events.NewMessage(pattern=r"\.track (.+)"))
async def track_user(event):
    target = event.pattern_match.group(1)
    try:
        user = await client.get_entity(target)
    except Exception as e:
        await event.reply(f"❌ Impossible de trouver l’utilisateur `{target}`.\nErreur : {e}")
        return

    buttons = [
        [Button.inline("📷 Photo de profil", f"photo_{user.id}"), Button.inline("👤 Nom", f"name_{user.id}")],
        [Button.inline("🔗 Username", f"username_{user.id}"), Button.inline("📱 Numéro", f"phone_{user.id}")],
        [Button.inline("🟢 Statut", f"status_{user.id}"), Button.inline("📝 Bio", f"bio_{user.id}")],
        [Button.inline("✅ Tout sélectionner", f"all_{user.id}")]
    ]
    await event.reply(
        f"Quel(s) élément(s) souhaitez-vous suivre pour @{user.username or 'Pas de pseudo'} (ID: {user.id}) ?",
        buttons=buttons
    )

# ===========================
# 🔹 Gestion des boutons avec messages explicatifs
# ===========================
@client.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    action, user_id = data.split("_")
    user_id = int(user_id)

    cursor.execute("SELECT * FROM tracked_users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
        INSERT OR REPLACE INTO tracked_users VALUES
        (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (user_id, "", 0,0,0,0,0,0,"","","","","",""))
        conn.commit()
        row = cursor.execute("SELECT * FROM tracked_users WHERE id=?", (user_id,)).fetchone()

    track_map = {
        "photo": 2,
        "name": 3,
        "username": 4,
        "phone": 5,
        "status": 6,
        "bio": 7
    }

    if action == "all":
        for col_index, col_name in enumerate(['track_photo','track_name','track_username','track_phone','track_status','track_bio'], start=2):
            cursor.execute(f"UPDATE tracked_users SET {col_name}=1 WHERE id=?", (user_id,))
        conn.commit()
        await event.answer(f"Toutes les actions de @{row[1] or 'Pas de pseudo'} (ID: {user_id}) sont suivies !", alert=True)
        return

    col = track_map.get(action)
    current_val = row[col]
    new_val = 1 if current_val == 0 else 0
    col_name = ['track_photo','track_name','track_username','track_phone','track_status','track_bio'][col-2]
    cursor.execute(f"UPDATE tracked_users SET {col_name}=? WHERE id=?", (new_val, user_id))
    conn.commit()

    messages = {
        "photo": f"*Coche bouton photo de profil*\nVous serez notifié quand @{row[1] or 'Pas de pseudo'} ou ID changera sa photo de profil",
        "name": f"*Coche bouton nom*\nVous serez notifié quand @{row[1] or 'Pas de pseudo'} ou ID changera son nom",
        "username": f"*Coche bouton username*\nVous serez notifié quand @{row[1] or 'Pas de pseudo'} ou ID changera son username",
        "phone": f"*Coche bouton numéro*\nVous serez notifié quand @{row[1] or 'Pas de pseudo'} ou ID rendra son numéro public",
        "status": f"*Coche bouton statut*\nVous serez notifié quand @{row[1] or 'Pas de pseudo'} ou ID sera en ligne ou hors ligne",
        "bio": f"*Coche bouton bio*\nVous serez notifié quand @{row[1] or 'Pas de pseudo'} ou ID changera sa bio"
    }
    await event.answer(messages[action], alert=True)

# ===========================
# 🔹 Commandes .list et .untrack
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

@client.on(events.NewMessage(pattern=r"\.untrack (.+)"))
async def untrack_user(event):
    target = event.pattern_match.group(1)
    try:
        user = await client.get_entity(target)
        cursor.execute("DELETE FROM tracked_users WHERE id=?", (user.id,))
        conn.commit()
        await event.reply(f"❌ Suivi arrêté pour @{user.username or 'Pas de pseudo'} (ID : {user.id})")
    except:
        await event.reply(f"❌ Impossible de supprimer `{target}`. Assurez-vous que c’est correct.")

# ===========================
# 🔹 Boucle de surveillance
# ===========================
async def monitor():
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
                    await client.send_message("me", f"📷 Nouvelle photo pour @{user.username or 'Pas de pseudo'}")
                    cursor.execute("UPDATE tracked_users SET last_photo=? WHERE id=?", (str(new_photo_id), user_id))

            # Nom
            if tn and user.first_name != last_name:
                await client.send_message("me", f"👤 Nom modifié : {last_name} → {user.first_name}")
                cursor.execute("UPDATE tracked_users SET last_name=? WHERE id=?", (user.first_name, user_id))

            # Username
            if tu and (user.username or "") != last_username:
                await client.send_message("me", f"🔗 Username modifié : {last_username} → {user.username}")
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

            conn.commit()
            await asyncio.sleep(1)

        await asyncio.sleep(5)

# ===========================
# 🔹 Démarrage
# ===========================
async def main():
    await monitor()

asyncio.run(main())
