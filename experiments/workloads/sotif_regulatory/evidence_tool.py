from __future__ import annotations

import argparse
import json

from experiments.workloads.sotif_regulatory.dataset import get_item


def list_evidence(dataset: str, item_id: str) -> dict:
    item = get_item(dataset, item_id)
    return {
        "evidence": [
            {
                "evidence_id": evidence["evidence_id"],
                "document_id": evidence["document_id"],
                "version": evidence["version"],
                "locator": evidence["locator"],
                "title": evidence.get("title", ""),
                "redistributable": evidence["redistributable"],
                "source_uri": evidence.get("source_uri"),
            }
            for evidence in item["evidence_catalog"]
        ]
    }


def read_evidence(dataset: str, item_id: str, evidence_id: str) -> dict:
    item = get_item(dataset, item_id)
    for evidence in item["evidence_catalog"]:
        if evidence["evidence_id"] != evidence_id:
            continue
        if "text" not in evidence:
            return {
                "status": "external_source_required",
                "evidence_id": evidence_id,
                "document_id": evidence["document_id"],
                "version": evidence["version"],
                "locator": evidence["locator"],
                "source_uri": evidence.get("source_uri"),
            }
        return {
            "status": "ready",
            **evidence,
        }
    return {"status": "not_found", "evidence_id": evidence_id}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--item", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    read = sub.add_parser("read")
    read.add_argument("--evidence", required=True)
    args = parser.parse_args()

    if args.command == "list":
        value = list_evidence(args.dataset, args.item)
    else:
        value = read_evidence(args.dataset, args.item, args.evidence)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
