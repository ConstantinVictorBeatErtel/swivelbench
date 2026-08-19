"""Command-line entry point for the content pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .education import generate_education
from .banking import generate_banking, validate_banking
from .reports import write_report_specs
from .render import render_assessment_pdf, render_education_world, render_report_templates
from .research import write_research_artifacts
from .release import build_release_manifest
from .sec import acquire_all, package_artifact, restore_artifact, verify_offline
from .validators import validate_education, validate_reports, validate_sec


def _json_print(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contentctl")
    sub = parser.add_subparsers(dest="command", required=True)

    reports = sub.add_parser("reports")
    reports.add_argument("action", choices=("generate", "render", "validate"))
    reports.add_argument("--root", type=Path, default=Path("data/banking/reports/specs"))

    education = sub.add_parser("education")
    education.add_argument("action", choices=("generate", "render", "validate"))
    education.add_argument("--root", type=Path, default=Path("data/education"))

    sec = sub.add_parser("sec")
    sec.add_argument("action", choices=("fetch", "verify", "restore", "package"))
    sec.add_argument("--root", type=Path, default=Path("data/banking/sec"))
    sec.add_argument("--artifact", type=Path)
    sec.add_argument("--cutoff", default="2026-08-18")
    sec.add_argument("--ticker", action="append", dest="tickers")
    sec.add_argument("--user-agent")
    sec.add_argument("--offline", action="store_true", help="verify without network (explicit documentation flag)")

    research = sub.add_parser("research")
    research.add_argument("action", choices=("generate",))
    research.add_argument("--root", type=Path, default=Path("data/sources"))
    research.add_argument("--sec-root", type=Path, default=Path("data/banking/sec"))

    banking = sub.add_parser("banking")
    banking.add_argument("action", choices=("generate", "validate"))
    banking.add_argument("--root", type=Path, default=Path("data/banking/content"))
    banking.add_argument("--sec-root", type=Path, default=Path("data/banking/sec"))

    release = sub.add_parser("release")
    release.add_argument("action", choices=("manifest",))
    release.add_argument("--root", type=Path, default=Path("data"))

    validate = sub.add_parser("validate")
    validate.add_argument("target", choices=("reports", "education", "sec"))
    validate.add_argument("--root", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "reports":
        if args.action == "generate":
            value = write_report_specs(args.root)
        elif args.action == "render":
            value = render_report_templates(args.root.parent / "templates")
        else:
            value = validate_reports(args.root)
        _json_print(value)
        return 0 if args.action in {"generate", "render"} or value["ok"] else 1
    if args.command == "education":
        if args.action == "generate":
            value = generate_education(args.root)
        elif args.action == "render":
            rendered_root = args.root / "rendered"
            count = 0
            for world_path in sorted((args.root / "submissions").glob("*.json")):
                count += render_education_world(world_path, rendered_root / world_path.stem)["submissions"]
            assessment_render_root = args.root / "assessment-sheets"
            assessment_count = 0
            for assessment_path in sorted((args.root / "assessments").glob("*.json")):
                render_assessment_pdf(assessment_path, assessment_render_root)
                assessment_count += 1
            value = {"submissions": count, "assessment_sheets": assessment_count,
                     "rendered_root": rendered_root, "assessment_root": assessment_render_root}
        else:
            value = validate_education(args.root)
        _json_print(value)
        return 0 if args.action in {"generate", "render"} or value["ok"] else 1
    if args.command == "sec":
        if args.action == "fetch":
            value = acquire_all(root=args.root, cutoff=args.cutoff,
                                tickers=args.tickers, user_agent=args.user_agent)
        elif args.action == "restore":
            if args.artifact is None:
                sec.error("sec restore requires --artifact")
            value = restore_artifact(args.artifact, args.root)
        elif args.action == "package":
            if args.artifact is None:
                sec.error("sec package requires --artifact")
            value = package_artifact(args.root, args.artifact)
        else:
            value = verify_offline(args.root)
        _json_print(value)
        return 0 if args.action in {"fetch", "restore", "package"} or value["ok"] else 1
    if args.command == "research":
        _json_print(write_research_artifacts(args.root, sec_root=args.sec_root))
        return 0
    if args.command == "banking":
        value = (generate_banking(args.root, sec_root=args.sec_root)
                 if args.action == "generate" else validate_banking(args.root))
        _json_print(value)
        return 0 if args.action == "generate" or value["ok"] else 1
    if args.command == "release":
        value = build_release_manifest(args.root)
        _json_print(value)
        return 0 if value["ready"] else 1
    value = {"reports": validate_reports(args.root),
             "education": validate_education(args.root),
             "sec": validate_sec(args.root)}[args.target]
    _json_print(value)
    return 0 if value["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
