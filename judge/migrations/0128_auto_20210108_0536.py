# Generated by Django 2.2.15 on 2021-01-08 05:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0127_auto_20210108_0523'),
    ]

    operations = [
        migrations.AlterField(
            model_name='achievement',
            name='rarity',
            field=models.FloatField(default=1, help_text='raresa del Achievement. Una raresa de 1 significa que té una probabilitat normal en apareixer. Una de 2 significa que té el doble de probabilitats que la resta dintre de la seva categoria de qualitat,etc', verbose_name='rarity'),
        ),
    ]
