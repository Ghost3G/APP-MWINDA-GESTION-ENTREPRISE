#!/usr/bin/env python
"""
Script pour tester le système de notifications de messages
"""
import os
import sys
import django
from django.contrib.auth import get_user_model
from django.test import Client

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AppMwinda.settings')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
django.setup()

from messaging.models import Message

User = get_user_model()
client = Client()

print("=" * 60)
print("TEST : Système de Notifications de Messages")
print("=" * 60)

# 1. Créer ou récupérer des utilisateurs de test
print("\n[1] Création/récupération des utilisateurs...")
user1, _ = User.objects.get_or_create(
    username='testuser1',
    defaults={'email': 'test1@example.com', 'first_name': 'Test', 'last_name': 'User1'}
)
user2, _ = User.objects.get_or_create(
    username='testuser2',
    defaults={'email': 'test2@example.com', 'first_name': 'Test', 'last_name': 'User2'}
)
user3, _ = User.objects.get_or_create(
    username='testuser3',
    defaults={'email': 'test3@example.com', 'first_name': 'Test', 'last_name': 'User3'}
)
print(f"✓ Utilisateurs créés : {user1.username}, {user2.username}, {user3.username}")

# 2. Créer des messages de test
print("\n[2] Création de messages de test...")
# Messages de user2 vers user1
msg1 = Message.objects.create(sender=user2, receiver=user1, content="Hello user1 from user2")
msg2 = Message.objects.create(sender=user2, receiver=user1, content="How are you?")
# Messages de user3 vers user1
msg3 = Message.objects.create(sender=user3, receiver=user1, content="Hi user1 from user3")
# Messages de user1 vers user2
msg4 = Message.objects.create(sender=user1, receiver=user2, content="Hi user2, responding to you")
msg4.is_read = True  # Marquer comme lu
msg4.save()

print(f"✓ Messages créés :")
print(f"  - Message 1 : user2 → user1 (non lu)")
print(f"  - Message 2 : user2 → user1 (non lu)")
print(f"  - Message 3 : user3 → user1 (non lu)")
print(f"  - Message 4 : user1 → user2 (LU)")

# 3. Se connecter avec user1
print("\n[3] Connexion avec user1...")
login_success = client.login(username='testuser1', password='')
print(f"✓ Connexion : {'SUCCESS' if login_success else 'FAILED (connexion sans mot de passe)'}")

# On va faire une requête GET simple pour établir la session si nécessaire
# (Dans Django test, on peut forcer une session)
client.force_login(user1)
print(f"✓ Force login : user1 connecté")

# 4. Tester l'API get_unread_count
print("\n[4] Test API /messaging/api/unread-count/...")
try:
    response = client.get('/messaging/api/unread-count/')
    print(f"   Status Code : {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Response JSON : {data}")
        print(f"   - unread_count : {data.get('unread_count')} (attendu: 3)")
        print(f"   - unread_conversations : {data.get('unread_conversations')} (attendu: 2)")
    else:
        print(f"   ✗ Erreur : {response.content.decode()}")
except Exception as e:
    print(f"   ✗ Exception : {e}")

# 5. Tester l'API get_conversations
print("\n[5] Test API /messaging/api/conversations/...")
try:
    response = client.get('/messaging/api/conversations/')
    print(f"   Status Code : {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Response JSON reçu")
        conversations = data.get('conversations', [])
        print(f"   - Nombre de conversations : {len(conversations)}")
        
        for conv in conversations:
            print(f"     • {conv['username']} : {conv['unread_count']} message(s) non lu(s)")
        
        # Vérifier les résultats
        user2_conv = next((c for c in conversations if c['id'] == user2.id), None)
        user3_conv = next((c for c in conversations if c['id'] == user3.id), None)
        
        if user2_conv and user2_conv['unread_count'] == 2:
            print(f"   ✓ Correct : {user2_conv['unread_count']} messages non lus de user2")
        if user3_conv and user3_conv['unread_count'] == 1:
            print(f"   ✓ Correct : {user3_conv['unread_count']} message non lu de user3")
    else:
        print(f"   ✗ Erreur : {response.content.decode()}")
except Exception as e:
    print(f"   ✗ Exception : {e}")

# 6. Tester le marquage automatique comme lu
print("\n[6] Test marquage automatique comme lu...")
print(f"   Messages non lus de user1 AVANT : {Message.objects.filter(receiver=user1, is_read=False).count()}")
try:
    response = client.get(f'/messaging/api/messages/{user2.id}/')
    if response.status_code == 200:
        print(f"   ✓ Requête API effectuée pour user2")
        unread_after = Message.objects.filter(receiver=user1, is_read=False).count()
        print(f"   Messages non lus de user1 APRÈS : {unread_after}")
        
        # Les messages de user2 doivent être marqués comme lus
        user2_unread = Message.objects.filter(sender=user2, receiver=user1, is_read=False).count()
        print(f"   Messages de user2 → user1 non lus : {user2_unread} (attendu: 0)")
        if user2_unread == 0:
            print(f"   ✓ Marquage automatique fonctionne !")
except Exception as e:
    print(f"   ✗ Exception : {e}")

# 7. Vérifier l'état final
print("\n[7] État final du système...")
print(f"   Total messages : {Message.objects.count()}")
print(f"   Total lus : {Message.objects.filter(is_read=True).count()}")
print(f"   Total non lus : {Message.objects.filter(is_read=False).count()}")

print("\n" + "=" * 60)
print("✓ TESTS TERMINES")
print("=" * 60)
