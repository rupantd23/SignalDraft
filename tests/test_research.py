from src.models import ProspectInput
from src.research import ResearchService


class FakeTavilyClient:
    def __init__(self):
        self.search_calls = []

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return {"results": []}


def test_research_includes_a_linkedin_query():
    service = ResearchService.__new__(ResearchService)
    service.client = FakeTavilyClient()
    prospect = ProspectInput(
        full_name="Jane Smith",
        company_name="Acme Corporation",
        company_domain="acme.com",
    )

    assert service.research(prospect) == []
    linkedin_calls = [
        call
        for call in service.client.search_calls
        if "site:linkedin.com/in" in call["query"]
    ]
    assert len(linkedin_calls) == 1
    assert linkedin_calls[0]["include_domains"] == ["linkedin.com"]
