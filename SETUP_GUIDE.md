# Adding InfraLens to Your Terraform Project

---

### Step 1 — Add AWS credentials as GitHub secrets

Go to your repo on GitHub:

**Settings → Secrets and variables → Actions → New repository secret**

Add these three:

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |
| `AWS_DEFAULT_REGION` | e.g. `ap-south-1` or `us-east-1` |

> If your repo already uses these secrets for other workflows, skip this step.

---

### Step 2 — Create the workflow file

In your repo create `.github/workflows/infralens.yml`:

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

---

### Step 3 — Push the workflow file

```bash
git add .
git commit -m "add infralens"
git push origin main
```

---

### Step 4 — Open a PR that changes any `.tf` file

InfraLens triggers automatically on every PR that touches a `.tf` file. It will post a comment showing resource changes, cost estimate, and security findings.

---

## Optional — Block merges on HIGH security findings

Change `block-on-high: false` to `block-on-high: true`. InfraLens will fail the CI check if HIGH severity issues are found, preventing merge until fixed.

## Optional — Add your own security rules

Create `.infralens.yml` in your repo root:

```yaml
rules:
  - resource: aws_s3_bucket
    field: versioning.enabled
    operator: equals
    value: true
    severity: HIGH
    message: "S3 versioning must be enabled per company policy"
```

InfraLens picks it up automatically on the next PR.

---

*[InfraLens](https://github.com/devDhiraj12/infralens) — built by [@devDhiraj12](https://github.com/devDhiraj12)*