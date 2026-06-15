import pytest
from scientra.release.gitignore_checker import GitignoreChecker
class TestGitignore:
    def test_check(self): r = GitignoreChecker().check(); assert isinstance(r, list)
