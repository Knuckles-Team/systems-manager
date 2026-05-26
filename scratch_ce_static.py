import json
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.append("/home/genius/.gemini/antigravity/skills/code-enhancer/scripts")

import generate_report

project_dir = "/home/apps/workspace/agent-packages/agents/systems-manager"
project_name = "systems-manager"
results = []
timing = {}

analyzers = [
    ("analyze_project", "analyze_project"),
    ("audit_dependencies", "audit_dependencies"),
    ("analyze_codebase", "analyze_codebase"),
    ("analyze_security", "analyze_security"),
    ("analyze_tests", "analyze_tests"),
    ("audit_documentation", "audit_documentation"),
    ("analyze_architecture", "analyze_architecture"),
    ("trace_concepts", "trace_concepts"),
    ("analyze_directory_density", "analyze_directory_density"),
    ("analyze_ui", "analyze_ui"),
    ("analyze_version_sync", "analyze_version_sync"),
    ("audit_changelog", "audit_changelog"),
    ("grade_pytest", "grade_pytest"),
    ("scan_env_vars", "scan_env_vars"),
    ("analyze_xdg_kg", "check_xdg_compliance"),
]

import time

for module_name, func_name in analyzers:
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            module_name,
            f"/home/genius/.gemini/antigravity/skills/code-enhancer/scripts/{module_name}.py",
        )
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        func = getattr(mod, func_name)

        print(f"Running {module_name}...")
        start = time.monotonic()
        result = func(project_dir)
        elapsed = time.monotonic() - start
        timing[module_name] = round(elapsed, 2)

        if result.get("score", 0) != -1:
            results.append(result)
            print(
                f"  Completed {module_name}: score={result.get('score')}, grade={result.get('grade')}"
            )
    except Exception as e:
        results.append(
            {
                "domain": module_name,
                "score": 0,
                "grade": "F",
                "findings": [f"Analysis error: {str(e)[:200]}"],
                "justifications": [],
            }
        )
        print(f"  Error running {module_name}: {e}")

# Save raw results
output_path = Path("specify_reports") / "systems-manager"
output_path.mkdir(parents=True, exist_ok=True)
(output_path / "results_static.json").write_text(
    json.dumps(
        {
            "project": project_name,
            "path": project_dir,
            "domain_results": results,
            "timing": timing,
        },
        indent=2,
    ),
    encoding="utf-8",
)

# Generate report
report = generate_report.generate_report(results, project_name="systems-manager")
(output_path / "code_enhancement_report.md").write_text(report, encoding="utf-8")
print(f"Report generated successfully at {output_path / 'code_enhancement_report.md'}!")
