#!/usr/bin/env python
"""
Test de scénario réel : Utilisateur envoie des messages et reçoit des notifications
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AppMwinda.settings')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from messaging.models import Message

User = get_user_model()

print("=" * 70)
print("SCÉNARIO RÉEL : Utilisateur reçoit et consulte des messages")
print("=" * 70)

# 1. Préparer le scénario
print("\n[SETUP] Préparation du scénario...")
alice, _ = User.objects.get_or_create(username='alice', defaults={'email': 'alice@test.com'})
bob, _ = User.objects.get_or_create(username='bob', defaults={'email': 'bob@test.com'})
charlie, _ = User.objects.get_or_create(username='charlie', defaults={'email': 'charlie@test.com'})

# Supprimer les anciens messages
Message.objects.filter(receiver=alice).delete()
print("✓ Utilisateurs prêts : Alice, Bob, Charlie")

# 2. Bob et Charlie envoient des messages à Alice
print("\n[ÉTAPE 1] Bob et Charlie envoient 3 messages à Alice...")
msg1 = Message.objects.create(sender=bob, receiver=alice, content="Salut Alice ! Comment ça va ?")
msg2 = Message.objects.create(sender=bob, receiver=alice, content="T'as des nouvelles ?")
msg3 = Message.objects.create(sender=charlie, receiver=alice, content="Coucou Alice !")

print(f"✓ Messages créés (tous non lus initialement)")
print(f"  - Bob → Alice : {msg1.content}")
print(f"  - Bob → Alice : {msg2.content}")
print(f"  - Charlie → Alice : {msg3.content}")

# 3. Alice se connecte
print("\n[ÉTAPE 2] Alice se connecte...")
client = Client()
client.force_login(alice)
print("✓ Alice est connectée")

# 4. Avant de consulter les messages - vérifier les notifications
print("\n[ÉTAPE 3] État des notifications AVANT consultation...")
response = client.get('/messaging/api/unread-count/')
data = response.json()
print(f"✓ API /messaging/api/unread-count/ :")
print(f"  - Messages non lus : {data['unread_count']}")
print(f"  - Conversations avec messages non lus : {data['unread_conversations']}")

response = client.get('/messaging/api/conversations/')
conversations = response.json()['conversations']
print(f"✓ API /messaging/api/conversations/ :")
for conv in conversations:
    if conv['unread_count'] > 0:
        print(f"  - {conv['username']} : ⏺ {conv['unread_count']} message(s) non lu(s)")

# 5. Alice clique sur la conversation avec Bob
print("\n[ÉTAPE 4] Alice clique sur la conversation avec Bob...")
response = client.get(f'/messaging/api/messages/{bob.id}/')
messages = response.json()['messages']
print(f"✓ Alice a ouvert la conversation avec Bob ({len(messages)} messages)")

# 6. Vérifier après consultation
print("\n[ÉTAPE 5] État des notifications APRÈS avoir lu Bob...")
unread_bob = Message.objects.filter(sender=bob, receiver=alice, is_read=False).count()
print(f"✓ Messages de Bob non lus : {unread_bob} (attendu: 0)")

response = client.get('/messaging/api/unread-count/')
data = response.json()
print(f"✓ API /messaging/api/unread-count/ :")
print(f"  - Messages non lus : {data['unread_count']} (attendu: 1 de Charlie)")
print(f"  - Conversations avec messages non lus : {data['unread_conversations']} (attendu: 1)")

response = client.get('/messaging/api/conversations/')
conversations = response.json()['conversations']
print(f"✓ Badges de contact mis à jour :")
for conv in conversations:
    if conv['username'] in ['bob', 'charlie']:
        badge = f"⏺ {conv['unread_count']}" if conv['unread_count'] > 0 else "✓"
        print(f"  - {conv['username']} : {badge}")

# 7. Alice ouvre la conversation avec Charlie
print("\n[ÉTAPE 6] Alice ouvre la conversation avec Charlie...")
response = client.get(f'/messaging/api/messages/{charlie.id}/')
messages = response.json()['messages']
print(f"✓ Alice a ouvert la conversation avec Charlie ({len(messages)} message)")

# 8. État final
print("\n[ÉTAPE 7] État final du systeme...")
response = client.get('/messaging/api/unread-count/')
data = response.json()
print(f"✓ API /messaging/api/unread-count/ :")
print(f"  - Messages non lus : {data['unread_count']} (attendu: 0)")
print(f"  - Conversations avec messages non lus : {data['unread_conversations']} (attendu: 0)")

total_unread = Message.objects.filter(receiver=alice, is_read=False).count()
print(f"✓ Total messages non lus pour Alice : {total_unread}")

print("\n" + "=" * 70)
if total_unread == 0:
    print("✓✓✓ SUCCÈS : Système de notification fonctionne parfaitement ! ✓✓✓")
else:
    print(f"⚠ Attention : {total_unread} message(s) non lus restant(s)")
print("=" * 70)
