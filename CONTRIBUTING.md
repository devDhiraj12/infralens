# Contributing to InfraLens

Thanks for your interest in contributing. InfraLens is built to grow with community contributions — new resource types, security checks, and IaC tool support are all welcome.

---

## What You Can Contribute

### Easy — no architecture knowledge needed
- Add pricing support for a new AWS resource type in `src/cost.py`
- Add a new security check in `src/security.py`
- Fix a bug or improve an error message
- Improve documentation or add examples

### Medium
- Add support for a new IaC tool (Pulumi, CDK) — follow `src/cfn_parser.py` as a reference
- Add support for Azure or GCP resources
- Add new operators to the custom rules engine in `src/security.py`

### Large — open an issue first
- Architectural changes to how plan data flows between modules
- New output formats (e.g. SARIF for GitHub Security tab)
- New CI integrations (GitLab CI, Bitbucket Pipelines)

---

## How to Contribute

### 1. Fork and clone

```bash
git clone https://github.com/your-username/infralens.git
cd infralens
```

### 2. Install dependencies

```bash
pip install requests boto3 pyyaml
```

### 3. Make your changes

The codebase is intentionally simple:

```
src/
├── main.py       # Entry point — don't change unless necessary
├── parser.py     # Terraform plan JSON parser
├── cfn_parser.py # CloudFormation changeset parser
├── cost.py       # AWS Pricing API — add new resource types here
├── security.py   # Security checks — add new checks here
└── comment.py    # PR comment builder — add new sections here
```

**Adding a new resource to cost.py:**

Add a new `elif` block in the `estimate_resource_cost` function:

```python
elif rtype == "aws_elasticache_replication_group":
    node_type = config.get("node_type") or "cache.t3.micro"
    hourly = _fetch_elasticache_price(node_type, region)
    if hourly:
        result["monthly_cost"] = round(hourly * HOURS_PER_MONTH, 2)
        result["detail"] = node_type
        result["source"] = "AWS Pricing API"
    else:
        result["note"] = f"No price found for {node_type}"
```

**Adding a new security check in security.py:**

Add a new checker function and register it in the `CHECKERS` dict:

```python
def _check_my_resource(resource):
    risks = []
    config = resource.get("config_raw", {})
    if config.get("some_field") is True:
        risks.append({
            "severity": SEVERITY_HIGH,
            "risk": "Description of the risk",
        })
    return risks

CHECKERS = {
    ...
    "aws_my_resource": _check_my_resource,
}
```

### 4. Test your changes locally

```bash
export PLAN_JSON_PATH=terraformtest/aws_plan.json
export BLOCK_ON_HIGH=false
python src/main.py
```

Make sure your change shows up correctly in the output before submitting.

### 5. Open a pull request

- Keep PRs focused — one feature or fix per PR
- Write a clear PR description explaining what you changed and why
- If you're adding a new resource type, mention which AWS service it belongs to

---

## Reporting Bugs

Open an issue and include:
- What you expected to happen
- What actually happened
- Your Terraform plan JSON (remove sensitive values)
- Any error output from the Action logs

---

## Sharing Rule Packs

If you've built a useful `.infralens.yml` for your team, share it in the **Discussions** tab under **Rule Packs**. Others can copy and adapt it.

---

## Code Style

- Python only — no new dependencies without discussion
- Keep functions small and single-purpose
- No hardcoded prices — always use the AWS Pricing API with fallback
- Every new security check must have a severity level and a clear human-readable message

---

*Questions? Open a GitHub Discussion or drop a comment on the issue.*