import os
import requests


GITHUB_API = "https://api.github.com"
COMMENT_MARKER = "<!-- infraguard-comment -->"


def build_markdown(summary: dict, costs: dict = None, findings: list = None) -> str:
    counts = summary["counts"]
    changes = summary["changes"]

    lines = [
        COMMENT_MARKER,
        "## 🔍 InfraLens — Terraform Impact Summary",
        "",
        "| Action | Count |",
        "|--------|-------|",
        f"| 🟢 Create  | {counts['create']} |",
        f"| 🟡 Update  | {counts['update']} |",
        f"| 🔴 Destroy | {counts['delete']} |",
        f"| 🔁 Replace | {counts['replace']} |",
        "",
    ]

    for action_key, label in [
        ("create", "🟢 Resources to Create"),
        ("update", "🟡 Resources to Update"),
        ("delete", "🔴 Resources to Destroy"),
        ("replace", "🔁 Resources to Replace"),
    ]:
        resources = changes[action_key]
        if not resources:
            continue

        lines.append(f"### {label}")
        lines.append("")
        lines.append("| Resource Address | Type |")
        lines.append("|-----------------|------|")

        for r in resources:
            lines.append(f"| `{r['address']}` | `{r['type']}` |")

        lines.append("")

    if costs:
        lines.append("### 💰 Estimated Cost Impact")
        lines.append("")
        lines.append("| Resource | Detail | Monthly Cost |")
        lines.append("|----------|--------|-------------|")

        for item in costs["added"]:
            if item["monthly_cost"] is not None:
                cost_str = f"+${item['monthly_cost']:.2f}"
            else:
                cost_str = f"~{item.get('note', 'unknown')}"
            detail = item.get("detail", item["type"])
            lines.append(f"| `{item['address']}` | {detail} | {cost_str} |")

        for item in costs["destroyed"]:
            if item["monthly_cost"] is not None:
                cost_str = f"-${item['monthly_cost']:.2f}"
            else:
                cost_str = f"~{item.get('note', 'unknown')}"
            detail = item.get("detail", item["type"])
            lines.append(f"| `{item['address']}` | {detail} | {cost_str} |")

        lines.append("")

        net = costs["net"]
        net_str = f"+${net:.2f}" if net >= 0 else f"-${abs(net):.2f}"
        lines.append(f"**Estimated monthly change: {net_str}/month**")

        if costs["has_unknown"]:
            lines.append("")
            lines.append("> ℹ️ Some resources could not be estimated — costs depend on usage.")

        lines.append("")

    if findings:
        high = [f for f in findings if "HIGH" in f["severity"]]
        lines.append("### 🔒 Security Risk Detection")
        lines.append("")
        if high:
            lines.append(f"> 🚨 **{len(high)} HIGH severity issue(s) found. Do not merge without review.**")
            lines.append("")
        lines.append("| Severity | Resource | Risk |")
        lines.append("|----------|----------|------|")
        for f in findings:
            lines.append(f"| {f['severity']} | `{f['address']}` | {f['risk']} |")
        lines.append("")

    if counts["delete"] > 0:
        lines.append("> ⚠️ **This PR destroys resources. Review carefully before merging.**")
        lines.append("")

    if counts["replace"] > 0:
        lines.append("> ⚠️ **Some resources will be destroyed and recreated. This may cause downtime.**")
        lines.append("")

    lines.append("---")
    lines.append("*Posted by [InfraLens](https://github.com/your-org/infralens)*")

    return "\n".join(lines)


def post_comment(summary: dict, costs: dict = None, findings: list = None):
    token = os.environ["GITHUB_TOKEN"]
    repository = os.environ["GITHUB_REPOSITORY"]
    pr_number = os.environ["GITHUB_PR_NUMBER"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Check if we already posted a comment and update it instead of spamming
    comments_url = f"{GITHUB_API}/repos/{repository}/issues/{pr_number}/comments"
    existing = requests.get(comments_url, headers=headers)
    existing.raise_for_status()

    existing_id = None
    for comment in existing.json():
        if COMMENT_MARKER in comment.get("body", ""):
            existing_id = comment["id"]
            break

    body = build_markdown(summary, costs, findings)

    if existing_id:
        url = f"{GITHUB_API}/repos/{repository}/issues/comments/{existing_id}"
        response = requests.patch(url, headers=headers, json={"body": body})
    else:
        response = requests.post(comments_url, headers=headers, json={"body": body})

    response.raise_for_status()
    print("Comment posted successfully.")