import tempfile, pytest
from pathlib import Path
from scientra.docs_tools.user_workflow_doc_builder import UserWorkflowDocBuilder
class TestWorkflow:
    def test_build(self):
        d = tempfile.mkdtemp()
        p = Path(d) / "USER_WORKFLOW.md"
        r = UserWorkflowDocBuilder().build(str(p))
        assert p.exists()
