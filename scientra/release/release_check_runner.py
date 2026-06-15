"""Release Check Runner — P6.4 orchestrator."""

from __future__ import annotations
from pathlib import Path
from typing import Any

from scientra.release.release_schema import make_report
from scientra.release.gitignore_checker import GitignoreChecker
from scientra.release.secret_scanner import SecretScanner
from scientra.release.large_file_scanner import LargeFileScanner
from scientra.release.storage_safety_checker import StorageSafetyChecker
from scientra.release.path_hardcode_checker import PathHardcodeChecker
from scientra.release.test_command_checker import TestCommandChecker
from scientra.release.release_report_builder import ReleaseReportBuilder


class ReleaseCheckRunner:
    def __init__(self, root: str | Path | None = None, max_file_mb: int = 20) -> None:
        if root is None: root = Path(__file__).resolve().parent.parent.parent
        self.root = Path(root)
        self.max_file_mb = max_file_mb

    def run(self, check_secrets: bool = True, check_large: bool = True,
            check_gitignore: bool = True, check_storage: bool = True,
            check_paths: bool = True, check_tests: bool = True) -> dict[str, Any]:
        all_p0, all_p1, all_p2, all_p3 = [], [], [], []
        checks: dict[str, int] = {}

        modules = [
            (check_gitignore, GitignoreChecker(self.root).check, "gitignore"),
            (check_secrets, SecretScanner(self.root).scan, "secrets"),
            (check_large, LargeFileScanner(self.root, self.max_file_mb).scan, "large_files"),
            (check_storage, StorageSafetyChecker(self.root).check, "storage_safety"),
            (check_paths, PathHardcodeChecker(self.root).scan, "path_hardcode"),
            (check_tests, TestCommandChecker(self.root).check, "test_commands"),
        ]

        for enabled, func, name in modules:
            if enabled:
                issues = func()
                checks[name] = len(issues)
                for issue in issues:
                    pri = issue.get("priority", "P2")
                    if pri == "P0": all_p0.append(issue)
                    elif pri == "P1": all_p1.append(issue)
                    elif pri == "P2": all_p2.append(issue)
                    else: all_p3.append(issue)

        report = make_report(all_p0, all_p1, all_p2, all_p3, checks)
        ReleaseReportBuilder(self.root).build(report)
        return report
