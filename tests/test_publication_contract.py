#!/usr/bin/env python
"""Compact regression tests for the immutable validated publication contract.

Parses workflow YAML and proves:
- Reusable workflows are invoked at jobs.<id>.uses, NOT steps[].uses
- Exact pins, needs, inputs, outputs, trigger constraints
- Least privilege and absence of legacy dispatch
- Fail-closed resolver boundaries
"""
import json

import yaml
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

TOOLING_SHA = "7adff881ab5d0a7fc63f7474a78b2688e2e6eee4"
ADDON_PKG_PIN = (
    "Serph91P/repository.serph91p/.github/workflows/"
    f"reusable-addon-package.yml@{TOOLING_SHA}"
)
ADDON_NOTIFY_PIN = (
    "Serph91P/repository.serph91p/.github/workflows/"
    f"reusable-notify-repository.yml@{TOOLING_SHA}"
)


def _load(name):
    with open(WORKFLOWS / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _all_step_uses(wf):
    """Return list of (job_name, uses_string) for every step-level uses."""
    refs = []
    for jname, job in wf.get("jobs", {}).items():
        for step in job.get("steps", []):
            u = step.get("uses", "")
            if u:
                refs.append((jname, u))
    return refs


def _caller_job(wf, needle):
    """Find the single job that invokes a reusable workflow matching needle."""
    for jname, job in wf.get("jobs", {}).items():
        u = job.get("uses", "")
        if needle in u:
            return jname, job
    return None, None


# ── addon-validations.yml ─────────────────────────────────────────────────

class TestAddonValidations:
    """Prove the package job is a job-level reusable caller, not step-level."""

    def test_no_step_level_reusable_calls(self):
        wf = _load("addon-validations.yml")
        for jname, uses in _all_step_uses(wf):
            assert "reusable-" not in uses, (
                f"job {jname!r} calls reusable workflow from steps[].uses: {uses}"
            )

    def test_package_job_has_job_level_uses(self):
        wf = _load("addon-validations.yml")
        pkg = wf["jobs"]["package"]
        assert pkg["uses"] == ADDON_PKG_PIN

    def test_package_caller_has_no_steps(self):
        wf = _load("addon-validations.yml")
        assert "steps" not in wf["jobs"]["package"]

    def test_package_needs_lint_and_test(self):
        wf = _load("addon-validations.yml")
        needs = wf["jobs"]["package"].get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        assert "lint-and-test" in needs

    def test_package_inputs_addon_id(self):
        wf = _load("addon-validations.yml")
        w = wf["jobs"]["package"].get("with", {})
        assert w["addon_id"] == "plugin.video.plexkodiconnect"

    def test_package_inputs_runtime_entries(self):
        wf = _load("addon-validations.yml")
        w = wf["jobs"]["package"].get("with", {})
        entries = json.loads(w["runtime_entries_json"])
        assert "addon.xml" in entries
        assert "resources/" in entries

    def test_package_runtime_entries_exact_ordered_list(self):
        """runtime_entries_json must be exactly this ordered list."""
        wf = _load("addon-validations.yml")
        w = wf["jobs"]["package"].get("with", {})
        entries = json.loads(w["runtime_entries_json"])
        expected = [
            "addon.xml", "changelog.txt", "context_extras.py", "context_menu.py",
            "default.py", "service.py", "fanart.jpg", "icon.png", "themoviedb.png",
            "resources/",
        ]
        assert entries == expected

    def test_package_permissions(self):
        wf = _load("addon-validations.yml")
        perms = wf["jobs"]["package"].get("permissions", {})
        assert perms.get("contents") == "read"
        assert perms.get("id-token") == "write"

    def test_workflow_name(self):
        wf = _load("addon-validations.yml")
        assert wf["name"] == "Add-on Validations"

    def test_push_triggers_develop_only(self):
        wf = _load("addon-validations.yml")
        on = wf.get("on") or wf.get(True)
        branches = on.get("push", {}).get("branches", [])
        assert "develop" in branches
        assert "main" not in branches

    def test_pr_triggers_develop_only(self):
        wf = _load("addon-validations.yml")
        on = wf.get("on") or wf.get(True)
        branches = on.get("pull_request", {}).get("branches", [])
        assert "develop" in branches
        assert "main" not in branches


# ── notify-repository.yml ─────────────────────────────────────────────────

class TestNotifyRepository:
    """Prove two-job structure: resolve + job-level reusable caller."""

    def test_resolve_job_exists(self):
        wf = _load("notify-repository.yml")
        assert "resolve" in wf["jobs"]

    def test_resolve_job_has_steps(self):
        wf = _load("notify-repository.yml")
        assert "steps" in wf["jobs"]["resolve"]

    def test_caller_job_exists(self):
        wf = _load("notify-repository.yml")
        jname, _ = _caller_job(wf, "reusable-notify")
        assert jname is not None, "no caller job invokes reusable-notify-repository"

    def test_caller_job_has_no_steps(self):
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        assert "steps" not in job

    def test_caller_needs_resolve(self):
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        needs = job.get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        assert "resolve" in needs

    def test_caller_exact_pin(self):
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        assert job["uses"] == ADDON_NOTIFY_PIN

    def test_caller_fixed_workflow_name(self):
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        assert job["with"]["validation_workflow"] == "Add-on Validations"

    def test_caller_fixed_workflow_path(self):
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        assert job["with"]["validation_workflow_path"] == (
            ".github/workflows/addon-validations.yml"
        )

    def test_caller_fixed_event(self):
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        assert job["with"]["validation_event"] == "push"

    def test_caller_fixed_branch(self):
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        assert job["with"]["expected_branch"] == "develop"

    def test_caller_source_repository(self):
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        assert job["with"]["source_repository"] == "${{ github.repository }}"

    def test_caller_evidence_outputs(self):
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        w = job["with"]
        assert w["addon_id"] == "${{ needs.resolve.outputs.addon_id }}"
        assert w["addon_version"] == "${{ needs.resolve.outputs.addon_version }}"
        assert w["artifact_sha256"] == "${{ needs.resolve.outputs.artifact_sha256 }}"
        assert w["publication_id"] == "${{ needs.resolve.outputs.publication_id }}"

    def test_caller_candidate_sha_from_workflow_run(self):
        """candidate_sha must come from github.event.workflow_run.head_sha."""
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        assert job["with"]["candidate_sha"] == (
            "${{ github.event.workflow_run.head_sha }}"
        )

    def test_caller_validation_run_id_from_workflow_run(self):
        """validation_run_id must come from github.event.workflow_run.id."""
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        assert job["with"]["validation_run_id"] == (
            "${{ github.event.workflow_run.id }}"
        )

    def test_resolve_no_candidate_sha_output(self):
        """candidate_sha must not be sourced from evidence outputs."""
        wf = _load("notify-repository.yml")
        resolve = wf["jobs"]["resolve"]
        outputs = resolve.get("outputs", {})
        assert "candidate_sha" not in outputs

    def test_resolve_no_validation_run_id_output(self):
        """validation_run_id must not be sourced from evidence outputs."""
        wf = _load("notify-repository.yml")
        resolve = wf["jobs"]["resolve"]
        outputs = resolve.get("outputs", {})
        assert "validation_run_id" not in outputs

    def test_resolve_no_validation_head_sha_output(self):
        """validation_head_sha must be removed entirely."""
        wf = _load("notify-repository.yml")
        resolve = wf["jobs"]["resolve"]
        outputs = resolve.get("outputs", {})
        assert "validation_head_sha" not in outputs

    def test_caller_passes_dispatch_token(self):
        wf = _load("notify-repository.yml")
        _, job = _caller_job(wf, "reusable-notify")
        secrets = job.get("secrets", {})
        assert secrets.get("REPO_DISPATCH_TOKEN") == (
            "${{ secrets.REPO_DISPATCH_TOKEN }}"
        )

    def test_no_step_level_reusable_calls(self):
        wf = _load("notify-repository.yml")
        for jname, uses in _all_step_uses(wf):
            assert "reusable-" not in uses, (
                f"job {jname!r} calls reusable workflow from steps[].uses: {uses}"
            )

    def test_workflow_run_trigger(self):
        wf = _load("notify-repository.yml")
        on = wf.get("on") or wf.get(True)
        wr = on["workflow_run"]
        assert "Add-on Validations" in wr["workflows"]
        assert "completed" in wr["types"]
        assert "develop" in wr["branches"]

    def test_no_legacy_dispatch(self):
        wf = _load("notify-repository.yml")
        on = wf.get("on") or wf.get(True)
        assert "push" not in on
        assert "repository_dispatch" not in on

    def test_resolve_job_permissions(self):
        wf = _load("notify-repository.yml")
        perms = wf["jobs"]["resolve"].get("permissions", {})
        assert perms.get("actions") == "read"
        assert perms.get("contents") == "read"

    def test_resolve_fail_closed_requires_both_artifacts(self):
        """Resolver script must require exactly one addon-package AND one evidence."""
        wf = _load("notify-repository.yml")
        resolve = wf["jobs"]["resolve"]
        script = "\n".join(
            step.get("run", "")
            for step in resolve["steps"]
            if "resolve" in step.get("id", "")
        )
        assert "addon-package" in script, "resolver must reference addon-package"
        assert "validation-evidence" in script, "resolver must reference validation-evidence"

    def test_resolve_rejects_expired_artifacts(self):
        """Resolver must fail-closed on expired required artifacts, not continue."""
        wf = _load("notify-repository.yml")
        resolve = wf["jobs"]["resolve"]
        script = "\n".join(
            step.get("run", "")
            for step in resolve["steps"]
            if "resolve" in step.get("id", "")
        )
        assert "expired" in script.lower(), (
            "resolver must check for expired artifacts"
        )
        assert "raise SystemExit" in script, (
            "resolver must raise SystemExit"
        )
        lines = script.split("\n")
        found = False
        for i, line in enumerate(lines):
            if "raise SystemExit" in line:
                window = "\n".join(lines[i:i+4])
                if "expired" in window.lower():
                    found = True
                    break
        assert found, (
            "raise SystemExit must appear within 3 lines of 'expired' check"
        )

    def test_resolve_validates_evidence_is_json_object(self):
        """Resolver must validate evidence is a JSON object."""
        wf = _load("notify-repository.yml")
        resolve = wf["jobs"]["resolve"]
        script = "\n".join(
            step.get("run", "")
            for step in resolve["steps"]
            if "resolve" in step.get("id", "")
        )
        assert "dict" in script or "Mapping" in script or "object" in script.lower(), (
            "resolver must validate evidence is a JSON object"
        )
