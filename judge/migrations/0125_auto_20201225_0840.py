# Generated by Django 2.2.15 on 2020-12-25 08:40

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0124_auto_20201225_0832'),
    ]

    operations = [
        migrations.AlterField(
            model_name='problemtask',
            name='name',
            field=models.CharField(help_text='A short, unique code for the task, used in the url after /task/', max_length=20, unique=True, validators=[django.core.validators.RegexValidator('^[a-z0-9]+$', 'Task code must be ^[a-z0-9]+$')], verbose_name='task code'),
        ),
    ]
