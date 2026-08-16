from django.db import migrations


def create_sql_group(apps, schema_editor):
    ProblemGroup = apps.get_model('judge', 'ProblemGroup')
    ProblemGroup.objects.get_or_create(name='sql', defaults={'full_name': 'Bases de Dades (SQL)'})


def remove_sql_group(apps, schema_editor):
    ProblemGroup = apps.get_model('judge', 'ProblemGroup')
    ProblemGroup.objects.filter(name='sql').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0140_guide_translation_runtime'),
    ]

    operations = [
        migrations.RunPython(create_sql_group, remove_sql_group),
    ]
