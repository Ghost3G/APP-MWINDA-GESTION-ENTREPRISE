from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0002_message_is_read'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='message_type',
            field=models.CharField(
                choices=[('text', 'Texte'), ('call', 'Appel')],
                default='text',
                max_length=20,
            ),
        ),
    ]
