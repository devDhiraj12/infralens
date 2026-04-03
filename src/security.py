import json

SEVERITY_HIGH = "🔴 HIGH"
SEVERITY_MEDIUM = "🟡 MEDIUM"
SEVERITY_LOW = "🔵 LOW"


def _check_aws_instance(resource):
    risks = []
    config = resource.get("config_raw", {})

    if not config.get("vpc_security_group_ids") and not config.get("subnet_id"):
        risks.append({
            "severity": SEVERITY_MEDIUM,
            "risk": "No VPC subnet specified — may launch in default VPC",
        })

    # Check for hardcoded secrets in user_data
    user_data = config.get("user_data", "") or ""
    for keyword in ["password=", "secret=", "api_key=", "token=", "aws_secret"]:
        if keyword.lower() in user_data.lower():
            risks.append({
                "severity": SEVERITY_HIGH,
                "risk": f"Possible hardcoded secret in user_data (found '{keyword}')",
            })
            break

    return risks


def _check_security_group(resource):
    risks = []
    config = resource.get("config_raw", {})

    ingress_rules = config.get("ingress", []) or []

    for rule in ingress_rules:
        if not isinstance(rule, dict):
            continue

        cidrs = rule.get("cidr_blocks", []) or []
        ipv6_cidrs = rule.get("ipv6_cidr_blocks", []) or []
        all_open = "0.0.0.0/0" in cidrs or "::/0" in ipv6_cidrs

        from_port = rule.get("from_port", -1)
        to_port = rule.get("to_port", -1)
        protocol = str(rule.get("protocol", ""))

        if all_open and protocol in ("-1", "all", "-1"):
            risks.append({
                "severity": SEVERITY_HIGH,
                "risk": "All ports open to 0.0.0.0/0 — completely unrestricted inbound",
            })
        elif all_open and str(from_port) == "22":
            risks.append({
                "severity": SEVERITY_HIGH,
                "risk": "SSH (port 22) open to 0.0.0.0/0",
            })
        elif all_open and str(from_port) == "3389":
            risks.append({
                "severity": SEVERITY_HIGH,
                "risk": "RDP (port 3389) open to 0.0.0.0/0",
            })
        elif all_open and str(from_port) == "3306":
            risks.append({
                "severity": SEVERITY_HIGH,
                "risk": "MySQL (port 3306) open to 0.0.0.0/0",
            })
        elif all_open and str(from_port) == "5432":
            risks.append({
                "severity": SEVERITY_HIGH,
                "risk": "PostgreSQL (port 5432) open to 0.0.0.0/0",
            })
        elif all_open:
            risks.append({
                "severity": SEVERITY_MEDIUM,
                "risk": f"Port {from_port}-{to_port} open to 0.0.0.0/0",
            })

    return risks


def _check_s3_bucket(resource):
    risks = []
    config = resource.get("config_raw", {})

    acl = config.get("acl", "") or ""
    if acl in ("public-read", "public-read-write", "authenticated-read"):
        risks.append({
            "severity": SEVERITY_HIGH,
            "risk": f"S3 bucket ACL is '{acl}' — bucket is publicly accessible",
        })

    if config.get("force_destroy") is True:
        risks.append({
            "severity": SEVERITY_MEDIUM,
            "risk": "force_destroy = true — all objects deleted if bucket is destroyed",
        })

    versioning = config.get("versioning", {}) or {}
    if isinstance(versioning, list):
        versioning = versioning[0] if versioning else {}
    if not versioning.get("enabled"):
        risks.append({
            "severity": SEVERITY_LOW,
            "risk": "Versioning not enabled — objects cannot be recovered after deletion",
        })

    return risks


def _check_iam_role(resource):
    risks = []
    config = resource.get("config_raw", {})

    risks.append({
        "severity": SEVERITY_MEDIUM,
        "risk": "New IAM role created — review trust policy and attached permissions",
    })

    assume_policy_str = config.get("assume_role_policy", "") or ""
    try:
        policy = json.loads(assume_policy_str) if isinstance(assume_policy_str, str) else assume_policy_str
        for stmt in policy.get("Statement", []):
            principal = stmt.get("Principal", {})
            if principal == "*" or principal == {"AWS": "*"}:
                risks.append({
                    "severity": SEVERITY_HIGH,
                    "risk": "IAM role trust policy allows ANY principal (*) to assume this role",
                })
    except Exception:
        pass

    return risks


def _check_iam_policy(resource):
    risks = []
    config = resource.get("config_raw", {})

    policy_str = config.get("policy", "") or ""
    try:
        policy = json.loads(policy_str) if isinstance(policy_str, str) else policy_str
        for stmt in policy.get("Statement", []):
            effect = stmt.get("Effect", "")
            actions = stmt.get("Action", [])
            resources = stmt.get("Resource", [])

            if isinstance(actions, str):
                actions = [actions]
            if isinstance(resources, str):
                resources = [resources]

            if effect == "Allow" and "*" in actions and "*" in resources:
                risks.append({
                    "severity": SEVERITY_HIGH,
                    "risk": "IAM policy grants Action:* on Resource:* — full admin access",
                })
            elif effect == "Allow" and "*" in actions:
                risks.append({
                    "severity": SEVERITY_HIGH,
                    "risk": "IAM policy grants Action:* — overly permissive actions",
                })
            elif effect == "Allow" and "*" in resources:
                risks.append({
                    "severity": SEVERITY_MEDIUM,
                    "risk": "IAM policy grants access to Resource:* — scope down to specific ARNs",
                })
    except Exception:
        pass

    return risks


def _check_rds(resource):
    risks = []
    config = resource.get("config_raw", {})

    if config.get("publicly_accessible") is True:
        risks.append({
            "severity": SEVERITY_HIGH,
            "risk": "RDS instance is publicly accessible over the internet",
        })

    if not config.get("storage_encrypted"):
        risks.append({
            "severity": SEVERITY_MEDIUM,
            "risk": "RDS storage encryption is not enabled",
        })

    if not config.get("deletion_protection"):
        risks.append({
            "severity": SEVERITY_LOW,
            "risk": "deletion_protection = false — RDS can be accidentally deleted",
        })

    password = config.get("password", "") or ""
    if password and password not in ("", None) and not password.startswith("var.") and not password.startswith("${"):
        risks.append({
            "severity": SEVERITY_HIGH,
            "risk": "RDS password appears hardcoded — use AWS Secrets Manager or SSM",
        })

    return risks


def _check_eks(resource):
    risks = []
    config = resource.get("config_raw", {})

    endpoint_config = config.get("kubernetes_network_config") or config.get("endpoint_public_access")

    # Check if public endpoint access is explicitly enabled
    vpc_config = config.get("vpc_config", {})
    if isinstance(vpc_config, list):
        vpc_config = vpc_config[0] if vpc_config else {}

    if vpc_config.get("endpoint_public_access") is True and not vpc_config.get("endpoint_private_access"):
        risks.append({
            "severity": SEVERITY_MEDIUM,
            "risk": "EKS API server is publicly accessible — consider enabling private endpoint",
        })

    return risks


CHECKERS = {
    "aws_instance": _check_aws_instance,
    "aws_security_group": _check_security_group,
    "aws_security_group_rule": _check_security_group,
    "aws_s3_bucket": _check_s3_bucket,
    "aws_iam_role": _check_iam_role,
    "aws_iam_policy": _check_iam_policy,
    "aws_iam_role_policy": _check_iam_policy,
    "aws_db_instance": _check_rds,
    "aws_eks_cluster": _check_eks,
}


def scan_security(summary: dict, plan_raw: dict) -> list:
    """
    Scan all created/replaced/updated resources for security risks.
    Returns a flat list of findings with address, severity, risk.
    """
    findings = []

    # Build a map of address -> raw config from the full plan JSON
    raw_config_map = {}
    for rc in plan_raw.get("resource_changes", []):
        address = rc.get("address")
        after = rc.get("change", {}).get("after") or {}
        raw_config_map[address] = after

    for action in ["create", "update", "replace"]:
        for resource in summary["changes"][action]:
            rtype = resource.get("type")
            address = resource.get("address")
            checker = CHECKERS.get(rtype)

            if not checker:
                continue

            resource_with_raw = dict(resource)
            resource_with_raw["config_raw"] = raw_config_map.get(address, {})

            risks = checker(resource_with_raw)
            for risk in risks:
                findings.append({
                    "address": address,
                    "type": rtype,
                    "severity": risk["severity"],
                    "risk": risk["risk"],
                    "source": "built-in",
                })

    # Run custom rules from .infralens.yml if present
    custom_findings = _run_custom_rules(summary, raw_config_map)
    findings.extend(custom_findings)

    # Sort by severity: HIGH first, then MEDIUM, then LOW
    severity_order = {SEVERITY_HIGH: 0, SEVERITY_MEDIUM: 1, SEVERITY_LOW: 2}
    findings.sort(key=lambda x: severity_order.get(x["severity"], 3))

    return findings


def _get_nested_value(config: dict, field_path: str):
    """Resolve dot-notation field path like 'versioning.enabled' from config dict."""
    keys = field_path.split(".")
    value = config
    for key in keys:
        if isinstance(value, list):
            value = value[0] if value else {}
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _run_custom_rules(summary: dict, raw_config_map: dict) -> list:
    """Load .infralens.yml from repo root and run custom rules."""
    import os

    rules_file = os.environ.get("INFRALENS_RULES_PATH", ".infralens.yml")

    if not os.path.exists(rules_file):
        return []

    try:
        import yaml
    except ImportError:
        print("  [custom rules] PyYAML not installed — skipping custom rules.")
        return []

    try:
        with open(rules_file, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"  [custom rules] Failed to parse {rules_file}: {e}")
        return []

    rules = config.get("rules", [])
    if not rules:
        return []

    severity_map = {
        "HIGH": SEVERITY_HIGH,
        "MEDIUM": SEVERITY_MEDIUM,
        "LOW": SEVERITY_LOW,
    }

    findings = []

    for action in ["create", "update", "replace"]:
        for resource in summary["changes"][action]:
            rtype = resource.get("type")
            address = resource.get("address")
            raw_config = raw_config_map.get(address, {})

            for rule in rules:
                # Match resource type
                rule_resource = rule.get("resource")
                if rule_resource and rule_resource != rtype:
                    continue

                field = rule.get("field")
                expected = rule.get("value")
                severity_str = str(rule.get("severity", "MEDIUM")).upper()
                severity = severity_map.get(severity_str, SEVERITY_MEDIUM)
                message = rule.get("message", f"Custom rule violation on field '{field}'")

                if field is None:
                    # Rule without a field check — always fires for matching resource type
                    findings.append({
                        "address": address,
                        "type": rtype,
                        "severity": severity,
                        "risk": f"[Custom] {message}",
                        "source": "custom",
                    })
                    continue

                actual = _get_nested_value(raw_config, field)

                # Evaluate the rule
                violated = False
                operator = rule.get("operator", "equals")

                if operator == "equals":
                    violated = actual != expected
                elif operator == "not_equals":
                    violated = actual == expected
                elif operator == "contains":
                    violated = expected not in (actual or "")
                elif operator == "exists":
                    violated = actual is None
                elif operator == "not_exists":
                    violated = actual is not None

                if violated:
                    findings.append({
                        "address": address,
                        "type": rtype,
                        "severity": severity,
                        "risk": f"[Custom] {message}",
                        "source": "custom",
                    })

    return findings