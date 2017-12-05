# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-12-05 02:03
from __future__ import unicode_literals

from django.db import migrations, models

from judge.models.choices import TIMEZONE


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0066_submission_date_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='access_code',
            field=models.CharField(blank=True, default=b'', help_text='An optional code to prompt contestants before they are allowed to join the contest. Leave it blank to disable.', max_length=255, verbose_name='access code'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='timezone',
            field=models.CharField(choices=TIMEZONE, default=b'America/Toronto', max_length=50, verbose_name='location'),
        ),
    ]
