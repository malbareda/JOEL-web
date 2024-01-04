# Generated by Django 2.2.15 on 2020-12-25 04:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0118_auto_20201116_2233'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProblemTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=20, unique=True, verbose_name='task ID')),
                ('full_name', models.CharField(max_length=100, verbose_name='task name')),
            ],
            options={
                'verbose_name': 'task',
                'verbose_name_plural': 'tasks',
                'ordering': ['full_name'],
            },
        ),
        migrations.AlterField(
            model_name='problem',
            name='types',
            field=models.ManyToManyField(help_text='The tasks this problem belongs with, as shown on the tasks page.', to='judge.ProblemTask', verbose_name='problem tasks'),
        ),
    ]