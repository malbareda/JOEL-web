# Generated by Django 2.2.15 on 2020-11-16 22:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0117_auto_20200911_1836'),
    ]

    operations = [
        migrations.AlterField(
            model_name='problemtranslation',
            name='language',
            field=models.CharField(choices=[('ca', 'Catalan'), ('en', 'English'), ('es', 'Spanish')], max_length=7, verbose_name='language'),
        ),
    ]