"""
PoC Pipeline - WAT (Workflows + Agents + Tools) orchestration.

Manages the five-agent proof-of-concept development workflow from concept
to stakeholder deliverables with automatic iteration and quality gates.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ..vault import VaultTools, Config
from ..projects import ProjectTools
from ..agent import ReActResult, ReactAgent, AgentResult
from ..agent.backend import AnthropicBackend
from ..agent.claude_code_agent import ClaudeCodeAgent
from .models import AgentContext, IterationDecision, CriticAssessment
from .skill_injector import SkillInjector


class PoCPipeline:
    """
    Main WAT (Workflows + Agents + Tools) pipeline orchestrator.

    Manages the five-agent PoC development workflow:
    1. Team Lead - Orchestration and iteration decisions
    2. Senior Architect - Technical design
    3. Senior Engineer - Implementation
    4. Solutions Critic - Quality gate
    5. Communications Specialist - Stakeholder deliverables
    """

    MAX_ITERATIONS = 5  # Allows for iterative refinement with skill improvements

    # Cost limits (in USD)
    # NOTE: These limits only apply to AnthropicBackend (ReactAgent) calls.
    # ClaudeCodeAgent runs are free (no per-token cost from subprocess `claude --print` calls).
    # With all 5 agents in autonomous mode (ClaudeCodeAgent), DEV_MODE cost limits are not enforced.
    COST_LIMIT_DEV = 2.00
    COST_LIMIT_PROD = 10.00

    def __init__(
        self,
        vault: Optional[VaultTools] = None,
        projects: Optional[ProjectTools] = None,
        api_key: Optional[str] = None,
        dev_mode: Optional[bool] = None,
        verbose: bool = True
    ):
        """
        Initialize the PoC pipeline.

        Args:
            vault: VaultTools instance (creates default if None)
            projects: ProjectTools instance (creates default if None)
            api_key: Anthropic API key (defaults to env var)
            dev_mode: DEV_MODE flag (defaults to env var)
            verbose: Whether to log pipeline progress
        """
        # Initialize vault
        if vault is None:
            config = Config()
            vault = VaultTools(config.vault_path)
        self.vault = vault

        # Initialize projects tools
        if projects is None:
            projects = ProjectTools()
        self.projects = projects

        # Determine dev mode
        if dev_mode is None:
            dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
        self.dev_mode = dev_mode

        self.verbose = verbose
        self.cost_limit = self.COST_LIMIT_DEV if dev_mode else self.COST_LIMIT_PROD

        # Initialize skill injector
        self.injector = SkillInjector(vault, projects)

        # Store API key for agents
        self.api_key = api_key

        if self.verbose:
            mode = "DEV" if dev_mode else "PRODUCTION"
            print(f"\n{'='*80}")
            print(f"🏗️  POC PIPELINE INITIALIZED ({mode} MODE)")
            print(f"{'='*80}")
            print(f"💵 Cost Limit: ${self.cost_limit:.2f}")
            print(f"🔄 Max Iterations: {self.MAX_ITERATIONS}")
            print(f"{'='*80}\n")

    def run(self, poc_idea: str, poc_slug: str) -> Dict[str, Any]:
        """
        Execute the full PoC pipeline.

        Args:
            poc_idea: High-level PoC concept from human
            poc_slug: URL-safe slug for project folder naming

        Returns:
            Pipeline execution result with paths to deliverables

        Example:
            >>> result = pipeline.run(
            ...     poc_idea="Build a client email summarization tool using GenAI",
            ...     poc_slug="client-email-summarizer"
            ... )
            >>> print(result["status"])
            >>> print(result["deliverables"])
        """
        try:
            # Setup project structure
            context = self._setup_project_structure(poc_slug)

            # Phase 1: Discovery & Planning (Team Lead)
            context = self._phase_discovery(context, poc_idea)
            self._check_cost_limit(context)

            # Phase 2: Architecture (Senior Architect)
            context = self._phase_architecture(context)
            self._check_cost_limit(context)

            # Main iteration loop (Phase 3-4)
            while context.iteration_count < self.MAX_ITERATIONS:
                # Phase 3: Development (Senior Engineer)
                context = self._phase_development(context)
                self._check_cost_limit(context)

                # Phase 4: Review (Solutions Critic)
                context, assessment = self._phase_review(context)
                self._check_cost_limit(context)

                # Apply iteration decision framework
                decision = self._apply_iteration_framework(context, assessment)

                if decision.action == "proceed":
                    # Quality gate passed - proceed to communications
                    break
                elif decision.action == "escalate_human":
                    # Need human intervention
                    return self._escalate_to_human(context, decision, assessment)
                else:
                    # Rework needed
                    context = self._rework_iteration(context, decision)

            # Check if we exited due to max iterations
            if context.iteration_count >= self.MAX_ITERATIONS:
                return self._escalate_to_human(
                    context,
                    IterationDecision(
                        action="escalate_human",
                        reason=f"Exceeded {self.MAX_ITERATIONS} iteration cycles",
                        target_issues=[]
                    ),
                    assessment
                )

            # Phase 5: Communications (Communications Specialist)
            context = self._phase_communications(context)
            self._check_cost_limit(context)

            # Finalize project
            return self._finalize_project(context)

        except Exception as e:
            if self.verbose:
                print(f"\n❌ Pipeline error: {e}")
            raise

    def _execute_agent(
        self,
        agent,  # Union[AnthropicBackend, ClaudeCodeAgent]
        task: str,
        system_prompt: str = "",
        role: str = "agent",
        poc_slug: Optional[str] = None,
        iteration: int = 1
    ) -> AgentResult:
        """
        Execute an agent task with unified interface for both backend types.

        Args:
            agent: AnthropicBackend or ClaudeCodeAgent instance
            task: Task to execute
            system_prompt: System prompt (used by ClaudeCodeAgent, ignored by AnthropicBackend)
            role: Agent role name
            poc_slug: PoC slug for reasoning logs
            iteration: Iteration number

        Returns:
            AgentResult with normalized response
        """
        if isinstance(agent, AnthropicBackend):
            # ReactAgent via AnthropicBackend
            return agent.execute(
                task=task,
                system_prompt=system_prompt,  # Ignored - ReactAgent has pre-configured prompt
                role=role,
                iteration=iteration
            )
        elif isinstance(agent, ClaudeCodeAgent):
            # ClaudeCodeAgent autonomous execution
            result = agent.execute_safe(
                task=task,
                system_prompt=system_prompt,
                role=role,
                poc_slug=poc_slug,
                iteration=iteration
            )
            # Convert ClaudeCodeResult to AgentResult
            return AgentResult(
                success=result.success,
                result=result.result,
                total_cost=result.total_cost_usd,
                total_tokens=result.usage.get('input_tokens', 0) + result.usage.get('output_tokens', 0),
                total_steps=1,  # Claude Code handles all steps internally
                error=result.error,
                metadata={
                    "backend": "claude_code",
                    "session_id": result.session_id,
                    "usage": result.usage
                }
            )
        else:
            raise TypeError(f"Unknown agent type: {type(agent)}")

    def _write_status(self, context: AgentContext, note: str) -> None:
        """
        Write STATUS.md file for human monitoring.

        Args:
            context: Current agent context
            note: One-line status note
        """
        status_path = f"{context.scratch_dir}/STATUS.md"
        status_content = f"""# Pipeline Status

**Project**: {context.poc_slug}
**Phase**: {context.current_phase}
**Iteration**: {context.iteration_count}
**Timestamp**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Cumulative Cost**: ${context.total_cost:.4f}

**Status**: {note}
"""
        self.vault.write_file(status_path, status_content)

        if self.verbose:
            print(f"📄 STATUS.md updated: {note}")

    def _setup_project_structure(self, poc_slug: str) -> AgentContext:
        """
        Create project folder structure.

        Creates:
        - 08-scratch/poc-pipeline-<slug>/  (vault, markdown only)
        - ~/projects/<slug>/               (real code)
        - 02-projects/<slug>/             (final deliverables, markdown)
        """
        if self.verbose:
            print(f"\n📁 Setting up project structure for: {poc_slug}")

        # Create scratch directory in vault
        scratch_dir = f"08-scratch/poc-pipeline-{poc_slug}"

        # Create projects directory (real code, outside vault)
        project_dir = Path.home() / "projects" / poc_slug
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create project folder in vault (deliverables)
        deliverables_dir = f"02-projects/{poc_slug}"

        # Create initial project overview
        overview_content = f"""---
type: project
created: {datetime.now().strftime("%Y-%m-%d")}
updated: {datetime.now().strftime("%Y-%m-%d")}
project: {poc_slug}
status: active
owner: both
tags: [poc, wat-pipeline, in-progress]
---

# {poc_slug.replace('-', ' ').title()} PoC

**Status**: In Progress
**Pipeline**: WAT (Workflows + Agents + Tools)
**Started**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Overview

PoC project managed by the WAT pipeline with five specialist agents.

## Progress

- [ ] Discovery & Planning (Team Lead)
- [ ] Architecture (Senior Architect)
- [ ] Development (Senior Engineer)
- [ ] Review (Solutions Critic)
- [ ] Communications (Communications Specialist)

## Links

- Scratch work: [[08-scratch/poc-pipeline-{poc_slug}]]
- Real code: `~/projects/{poc_slug}/`
"""
        self.vault.write_file(f"{deliverables_dir}/overview.md", overview_content)

        if self.verbose:
            print(f"   ✓ Vault scratch: {scratch_dir}/")
            print(f"   ✓ Project code: ~/projects/{poc_slug}/")
            print(f"   ✓ Deliverables: {deliverables_dir}/")

        return AgentContext(
            poc_slug=poc_slug,
            scratch_dir=scratch_dir,
            project_dir=str(project_dir),
            brief_path=f"{scratch_dir}/00-brief.md",
            current_phase="setup",
            iteration_count=0
        )

    def _phase_discovery(self, context: AgentContext, poc_idea: str) -> AgentContext:
        """
        Phase 1: Discovery & Planning (Team Lead)

        Team Lead:
        - Orients in vault
        - Reads firm context
        - Searches for related work
        - Creates project brief
        """
        if self.verbose:
            print(f"\n{'='*80}")
            print("PHASE 1: DISCOVERY & PLANNING (Team Lead)")
            print(f"{'='*80}\n")

        # Create Team Lead agent (vault-only tools, autonomous mode)
        team_lead = self.injector.create_specialist_agent(
            role="Team Lead",
            skill_file="04-skills/team-lead.md",
            tools_filter='vault_only',
            execution_mode='autonomous',
            api_key=self.api_key,
            verbose=self.verbose
        )

        # Task instruction for Team Lead
        task = f"""
You are the Team Lead. Execute Phase 1: Discovery & Planning.

IMPORTANT: Firm context (CONSTRAINTS.md and DOMAIN.md) has been PRE-LOADED into your system prompt.
You do NOT need to read these files - the information is already available to you.

PoC Idea: {poc_idea}
Project Slug: {context.poc_slug}

Your Phase 1 tasks:
1. Read 00-index/INDEX.md to orient in the vault
2. Review the pre-loaded firm constraints and domain context (already in your system prompt)
3. Read 01-firm-context/STAKEHOLDERS.md (if needed for stakeholder mapping)
4. Search 05-conversations/ and 06-findings/ for related past work
5. Check 02-projects/ for any active related projects

Then write a comprehensive project brief to: {context.brief_path}

The brief should include:
- Problem statement
- Success criteria
- Approach overview (high-level)
- Related past work found (if any)
- Key constraints from firm context
- Target stakeholders

Use YAML frontmatter:
---
type: brief
created: {datetime.now().strftime("%Y-%m-%d")}
poc-slug: {context.poc_slug}
phase: discovery
---

When you're done, provide Final Answer summarizing the brief.
"""

        # Run Team Lead
        # Build system prompt for ClaudeCodeAgent
        system_prompt = self.injector._build_system_prompt(
            firm_context=self.injector._load_firm_context(),
            skill_content=self.injector.load_skill("04-skills/team-lead.md"),
            tools_filter='vault_only'
        )

        result = self._execute_agent(
            agent=team_lead,
            task=task,
            system_prompt=system_prompt,
            role="Team Lead",
            poc_slug=context.poc_slug,
            iteration=context.iteration_count + 1
        )

        # Update context
        context.specialist_outputs["team_lead"] = context.brief_path
        context.total_cost += result.total_cost
        context.current_phase = "discovery_complete"

        if not result.success:
            raise RuntimeError(f"Team Lead agent failed: {result.error}")

        if not self._check_prerequisite(context.brief_path, "Architecture"):
            raise RuntimeError(f"Team Lead did not create brief at {context.brief_path}")

        if self.verbose:
            print(f"\n✅ Discovery complete")
            print(f"   Brief: {context.brief_path}")
            print(f"   Cost: ${result.total_cost:.4f}")

        self._write_status(context, "Discovery complete - project brief created")

        return context

    def _phase_architecture(self, context: AgentContext) -> AgentContext:
        """
        Phase 2: Architecture (Senior Architect)

        Architect:
        - Reads brief and firm context
        - Designs production-viable architecture
        - Checks all constraints
        - Writes spec to scratch/01-architect-spec.md
        """
        if self.verbose:
            print(f"\n{'='*80}")
            print("PHASE 2: ARCHITECTURE (Senior Architect)")
            print(f"{'='*80}\n")

        # Create Architect agent (vault-only tools, autonomous mode)
        architect = self.injector.create_specialist_agent(
            role="Senior Architect",
            skill_file="04-skills/senior-architect.md",
            tools_filter='vault_only',
            execution_mode='autonomous',
            api_key=self.api_key,
            verbose=self.verbose
        )

        spec_path = f"{context.scratch_dir}/01-architect-spec.md"

        task = f"""
You are the Senior Architect. Execute Phase 2: Architecture.

IMPORTANT: Firm context (CONSTRAINTS.md and DOMAIN.md) has been PRE-LOADED into your system prompt.
You do NOT need to read these files - the information is already available to you.

Read the project brief at: {context.brief_path}

Your Phase 2 tasks:
1. Read the brief completely
2. Review the pre-loaded firm constraints and domain context (already in your system prompt)
3. Search 06-findings/ for related architectural decisions (if relevant)
4. Design a production-viable architecture

Write your complete architecture spec to: {spec_path}

Include all deliverables per your skill file:
- Executive summary
- Architecture overview
- Constraint analysis
- Technology decisions
- Security design
- Scalability approach
- Implementation roadmap
- Cost estimate
- Risk register
- Engineer handoff

Use YAML frontmatter:
---
type: architect-spec
created: {datetime.now().strftime("%Y-%m-%d")}
poc-slug: {context.poc_slug}
phase: architecture
iteration: {context.iteration_count + 1}
---

When done, provide Final Answer summarizing the architecture.
"""

        # Build system prompt for ClaudeCodeAgent
        system_prompt = self.injector._build_system_prompt(
            firm_context=self.injector._load_firm_context(),
            skill_content=self.injector.load_skill("04-skills/senior-architect.md"),
            tools_filter='vault_only'
        )

        result = self._execute_agent(
            agent=architect,
            task=task,
            system_prompt=system_prompt,
            role="Senior Architect",
            poc_slug=context.poc_slug,
            iteration=context.iteration_count + 1
        )

        context.specialist_outputs["architect"] = spec_path
        context.total_cost += result.total_cost
        context.current_phase = "architecture_complete"

        if not result.success:
            raise RuntimeError(f"Architect agent failed: {result.error}")

        if not self._check_prerequisite(spec_path, "Development"):
            raise RuntimeError(f"Architect did not create spec at {spec_path}")

        if self.verbose:
            print(f"\n✅ Architecture complete")
            print(f"   Spec: {spec_path}")
            print(f"   Cost: ${result.total_cost:.4f}")

        self._write_status(context, "Architecture complete - spec created")



        return context

    def _check_prerequisite(self, file_path: str, phase_name: str) -> bool:
        """
        Check if a prerequisite file exists and has content.

        Args:
            file_path: Path to required file
            phase_name: Name of phase for error reporting

        Returns:
            True if prerequisite met, False otherwise
        """
        try:
            content = self.vault.read_file(file_path)
            if not content or len(content.strip()) == 0:
                if self.verbose:
                    print(f"⚠️  Prerequisite check FAILED: {file_path} is empty")
                return False
            if self.verbose:
                print(f"✓ Prerequisite check passed: {file_path}")
            return True
        except Exception as e:
            if self.verbose:
                print(f"⚠️  Prerequisite check FAILED: {file_path} does not exist")
                print(f"   Error: {e}")
            return False

    def _phase_development(self, context: AgentContext) -> AgentContext:
        """
        Phase 3: Development (Senior Engineer)

        Engineer:
        - Reads architect spec
        - Implements REAL, EXECUTABLE code
        - Writes documentation to scratch/02-engineer-output.md
        - Writes actual code to ~/projects/<slug>/
        """
        if self.verbose:
            print(f"\n{'='*80}")
            print("PHASE 3: DEVELOPMENT (Senior Engineer)")
            print(f"{'='*80}\n")

        # PREREQUISITE CHECK: Architect spec must exist
        spec_path = f"{context.scratch_dir}/01-architect-spec.md"
        if not self._check_prerequisite(spec_path, "Development"):
            raise RuntimeError(
                f"Cannot proceed with Development phase: "
                f"Architect spec missing at {spec_path}"
            )

        # Create Engineer agent (ALL tools - vault + projects, autonomous mode)
        engineer = self.injector.create_specialist_agent(
            role="Senior AI/ML Engineer",
            skill_file="04-skills/senior-engineer.md",
            tools_filter='all',
            execution_mode='autonomous',  # ClaudeCodeAgent for code generation
            api_key=self.api_key,
            verbose=self.verbose
        )

        output_path = f"{context.scratch_dir}/02-engineer-output.md"

        task = f"""
You are the Senior AI/ML Engineer. Execute Phase 3: Development.

⚠️  CRITICAL TOOL USAGE RULES ⚠️

YOUR FIRST ACTION must be projects__create_structure().
YOUR ONLY tool for writing code is projects__write_file.

If you find yourself calling vault__write_file for a non-markdown file, STOP and use projects__write_file instead.

The vault__write_file tool will REJECT code files (.py, .toml, .yml, .gitignore, .env, etc.) with an error.
Only markdown (.md) files belong in the vault.

Read the architecture spec at: {spec_path}

You have TWO output requirements:

OUTPUT 1 - Real Code (Python) - Create FIRST:
Use projects tools to create executable code:

Step 1: YOUR FIRST ACTION - Scaffold the project structure:
Action: projects__create_structure
Action Input: {{"slug": "{context.poc_slug}"}}
This creates: pyproject.toml, src/, tests/, README.md, .gitignore, .env.example

Step 2: Write ALL Python files using projects__write_file:
Action: projects__write_file
Action Input: {{"slug": "{context.poc_slug}", "path": "src/<package>/main.py", "content": "..."}}

Repeat for ALL files:
- src/{context.poc_slug.replace('-', '_')}/*.py (all modules - note: hyphens become underscores)
- tests/*.py (all test files)
- Any configuration files (.yml, .toml, etc.) - use projects__write_file for these too

OUTPUT 2 - Documentation (Markdown) - Write AFTER code is done:
Write to: {output_path}
Include:
- Implementation summary
- Architecture decisions
- Code file descriptions (list actual files created)
- Test results (report what projects__run_tests shows)
- Evaluation metrics
- Known limitations
- Critic handoff notes

CRITICAL REMINDERS:
- ✅ projects__create_structure("{context.poc_slug}") MUST be your FIRST action
- ✅ projects__write_file() is your ONLY tool for code files (.py, .toml, .yml, .gitignore, .env, etc.)
- ✅ vault__write_file() is ONLY for markdown (.md) documentation
- ❌ vault__write_file() will REJECT any code file with an error message
- ✅ No placeholder code - everything must be executable
- ✅ Tests must run and pass when Critic runs projects__run_tests
- ✅ Document real file paths in your markdown output

Use YAML frontmatter for your markdown output:
---
type: engineer-output
created: {datetime.now().strftime("%Y-%m-%d")}
poc-slug: {context.poc_slug}
phase: development
iteration: {context.iteration_count + 1}
project-dir: {context.project_dir}
---

When done, provide Final Answer summarizing what was built.
"""

        # Build system prompt for ClaudeCodeAgent
        # Note: SkillInjector already builds this with firm context + skill content
        system_prompt = self.injector._build_system_prompt(
            firm_context=self.injector._load_firm_context(),
            skill_content=self.injector.load_skill("04-skills/senior-engineer.md"),
            tools_filter='all'
        )

        result = self._execute_agent(
            agent=engineer,
            task=task,
            system_prompt=system_prompt,
            role="Senior AI/ML Engineer",
            poc_slug=context.poc_slug,
            iteration=context.iteration_count + 1
        )

        context.specialist_outputs["engineer"] = output_path
        context.code_artifacts["main"] = f"{context.project_dir}/src/{context.poc_slug}/main.py"
        context.total_cost += result.total_cost
        context.current_phase = "development_complete"

        if self.verbose:
            print(f"\n✅ Development complete")


        print(f"   Docs: {output_path}")


        print(f"   Code: {context.project_dir}/")


        print(f"   Cost: ${result.total_cost:.4f}")



        self._write_status(context, f"Development complete (iter {context.iteration_count})")



        return context

    def _phase_review(self, context: AgentContext) -> tuple[AgentContext, CriticAssessment]:
        """
        Phase 4: Review (Solutions Critic)

        Critic:
        - Reviews all prior outputs
        - Evaluates against firm constraints
        - Issues verdict: PASS / PASS_WITH_CONDITIONS / FAIL
        - Writes report with YAML frontmatter
        """
        if self.verbose:
            print(f"\n{'='*80}")
            print(f"PHASE 4: REVIEW (Solutions Critic) - Iteration {context.iteration_count + 1}")
            print(f"{'='*80}\n")

        # Create Critic agent (ALL tools - needs projects tools to verify implementation, autonomous mode)
        critic = self.injector.create_specialist_agent(
            role="Solutions Critic",
            skill_file="04-skills/solutions-critic.md",
            tools_filter='all',
            execution_mode='autonomous',  # ClaudeCodeAgent for thorough verification
            api_key=self.api_key,
            verbose=self.verbose
        )

        report_path = f"{context.scratch_dir}/03-critic-report.md"

        task = f"""
You are the Solutions Critic. Execute Phase 4: Review.

This is iteration {context.iteration_count + 1} of {self.MAX_ITERATIONS}.

Read these files in order:
1. {context.brief_path}
2. {context.specialist_outputs.get('architect')}
3. {context.specialist_outputs.get('engineer')}
4. 01-firm-context/CONSTRAINTS.md
5. 01-firm-context/DOMAIN.md

IMPORTANT: Verify Engineer's implementation directly using projects tools:
- Use projects__list_files("{context.poc_slug}") to check file structure
- Use projects__check_dependencies("{context.poc_slug}") to validate pyproject.toml
- Use projects__check_syntax() for each Python file to verify no syntax errors
- Use projects__run_tests("{context.poc_slug}") to run actual tests

DO NOT trust Engineer's self-reported test results. Run verification yourself.

Review across all six dimensions per your skill file.

Write your report to: {report_path}

REQUIRED YAML frontmatter:
---
type: critic-report
created: {datetime.now().strftime("%Y-%m-%d")}
updated: {datetime.now().strftime("%Y-%m-%d")}
poc-slug: {context.poc_slug}
verdict: PASS | PASS_WITH_CONDITIONS | FAIL
confidence: high | medium | low
critical-count: 0
high-count: 0
medium-count: 0
low-count: 0
root-cause: design_flaw | implementation_bug | infeasible | null
requires-human-decision: true | false
iteration-number: {context.iteration_count + 1}
---

Set requires-human-decision to true if substantial HIGH issues need human risk acceptance.

In the markdown body, include:
- Overall Assessment
- Critical Issues (if any)
- High Issues (if any)
- Medium/Low Issues
- Strengths
- Root Cause Classification (on FAIL only)

When done, provide Final Answer with your verdict.
"""

        # Build system prompt for ClaudeCodeAgent
        system_prompt = self.injector._build_system_prompt(
            firm_context=self.injector._load_firm_context(),
            skill_content=self.injector.load_skill("04-skills/solutions-critic.md"),
            tools_filter='all'
        )

        result = self._execute_agent(
            agent=critic,
            task=task,
            system_prompt=system_prompt,
            role="Solutions Critic",
            poc_slug=context.poc_slug,
            iteration=context.iteration_count + 1
        )

        context.specialist_outputs["critic"] = report_path
        context.total_cost += result.total_cost
        context.current_phase = "review_complete"

        # Try to parse critic assessment - if file doesn't exist, return early with failure
        try:
            assessment = CriticAssessment.parse_from_report(report_path, self.vault)
        except (FileNotFoundError, KeyError) as e:
            if self.verbose:
                print(f"\n❌ Critic failed to create valid report at {report_path}")
                print(f"   Error: {e}")
            context.failed = True
            context.error = f"Critic agent did not create required report at {report_path}: {e}"
            # Return a dummy failed assessment
            return context, CriticAssessment(
                verdict="FAIL",
                confidence="high",
                critical_count=1,
                high_count=0,
                medium_count=0,
                low_count=0,
                root_cause="implementation_bug",
                requires_human_decision=True,
                iteration_number=context.iteration_count + 1,
                issues=[],
                summary="Critic agent failed to create required report file",
                strengths=[]
            )

        if self.verbose:
            print(f"\n✅ Review complete")


        print(f"   Verdict: {assessment.verdict}")


        print(f"   Confidence: {assessment.confidence}")


        print(f"   Critical: {assessment.critical_count}, High: {assessment.high_count}")


        print(f"   Report: {report_path}")


        print(f"   Cost: ${result.total_cost:.4f}")



        self._write_status(context, f"Review complete - verdict: {assessment.verdict} (iter {context.iteration_count})")



        return context, assessment

    def _apply_iteration_framework(
        self,
        context: AgentContext,
        assessment: CriticAssessment
    ) -> IterationDecision:
        """
        Team Lead's iteration decision framework.

        - PASS → proceed to communications
        - PASS_WITH_CONDITIONS → evaluate severity
        - FAIL → classify root cause and route rework

        Enforces 3-cycle maximum before human escalation.
        """
        if self.verbose:
            print(f"\n🤔 Applying iteration decision framework...")

        # Check iteration limit
        if context.iteration_count >= self.MAX_ITERATIONS - 1:  # -1 because we increment before rework
            if self.verbose:
                print(f"   ⚠️  At maximum iterations ({self.MAX_ITERATIONS})")

            if assessment.verdict != "PASS":
                return IterationDecision(
                    action="escalate_human",
                    reason=f"Exceeded {self.MAX_ITERATIONS} iteration cycles",
                    target_issues=[]
                )

        # FAIL verdict
        if assessment.verdict == "FAIL":
            if assessment.has_critical_issues():
                critical_issues = assessment.get_issues_by_severity("critical")

                # Route based on root cause
                if assessment.root_cause == "design_flaw":
                    if self.verbose:
                        print(f"   🔄 FAIL: Design flaw → Routing to Architect")
                    return IterationDecision(
                        action="rework_architect",
                        reason="Critical issues stem from architectural design",
                        target_issues=[i.title for i in critical_issues]
                    )
                elif assessment.root_cause == "implementation_bug":
                    if self.verbose:
                        print(f"   🔄 FAIL: Implementation bug → Routing to Engineer")
                    return IterationDecision(
                        action="rework_engineer",
                        reason="Critical issues stem from implementation bugs",
                        target_issues=[i.title for i in critical_issues]
                    )
                else:  # infeasible
                    if self.verbose:
                        print(f"   🚫 FAIL: Infeasible → Escalating to human")
                    return IterationDecision(
                        action="escalate_human",
                        reason="Fundamental feasibility concerns require human decision",
                        target_issues=[i.title for i in critical_issues]
                    )

        # PASS_WITH_CONDITIONS
        elif assessment.verdict == "PASS_WITH_CONDITIONS":
            if assessment.requires_human_decision:
                if self.verbose:
                    print(f"   ⏸️  PASS_WITH_CONDITIONS: Substantial HIGH issues → Human decision needed")
                return IterationDecision(
                    action="escalate_human",
                    reason="Substantial HIGH issues require risk acceptance decision",
                    target_issues=[i.title for i in assessment.get_issues_by_severity("high")]
                )
            elif assessment.has_high_issues():
                if self.verbose:
                    print(f"   🔄 PASS_WITH_CONDITIONS: Minor HIGH issues → Auto-iterating")
                return IterationDecision(
                    action="rework_engineer",
                    reason="Minor HIGH issues - auto-iterating without human approval",
                    target_issues=[i.title for i in assessment.get_issues_by_severity("high")]
                )
            else:
                if self.verbose:
                    print(f"   ✅ PASS_WITH_CONDITIONS: Only MEDIUM/LOW → Proceeding")
                return IterationDecision(
                    action="proceed",
                    reason="Only MEDIUM/LOW issues - acceptable to proceed",
                    target_issues=[]
                )

        # PASS
        else:
            if self.verbose:
                print(f"   ✅ PASS: No blocking issues → Proceeding to Communications")
            return IterationDecision(
                action="proceed",
                reason="PASS - no blocking issues",
                target_issues=[]
            )

    def _rework_iteration(
        self,
        context: AgentContext,
        decision: IterationDecision
    ) -> AgentContext:
        """
        Execute rework iteration based on Team Lead decision.

        Routes back to Architect or Engineer, increments iteration count.
        """
        context.iteration_count += 1

        if self.verbose:
            print(f"\n{'='*80}")
            print(f"🔄 REWORK ITERATION {context.iteration_count}")
            print(f"{'='*80}")
            print(f"   Action: {decision.action}")
            print(f"   Reason: {decision.reason}")
            if decision.target_issues:
                print(f"   Issues: {', '.join(decision.target_issues[:3])}...")
            print()

        if decision.action == "rework_architect":
            # Re-run architecture phase
            context = self._phase_architecture(context)
        elif decision.action == "rework_engineer":
            # Re-run development phase
            context = self._phase_development(context)

        return context

    def _phase_communications(self, context: AgentContext) -> AgentContext:
        """
        Phase 5: Communications (Communications Specialist)

        Communications Specialist:
        - Reads all prior outputs
        - Generates stakeholder deliverables
        - Writes to 02-projects/<slug>/
        """
        if self.verbose:
            print(f"\n{'='*80}")
            print("PHASE 5: COMMUNICATIONS (Communications Specialist)")
            print(f"{'='*80}\n")

        # PREREQUISITE CHECK: Critic report must exist with PASS verdict
        critic_report_path = context.specialist_outputs.get('critic', f"{context.scratch_dir}/03-critic-report.md")
        if not self._check_prerequisite(critic_report_path, "Communications"):
            if self.verbose:
                print(f"\n❌ Cannot proceed with Communications phase")
                print(f"   Required file missing: {critic_report_path}")
                print(f"   Critic must complete quality assessment first\n")
            context.specialist_outputs["communications_error"] = "prerequisite_missing"
            return context

        # Additional check: Verify PASS verdict
        try:
            critic_content = self.vault.read_file(critic_report_path)
            if "verdict: PASS" not in critic_content.lower():
                if self.verbose:
                    print(f"\n⚠️  Critic verdict is not PASS")
                    print(f"   Communications phase should only run after successful review")
                    print(f"   Consider this a warning, but proceeding anyway\n")
        except Exception:
            pass  # Already caught by prerequisite check

        # Create Communications agent (vault-only tools, autonomous mode)
        communicator = self.injector.create_specialist_agent(
            role="Communications Specialist",
            skill_file="04-skills/communications-specialist.md",
            tools_filter='vault_only',
            execution_mode='autonomous',
            api_key=self.api_key,
            verbose=self.verbose
        )

        deliverables_dir = f"02-projects/{context.poc_slug}"

        task = f"""
You are the Communications Specialist. Execute Phase 5: Communications.

Read all prior outputs:
1. {context.specialist_outputs.get('critic')}
2. {context.specialist_outputs.get('architect')}
3. {context.specialist_outputs.get('engineer')}
4. {context.brief_path}
5. 01-firm-context/STAKEHOLDERS.md
6. 01-firm-context/DOMAIN.md

Generate all stakeholder deliverables to: {deliverables_dir}/

Required deliverables:
1. executive-summary.md
2. presentation-deck.md
3. position-paper.md
4. talking-points.md
5. faq.md

Apply the Switch framework (Rider + Elephant + Path) to all communications.

Address financial services stakeholder priorities:
1. Risk management
2. Compliance
3. ROI
4. Competitive advantage

Include Critic's risks transparently in all deliverables.

When done, provide Final Answer listing all deliverables created.
"""

        # Build system prompt for ClaudeCodeAgent
        system_prompt = self.injector._build_system_prompt(
            firm_context=self.injector._load_firm_context(),
            skill_content=self.injector.load_skill("04-skills/communications-specialist.md"),
            tools_filter='vault_only'
        )

        result = self._execute_agent(
            agent=communicator,
            task=task,
            system_prompt=system_prompt,
            role="Communications Specialist",
            poc_slug=context.poc_slug,
            iteration=context.iteration_count + 1
        )

        context.specialist_outputs["communicator"] = deliverables_dir
        context.total_cost += result.total_cost
        context.current_phase = "communications_complete"

        if self.verbose:
            print(f"\n✅ Communications complete")


        print(f"   Deliverables: {deliverables_dir}/")


        print(f"   Cost: ${result.total_cost:.4f}")



        self._write_status(context, "Communications complete - stakeholder deliverables created")



        return context

    def _check_cost_limit(self, context: AgentContext) -> None:
        """Check if cost limit exceeded and escalate if needed."""
        if context.total_cost > self.cost_limit:
            raise RuntimeError(
                f"Cost limit exceeded: ${context.total_cost:.2f} > ${self.cost_limit:.2f}. "
                f"Escalating to human for budget approval."
            )

    def _escalate_to_human(
        self,
        context: AgentContext,
        decision: IterationDecision,
        assessment: CriticAssessment
    ) -> Dict[str, Any]:
        """
        Escalate to human for decision.

        Returns a result dict with escalation details.
        """
        if self.verbose:
            print(f"\n{'='*80}")
            print("⏸️  HUMAN ESCALATION REQUIRED")
            print(f"{'='*80}")
            print(f"\nReason: {decision.reason}")
            print(f"Status: {context.current_phase}")
            print(f"Iterations: {context.iteration_count}/{self.MAX_ITERATIONS}")
            print(f"Total Cost: ${context.total_cost:.2f}")
            print(f"\nCritic Verdict: {assessment.verdict}")
            print(f"Confidence: {assessment.confidence}")
            if decision.target_issues:
                print(f"\nTarget Issues:")
                for issue in decision.target_issues[:5]:
                    print(f"  - {issue}")
            print(f"\nReview report: {context.specialist_outputs.get('critic')}")
            print()

        return {
            "status": "escalated",
            "reason": decision.reason,
            "phase": context.current_phase,
            "iteration": context.iteration_count,
            "total_cost": context.total_cost,
            "critic_verdict": assessment.verdict,
            "critic_report": context.specialist_outputs.get("critic"),
            "scratch_dir": context.scratch_dir,
            "project_dir": context.project_dir,
            "action_required": "Review Critic report and decide: approve, reject, or request changes"
        }

    def _finalize_project(self, context: AgentContext) -> Dict[str, Any]:
        """
        Finalize project and return results.
        """
        # Update project overview
        overview_path = f"02-projects/{context.poc_slug}/overview.md"
        overview = self.vault.read_file(overview_path)

        # Update status
        updated = overview.replace("status: active", "status: complete")
        updated = updated.replace("Status**: In Progress", "Status**: Complete")
        updated = updated.replace("- [ ]", "- [x]")  # Check all boxes
        updated += f"\n\n**Completed**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        updated += f"**Total Cost**: ${context.total_cost:.2f}\n"
        updated += f"**Iterations**: {context.iteration_count}\n"

        self.vault.write_file(overview_path, updated)

        if self.verbose:
            print(f"\n{'='*80}")
            print("✅ POC PIPELINE COMPLETE")
            print(f"{'='*80}")
            print(f"\nProject: {context.poc_slug}")
            print(f"Total Cost: ${context.total_cost:.2f}")
            print(f"Iterations: {context.iteration_count}")
            print(f"\nDeliverables: 02-projects/{context.poc_slug}/")
            print(f"Code: {context.project_dir}/")
            print(f"Scratch: {context.scratch_dir}/")
            print()

        return {
            "status": "completed",
            "poc_slug": context.poc_slug,
            "total_cost": context.total_cost,
            "iterations": context.iteration_count,
            "deliverables": {
                "overview": f"02-projects/{context.poc_slug}/overview.md",
                "executive_summary": f"02-projects/{context.poc_slug}/executive-summary.md",
                "presentation_deck": f"02-projects/{context.poc_slug}/presentation-deck.md",
                "position_paper": f"02-projects/{context.poc_slug}/position-paper.md",
                "talking_points": f"02-projects/{context.poc_slug}/talking-points.md",
                "faq": f"02-projects/{context.poc_slug}/faq.md",
            },
            "code": context.project_dir,
            "scratch": context.scratch_dir
        }


# Convenience function
def run_poc_pipeline(
    poc_idea: str,
    poc_slug: str,
    api_key: Optional[str] = None,
    dev_mode: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Run the complete PoC pipeline with default settings.

    Args:
        poc_idea: High-level PoC concept
        poc_slug: URL-safe project slug
        api_key: Anthropic API key (optional, defaults to env var)
        dev_mode: Use DEV_MODE for cost control (optional, defaults to env var)

    Returns:
        Pipeline result with deliverable paths or escalation details

    Example:
        >>> result = run_poc_pipeline(
        ...     poc_idea="Build a client email summarization tool using GenAI",
        ...     poc_slug="client-email-summarizer"
        ... )
        >>> print(result["status"])  # "completed" or "escalated"
        >>> if result["status"] == "completed":
        ...     print(result["deliverables"])
    """
    pipeline = PoCPipeline(api_key=api_key, dev_mode=dev_mode)
    return pipeline.run(poc_idea, poc_slug)
