"""HTML renderer for character cards."""

from pathlib import Path

from jinja2 import Template

from .engine import calc_derived, calc_interest_points, calc_pro_points, get_skill_init
from .schema import ATTR_KEYS, ATTR_NAMES
from .data.skills import SKILL_MAP
from .data.jobs import JOBS


# ---------------------------------------------------------------------------
# Skill grouping - matches trpg-saikou's 10 groups
# ---------------------------------------------------------------------------

# Left column groups (indices 0-5)
LEFT_GROUP_NAMES = ["特殊", "探索", "社交", "战斗", "医疗", "运动"]
# Right column groups (indices 6-9)
RIGHT_GROUP_NAMES = ["知识", "技术", "操纵", "其它"]

_GROUP_TONES = {
    "特殊": "tone-red",
    "探索": "tone-blue",
    "社交": "tone-olive",
    "战斗": "tone-rust",
    "医疗": "tone-teal",
    "运动": "tone-green",
    "知识": "tone-indigo",
    "技术": "tone-gold",
    "操纵": "tone-slate",
    "其它": "tone-neutral",
}

# Core skills shown in each group (mimics blank card layout)
_CORE_SKILLS = {
    "特殊": ["信用评级", "克苏鲁神话"],
    "探索": ["侦查", "聆听", "图书馆使用", "计算机使用Ω", "潜行", "追踪", "导航"],
    "社交": ["话术", "说服", "取悦", "恐吓", "心理学", "母语(汉语)", "外语(英语)"],
    "战斗": ["闪避", "格斗(斗殴)", "格斗(刀剑)", "射击(手枪)", "射击(步/霰)", "投掷"],
    "医疗": ["急救", "医学", "精神分析"],
    "运动": ["攀爬", "跳跃", "游泳"],
    "知识": ["博物学", "神秘学", "考古学", "人类学", "估价", "会计", "法律", "历史", "电子学Ω", "科学(数学)", "科学(物理)"],
    "技术": ["乔装", "妙手", "锁匠", "机械维修", "电气维修", "驯兽", "技艺(表演)", "技艺(音乐)", "生存(森林)"],
    "操纵": ["汽车驾驶", "骑术", "驾驶(船)", "操作重型机械"],
    "其它": [],
}

# Skills that are always worth showing
_ALWAYS_SHOW = {"信用评级", "克苏鲁神话", "侦查", "聆听", "图书馆使用"}


def _get_skill_group(skill_name: str) -> str:
    """Determine which of the 10 groups a skill belongs to."""
    if skill_name in ("信用评级", "克苏鲁神话"):
        return "特殊"
    if skill_name in ("侦查", "聆听", "图书馆使用", "计算机使用Ω", "潜行", "追踪", "导航", "读唇"):
        return "探索"
    if skill_name in ("话术", "说服", "取悦", "恐吓", "心理学") or skill_name.startswith(("母语(", "外语(")):
        return "社交"
    if skill_name in ("闪避", "投掷", "炮术", "爆破") or skill_name.startswith(("格斗(", "射击(")):
        return "战斗"
    if skill_name in ("急救", "医学", "精神分析", "催眠"):
        return "医疗"
    if skill_name in ("攀爬", "跳跃", "游泳", "潜水"):
        return "运动"
    if skill_name in ("博物学", "神秘学", "考古学", "人类学", "估价", "会计", "法律", "历史", "电子学Ω") or skill_name.startswith("科学("):
        return "知识"
    if skill_name in ("乔装", "妙手", "锁匠", "机械维修", "电气维修", "驯兽") or skill_name.startswith(("技艺(", "生存(")):
        return "技术"
    if skill_name in ("汽车驾驶", "骑术", "操作重型机械") or skill_name.startswith("驾驶("):
        return "操纵"
    return "其它"


def build_skill_tables(data: dict) -> tuple[list[dict], list[dict]]:
    """Build left and right skill table data.
    
    Always shows core skills (like blank card) plus any extra allocated skills.
    Returns (left_groups, right_groups) where each group is {"group_name", "skills": [...]}.
    """
    attrs = data.get("attributes", {})
    skill_allocs = data.get("skill_allocations", {})
    pro_allocs = skill_allocs.get("pro", {})
    interest_allocs = skill_allocs.get("interest", {})
    job_name = data.get("basic", {}).get("job", "")
    job = JOBS.get(job_name)
    
    occupation_skills = set(job.get("occupation_skills", [])) if job else set()
    allocated_skills = set(pro_allocs.keys()) | set(interest_allocs.keys())
    
    # Build per-group skill name lists
    group_names: dict[str, list[str]] = {g: [] for g in (LEFT_GROUP_NAMES + RIGHT_GROUP_NAMES)}
    
    for group_name in LEFT_GROUP_NAMES + RIGHT_GROUP_NAMES:
        core = _CORE_SKILLS.get(group_name, [])
        seen = set()
        # Always show all core skills (like blank card)
        for s in core:
            seen.add(s)
            group_names[group_name].append(s)
        
        # Add allocated skills not in core list
        for skill_name in sorted(allocated_skills):
            if skill_name not in seen and _get_skill_group(skill_name) == group_name:
                group_names[group_name].append(skill_name)
                seen.add(skill_name)
    
    def _build_group(group_name: str, stripe_counter: list[int]) -> dict | None:
        skill_names = group_names.get(group_name, [])
        if not skill_names:
            return None
        rows = []
        for name in skill_names:
            init = get_skill_init(name, attrs)
            pro = pro_allocs.get(name, 0)
            interest = interest_allocs.get(name, 0)
            total = init + pro + interest
            rows.append({
                "name": name,
                "init": init,
                "pro": pro,
                "interest": interest,
                "total": total,
                "is_occupation": name in occupation_skills,
                "stripe": stripe_counter[0] % 2,
            })
            stripe_counter[0] += 1
        return {
            "group_name": group_name,
            "skills": rows,
            "size": len(rows),
            "tone": _GROUP_TONES.get(group_name, "tone-neutral"),
        }
    
    left_counter = [0]
    left_groups = [_build_group(g, left_counter) for g in LEFT_GROUP_NAMES]
    left_groups = [g for g in left_groups if g is not None]
    
    right_counter = [0]
    right_groups = [_build_group(g, right_counter) for g in RIGHT_GROUP_NAMES]
    right_groups = [g for g in right_groups if g is not None]
    
    return left_groups, right_groups


# ---------------------------------------------------------------------------
# Weapon success rate helper
# ---------------------------------------------------------------------------

def _enrich_weapons(weapons: list[dict], skill_totals: dict[str, int]) -> list[dict]:
    """Add computed success_rate to each weapon based on its skill."""
    result = []
    for w in weapons[:5]:
        wc = dict(w)
        skill_name = wc.get("skill", "")
        wc["success_rate"] = skill_totals.get(skill_name, "")
        result.append(wc)
    return result


# ---------------------------------------------------------------------------
# Story background items
# ---------------------------------------------------------------------------

STORY_LEFT_ITEMS = [
    ("形象描述", "appearance"),
    ("思想与信念", "belief"),
    ("重要之人", "important_person"),
    ("意义非凡之地", "important_place"),
    ("宝贵之物", "important_item"),
    ("特质", "trait"),
    ("伤口与疤痕", "scar"),
    ("精神症状", "madness"),
]


def _text(value: object, fallback: str = "") -> str:
    """Return display-safe text without changing the source data contract."""
    if value is None:
        return fallback
    value = str(value).strip()
    return value if value else fallback


def render(data: dict) -> str:
    """Render character sheet data to HTML string."""
    basic = data.get("basic", {})
    attrs = data.get("attributes", {})
    luck = data.get("luck", 0)
    age = basic.get("age", 0)
    if isinstance(age, str):
        try:
            age = int(age)
        except ValueError:
            age = 0

    derived = calc_derived(attrs, luck, age)
    job_name = basic.get("job", "")
    job = JOBS.get(job_name)

    pro_total = calc_pro_points(job_name, attrs) if job else 0
    interest_total = calc_interest_points(attrs)
    skill_allocs = data.get("skill_allocations", {})
    pro_allocs = skill_allocs.get("pro", {})
    interest_allocs = skill_allocs.get("interest", {})
    pro_used = sum(pro_allocs.values())
    interest_used = sum(interest_allocs.values())

    # Build skill total map for weapon lookups
    skill_totals = {}
    for name in set(pro_allocs) | set(interest_allocs) | set(SKILL_MAP.keys()):
        init = get_skill_init(name, attrs)
        pro = pro_allocs.get(name, 0)
        interest = interest_allocs.get(name, 0)
        skill_totals[name] = init + pro + interest

    skill_table_left, skill_table_right = build_skill_tables(data)
    weapons = _enrich_weapons(data.get("weapons", []) or [], skill_totals)

    background = data.get("background", {}) or {}
    assets = data.get("assets", {}) or {}

    identity_fields = [
        {"label": "姓名", "value": _text(basic.get("name"))},
        {"label": "职业", "value": _text(basic.get("job"))},
        {"label": "玩家", "value": _text(basic.get("player"))},
        {"label": "时代", "value": _text(basic.get("era"), "1920s")},
        {"label": "年龄", "value": _text(basic.get("age"))},
        {"label": "性别", "value": _text(basic.get("gender"))},
        {"label": "住地", "value": _text(basic.get("location"))},
        {"label": "故乡", "value": _text(basic.get("hometown"))},
    ]

    attr_panels = [
        {"key": key.upper(), "label": ATTR_NAMES[key], "value": attrs.get(key, 0)}
        for key in ATTR_KEYS
    ]

    derived_panels = [
        {"label": "理智", "sub": "SAN", "value": derived["san"]},
        {"label": "生命", "sub": "HP", "value": derived["hp"]},
        {"label": "魔法", "sub": "MP", "value": derived["mp"]},
        {"label": "幸运", "sub": "Luck", "value": luck},
        {"label": "闪避", "sub": "Dodge", "value": derived["dodge"]},
        {"label": "移动", "sub": "MOV", "value": derived["mov"]},
        {"label": "伤害加值", "sub": "DB", "value": derived["db"]},
        {"label": "体格", "sub": "Build", "value": derived["build"]},
    ]

    status_groups = [
        {"title": "身体状态", "items": ["重伤", "昏迷", "濒死", "死亡"]},
        {"title": "精神状态", "items": ["临时疯狂", "不定期疯狂", "永久疯狂"]},
    ]

    story_left = []
    for label, key in STORY_LEFT_ITEMS:
        val = background.get(key, "")
        story_left.append({"label": label, "value": val})
    
    desc = background.get("description", "")

    asset_rows = [
        {"label": "消费水平", "value": assets.get("consumption", "")},
        {"label": "现金", "value": assets.get("cash", "")},
        {"label": "总资产", "value": assets.get("assets", "")},
        {"label": "资产详情", "value": assets.get("items", "")},
    ]

    item_tags = [_text(item) for item in (data.get("items", []) or []) if _text(item)]

    context = {
        "basic": basic,
        "attrs": attrs,
        "identity_fields": identity_fields,
        "attr_panels": attr_panels,
        "derived_panels": derived_panels,
        "status_groups": status_groups,
        "attr_names": ATTR_NAMES,
        "attr_keys": ATTR_KEYS,
        "luck": luck,
        "derived": derived,
        "job": job,
        "job_name": job_name,
        "credit_rating": data.get("credit_rating", 0),
        "pro_total": pro_total,
        "pro_used": pro_used,
        "pro_remaining": pro_total - pro_used,
        "interest_total": interest_total,
        "interest_used": interest_used,
        "interest_remaining": interest_total - interest_used,
        "pro_cap": 80,
        "interest_cap": 60,
        "skill_table_left": skill_table_left,
        "skill_table_right": skill_table_right,
        "background": background,
        "assets": assets,
        "asset_rows": asset_rows,
        "weapons": weapons,
        "items": data.get("items", []) or [],
        "item_tags": item_tags,
        "mythos": data.get("mythos", 0),
        "friends": data.get("friends", "") or "",
        "experienced_modules": data.get("experienced_modules", "") or "",
        "story_left": story_left,
        "desc": desc,
    }

    template_path = Path(__file__).parent / "data" / "templates" / "card.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    return template.render(**context)
