#!/usr/bin/env python3
"""Extract data from trpg-saikou TypeScript files into Python modules."""

import ast
import json
import re
import sys
from pathlib import Path

# Paths
TRPG_DIR = Path(__file__).parent.parent.parent / "trpg-saikou" / "src" / "apps" / "coc-card" / "constants"
OUTPUT_DIR = Path(__file__).parent.parent / "coc_generator" / "data"

SKILL_TS = TRPG_DIR / "skill.ts"
JOB_TS = TRPG_DIR / "job.ts"


def ts_dict_to_python(text: str) -> str:
    """Convert TypeScript object-literal-ish text to Python dict literal."""
    # Add quotes to unquoted keys (both English and Chinese)
    # Key followed by colon, optional question mark (for TypeScript optional)
    text = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\??:\s*', r'"\1": ', text)
    text = re.sub(r'([\u4e00-\u9fff][\u4e00-\u9fffΩ]*)\??:\s*', r'"\1": ', text)
    # Remove trailing commas before } or ]
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    # Single quotes to double quotes
    text = text.replace("'", '"')
    return text


def extract_array(ts_file: Path, var_name: str) -> list:
    """Extract the exported const array from a TypeScript file."""
    content = ts_file.read_text(encoding="utf-8")
    # Find the array content
    pattern = rf'export const {var_name}:\s*\w+\[\]\s*=\s*\['
    match = re.search(pattern, content)
    if not match:
        raise ValueError(f"Could not find export const {var_name} in {ts_file}")
    
    start = match.end() - 1  # include the '['
    
    # Find matching closing bracket
    depth = 0
    end = start
    for i, ch in enumerate(content[start:], start):
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    
    array_text = content[start:end]
    python_text = ts_dict_to_python(array_text)
    
    try:
        return ast.literal_eval(python_text)
    except SyntaxError as e:
        # Debug: write problematic text to file
        debug_file = Path("/tmp/extract_debug.txt")
        debug_file.write_text(python_text, encoding="utf-8")
        print(f"SyntaxError parsing {var_name}. Debug written to {debug_file}")
        raise


def parse_skills(skills_raw: list) -> tuple[dict, dict]:
    """Parse skills into flat skill map and group definitions."""
    skill_map = {}  # name -> {init, group, aliases}
    group_defs = {}  # group_name -> list of child_skill names
    
    for skill in skills_raw:
        name = skill.get("name", "")
        if not name:
            continue  # skip empty custom skill slot
        
        init = skill.get("init", 0)
        init_placeholder = skill.get("initPlaceholder", "")
        group = skill.get("group")
        
        # Handle dynamic init skills
        dynamic = None
        if init_placeholder == "教育":
            dynamic = "edu"
        elif init_placeholder == "1/2敏捷":
            dynamic = "dex_half"
        
        skill_map[name] = {
            "init": init,
            "dynamic": dynamic,
            "group": None,
            "aliases": [],
        }
        
        if group:
            child_skills = group.get("skills", [])
            child_names = []
            for child in child_skills:
                child_name = child.get("name", "")
                if not child_name:
                    continue
                child_init = child.get("init", init)  # default to parent init
                full_name = f"{name}({child_name})"
                skill_map[full_name] = {
                    "init": child_init,
                    "dynamic": None,
                    "group": name,
                    "aliases": [],
                }
                child_names.append(child_name)
            
            group_defs[name] = child_names
            skill_map[name]["group"] = name  # mark parent as group
    
    return skill_map, group_defs


def extract_job_skills(job_skills_raw: list, skill_map: dict, group_defs: dict) -> set:
    """Extract all valid occupation skill names from a job's skills field."""
    allowed = set()
    
    def process_item(item):
        if isinstance(item, str):
            # Direct skill name
            if item in skill_map:
                allowed.add(item)
            else:
                # Try to match aliases or add as-is (for custom skills)
                allowed.add(item)
        elif isinstance(item, dict):
            # { 格斗: '' } or { 格斗: '斗殴' }
            for key, val in item.items():
                if key in group_defs:
                    # It's a group
                    if val == "":
                        # Allow any child in this group
                        for child in group_defs[key]:
                            allowed.add(f"{key}({child})")
                    else:
                        # Specific child
                        allowed.add(f"{key}({val})")
                else:
                    # Not a known group, add as-is
                    if val:
                        allowed.add(f"{key}({val})")
                    else:
                        allowed.add(key)
        elif isinstance(item, list):
            # Array of options - allow all items in the array
            for sub in item:
                process_item(sub)
    
    for item in job_skills_raw:
        process_item(item)
    
    return allowed


def parse_jobs(jobs_raw: list, skill_map: dict, group_defs: dict) -> dict:
    """Parse jobs into standardized format."""
    jobs = {}
    
    for job in jobs_raw:
        name = job.get("name", "")
        if not name:
            continue
        
        point = job.get("point", [])
        wealth = job.get("wealth", [0, 0])
        skills_raw = job.get("skills", [])
        
        # Extract occupation skill pool
        occupation_skills = sorted(extract_job_skills(skills_raw, skill_map, group_defs))
        
        # Build skill description
        skill_desc = build_skill_description(skills_raw)
        
        # Calculate point formula text
        formula_text = build_formula_text(point)
        
        jobs[name] = {
            "point_formula": point,
            "credit_range": tuple(wealth),
            "occupation_skills": occupation_skills,
            "skill_description": skill_desc,
            "formula_text": formula_text,
        }
    
    return jobs


def build_skill_description(skills_raw: list) -> str:
    """Build a human-readable skill description."""
    parts = []
    for item in skills_raw:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            for k, v in item.items():
                if v:
                    parts.append(f"{k}({v})")
                else:
                    parts.append(f"{k}(任一)")
        elif isinstance(item, list):
            subparts = []
            for sub in item:
                if isinstance(sub, str):
                    subparts.append(sub)
                elif isinstance(sub, dict):
                    for k, v in sub.items():
                        if v:
                            subparts.append(f"{k}({v})")
                        else:
                            subparts.append(f"{k}(任一)")
            parts.append(f"({' 或 '.join(subparts)})")
    return "，".join(parts)


def build_formula_text(point: list) -> str:
    """Build human-readable point formula text."""
    attr_names = {
        "str": "力量", "con": "体质", "dex": "敏捷", "app": "外貌",
        "pow": "意志", "siz": "体型", "edu": "教育", "int": "智力"
    }
    groups = []
    for formula in point:
        terms = []
        for attr, mult in formula:
            terms.append(f"{attr_names.get(attr, attr)}×{mult}")
        if len(terms) == 1:
            groups.append(terms[0])
        else:
            groups.append(f"({' 或 '.join(terms)})")
    return " + ".join(groups)


def generate_skills_py(skill_map: dict, group_defs: dict) -> str:
    """Generate the skills.py module content."""
    lines = [
        '# Auto-generated from trpg-saikou. Do not edit manually.',
        '',
        'SKILL_MAP = {',
    ]
    
    for name, info in sorted(skill_map.items()):
        lines.append(f'    "{name}": {{')
        lines.append(f'        "init": {info["init"]},')
        lines.append(f'        "dynamic": {json.dumps(info["dynamic"])},')
        lines.append(f'        "group": {json.dumps(info["group"])},')
        lines.append(f'        "aliases": {info["aliases"]},')
        lines.append('    },')
    
    lines.append('}')
    lines.append('')
    lines.append('GROUP_DEFS = {')
    for name, children in sorted(group_defs.items()):
        lines.append(f'    "{name}": {json.dumps(children, ensure_ascii=False)},')
    lines.append('}')
    lines.append('')
    
    # Add recommended skills
    lines.append('RECOMMENDED_SKILLS = ["侦查", "聆听", "图书馆使用"]')
    lines.append('')
    
    return "\n".join(lines)


def generate_jobs_py(jobs: dict) -> str:
    """Generate the jobs.py module content."""
    lines = [
        '# Auto-generated from trpg-saikou. Do not edit manually.',
        '',
        'JOBS = {',
    ]
    
    for name, info in sorted(jobs.items()):
        lines.append(f'    "{name}": {{')
        lines.append(f'        "point_formula": {json.dumps(info["point_formula"], ensure_ascii=False)},')
        lines.append(f'        "credit_range": {info["credit_range"]},')
        lines.append(f'        "occupation_skills": {json.dumps(info["occupation_skills"], ensure_ascii=False)},')
        lines.append(f'        "skill_description": {json.dumps(info["skill_description"], ensure_ascii=False)},')
        lines.append(f'        "formula_text": {json.dumps(info["formula_text"], ensure_ascii=False)},')
        lines.append('    },')
    
    lines.append('}')
    lines.append('')
    lines.append('JOB_NAMES = sorted(JOBS.keys())')
    lines.append('')
    
    return "\n".join(lines)


def main():
    print(f"Extracting from {TRPG_DIR}...")
    
    # Extract skills
    print("Parsing skills...")
    skills_raw = extract_array(SKILL_TS, "skills")
    skill_map, group_defs = parse_skills(skills_raw)
    print(f"  Found {len(skill_map)} skills, {len(group_defs)} groups")
    
    # Extract jobs
    print("Parsing jobs...")
    jobs_raw = extract_array(JOB_TS, "jobs")
    jobs = parse_jobs(jobs_raw, skill_map, group_defs)
    print(f"  Found {len(jobs)} jobs")
    
    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    skills_py = OUTPUT_DIR / "skills.py"
    skills_py.write_text(generate_skills_py(skill_map, group_defs), encoding="utf-8")
    print(f"  Written {skills_py}")
    
    jobs_py = OUTPUT_DIR / "jobs.py"
    jobs_py.write_text(generate_jobs_py(jobs), encoding="utf-8")
    print(f"  Written {jobs_py}")
    
    print("Done!")


if __name__ == "__main__":
    main()
