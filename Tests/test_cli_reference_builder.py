import tempfile, pytest
from pathlib import Path
from scientra.docs_tools.cli_reference_builder import CLIReferenceBuilder
class TestCLI:
    def test_build(self):
        d = tempfile.mkdtemp()
        p = Path(d) / "CLI_REFERENCE.md"
        r = CLIReferenceBuilder().build(str(p))
        assert p.exists(); assert p.read_text(encoding="utf-8")
