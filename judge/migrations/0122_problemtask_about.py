# Generated by Django 2.2.15 on 2020-12-25 08:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0121_auto_20201225_0747'),
    ]

    operations = [
        migrations.AddField(
            model_name='problemtask',
            name='about',
            field=models.TextField(default='', verbose_name='task description'),
        ),
    ]