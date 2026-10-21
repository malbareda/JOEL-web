# Feedback the judge engine itself gives when its sandbox stops a program (not a checker): cptbox killing a
# disallowed syscall ("<name> syscall disallowed", dmoj/result.py in the judge; any language running under cptbox,
# e.g. Python or Java 25), and java_executor.py's message for an AccessControlException from the Java 8/11/Kotlin
# SecurityManager. The bridge marks these SEC (like the SQL checker's marker): the user explicitly prefers false
# positives (e.g. a legitimate program hitting a syscall cptbox doesn't know about yet) to letting a real attempt pass
# as an ordinary runtime error.
SANDBOX_SYSCALL_SUFFIX = ' syscall disallowed'
SANDBOX_JAVA_FEEDBACK = 'Has intentat hackejar-me'


def is_sandbox_violation(status, feedback):
    """Whether a test case with this status and feedback was stopped by the judge's sandbox."""
    if status not in ('RTE', 'IR'):
        return False
    feedback = (feedback or '').strip()
    return feedback.endswith(SANDBOX_SYSCALL_SUFFIX) or feedback.startswith(SANDBOX_JAVA_FEEDBACK)


def is_sandbox_feedback(feedback):
    """Same check for a case already stored as SEC, whose original status (RTE/IR) is no longer known."""
    return is_sandbox_violation('RTE', feedback)
