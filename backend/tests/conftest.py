import pytest
from app.core.database import get_knowledge_collection

@pytest.fixture(scope="session", autouse=True)
def clean_fixtures_after_test_session():
    """
    Ensures that temporary test knowledge fixtures are cleaned up after the test session
    so that the live MongoDB collection does not retain fixture/sample data.
    """
    yield
    try:
        col = get_knowledge_collection()
        col.delete_many({"provenance": "approved_astroved_knowledge_base"})
    except Exception:
        pass
