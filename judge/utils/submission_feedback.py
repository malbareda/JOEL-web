import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage

__all__ = ['submission_feedback_storage', 'submission_feedback_file']


class SubmissionFeedbackStorage(FileSystemStorage):
    def __init__(self):
        super(SubmissionFeedbackStorage, self).__init__(settings.DMOJ_SUBMISSION_FEEDBACK_ROOT)

    def get_available_name(self, name, max_length=None):
        # Each (submission, case) pair is unique and immutable once written, so
        # overwrite in place instead of appending a Django-style random suffix.
        if self.exists(name):
            self.delete(name)
        return name


submission_feedback_storage = SubmissionFeedbackStorage()


def submission_feedback_file(instance, filename):
    # Bucket by the submission id so a single directory never has to hold
    # one entry per submission test case (currently ~900k rows and growing).
    bucket = '%03d' % (instance.submission_id % 1000)
    return os.path.join(bucket, '%d_%d.txt' % (instance.submission_id, instance.case))
