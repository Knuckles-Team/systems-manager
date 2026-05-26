import json
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.append("/home/genius/.gemini/antigravity/skills/code-enhancer/scripts")

import generate_report
import run_multi_project

project_dir = "/home/apps/workspace/agent-packages/agents/systems-manager"
print("Starting direct CE analysis...")
result = run_multi_project._run_single_project(project_dir)
print("Analysis complete!")

# Save raw results
output_path = Path("specify_reports") / "systems-manager"
output_path.mkdir(parents=True, exist_ok=True)
(output_path / "results.json").write_text(
    json.dumps(result, indent=2), encoding="utf-8"
)
print(f"Results saved to {output_path / 'results.json'}")

# Generate report
report = generate_report.generate_report(
    result["domain_results"], project_name="systems-manager"
)
(output_path / "code_enhancement_report.md").write_text(report, encoding="utf-8")
print(f"Report generated at {output_path / 'code_enhancement_report.md'}")
