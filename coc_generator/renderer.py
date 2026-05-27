"""HTML renderer for character cards."""

import json
from pathlib import Path

from jinja2 import Template

from .engine import calc_derived, calc_interest_points, calc_pro_points, get_skill_init
from .schema import ATTR_KEYS, ATTR_NAMES
from .data.skills import SKILL_MAP
from .data.jobs import JOBS


# Skill display order (grouped)
SKILL_GROUPS = [
    ("侦查类", ["侦查", "聆听", "图书馆使用", "读唇"]),
    ("社交", ["取悦", "话术", "恐吓", "说服", "心理学"]),
    ("隐匿", ["潜行", "追踪", "乔装", "妙手", "锁匠"]),
    ("运动", ["攀爬", "跳跃", "游泳", "潜水", "骑术", "投掷"]),
    ("战斗", ["闪避", "格斗(斗殴)", "格斗(刀剑)", "格斗(矛)", "格斗(斧)", "格斗(绞索)", "格斗(链锯)", "格斗(链枷)", "格斗(鞭)", "射击(手枪)", "射击(步/霰)", "射击(冲锋枪)", "射击(弓弩)", "射击(机枪)", "射击(重武器)", "炮术", "爆破"]),
    ("学识", ["会计", "法律", "历史", "考古学", "图书馆使用", "神秘学", "估价", "母语(汉语)", "母语(英语)", "母语(日语)", "外语(汉语)", "外语(英语)", "外语(日语)", "外语(法语)", "外语(俄语)", "外语(德语)", "外语(韩语)", "外语(粤语)", "外语(拉丁语)", "外语(荷兰语)", "外语(挪威语)", "外语(丹麦语)", "外语(印度语)", "外语(西班牙语)", "外语(葡萄牙语)", "外语(阿拉伯语)"]),
    ("技艺", ["技艺(表演)", "技艺(音乐)", "技艺(绘画)", "技艺(艺术)", "技艺(摄影)", "技艺(写作)", "技艺(书法)", "技艺(打字)", "技艺(速记)", "技艺(伪造)", "技艺(烹饪)", "技艺(裁缝)", "技艺(理发)", "技艺(技术制图)", "技艺(耕作)", "技艺(木工)", "技艺(铁匠)", "技艺(焊接)", "技艺(管道工)"]),
    ("科学", ["科学(数学)", "科学(物理)", "科学(化学)", "科学(药学)", "科学(地质学)", "科学(生物学)", "科学(动物学)", "科学(植物学)", "科学(天文学)", "科学(密码学)", "科学(气象学)", "科学(工程学)", "科学(鉴证)", "科学(制药)"]),
    ("生存", ["生存(沙漠)", "生存(森林)", "生存(荒岛)", "生存(高山)", "生存(海上)"]),
    ("驾驶", ["汽车驾驶", "驾驶(船)", "驾驶(马车)", "驾驶(飞行器)"]),
    ("医疗", ["急救", "医学", "精神分析", "催眠"]),
    ("其他", ["电气维修", "机械维修", "导航", "操作重型机械", "驯兽", "计算机使用Ω", "电子学Ω", "博物学"]),
]


def build_skill_table(data: dict) -> list[dict]:
    """Build a flat skill table for rendering.
    
    Only show:
    1. Skills with pro/interest points allocated
    2. Recommended skills (侦查, 聆听, 图书馆使用)
    3. Occupation skills for this job
    """
    from .data.skills import RECOMMENDED_SKILLS
    from .data.jobs import JOBS
    
    attrs = data.get("attributes", {})
    skill_allocs = data.get("skill_allocations", {})
    pro_allocs = skill_allocs.get("pro", {})
    interest_allocs = skill_allocs.get("interest", {})
    job_name = data.get("basic", {}).get("job", "")
    job = JOBS.get(job_name)

    # Determine which skills to show
    show_skills = set()
    # All allocated skills
    show_skills.update(pro_allocs.keys())
    show_skills.update(interest_allocs.keys())
    # Recommended skills
    show_skills.update(RECOMMENDED_SKILLS)
    # Always show credit rating if it has points
    if "信用评级" in pro_allocs or "信用评级" in interest_allocs:
        show_skills.add("信用评级")

    # Build rows
    rows = []
    seen = set()

    # First, grouped skills
    for group_name, skill_names in SKILL_GROUPS:
        group_rows = []
        for name in skill_names:
            if name not in show_skills:
                continue
            init = get_skill_init(name, attrs)
            pro = pro_allocs.get(name, 0)
            interest = interest_allocs.get(name, 0)
            total = init + pro + interest
            group_rows.append({
                "name": name,
                "init": init,
                "pro": pro,
                "interest": interest,
                "total": total,
            })
            seen.add(name)

        if group_rows:
            rows.append({"type": "header", "name": group_name})
            rows.extend({"type": "skill", **r} for r in group_rows)

    # Then, any remaining skills not in groups
    remaining = []
    for name in sorted(show_skills):
        if name in seen:
            continue
        init = get_skill_init(name, attrs)
        pro = pro_allocs.get(name, 0)
        interest = interest_allocs.get(name, 0)
        total = init + pro + interest
        remaining.append({
            "name": name,
            "init": init,
            "pro": pro,
            "interest": interest,
            "total": total,
        })

    if remaining:
        rows.append({"type": "header", "name": "其他"})
        rows.extend({"type": "skill", **r} for r in remaining)

    return rows


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
    pro_used = sum(skill_allocs.get("pro", {}).values())
    interest_used = sum(skill_allocs.get("interest", {}).values())

    skill_table = build_skill_table(data)

    context = {
        "basic": basic,
        "attrs": attrs,
        "attr_names": ATTR_NAMES,
        "attr_keys": ATTR_KEYS,
        "luck": luck,
        "derived": derived,
        "job": job,
        "job_name": job_name,
        "credit_rating": data.get("credit_rating", 0),
        "pro_total": pro_total,
        "pro_used": pro_used,
        "interest_total": interest_total,
        "interest_used": interest_used,
        "skill_table": skill_table,
        "background": data.get("background", {}),
        "assets": data.get("assets", {}),
        "weapons": data.get("weapons", []),
        "items": data.get("items", []),
        "mythos": data.get("mythos", 0),
        "friends": data.get("friends", ""),
        "experienced_modules": data.get("experienced_modules", ""),
    }

    template_path = Path(__file__).parent / "data" / "templates" / "card.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    return template.render(**context)
