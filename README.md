# 🔍 InfraLens

**Know exactly what your Terraform or CloudFormation PR will do — before it merges.**

InfraLens is a GitHub Action that analyzes your IaC plan and posts a structured impact summary directly on the pull request — resource changes, live AWS cost estimates, and security risk detection. All in one PR comment, zero setup beyond a workflow file.

→ [Step by step setup guide](./SETUP_GUIDE.md)

---

## Quick Start

### Step 1 — Add the workflow to your repo

Create `.github/workflows/infralens.yml` in your Terraform repo:

```yaml
name: InfraLens PR Check

on:
  pull_request:
    paths:
      - '**.tf'

jobs:
  infralens:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write

    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3

      - name: Terraform Init
        run: terraform init

      - name: Terraform Plan
        run: |
          terraform plan -out=plan.bin
          terraform show -json plan.bin > plan.json
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: ${{ secrets.AWS_DEFAULT_REGION }}

      - name: Run InfraLens
        uses: devDhiraj12/infralens@v2
        with:
          plan-json-path: plan.json
          github-token: ${{ secrets.GITHUB_TOKEN }}
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_DEFAULT_REGION }}
          block-on-high: false
```

### Step 2 — Add AWS secrets to your repo

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |
| `AWS_DEFAULT_REGION` | e.g. `ap-south-1` or `us-east-1` |

### Step 3 — Open a PR that changes any `.tf` file

InfraLens runs automatically and posts the comment. That's it.

---

## What It Looks Like on a Real PR

![InfraLens in action — real PR comment on a Terraform project](./infralens-screenshot.png)

---

## What InfraLens Checks

### 📋 Resource Diff
Every resource being created, updated, destroyed, or replaced — shown in a clean table. Warns you when a PR destroys or replaces resources.

### 💰 Live Cost Estimation
Uses the **AWS Pricing API** to fetch real-time prices on every run. Region-aware, no hardcoded tables. Falls back to a built-in price table automatically if AWS credentials are unavailable.

| Resource | Pricing |
|----------|---------|
| `aws_instance` | EC2 Pricing API — any instance type |
| `aws_db_instance` | RDS Pricing API — engine aware, includes storage |
| `aws_nat_gateway` | EC2 Pricing API |
| `aws_lb` / `aws_alb` | ELB Pricing API |
| `aws_elasticache_cluster` | ElastiCache Pricing API |
| `aws_eks_cluster` | Fixed $0.10/hr control plane |
| `aws_lambda_function` | Usage-based note |
| `aws_s3_bucket` | Usage-based note |
| `aws_ecs_service` | Usage-based note |

### 🔒 Security Risk Detection

| Severity | What Gets Flagged |
|----------|-------------------|
| 🔴 HIGH | SSH/RDP/DB ports open to `0.0.0.0/0`, all ports open, RDS publicly accessible, hardcoded passwords, public S3 ACL, IAM `Action:*` or `Resource:*`, IAM role `Principal:*`, hardcoded secrets in `user_data` |
| 🟡 MEDIUM | RDS storage not encrypted, EKS public API endpoint, new IAM role, S3 `force_destroy`, EC2 without VPC |
| 🔵 LOW | RDS without `deletion_protection`, S3 versioning not enabled |

### 🚫 Fail CI on HIGH Severity
InfraLens fails the GitHub Actions check if HIGH severity findings exist — blocking the merge until fixed. Disable it with `block-on-high: false`.

### 📝 Custom Security Rules
Define your own policies in `.infralens.yml` in your repo root:

```yaml
rules:
  - resource: aws_s3_bucket
    field: versioning.enabled
    operator: equals
    value: true
    severity: HIGH
    message: "S3 versioning must be enabled per company policy"

  - resource: aws_db_instance
    field: multi_az
    operator: equals
    value: true
    severity: MEDIUM
    message: "RDS Multi-AZ must be enabled for production databases"

  - resource: aws_instance
    field: instance_type
    operator: not_equals
    value: t2.micro
    severity: LOW
    message: "t2.micro is previous gen — use t3.micro instead"
```

Supported operators: `equals`, `not_equals`, `contains`, `exists`, `not_exists`

Custom findings are tagged `[Custom]` in the PR comment.

### ☁️ CloudFormation Support
Works with AWS CloudFormation changesets too — not just Terraform.

```yaml
      - name: Create Changeset
        run: |
          aws cloudformation create-change-set \
            --stack-name my-stack \
            --change-set-name pr-${{ github.event.pull_request.number }} \
            --template-body file://template.yml
          aws cloudformation describe-change-set \
            --stack-name my-stack \
            --change-set-name pr-${{ github.event.pull_request.number }} > changeset.json

      - name: Run InfraLens
        uses: devDhiraj12/infralens@v2
        with:
          plan-json-path: changeset.json
          plan-type: cloudformation
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

## All Action Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `plan-json-path` | Yes | `plan.json` | Path to Terraform plan JSON or CloudFormation changeset JSON |
| `github-token` | Yes | — | GitHub token for posting PR comments — use `${{ secrets.GITHUB_TOKEN }}` |
| `plan-type` | No | `terraform` | `terraform` or `cloudformation` |
| `block-on-high` | No | `true` | Fail CI if HIGH severity findings exist. Set `false` to warn only |
| `aws-access-key-id` | No | — | AWS credentials for live cost estimation |
| `aws-secret-access-key` | No | — | AWS credentials for live cost estimation |
| `aws-region` | No | `us-east-1` | AWS region for cost estimation — should match your deployment region |

---

## Running Locally

Test InfraLens locally before pushing to GitHub. It prints the full PR comment as a terminal preview without posting anything to GitHub.

**Generate a Terraform plan JSON:**

```bash
# Linux/Mac
terraform init
terraform plan -out=plan.bin
terraform show -json plan.bin > plan.json

# Windows PowerShell
terraform plan -out="plan.bin"
terraform show -json plan.bin | Out-File -Encoding utf8 plan.json
```

**Install dependencies:**

```bash
pip install requests boto3 pyyaml
```

**Run InfraLens:**

```bash
# Linux/Mac
export PLAN_JSON_PATH=plan.json
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-east-1
python src/main.py
```

```powershell
# Windows PowerShell
$env:PLAN_JSON_PATH="path\to\plan.json"
$env:AWS_ACCESS_KEY_ID="your-key"
$env:AWS_SECRET_ACCESS_KEY="your-secret"
$env:AWS_DEFAULT_REGION="us-east-1"
python src/main.py
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PLAN_JSON_PATH` | Yes | `plan.json` | Path to plan JSON file |
| `PLAN_TYPE` | No | `terraform` | `terraform` or `cloudformation` |
| `BLOCK_ON_HIGH` | No | `true` | Set `false` to skip CI failure on HIGH findings |
| `INFRALENS_RULES_PATH` | No | `.infralens.yml` | Path to custom rules file — skipped silently if not found |
| `AWS_ACCESS_KEY_ID` | No | — | For live pricing. Falls back to built-in table if not set |
| `AWS_SECRET_ACCESS_KEY` | No | — | AWS credentials |
| `AWS_DEFAULT_REGION` | No | `us-east-1` | Region for cost estimation |
| `GITHUB_TOKEN` | CI only | — | Auto-provided by GitHub Actions |
| `GITHUB_REPOSITORY` | CI only | — | Auto-provided by GitHub Actions |
| `GITHUB_PR_NUMBER` | CI only | — | Auto-provided by GitHub Actions |

**Quick local test scenarios:**

```powershell
# Basic test — no AWS credentials needed
$env:PLAN_JSON_PATH="plan.json"
$env:BLOCK_ON_HIGH="false"
python src/main.py

# With custom rules
$env:PLAN_JSON_PATH="plan.json"
$env:INFRALENS_RULES_PATH=".infralens.yml"
python src/main.py

# CloudFormation changeset
$env:PLAN_JSON_PATH="changeset.json"
$env:PLAN_TYPE="cloudformation"
python src/main.py
```

---

## Project Structure

```
infralens/
├── action.yml          # GitHub Action definition and inputs
├── Dockerfile          # Python container build
├── requirements.txt    # requests, boto3, pyyaml
├── README.md
└── src/
    ├── main.py         # Entry point
    ├── parser.py       # Terraform plan JSON parser
    ├── cfn_parser.py   # CloudFormation changeset parser
    ├── cost.py         # AWS Pricing API cost estimation
    ├── security.py     # Built-in + custom security rule engine
    └── comment.py      # GitHub PR comment builder and poster
```

---

## Contributing

Good first PRs:

- Add support for new AWS resource types in `cost.py`
- Add new built-in security checks in `security.py`
- Add Azure or GCP resource support
- Add Pulumi or CDK plan support
- Share `.infralens.yml` rule packs in the Discussions tab

Open an issue before starting large changes.

---

## Changelog

**v2**
- Fail CI on HIGH severity findings (`block-on-high: false` to opt out)
- Custom security rules via `.infralens.yml`
- CloudFormation changeset support

**v1**
- Terraform plan parsing
- Live AWS cost estimation via Pricing API
- Built-in security scanning (IAM, SG, S3, RDS, EKS)
- GitHub PR comment with auto-update on each push

---

## License

MIT

---

*Built by [@devDhiraj12](https://github.com/devDhiraj12)*