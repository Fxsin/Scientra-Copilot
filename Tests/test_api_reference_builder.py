import tempfile, pytest
from pathlib import Path
from scientra.docs_tools.api_reference_builder import APIReferenceBuilder
class TestAPI:
    def test_build(self):
        d = tempfile.mkdtemp()
        p = Path(d) / "API_REFERENCE.md"
        r = APIReferenceBuilder().build(str(p))
        assert p.exists()
