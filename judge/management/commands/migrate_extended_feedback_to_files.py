from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import connection

from judge.utils.submission_feedback import submission_feedback_storage

CHUNK_SIZE = 2000


class Command(BaseCommand):
    help = (
        'One-off backfill: moves SubmissionTestCase.extended_feedback (legacy TextField, '
        'still present in the DB but no longer used by the model) out to files on disk, '
        'populating extended_feedback_file for every row that still needs it. '
        'Safe to re-run: already-migrated rows are skipped.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='count rows without writing anything')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        cursor = connection.cursor()

        cursor.execute('''
            SELECT COUNT(*) FROM judge_submissiontestcase
            WHERE extended_feedback IS NOT NULL AND extended_feedback != ''
              AND (extended_feedback_file IS NULL OR extended_feedback_file = '')
        ''')
        total = cursor.fetchone()[0]
        self.stdout.write('Files per migrar: %d' % total)
        if dry_run or total == 0:
            return

        migrated = 0
        last_id = 0
        while True:
            cursor.execute('''
                SELECT id, submission_id, `case`, extended_feedback
                FROM judge_submissiontestcase
                WHERE id > %s
                  AND extended_feedback IS NOT NULL AND extended_feedback != ''
                  AND (extended_feedback_file IS NULL OR extended_feedback_file = '')
                ORDER BY id
                LIMIT %s
            ''', [last_id, CHUNK_SIZE])
            rows = cursor.fetchall()
            if not rows:
                break

            updates = []
            for row_id, submission_id, case, extended_feedback in rows:
                bucket = '%03d' % (submission_id % 1000)
                path = '%s/%d_%d.txt' % (bucket, submission_id, case)
                saved_name = submission_feedback_storage.save(path, ContentFile(extended_feedback.encode('utf-8')))
                updates.append((saved_name, row_id))

            cursor.executemany(
                'UPDATE judge_submissiontestcase SET extended_feedback_file = %s WHERE id = %s',
                updates,
            )

            migrated += len(rows)
            last_id = rows[-1][0]
            self.stdout.write('Migrats %d / %d (last id=%d)' % (migrated, total, last_id))

        self.stdout.write(self.style.SUCCESS('Fet. %d files migrades a %s' % (
            migrated, submission_feedback_storage.location)))
