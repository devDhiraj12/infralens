import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))

from parser import parse_plan
from cfn_parser import parse_changeset
from cost import estimate_costs
from security import scan_security
from comment import post_comment, build_markdown


def main():
    plan_path = os.environ.get("PLAN_JSON_PATH", "plan.json")
    plan_type = os.environ.get("PLAN_TYPE", "terraform").lower()
    block_on_high = os.environ.get("BLOCK_ON_HIGH", "true").lower() == "true"

    if not os.path.exists(plan_path):
        print(f"Error: plan file not found at '{plan_path}'")
        sys.exit(1)

    print(f"Parsing {plan_type} plan from {plan_path}...")

    if plan_type == "cloudformation":
        summary, plan_raw = parse_changeset(plan_path)
    else:
        summary = parse_plan(plan_path)
        with open(plan_path, "r", encoding="utf-8-sig") as f:
            plan_raw = json.load(f)

    counts = summary["counts"]
    print(f"Found: {counts['create']} create, {counts['update']} update, {counts['delete']} destroy, {counts['replace']} replace")

    print("Estimating costs...")
    costs = estimate_costs(summary)
    print(f"Estimated monthly change: net ${costs['net']:.2f}")

    print("Scanning for security risks...")
    findings = scan_security(summary, plan_raw)
    high_count = sum(1 for f in findings if "HIGH" in f["severity"])
    print(f"Found {len(findings)} security finding(s), {high_count} HIGH severity")

    github_token = os.environ.get("GITHUB_TOKEN")

    if not github_token:
        print("\n--- PR Comment Preview ---\n")
        print(build_markdown(summary, costs, findings))
        print("\n(Skipping GitHub comment — GITHUB_TOKEN not set)")
    else:
        print("Posting PR comment...")
        post_comment(summary, costs, findings)

    if block_on_high and high_count > 0:
        print(f"\n❌ Blocking: {high_count} HIGH severity security issue(s) found. Fix before merging.")
        sys.exit(1)

    print("\n✅ InfraLens check passed.")


if __name__ == "__main__":
    main()