# 🔍 InfraLens

**Know exactly what your Terraform PR will do before it merges.**

InfraLens is a GitHub Action that analyzes your Terraform plan and posts a structured impact summary directly on your pull request — covering resource changes, estimated AWS costs, and security risks. No account required, no dashboard, no setup beyond 5 lines of YAML.

---

## What it does

Every time a PR touches a `.tf` file, InfraLens automatically comments:

- **Resource diff** — what's being created, updated, destroyed, or replaced
- **Cost estimation** — monthly cost delta using live AWS Pricing API
- **Security scan** — flags IAM misconfigs, open ports, public S3 buckets, hardcoded secrets, and more
- **Smart updates** — edits the same comment on every new push instead of spamming the PR

---

## Example PR Comment

```
🔍 InfraLens — Terraform Impact Summary

| Action  | Count |
|---------|-------|
| 🟢 Create  | 4 |
| 🟡 Update  | 1 |
| 🔴 Destroy | 1 |
| 🔁 Replace | 0 |

💰 Estimated Cost Impact

| Resource                  | Detail                        | Monthly Cost |
|---------------------------|-------------------------------|-------------|
| aws_instance.web_server   | t3.medium                     | +$30.37     |
| aws_db_instance.database  | db.t3.micro (mysql), 20GB     | +$14.71     |
| aws_nat_gateway.nat       | NAT Gateway                   | +$32.85     |
| aws_instance.old_server   | t2.micro                      | -$8.47      |

Estimated monthly change: +$69.46/month

🔒 Security Risk Detection

🚨 3 HIGH severity issue(s) found. Do not merge without review.

| Severity   | Resource                    | Risk                                          |
|------------|-----------------------------|-----------------------------------------------|
| 🔴 HIGH    | aws_security_group.web_sg   | SSH (port 22) open to 0.0.0.0/0              |
| 🔴 HIGH    | aws_db_instance.database    | RDS instance is publicly accessible           |
| 🔴 HIGH    | aws_s3_bucket.assets        | S3 bucket ACL is 'public-read'               |
| 🟡 MEDIUM  | aws_db_instance.database    | RDS storage encryption is not enabled         |
| 🔵 LOW     | aws_s3_bucket.assets        | Versioning not enabled                        |
```

---

## Quick Start

### 1. Add the workflow to your Terraform repo

Create `.github/workflows/infralens.yml`:

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
        uses: devDhiraj12/infralens@v1
        with:
          plan-json-path: plan.json
          github-token: ${{ secrets.GITHUB_TOKEN }}
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: ${{ secrets.AWS_DEFAULT_REGION }}
```

### 2. Add GitHub secrets

In your repo go to **Settings → Secrets → Actions** and add:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION` (e.g. `us-east-1`)

### 3. Open a PR that changes any `.tf` file

InfraLens runs automatically and posts the comment.

---

## Cost Estimation

InfraLens uses the **AWS Pricing API** to fetch live, real-time prices — no hardcoded tables. Pricing is region-aware and fetched fresh on every run.

Supported resources:

| Terraform Resource           | Pricing Method              |
|------------------------------|-----------------------------|
| `aws_instance`               | EC2 Pricing API (per instance type) |
| `aws_db_instance`            | RDS Pricing API (engine + storage)  |
| `aws_nat_gateway`            | EC2 Pricing API             |
| `aws_lb` / `aws_alb`         | ELB Pricing API             |
| `aws_elasticache_cluster`    | ElastiCache Pricing API     |
| `aws_eks_cluster`            | Fixed $0.10/hr (control plane) |
| `aws_lambda_function`        | Usage-based note            |
| `aws_s3_bucket`              | Usage-based note            |

If AWS credentials are unavailable, InfraLens falls back to a built-in pricing table automatically.

---

## Security Scanning

InfraLens scans every created, updated, or replaced resource and flags risks across three severity levels.

**HIGH** — must review before merging:
- Security group with SSH/RDP/DB port open to `0.0.0.0/0`
- RDS instance with `publicly_accessible = true`
- RDS with hardcoded password — use AWS Secrets Manager
- S3 bucket with public ACL
- IAM policy with `Action: *` or `Resource: *`
- IAM role with `Principal: *` in trust policy
- Hardcoded secrets in EC2 `user_data`

**MEDIUM** — should review:
- RDS storage encryption not enabled
- EKS API server publicly accessible
- New IAM role created — review permissions
- S3 `force_destroy = true`
- EC2 launched without explicit VPC

**LOW** — good practice:
- RDS without `deletion_protection`
- S3 versioning not enabled

---

## Running Locally

Generate a Terraform plan JSON from any project:

```bash
terraform init
terraform plan -out=plan.bin
terraform show -json plan.bin > plan.json
```

Then run InfraLens:

```bash
pip install requests boto3
export PLAN_JSON_PATH=plan.json
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-east-1
python src/main.py
```

You'll see the full PR comment preview in your terminal.

---

## Project Structure

```
infralens/
├── action.yml          # GitHub Action definition
├── Dockerfile          # Container build
├── requirements.txt    # Python dependencies
├── README.md
└── src/
    ├── main.py         # Entry point
    ├── parser.py       # Terraform plan JSON parser
    ├── cost.py         # AWS Pricing API cost estimation
    ├── security.py     # Security risk detection
    └── comment.py      # GitHub PR comment builder and poster
```

---

## Contributing

InfraLens is built to be extended by the community. Good first contributions:

- Add support for new AWS resource types in `cost.py`
- Add new security checks in `security.py`
- Add Azure or GCP resource support
- Add Slack notification support
- Add CloudFormation plan support

Open an issue or PR — all contributions welcome.

---

## License

MIT — free to use, modify, and distribute.

---

*Built by [@devDhiraj12](https://github.com/devDhiraj12)*