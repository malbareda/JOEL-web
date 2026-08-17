from django.db import migrations


def rename_label(apps, schema_editor):
    ProblemGroup = apps.get_model('judge', 'ProblemGroup')
    ProblemGroup.objects.filter(name='sql').update(full_name='Bases de Dades')


def restore_label(apps, schema_editor):
    ProblemGroup = apps.get_model('judge', 'ProblemGroup')
    ProblemGroup.objects.filter(name='sql').update(full_name='Bases de Dades (SQL)')


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0142_sql_points'),
    ]

    operations = [
        migrations.RunPython(rename_label, restore_label),
    ]
