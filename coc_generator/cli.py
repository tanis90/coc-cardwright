"""CLI entry point for COC character card generator."""

import argparse
import json
import sys
from pathlib import Path

from .engine import format_validation_result, validate
from .data.jobs import JOBS, JOB_NAMES


def cmd_verify(args):
    """Verify a character JSON file."""
    path = Path(args.input)
    if not path.exists():
        print(json.dumps({"valid": False, "errors": [{"code": "FILE_NOT_FOUND", "message": f"文件不存在: {path}"}]}), ensure_ascii=False)
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    result = validate(data)
    output = format_validation_result(result)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0 if result.valid else 1)


def cmd_render(args):
    """Render a character JSON file to HTML."""
    from .renderer import render

    path = Path(args.input)
    if not path.exists():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    result = validate(data)
    if not result.valid:
        print("校验未通过，无法生成HTML。错误如下:", file=sys.stderr)
        print(json.dumps(format_validation_result(result), ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else path.with_suffix(".html")
    html = render(data, style=args.style)
    output_path.write_text(html, encoding="utf-8")
    print(f"角色卡已生成: {output_path.absolute()}")


def cmd_jobs(args):
    """List all available jobs."""
    print(json.dumps(JOB_NAMES, ensure_ascii=False, indent=2))


def cmd_job(args):
    """Show details of a specific job."""
    name = args.name
    job = JOBS.get(name)
    if not job:
        print(f"错误: 未找到职业 '{name}'", file=sys.stderr)
        print(f"提示: 使用 'coc jobs' 查看所有职业", file=sys.stderr)
        sys.exit(1)

    output = {
        "name": name,
        "formula_text": job["formula_text"],
        "credit_range": f"{job['credit_range'][0]}~{job['credit_range'][1]}",
        "occupation_skills": job["occupation_skills"],
        "skill_description": job["skill_description"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        prog="coc",
        description="COC 7th Edition 480-point buy character card generator",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # verify
    verify_parser = subparsers.add_parser("verify", help="校验角色卡JSON")
    verify_parser.add_argument("input", help="输入JSON文件路径")
    verify_parser.set_defaults(func=cmd_verify)

    # render
    render_parser = subparsers.add_parser("render", help="生成HTML角色卡")
    render_parser.add_argument("input", help="输入JSON文件路径")
    render_parser.add_argument("-o", "--output", help="输出HTML文件路径（默认同名.html）")
    render_parser.add_argument(
        "--style",
        choices=("color", "mono"),
        default="color",
        help="打印样式：color=彩色，mono=黑白",
    )
    render_parser.set_defaults(func=cmd_render)

    # jobs
    jobs_parser = subparsers.add_parser("jobs", help="列出所有职业")
    jobs_parser.set_defaults(func=cmd_jobs)

    # job
    job_parser = subparsers.add_parser("job", help="查看职业详情")
    job_parser.add_argument("name", help="职业名称")
    job_parser.set_defaults(func=cmd_job)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
