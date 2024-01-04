# Generated by Django 2.2.15 on 2020-12-25 08:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0123_auto_20201225_0822'),
    ]

    operations = [
        migrations.AlterField(
            model_name='problemtask',
            name='name',
            field=models.SlugField(help_text='Task name shown in URL', max_length=128, verbose_name='task slug'),
        ),
        migrations.AlterField(
            model_name='problemtask',
            name='problems',
            field=models.ManyToManyField(help_text='the problems this task has.', related_name='tasks_of_problem', to='judge.Problem', verbose_name='Problems in task'),
        ),
    ]