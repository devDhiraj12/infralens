# InfraLens

A GitHub Action that analyzes your Terraform plan and posts an infrastructure impact summary directly on the PR — before anything gets merged.

## What it does

- Shows exactly which resources will be created, updated, destroyed, or replaced
- Warns you when a PR destroys or replaces resources
- Updates the comment on each new push instead of spamming the PR
- Zero setup — no account, no API key, no dashboard

## Usage

Add this to your GitHub Actions workflow:

```yaml
name: Terraform PR Check

on:
  pull_request:
    paths:
      - '**.tf'

jobs:
  infralens:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3

      - name: Terraform Init
        run: terraform init

      - name: Terraform Plan
        run: terraform plan -out=plan.bin && terraform show -json plan.bin > plan.json
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}

      - name: InfraLens
        uses: your-org/infralens@v1
        with:
          plan-json-path: plan.json
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Roadmap

- [ ] AWS cost estimation (Phase 2)
- [ ] IAM and security group risk detection (Phase 3)
- [ ] CloudFormation support
- [ ] Slack notification support

## Contributing

PRs welcome. See `src/parser.py` to add support for new resource types or IaC tools.
