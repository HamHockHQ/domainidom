"""
Multi-Agent Orchestration System for Domain Research
Based on Agency Swarm principles with specialized agents for each stage
"""
from __future__ import annotations

import os
import re
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

import httpx

from .models import ScoredCandidate, DomainCheckResult, IdeaInput
from .brainstorm import brainstorm_names  
from .research import check_domains
from .analyze import score_candidates
from .package import write_reports


@dataclass
class AgentMessage:
    """Message passed between agents"""
    from_agent: str
    to_agent: str
    content: Any
    timestamp: datetime
    message_type: str = "data"


@dataclass 
class AgentResult:
    """Result from an agent operation"""
    agent_name: str
    success: bool
    data: Any
    error: Optional[str] = None
    execution_time: float = 0.0


class BaseAgent:
    """Base class for all domain research agents"""
    
    def __init__(self, name: str, instructions: str):
        self.name = name
        self.instructions = instructions
        self.messages: List[AgentMessage] = []
        
    def receive_message(self, message: AgentMessage):
        """Receive a message from another agent"""
        self.messages.append(message)
        
    def send_message(self, to_agent: str, content: Any, message_type: str = "data") -> AgentMessage:
        """Send a message to another agent"""
        return AgentMessage(
            from_agent=self.name,
            to_agent=to_agent,
            content=content,
            timestamp=datetime.now(),
            message_type=message_type
        )
        
    async def execute(self, input_data: Any) -> AgentResult:
        """Execute the agent's main task - to be implemented by subclasses"""
        raise NotImplementedError
        

class BrainstormerAgent(BaseAgent):
    """
    Generates diverse, on-brief name ideas using multiple methods
    Implements SCAMPER methodology, role-storming techniques
    Focuses on rhyme/phoneme patterns and memorability
    """
    
    def __init__(self):
        super().__init__(
            name="Brainstormer",
            instructions="""Generate creative, memorable domain names using multiple methodologies:
            - SCAMPER (Substitute, Combine, Adapt, Modify, Put to other uses, Eliminate, Reverse)
            - Role-storming from different user perspectives
            - Rhyme and phoneme pattern analysis
            - Memorability optimization"""
        )
        
    async def execute(self, input_data: IdeaInput) -> AgentResult:
        """Generate diverse name ideas using multiple creative methods"""
        start_time = datetime.now()
        
        try:
            # Use existing brainstorm functionality as base
            base_names = brainstorm_names(input_data.idea or "", input_data.max_candidates // 3)
            
            # Apply SCAMPER methodology
            scamper_names = await self._apply_scamper(input_data.idea or "", input_data.max_candidates // 3)
            
            # Apply role-storming 
            role_names = await self._apply_role_storming(input_data.idea or "", input_data.max_candidates // 3)
            
            # Combine and deduplicate
            all_names = list(set(base_names + scamper_names + role_names))
            
            # Limit to requested amount
            final_names = all_names[:input_data.max_candidates]
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResult(
                agent_name=self.name,
                success=True,
                data=final_names,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                success=False,
                data=[],
                error=str(e),
                execution_time=execution_time
            )
    
    async def _apply_scamper(self, idea: str, max_names: int) -> List[str]:
        """Apply SCAMPER methodology for creative name generation"""
        scamper_prompt = f"""
        Using SCAMPER methodology, generate creative brand names for: {idea}
        
        Apply these techniques:
        - Substitute: Replace words with synonyms or related terms
        - Combine: Merge concepts or words 
        - Adapt: Modify existing names for this context
        - Modify: Enhance or diminish certain aspects
        - Put to other uses: Apply naming from other industries
        - Eliminate: Remove unnecessary parts
        - Reverse: Flip or invert concepts
        
        Generate {max_names} unique, pronounceable names. Return as JSON array.
        """
        
        return await self._call_llm(scamper_prompt, max_names)
    
    async def _apply_role_storming(self, idea: str, max_names: int) -> List[str]:
        """Apply role-storming from different user perspectives"""
        role_prompt = f"""
        Generate brand names for: {idea}
        
        Consider these different user perspectives:
        - Tech enthusiast (values innovation, cutting-edge)
        - Business executive (values professionalism, trust)
        - Creative professional (values originality, inspiration)
        - End consumer (values simplicity, memorability)
        - International user (values pronunciation, cultural neutrality)
        
        Generate {max_names} names that appeal across these perspectives. Return as JSON array.
        """
        
        return await self._call_llm(role_prompt, max_names)
    
    async def _call_llm(self, prompt: str, max_names: int) -> List[str]:
        """Call LLM for name generation"""
        base_url = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
        api_key = os.getenv("OPENAI_API_KEY", "lm-studio")
        model = os.getenv("OPENAI_MODEL", "qwen3-coder-30b-a3b-instruct")
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "You are a creative naming expert."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.9,
                        "max_tokens": 800,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"].strip()
                
                # Parse JSON response
                if content.startswith("["):
                    try:
                        names = json.loads(content)
                        return [str(name).strip() for name in names[:max_names]]
                    except:
                        pass
                
                # Fallback parsing
                lines = content.splitlines()
                names = []
                for line in lines:
                    line = re.sub(r'^[-*\d\.\)\]]+\s*', '', line.strip())
                    line = line.strip('"\'.,')
                    if line and len(line) > 2:
                        names.append(line)
                        if len(names) >= max_names:
                            break
                
                return names
                
        except Exception:
            # Fallback names for SCAMPER/role-storming
            fallback = [
                "Nexion", "Creativio", "Adaptly", "Morphex", "Reversio",
                "Combinex", "Modifiex", "Eliminato", "Substitux", "Innovex"
            ]
            return fallback[:max_names]


class ResearcherAgent(BaseAgent):
    """
    Expands names to domain variants across TLDs
    Checks availability via MCP/registrar APIs  
    Fetches pricing information when available
    """
    
    def __init__(self):
        super().__init__(
            name="Researcher", 
            instructions="""Research domain availability and expand to variants:
            - Generate domain variants across multiple TLDs
            - Check availability using registrar APIs
            - Fetch pricing information when available
            - Consider alternative spellings and formats"""
        )
        
    async def execute(self, input_data: Tuple[List[str], List[str]]) -> AgentResult:
        """Research domain availability for generated names"""
        start_time = datetime.now()
        
        try:
            names, tlds = input_data
            
            # Create domain candidates 
            domain_candidates = {}
            for name in names:
                # Generate variants for each name
                variants = self._generate_variants(name)
                domains = []
                for variant in variants:
                    for tld in tlds:
                        domains.append(f"{variant}.{tld}")
                domain_candidates[name] = domains
            
            # Check domain availability using the async version
            research_results = await self._check_domains_async(domain_candidates)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResult(
                agent_name=self.name,
                success=True,
                data=research_results,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                success=False,
                data={},
                error=str(e),
                execution_time=execution_time
            )
    
    async def _check_domains_async(self, domain_candidates):
        """Async version of domain checking for multi-agent use"""
        # Import here to avoid circular imports
        import os
        import asyncio
        from domainidom.services.domain_check import DomainCache, _fetch_best, ProviderResponse
        from domainidom.models import DomainCheckResult
        
        cache_path = os.getenv("DOMAIN_CACHE_PATH", "domain_cache.sqlite3")
        cache = DomainCache(cache_path)
        max_calls_total = int(os.getenv("DOMAIN_CHECK_MAX_CALLS", "80"))
        calls_made = 0
        
        results = {}
        domains_to_check = []
        
        # First pass: handle cached domains and collect uncached ones
        for name, domains in domain_candidates.items():
            results[name] = []
            for d in domains:
                cached = cache.get(d)
                if cached is not None:
                    available, price, provider, error = cached
                    results[name].append(
                        (d, DomainCheckResult(d, available, price, provider, error))
                    )
                    continue
                if calls_made >= max_calls_total:
                    results[name].append(
                        (d, DomainCheckResult(d, None, None, "quota", "max_calls_reached"))
                    )
                    continue
                domains_to_check.append((name, d))
                calls_made += 1
        
        # Process uncached domains
        if domains_to_check:
            tasks = []
            for name, domain in domains_to_check:
                tasks.append((name, domain, asyncio.create_task(_fetch_best(domain))))
            
            for name, domain, task in tasks:
                try:
                    resp = await task
                except Exception as e:
                    resp = ProviderResponse(None, None, "error", str(e))
                    
                dcr = DomainCheckResult(
                    domain=domain,
                    available=resp.available,
                    registrar_price_usd=resp.price_usd,
                    provider=resp.provider,
                    error=resp.error,
                    price_comparison=resp.price_comparison,
                )
                results.setdefault(name, []).append((domain, dcr))
                cache.set(domain, (dcr.available, dcr.registrar_price_usd, dcr.provider, dcr.error))
        
        return results
    
    def _generate_variants(self, name: str) -> List[str]:
        """Generate domain variants for a name"""
        base = re.sub(r'[^a-zA-Z0-9]', '', name.lower())
        variants = [base]
        
        # Add common variations
        if len(base) > 6:
            # Shortened version
            variants.append(base[:6])
            
        # Add 'get' prefix for apps
        variants.append(f"get{base}")
        
        # Add 'my' prefix  
        variants.append(f"my{base}")
        
        # Replace vowels for creative variants
        vowel_replacements = {'a': 'ai', 'e': 'ee', 'i': 'y', 'o': 'ou'}
        for old, new in vowel_replacements.items():
            if old in base:
                variants.append(base.replace(old, new, 1))
        
        return list(set(variants))


class AnalyzerAgent(BaseAgent):
    """
    Scores names for memorability and pronounceability
    Evaluates SEO potential and brand safety
    Performs cultural appropriateness checks
    """
    
    def __init__(self):
        super().__init__(
            name="Analyzer",
            instructions="""Analyze and score domain names for:
            - Memorability and pronounceability
            - SEO potential and keyword relevance
            - Brand safety and trademark risks
            - Cultural appropriateness and global appeal
            - Overall business value"""
        )
        
    async def execute(self, input_data: Tuple[List[str], Dict]) -> AgentResult:
        """Analyze and score domain candidates"""
        start_time = datetime.now()
        
        try:
            names, research_results = input_data
            
            # Use existing scoring functionality
            scored_candidates = score_candidates(names, research_results)
            
            # Enhance scoring with additional analysis
            enhanced_candidates = []
            for candidate in scored_candidates:
                enhanced = await self._enhance_scoring(candidate)
                enhanced_candidates.append(enhanced)
            
            # Re-sort by enhanced scores
            enhanced_candidates.sort(key=lambda c: c.score, reverse=True)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResult(
                agent_name=self.name,
                success=True,
                data=enhanced_candidates,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                success=False,
                data=[],
                error=str(e),
                execution_time=execution_time
            )
    
    async def _enhance_scoring(self, candidate: ScoredCandidate) -> ScoredCandidate:
        """Enhance scoring with additional analysis"""
        # SEO analysis
        seo_score = self._analyze_seo_potential(candidate.name)
        
        # Brand safety analysis
        brand_safety = self._analyze_brand_safety(candidate.name)
        
        # Cultural analysis
        cultural_score = self._analyze_cultural_appropriateness(candidate.name)
        
        # Update details
        candidate.details.update({
            "seo": round(seo_score, 4),
            "brand_safety": round(brand_safety, 4), 
            "cultural": round(cultural_score, 4)
        })
        
        # Recalculate overall score with new factors
        original_score = candidate.score
        enhanced_score = (
            0.30 * original_score +
            0.25 * seo_score +
            0.25 * brand_safety +
            0.20 * cultural_score
        )
        
        candidate.score = round(enhanced_score, 4)
        
        return candidate
    
    def _analyze_seo_potential(self, name: str) -> float:
        """Analyze SEO potential of a name"""
        score = 0.5  # Base score
        
        # Prefer shorter names for SEO
        if len(name) <= 8:
            score += 0.2
        elif len(name) <= 12:
            score += 0.1
            
        # Check for common business keywords
        business_keywords = ['app', 'tech', 'pro', 'smart', 'digital', 'net', 'hub']
        if any(keyword in name.lower() for keyword in business_keywords):
            score += 0.15
            
        # Avoid numbers and hyphens which are less SEO friendly
        if not re.search(r'\d|-', name):
            score += 0.15
            
        return min(1.0, score)
    
    def _analyze_brand_safety(self, name: str) -> float:
        """Analyze brand safety of a name"""
        score = 0.8  # Start with high safety score
        
        # Check for potentially problematic words
        risky_words = ['hack', 'crack', 'pirate', 'steal', 'fake', 'spam']
        for word in risky_words:
            if word in name.lower():
                score -= 0.3
                
        # Prefer names that don't conflict with major brands
        major_brands = ['google', 'apple', 'microsoft', 'amazon', 'facebook', 'meta']
        for brand in major_brands:
            if brand in name.lower():
                score -= 0.5
                
        return max(0.0, score)
    
    def _analyze_cultural_appropriateness(self, name: str) -> float:
        """Analyze cultural appropriateness and global appeal"""
        score = 0.7  # Base cultural score
        
        # Prefer names with latin characters
        if name.isascii():
            score += 0.2
            
        # Check for easy pronunciation across languages
        difficult_combos = ['sch', 'tsch', 'tz', 'zh', 'kh']
        if not any(combo in name.lower() for combo in difficult_combos):
            score += 0.1
            
        return min(1.0, score)


class PackagerAgent(BaseAgent):
    """
    Ranks results based on multiple scoring factors
    Compiles comprehensive reports (CSV/JSON + Markdown)
    Provides rationale and alternatives
    """
    
    def __init__(self):
        super().__init__(
            name="Packager",
            instructions="""Package final results with:
            - Ranked recommendations based on comprehensive scoring
            - Detailed rationale for each recommendation
            - Alternative suggestions and backup options
            - Executive summary and insights
            - Multiple output formats (CSV, JSON, Markdown)"""
        )
        
    async def execute(self, input_data: List[ScoredCandidate]) -> AgentResult:
        """Package final results with comprehensive reporting"""
        start_time = datetime.now()
        
        try:
            scored_candidates = input_data
            
            # Generate comprehensive package
            package_data = {
                "candidates": scored_candidates,
                "summary": self._generate_summary(scored_candidates),
                "recommendations": self._generate_recommendations(scored_candidates),
                "alternatives": self._generate_alternatives(scored_candidates),
                "insights": self._generate_insights(scored_candidates)
            }
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResult(
                agent_name=self.name,
                success=True,
                data=package_data,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult(
                agent_name=self.name,
                success=False,
                data={},
                error=str(e),
                execution_time=execution_time
            )
    
    def _generate_summary(self, candidates: List[ScoredCandidate]) -> Dict[str, Any]:
        """Generate executive summary"""
        if not candidates:
            return {"total_candidates": 0, "available_domains": 0}
            
        total_candidates = len(candidates)
        available_domains = sum(
            1 for candidate in candidates 
            for domain in candidate.domains 
            if domain.available
        )
        
        avg_score = sum(c.score for c in candidates) / len(candidates)
        top_score = candidates[0].score if candidates else 0
        
        return {
            "total_candidates": total_candidates,
            "available_domains": available_domains,
            "average_score": round(avg_score, 4),
            "top_score": round(top_score, 4),
            "generated_at": datetime.now().isoformat()
        }
    
    def _generate_recommendations(self, candidates: List[ScoredCandidate]) -> List[Dict[str, Any]]:
        """Generate top recommendations with rationale"""
        recommendations = []
        
        for i, candidate in enumerate(candidates[:5]):  # Top 5
            available_domains = [d for d in candidate.domains if d.available]
            
            # Generate rationale
            rationale = []
            if candidate.details.get("length", 0) > 0.7:
                rationale.append("Optimal length for memorability")
            if candidate.details.get("balance", 0) > 0.7:
                rationale.append("Good phonetic balance")
            if candidate.details.get("availability", 0) > 0.5:
                rationale.append("Multiple TLD options available")
            if candidate.details.get("seo", 0) > 0.7:
                rationale.append("Strong SEO potential")
            if candidate.details.get("brand_safety", 0) > 0.8:
                rationale.append("High brand safety score")
                
            recommendations.append({
                "rank": i + 1,
                "name": candidate.name,
                "score": candidate.score,
                "available_domains": len(available_domains),
                "best_domain": available_domains[0].domain if available_domains else None,
                "rationale": rationale,
                "details": candidate.details
            })
            
        return recommendations
    
    def _generate_alternatives(self, candidates: List[ScoredCandidate]) -> List[str]:
        """Generate alternative suggestions"""
        # Return mid-tier candidates as alternatives
        return [c.name for c in candidates[5:15] if c.score > 0.5]
    
    def _generate_insights(self, candidates: List[ScoredCandidate]) -> Dict[str, Any]:
        """Generate insights about the results"""
        if not candidates:
            return {}
            
        # Analyze scoring patterns
        length_scores = [c.details.get("length", 0) for c in candidates]
        balance_scores = [c.details.get("balance", 0) for c in candidates]
        availability_scores = [c.details.get("availability", 0) for c in candidates]
        
        return {
            "avg_length_score": round(sum(length_scores) / len(length_scores), 4),
            "avg_balance_score": round(sum(balance_scores) / len(balance_scores), 4),
            "avg_availability_score": round(sum(availability_scores) / len(availability_scores), 4),
            "high_scoring_names": len([c for c in candidates if c.score > 0.7]),
            "available_premium_domains": len([
                c for c in candidates[:10] 
                for d in c.domains 
                if d.available and d.domain.endswith('.com')
            ])
        }


class MultiAgentOrchestrator:
    """Orchestrates the multi-agent domain research workflow"""
    
    def __init__(self):
        self.brainstormer = BrainstormerAgent()
        self.researcher = ResearcherAgent()
        self.analyzer = AnalyzerAgent()
        self.packager = PackagerAgent()
        
        self.execution_log: List[AgentResult] = []
        
    async def execute_workflow(self, idea_input: IdeaInput) -> Dict[str, Any]:
        """Execute the complete multi-agent workflow"""
        
        # Stage 1: Brainstorming
        print(f"🧠 {self.brainstormer.name} Agent: Generating creative names...")
        brainstorm_result = await self.brainstormer.execute(idea_input)
        self.execution_log.append(brainstorm_result)
        
        if not brainstorm_result.success:
            return {"error": f"Brainstorming failed: {brainstorm_result.error}"}
        
        names = brainstorm_result.data
        print(f"   Generated {len(names)} creative names")
        
        # Stage 2: Research
        print(f"🔍 {self.researcher.name} Agent: Researching domain availability...")
        research_input = (names, idea_input.tlds or ["com", "io", "ai"])
        research_result = await self.researcher.execute(research_input)
        self.execution_log.append(research_result)
        
        if not research_result.success:
            return {"error": f"Research failed: {research_result.error}"}
        
        research_results = research_result.data
        print(f"   Researched domains for {len(research_results)} names")
        
        # Stage 3: Analysis
        print(f"📊 {self.analyzer.name} Agent: Analyzing and scoring candidates...")
        analysis_input = (names, research_results)
        analysis_result = await self.analyzer.execute(analysis_input)
        self.execution_log.append(analysis_result)
        
        if not analysis_result.success:
            return {"error": f"Analysis failed: {analysis_result.error}"}
        
        scored_candidates = analysis_result.data
        print(f"   Analyzed and scored {len(scored_candidates)} candidates")
        
        # Stage 4: Packaging
        print(f"📦 {self.packager.name} Agent: Creating comprehensive package...")
        package_result = await self.packager.execute(scored_candidates)
        self.execution_log.append(package_result)
        
        if not package_result.success:
            return {"error": f"Packaging failed: {package_result.error}"}
        
        final_package = package_result.data
        print(f"   Package created with {len(final_package['recommendations'])} recommendations")
        
        # Add execution metadata
        final_package.update({
            "execution_log": [asdict(result) for result in self.execution_log],
            "total_execution_time": sum(r.execution_time for r in self.execution_log),
            "workflow_version": "multi-agent-v1.0"
        })
        
        return final_package


async def run_multi_agent_research(
    idea: str,
    tlds: List[str] = None,
    max_candidates: int = 50
) -> Dict[str, Any]:
    """
    Run the complete multi-agent domain research workflow
    
    Args:
        idea: Business idea description
        tlds: List of TLDs to research (default: com, io, ai)
        max_candidates: Maximum number of candidates to generate
        
    Returns:
        Comprehensive research package with recommendations
    """
    if tlds is None:
        tlds = ["com", "io", "ai"]
        
    idea_input = IdeaInput(
        idea=idea,
        tlds=tlds,
        max_candidates=max_candidates
    )
    
    orchestrator = MultiAgentOrchestrator()
    return await orchestrator.execute_workflow(idea_input)