from __future__ import annotations

import pytest

from cogenai.application.orchestrator.refiners.issue_analyzer import IssueAnalyzer

from ._fixtures import make_issues


class TestIssueAnalyzer:

    def setup_method(self):
        self.analyzer = IssueAnalyzer()

    def test_routes_block_scope_to_block_level(self):
        issues = make_issues(("i-1", "block", "b-1", "completeness"))
        analysis = self.analyzer.analyze(issues)
        assert analysis.issues_for("block") == issues
        assert analysis.issues_for("module") == ()

    def test_routes_section_scope_to_section_level(self):
        issues = make_issues(("i-1", "section", "s-1", "pedagogical"))
        analysis = self.analyzer.analyze(issues)
        assert analysis.issues_for("section") == issues

    def test_routes_module_scope_to_module_level(self):
        issues = make_issues(("i-1", "module", "m-1", "structural"))
        analysis = self.analyzer.analyze(issues)
        assert analysis.issues_for("module") == issues

    def test_audience_alignment_routes_to_context(self):
        issues = make_issues(("i-1", "course", "c-1", "audience_alignment"))
        analysis = self.analyzer.analyze(issues)
        assert analysis.issues_for("context") == issues

    def test_depth_routes_to_context(self):
        issues = make_issues(("i-1", "course", "c-1", "depth"))
        analysis = self.analyzer.analyze(issues)
        assert analysis.issues_for("context") == issues

    def test_prerequisite_category_routes_to_prerequisites(self):
        issues = make_issues(("i-1", "course", "c-1", "prerequisite"))
        analysis = self.analyzer.analyze(issues)
        assert analysis.issues_for("prerequisites") == issues

    def test_structural_routes_to_plan(self):
        issues = make_issues(("i-1", "course", "c-1", "structural"))
        analysis = self.analyzer.analyze(issues)
        assert analysis.issues_for("plan") == issues

    def test_unknown_scope_defaults_to_context(self):
        issues = make_issues(("i-1", "weird-scope", "x-1", "general"))
        analysis = self.analyzer.analyze(issues)
        assert analysis.issues_for("context") == issues

    def test_cascade_context_invalidates_all_levels(self):
        issues = make_issues(("i-1", "course", "c-1", "audience_alignment"))
        analysis = self.analyzer.analyze(issues)
        cascade = analysis.cascade.get("context", ())
        assert "prerequisites" in cascade
        assert "plan" in cascade
        assert "module" in cascade
        assert "section" in cascade
        assert "block" in cascade

    def test_cascade_module_invalidates_section_and_block(self):
        issues = make_issues(("i-1", "module", "m-1", "completeness"))
        analysis = self.analyzer.analyze(issues)
        cascade = analysis.cascade.get("module", ())
        assert "section" in cascade
        assert "block" in cascade
        assert "context" not in cascade

    def test_cascade_section_invalidates_block(self):
        issues = make_issues(("i-1", "section", "s-1", "pedagogical"))
        analysis = self.analyzer.analyze(issues)
        cascade = analysis.cascade.get("section", ())
        assert "block" in cascade
        assert "module" not in cascade

    def test_no_cascade_for_block_level(self):
        issues = make_issues(("i-1", "block", "b-1", "completeness"))
        analysis = self.analyzer.analyze(issues)
        assert analysis.cascade.get("block", ()) == ()

    def test_mixed_issues_route_to_correct_levels(self):
        issues = make_issues(
            ("i-1", "course", "c-1", "audience_alignment"),
            ("i-2", "module", "m-1", "structural"),
            ("i-3", "section", "s-1", "pedagogical"),
            ("i-4", "block", "b-1", "completeness"),
            ("i-5", "block", "b-2", "factual"),
        )
        analysis = self.analyzer.analyze(issues)
        assert len(analysis.issues_for("context")) == 1
        assert len(analysis.issues_for("module")) == 1
        assert len(analysis.issues_for("section")) == 1
        assert len(analysis.issues_for("block")) == 2
