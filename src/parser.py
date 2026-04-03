import json


ACTION_LABELS = {
    "create": "🟢 Create",
    "update": "🟡 Update",
    "delete": "🔴 Destroy",
    "replace": "🔁 Replace",
    "no-op": "⬜ No Change",
    "read": "🔵 Read",
}


def parse_plan(plan_json_path: str) -> dict:
    with open(plan_json_path, "r", encoding="utf-8-sig") as f:
        plan = json.load(f)

    changes = {
        "create": [],
        "update": [],
        "delete": [],
        "replace": [],
        "no-op": [],
        "read": [],
    }

    resource_changes = plan.get("resource_changes", [])

    for resource in resource_changes:
        actions = resource.get("change", {}).get("actions", [])

        if actions == ["no-op"] or actions == ["read"]:
            action_key = actions[0]
        elif "delete" in actions and "create" in actions:
            action_key = "replace"
        elif "create" in actions:
            action_key = "create"
        elif "update" in actions:
            action_key = "update"
        elif "delete" in actions:
            action_key = "delete"
        else:
            action_key = "no-op"

        after = resource.get("change", {}).get("after") or {}
        before = resource.get("change", {}).get("before") or {}
        config_source = after if after else before

        entry = {
            "name": resource.get("name"),
            "type": resource.get("type"),
            "module": resource.get("module_address", None),
            "address": resource.get("address"),
            "config": {
                "instance_type": config_source.get("instance_type"),
                "instance_class": config_source.get("instance_class"),
                "runtime": config_source.get("runtime"),
                "allocated_storage": config_source.get("allocated_storage"),
                "region": config_source.get("region", "us-east-1"),
            }
        }

        changes[action_key].append(entry)

    summary = {
        "total": len(resource_changes),
        "changes": changes,
        "counts": {k: len(v) for k, v in changes.items()},
    }

    return summary