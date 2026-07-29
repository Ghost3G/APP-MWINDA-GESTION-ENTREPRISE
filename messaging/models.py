from django.db import models
from django.conf import settings

# Create your models here.

class Message(models.Model):
    MESSAGE_TYPE_CHOICES = (
        ('text', 'Texte'),
        ('call', 'Appel'),
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )

    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages"
    )

    content = models.TextField()

    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text')

    created_at = models.DateTimeField(auto_now_add=True)
    
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}"