"""
Tests for the multi-agent orchestration system
"""

import pytest

from domainidom.multi_agent import (
    BrainstormerAgent,
    ResearcherAgent,
    AnalyzerAgent,
    PackagerAgent,
    MultiAgentOrchestrator,
    run_multi_agent_research,
    AgentMessage,
    AgentResult,
)
from domainidom.models import IdeaInput, ScoredCandidate, DomainCheckResult


class TestAgentMessage:
    def test_agent_message_creation(self):
        from datetime import datetime

        msg = AgentMessage(
            from_agent="test1", to_agent="test2", content="test content", timestamp=datetime.now()
        )
        assert msg.from_agent == "test1"
        assert msg.to_agent == "test2"
        assert msg.content == "test content"
        assert msg.message_type == "data"


class TestAgentResult:
    def test_agent_result_success(self):
        result = AgentResult(agent_name="test", success=True, data=["item1", "item2"])
        assert result.agent_name == "test"
        assert result.success is True
        assert result.data == ["item1", "item2"]
        assert result.error is None


class TestBrainstormerAgent:
    @pytest.mark.asyncio
    async def test_brainstormer_execution(self):
        agent = BrainstormerAgent()
        idea_input = IdeaInput(idea="test business idea", max_candidates=5)

        result = await agent.execute(idea_input)

        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) > 0
        assert result.error is None
        assert result.execution_time > 0

    @pytest.mark.asyncio
    async def test_brainstormer_with_invalid_input(self):
        agent = BrainstormerAgent()

        # Test with None idea
        idea_input = IdeaInput(idea=None, max_candidates=5)
        result = await agent.execute(idea_input)

        # Should still work with fallback
        assert result.success is True
        assert isinstance(result.data, list)


class TestResearcherAgent:
    @pytest.mark.asyncio
    async def test_researcher_execution(self):
        agent = ResearcherAgent()
        input_data = (["TestName", "AnotherName"], ["com", "io"])

        result = await agent.execute(input_data)

        assert result.success is True
        assert isinstance(result.data, dict)
        assert "TestName" in result.data
        assert "AnotherName" in result.data
        assert result.error is None

    def test_generate_variants(self):
        agent = ResearcherAgent()
        variants = agent._generate_variants("TestName")

        assert "testname" in variants
        assert "gettestname" in variants
        assert "mytestname" in variants
        assert len(variants) > 1


class TestAnalyzerAgent:
    @pytest.mark.asyncio
    async def test_analyzer_execution(self):
        agent = AnalyzerAgent()

        # Mock input data
        names = ["TestName"]
        research_results = {
            "TestName": [("testname.com", DomainCheckResult("testname.com", True, 10.0, "test"))]
        }
        input_data = (names, research_results)

        result = await agent.execute(input_data)

        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) == 1
        assert isinstance(result.data[0], ScoredCandidate)
        assert result.error is None

    def test_seo_analysis(self):
        agent = AnalyzerAgent()

        # Test short name (good SEO)
        score = agent._analyze_seo_potential("TestApp")
        assert score > 0.5

        # Test very long name (worse SEO)
        score = agent._analyze_seo_potential("VeryLongComplexBusinessName")
        assert score <= 1.0

    def test_brand_safety_analysis(self):
        agent = AnalyzerAgent()

        # Test safe name
        score = agent._analyze_brand_safety("SafeName")
        assert score > 0.7

        # Test risky name
        score = agent._analyze_brand_safety("HackSite")
        assert score < 0.6

    def test_cultural_analysis(self):
        agent = AnalyzerAgent()

        # Test ASCII name
        score = agent._analyze_cultural_appropriateness("TestName")
        assert score > 0.8

        # Test name with difficult pronunciation
        score = agent._analyze_cultural_appropriateness("Tschaikovsky")
        assert score < 1.0


class TestPackagerAgent:
    @pytest.mark.asyncio
    async def test_packager_execution(self):
        agent = PackagerAgent()

        # Mock scored candidates
        scored_candidates = [
            ScoredCandidate(
                name="TestName",
                score=0.8,
                details={"length": 0.9, "balance": 0.8, "availability": 0.7},
                domains=[DomainCheckResult("testname.com", True, 10.0, "test")],
            )
        ]

        result = await agent.execute(scored_candidates)

        assert result.success is True
        assert isinstance(result.data, dict)
        assert "summary" in result.data
        assert "recommendations" in result.data
        assert "alternatives" in result.data
        assert "insights" in result.data

    def test_generate_summary(self):
        agent = PackagerAgent()

        candidates = [
            ScoredCandidate(
                name="Test",
                score=0.8,
                details={},
                domains=[DomainCheckResult("test.com", True, 10.0, "test")],
            )
        ]

        summary = agent._generate_summary(candidates)
        assert summary["total_candidates"] == 1
        assert summary["available_domains"] == 1
        assert "generated_at" in summary

    def test_generate_recommendations(self):
        agent = PackagerAgent()

        candidates = [
            ScoredCandidate(
                name="Test",
                score=0.8,
                details={"length": 0.9, "balance": 0.8, "seo": 0.7},
                domains=[DomainCheckResult("test.com", True, 10.0, "test")],
            )
        ]

        recommendations = agent._generate_recommendations(candidates)
        assert len(recommendations) == 1
        assert recommendations[0]["rank"] == 1
        assert recommendations[0]["name"] == "Test"
        assert "rationale" in recommendations[0]


class TestMultiAgentOrchestrator:
    @pytest.mark.asyncio
    async def test_orchestrator_workflow(self):
        orchestrator = MultiAgentOrchestrator()
        idea_input = IdeaInput(idea="test business", tlds=["com"], max_candidates=3)

        result = await orchestrator.execute_workflow(idea_input)

        assert "candidates" in result
        assert "summary" in result
        assert "recommendations" in result
        assert "execution_log" in result
        assert result["workflow_version"] == "multi-agent-v1.0"
        assert len(orchestrator.execution_log) == 4  # 4 agents

    @pytest.mark.asyncio
    async def test_orchestrator_error_handling(self):
        orchestrator = MultiAgentOrchestrator()

        # Mock a failing brainstormer with an async function
        async def mock_failing_execute(input_data):
            return AgentResult("Brainstormer", False, [], "Test error")

        orchestrator.brainstormer.execute = mock_failing_execute

        result = await orchestrator.execute_workflow(IdeaInput(idea="test"))
        assert "error" in result
        assert "Brainstorming failed" in result["error"]


class TestMultiAgentWorkflow:
    @pytest.mark.asyncio
    async def test_run_multi_agent_research(self):
        result = await run_multi_agent_research(
            idea="test business", tlds=["com"], max_candidates=3
        )

        assert isinstance(result, dict)
        assert "candidates" in result
        assert "summary" in result
        assert "recommendations" in result
        assert "execution_log" in result
        assert "total_execution_time" in result

    @pytest.mark.asyncio
    async def test_run_multi_agent_research_default_params(self):
        result = await run_multi_agent_research("test business idea")

        assert isinstance(result, dict)
        assert "candidates" in result
        # Should use default TLDs
        assert len(result.get("execution_log", [])) == 4


class TestIntegration:
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test the complete multi-agent workflow end-to-end"""
        result = await run_multi_agent_research(
            idea="AI-powered travel planning app", tlds=["com", "io"], max_candidates=5
        )

        # Verify structure
        assert "candidates" in result
        assert "summary" in result
        assert "recommendations" in result
        assert "alternatives" in result
        assert "insights" in result
        assert "execution_log" in result

        # Verify execution log
        log = result["execution_log"]
        assert len(log) == 4
        agent_names = [entry["agent_name"] for entry in log]
        assert "Brainstormer" in agent_names
        assert "Researcher" in agent_names
        assert "Analyzer" in agent_names
        assert "Packager" in agent_names

        # Verify all agents succeeded
        for entry in log:
            assert entry["success"] is True

        # Verify summary structure
        summary = result["summary"]
        assert "total_candidates" in summary
        assert "generated_at" in summary

        # Verify recommendations structure
        recommendations = result["recommendations"]
        assert isinstance(recommendations, list)
        if recommendations:
            rec = recommendations[0]
            assert "rank" in rec
            assert "name" in rec
            assert "score" in rec
            assert "rationale" in rec
