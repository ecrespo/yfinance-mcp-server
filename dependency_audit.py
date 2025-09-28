#!/usr/bin/env python3
"""
Dependency audit script for this repository.

- Scans all detected package managers:
  - Python (uv.lock / pyproject.toml)
  - Dockerfile (apt-get installs) — informational
- Queries OSV.dev for known vulnerabilities (IDs, severity, fixed versions) per resolved dependency version.
- Queries PyPI for available updates and classifies as patch/minor/major. Majors are noted as potentially breaking changes.
- Writes report to dependency-audit-<YYYY-MM-DD>.md in the project root.

Run: python3 dependency_audit.py
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    tomllib = None

import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))

UV_LOCK_PATH = os.path.join(ROOT, "uv.lock")
PYPROJECT_PATH = os.path.join(ROOT, "pyproject.toml")
DOCKERFILE_PATH = os.path.join(ROOT, "Dockerfile")

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
PYPI_JSON_URL_TMPL = "https://pypi.org/pypi/{name}/json"


@dataclass
class Dep:
    name: str
    version: str


@dataclass
class Vuln:
    id: str
    summary: Optional[str]
    severity: Optional[str]
    affected_ranges: List[str]
    fixed_versions: List[str]
    references: List[str]


@dataclass
class UpdateInfo:
    current: str
    latest: Optional[str]
    update_type: Optional[str]  # patch|minor|major|unknown
    is_breaking: bool


def _load_toml(path: str) -> dict:
    if not tomllib:
        raise RuntimeError("Python tomllib is required to parse TOML files")
    with open(path, "rb") as f:
        return tomllib.load(f)


def parse_uv_lock(path: str) -> List[Dep]:
    if not os.path.exists(path):
        return []
    data = _load_toml(path)
    packages = data.get("package", [])
    deps: List[Dep] = []
    for p in packages:
        name = p.get("name")
        version = p.get("version")
        if name and version:
            deps.append(Dep(name=name, version=version))
    # de-duplicate by name@version in case of repeats
    uniq = {}
    for d in deps:
        uniq[(d.name.lower(), d.version)] = d
    return list(uniq.values())


def parse_pip_deps_from_pyproject(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    data = _load_toml(path)
    project = data.get("project", {})
    deps = project.get("dependencies", []) or []
    # normalize entries like "package[extra]>=1.2.3" -> package
    names: List[str] = []
    for s in deps:
        # take leading token up to first space or comparison operator
        m = re.match(r"^([A-Za-z0-9_.\-]+)", s)
        if not m:
            continue
        name = m.group(1)
        # strip extras: package[cli] -> package
        name = name.split("[")[0]
        names.append(name)
    return names


def parse_apt_packages_from_dockerfile(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # Very simple heuristic: look for lines with "apt-get install" and collect tokens until end of line or backslash chain.
    pkgs: List[str] = []
    # Combine backslash-continued lines for easier parsing
    # Replace line continuations with spaces
    normalized = re.sub(r"\\\n", " ", text)
    for line in normalized.splitlines():
        if "apt-get install" in line:
            # split and take tokens after 'install'
            after = line.split("apt-get install", 1)[1]
            # Remove options like -y and --no-install-recommends
            after = re.sub(r"\s*-\S+", " ", after)
            after = re.sub(r"\s+--\S+", " ", after)
            # Remove shell operators and clean
            after = re.split(r"[;&|]", after)[0]
            for tok in after.strip().split():
                if tok and tok not in {"&&", "\\", "rm", "-rf", "/var/lib/apt/lists/*", "apt-get", "clean", "/var/lib/apt/lists/*"}:
                    pkgs.append(tok)
    # filter obvious non-package tokens
    pkgs = [p for p in pkgs if all(ch not in p for ch in "=/")]  # exclude paths
    # e.g. empty in this Dockerfile
    return sorted(set(pkgs))


def http_json(url: str, data: Optional[dict] = None, timeout: int = 30) -> dict:
    try:
        if data is None:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        else:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = e.read().decode("utf-8")
        except Exception:
            payload = ""
        raise RuntimeError(f"HTTP error for {url}: {e.code} {e.reason} {payload}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error for {url}: {e.reason}")


def query_osv_vulns(deps: List[Dep]) -> Dict[Tuple[str, str], List[Vuln]]:
    if not deps:
        return {}
    queries = [
        {
            "package": {"ecosystem": "PyPI", "name": d.name},
            "version": d.version,
        }
        for d in deps
    ]
    payload = {"queries": queries}
    data = http_json(OSV_BATCH_URL, data=payload)
    results: Dict[Tuple[str, str], List[Vuln]] = {}
    for d, res in zip(deps, data.get("results", [])):
        vulns = []
        for v in res.get("vulns", []) or []:
            sev = None
            # Prefer CVSS severity if available
            if v.get("severity"):
                # severity is list of {type, score}
                sev = ", ".join(f"{sv.get('type')}: {sv.get('score')}" for sv in v["severity"]) or None
            # collect fixed versions from affected ranges
            fixed_versions: List[str] = []
            affected_ranges: List[str] = []
            for aff in v.get("affected", []) or []:
                for r in aff.get("ranges", []) or []:
                    rtype = r.get("type")
                    events = r.get("events", []) or []
                    parts = []
                    for ev in events:
                        if "introduced" in ev:
                            parts.append(f"introduced {ev['introduced']}")
                        if "fixed" in ev:
                            fv = ev["fixed"]
                            if fv:
                                fixed_versions.append(fv)
                            parts.append(f"fixed {fv}")
                    if parts:
                        affected_ranges.append(f"{rtype}: {', '.join(parts)}")
                for ver in aff.get("versions", []) or []:
                    # sometimes explicit fixed versions are in versions list, include for context
                    pass
            refs = [r.get("url") for r in v.get("references", []) or [] if r.get("url")]
            vulns.append(Vuln(
                id=v.get("id"),
                summary=v.get("summary"),
                severity=sev,
                affected_ranges=affected_ranges,
                fixed_versions=sorted(set([fv for fv in fixed_versions if fv])),
                references=refs,
            ))
        results[(d.name.lower(), d.version)] = vulns
    return results


def _numeric_prefix(version: str) -> List[int]:
    # Extract leading numeric components (PEP 440 aware enough for basic comparison)
    # e.g., '1.2.3.post1' -> [1,2,3]
    nums: List[int] = []
    for part in re.split(r"[.+-]", version):
        if not part:
            break
        m = re.match(r"^(\d+)", part)
        if not m:
            break
        nums.append(int(m.group(1)))
    return nums


def classify_update(current: str, candidate: str) -> str:
    c = _numeric_prefix(current)
    n = _numeric_prefix(candidate)
    if not c or not n:
        return "unknown"
    # pad
    L = max(len(c), len(n), 3)
    c = (c + [0] * (L - len(c)))[:L]
    n = (n + [0] * (L - len(n)))[:L]
    if n[0] > c[0]:
        return "major"
    if n[0] == c[0] and n[1] > c[1]:
        return "minor"
    if n[0] == c[0] and n[1] == c[1] and n[2] > c[2]:
        return "patch"
    return "unknown"


def query_pypi_update(name: str, current_version: str) -> UpdateInfo:
    url = PYPI_JSON_URL_TMPL.format(name=name)
    try:
        data = http_json(url)
    except Exception:
        return UpdateInfo(current=current_version, latest=None, update_type=None, is_breaking=False)
    info = data.get("info", {})
    latest = info.get("version")
    if not latest:
        return UpdateInfo(current=current_version, latest=None, update_type=None, is_breaking=False)
    utype = classify_update(current_version, latest)
    return UpdateInfo(current=current_version, latest=latest, update_type=utype, is_breaking=(utype == "major"))


def generate_markdown(
    python_deps: List[Dep],
    vulns: Dict[Tuple[str, str], List[Vuln]],
    updates: Dict[str, UpdateInfo],
    apt_packages: List[str],
) -> str:
    today = _dt.date.today().isoformat()
    lines: List[str] = []
    lines.append(f"# Dependency Audit — {today}")
    lines.append("")
    lines.append("Scope: Python (uv.lock/pyproject.toml); Dockerfile apt packages (informational).")
    lines.append("")
    # Python deps
    lines.append("## Python (uv.lock)")
    if not python_deps:
        lines.append("- No uv.lock found or no packages parsed.")
    else:
        for d in sorted(python_deps, key=lambda x: x.name.lower()):
            key = (d.name.lower(), d.version)
            vlist = vulns.get(key, [])
            upd = updates.get(d.name.lower())
            update_str = ""
            if upd and upd.latest and upd.latest != d.version:
                note = " — potential breaking changes" if upd.update_type == "major" else ""
                update_str = f" | Update available: {upd.latest} ({upd.update_type}){note}"
            lines.append(f"- {d.name}=={d.version}{update_str}")
            if vlist:
                for v in vlist:
                    sev = f" | Severity: {v.severity}" if v.severity else ""
                    fixed = f" | Fixed in: {', '.join(v.fixed_versions)}" if v.fixed_versions else ""
                    lines.append(f"  - Vulnerability: {v.id}{sev}{fixed}")
                    if v.summary:
                        lines.append(f"    - {v.summary}")
                    if v.references:
                        lines.append(f"    - Refs: {', '.join(v.references[:3])}")
    lines.append("")

    # Apt packages
    lines.append("## Dockerfile apt packages")
    if not apt_packages:
        lines.append("- No apt packages installed (or none detected).")
    else:
        for p in apt_packages:
            lines.append(f"- {p}")
        lines.append("- Note: Vulnerability scanning for apt packages not implemented in this script.")
    lines.append("")

    # Summary of updates
    lines.append("## Update summary")
    patch_minor: List[str] = []
    majors: List[str] = []
    for dep in python_deps:
        u = updates.get(dep.name.lower())
        if u and u.latest and u.latest != dep.version:
            entry = f"{dep.name} {dep.version} -> {u.latest} ({u.update_type})"
            if u.update_type in {"patch", "minor"}:
                patch_minor.append(entry)
            elif u.update_type == "major":
                majors.append(entry)
    if patch_minor:
        lines.append("### Patch/Minor (safe to apply after tests)")
        for e in sorted(patch_minor):
            lines.append(f"- {e}")
    else:
        lines.append("- No patch/minor updates available.")
    if majors:
        lines.append("")
        lines.append("### Major updates (potential breaking changes — review before applying)")
        for e in sorted(majors):
            lines.append(f"- {e}")
    lines.append("")

    # Guidance
    lines.append("## Next steps")
    lines.append("- Recommend applying patch/minor updates where tests pass.")
    lines.append("- For major updates, review changelogs and breaking changes.")
    lines.append("- This repo currently has no tests; consider adding a small smoke test suite to validate functionality before updating.")

    return "\n".join(lines)


def main() -> int:
    # Parse dependencies
    python_deps = parse_uv_lock(UV_LOCK_PATH)
    top_names = set(parse_pip_deps_from_pyproject(PYPROJECT_PATH))

    # Query vulnerabilities
    vulns = query_osv_vulns(python_deps)

    # Query updates for top-level packages only (keep noise down)
    updates: Dict[str, UpdateInfo] = {}
    for d in python_deps:
        if d.name.split("[")[0].lower() in top_names:
            updates[d.name.lower()] = query_pypi_update(d.name, d.version)

    # Apt packages (informational only)
    apt_packages = parse_apt_packages_from_dockerfile(DOCKERFILE_PATH)

    # Generate report
    today = _dt.date.today().isoformat()
    out_name = f"dependency-audit-{today}.md"
    content = generate_markdown(python_deps, vulns, updates, apt_packages)
    with open(os.path.join(ROOT, out_name), "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {out_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
