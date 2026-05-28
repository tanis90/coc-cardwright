"""Rule engine for COC 7th Edition character validation and calculation."""

import math
from .schema import ATTR_KEYS, ATTR_NAMES, Error, ValidationResult
from .data.skills import SKILL_MAP
from .data.jobs import JOBS


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ATTR_MIN = 20
ATTR_MAX = 80
TOTAL_ATTR_POINTS = 480
PRO_SKILL_CAP = 80
INTEREST_SKILL_CAP = 60


# ---------------------------------------------------------------------------
# Derived attribute calculation
# ---------------------------------------------------------------------------
def calc_derived(attrs: dict, luck: int, age: int) -> dict:
    """Calculate all derived attributes from base stats."""
    str_ = attrs.get("str", 0)
    con = attrs.get("con", 0)
    dex = attrs.get("dex", 0)
    siz = attrs.get("siz", 0)
    pow_ = attrs.get("pow", 0)
    edu = attrs.get("edu", 0)
    int_ = attrs.get("int", 0)

    hp = math.floor((con + siz) / 10)
    mp = math.floor(pow_ / 5)
    san = pow_
    dodge = math.floor(dex / 2)
    native_language = edu

    # Damage bonus & build
    str_siz = str_ + siz
    if str_siz <= 64:
        db, build = "-2", -2
    elif str_siz <= 84:
        db, build = "-1", -1
    elif str_siz <= 124:
        db, build = "0", 0
    elif str_siz <= 164:
        db, build = "+1D4", 1
    elif str_siz <= 204:
        db, build = "+1D6", 2
    else:
        rate = math.floor((str_siz - 205) / 80) + 2
        db, build = f"+{rate}D6", rate + 1

    # MOV
    if dex < siz and str_ < siz:
        mov = 7
    elif dex > siz and str_ > siz:
        mov = 9
    else:
        mov = 8

    # Age modifier for MOV only (no attribute modification in buy-point system)
    if age >= 80:
        mov -= 5
    elif age >= 70:
        mov -= 4
    elif age >= 60:
        mov -= 3
    elif age >= 50:
        mov -= 2
    elif age >= 40:
        mov -= 1

    return {
        "hp": hp,
        "mp": mp,
        "san": san,
        "db": db,
        "build": build,
        "mov": mov,
        "dodge": dodge,
        "native_language": native_language,
    }


# ---------------------------------------------------------------------------
# Point calculation
# ---------------------------------------------------------------------------
def calc_pro_points(job_name: str, attrs: dict) -> int:
    """Calculate occupation skill points based on job formula and attributes."""
    job = JOBS.get(job_name)
    if not job:
        return 0

    formula = job["point_formula"]
    total = 0
    for group in formula:
        values = [attrs.get(attr, 0) * mult for attr, mult in group]
        total += max(values) if values else 0
    return total


def calc_interest_points(attrs: dict) -> int:
    return attrs.get("int", 0) * 2


# ---------------------------------------------------------------------------
# Skill helpers
# ---------------------------------------------------------------------------
def get_skill_init(skill_name: str, attrs: dict) -> int:
    """Get the base/init value of a skill."""
    info = SKILL_MAP.get(skill_name)
    if not info:
        group_name = skill_name.split("(", 1)[0] if "(" in skill_name else ""
        group_info = SKILL_MAP.get(group_name)
        if group_info:
            return attrs.get("edu", 0) if group_info.get("dynamic") == "edu" else group_info.get("init", 0)
        return 0  # custom skill

    dynamic = info.get("dynamic")
    if dynamic == "edu" or skill_name.startswith("母语("):
        return attrs.get("edu", 0)
    elif dynamic == "dex_half":
        return math.floor(attrs.get("dex", 0) / 2)
    else:
        return info.get("init", 0)


def _is_plain_int(value: object) -> bool:
    """JSON integer, excluding booleans which are int subclasses in Python."""
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_allocations(allocs: object, kind: str, errors: list[Error]) -> dict[str, int]:
    """Validate skill allocation point values and return only usable entries."""
    if not isinstance(allocs, dict):
        errors.append(Error(
            code="SKILL_ALLOCATIONS_NOT_OBJECT",
            field=f"skill_allocations.{kind}",
            expected="object",
            actual=type(allocs).__name__,
            message=f"{'职业' if kind == 'pro' else '兴趣'}技能点分配必须是对象",
        ))
        return {}

    valid: dict[str, int] = {}
    for skill_name, points in allocs.items():
        field = f"skill_allocations.{kind}.{skill_name}"
        if not isinstance(skill_name, str):
            errors.append(Error(
                code="SKILL_NAME_NOT_STRING",
                field=f"skill_allocations.{kind}",
                expected="技能名字符串",
                actual=skill_name,
                message="技能名必须是字符串",
            ))
            continue
        if not _is_plain_int(points):
            errors.append(Error(
                code="SKILL_POINTS_NOT_INTEGER",
                field=field,
                expected="非负整数",
                actual=points,
                message=f"技能【{skill_name}】分配点数必须是非负整数",
            ))
            continue
        if points < 0:
            errors.append(Error(
                code="SKILL_POINTS_NEGATIVE",
                field=field,
                expected=">=0",
                actual=points,
                message=f"技能【{skill_name}】分配点数不能为负数",
            ))
            continue
        valid[skill_name] = points
    return valid


def _is_allowed_occupation_skill(skill_name: str, allowed_skills: set[str]) -> bool:
    if skill_name in allowed_skills:
        return True

    group_name = skill_name.split("(", 1)[0] if "(" in skill_name else ""
    if not group_name:
        return False

    # Some source jobs contain open-ended specializations, e.g.
    # 技艺(生活类，如烹饪、裁缝、理发) or 生存(高山/冰山).
    for allowed in allowed_skills:
        if allowed.startswith(f"{group_name}(") and any(marker in allowed for marker in ("任一", "如", "等", "类", "/")):
            return True
    return False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate(data: dict) -> ValidationResult:
    """Validate a character sheet JSON."""
    errors: list[Error] = []
    warnings: list[str] = []
    derived: dict = {}

    # --- Basic info ---
    basic = data.get("basic", {})
    job_name = basic.get("job", "")
    age = basic.get("age", 0)
    if isinstance(age, str):
        try:
            age = int(age)
        except ValueError:
            age = 0

    # --- Attributes ---
    attrs_raw = data.get("attributes", {})
    attrs = {}
    if not isinstance(attrs_raw, dict):
        errors.append(Error(
            code="ATTRIBUTES_NOT_OBJECT",
            field="attributes",
            expected="object",
            actual=type(attrs_raw).__name__,
            message="attributes 必须是对象",
        ))
        attrs_raw = {}

    # Check type/range before using attributes in calculations.
    for key in ATTR_KEYS:
        val = attrs_raw.get(key, 0)
        if not _is_plain_int(val):
            errors.append(Error(
                code="ATTR_NOT_INTEGER",
                field=f"attributes.{key}",
                expected="整数",
                actual=val,
                message=f"属性【{ATTR_NAMES.get(key, key)}({key.upper()})】必须是整数",
            ))
            attrs[key] = 0
            continue
        attrs[key] = val
        if not ATTR_MIN <= val <= ATTR_MAX:
            errors.append(Error(
                code="ATTR_OUT_OF_RANGE",
                field=f"attributes.{key}",
                expected=f"{ATTR_MIN}~{ATTR_MAX}",
                actual=val,
                message=f"属性【{ATTR_NAMES.get(key, key)}({key.upper()})】为{val}，超出范围{ATTR_MIN}~{ATTR_MAX}",
            ))

    # Check sum
    total = sum(attrs.get(k, 0) for k in ATTR_KEYS)
    if total != TOTAL_ATTR_POINTS:
        errors.append(Error(
            code="ATTR_SUM_MISMATCH",
            field="attributes.sum",
            expected=TOTAL_ATTR_POINTS,
            actual=total,
            message=f"8项属性总和为{total}，必须等于{TOTAL_ATTR_POINTS}",
        ))

    # --- Job exists ---
    job = JOBS.get(job_name)
    if not job:
        errors.append(Error(
            code="JOB_NOT_FOUND",
            field="basic.job",
            expected="已知职业",
            actual=job_name,
            message=f"职业【{job_name}】不在职业列表中",
        ))

    # --- Luck ---
    luck = data.get("luck", 0)
    if not _is_plain_int(luck):
        errors.append(Error(
            code="LUCK_NOT_INTEGER",
            field="luck",
            expected="整数",
            actual=luck,
            message="幸运值必须是整数",
        ))
        luck = 0
    elif not 15 <= luck <= 90:
        errors.append(Error(
            code="LUCK_OUT_OF_RANGE",
            field="luck",
            expected="15~90",
            actual=luck,
            message=f"幸运值{luck}超出范围15~90",
        ))

    # --- Skill allocations ---
    skill_allocs = data.get("skill_allocations", {})
    if not isinstance(skill_allocs, dict):
        errors.append(Error(
            code="SKILL_ALLOCATIONS_NOT_OBJECT",
            field="skill_allocations",
            expected="object",
            actual=type(skill_allocs).__name__,
            message="skill_allocations 必须是对象",
        ))
        skill_allocs = {}
    pro_allocs = _validate_allocations(skill_allocs.get("pro", {}), "pro", errors)
    interest_allocs = _validate_allocations(skill_allocs.get("interest", {}), "interest", errors)

    # Cthulhu Mythos check
    if "克苏鲁神话" in pro_allocs and pro_allocs["克苏鲁神话"] > 0:
        errors.append(Error(
            code="MYTHOS_PROHIBITED",
            field="skill_allocations.pro.克苏鲁神话",
            expected=0,
            actual=pro_allocs["克苏鲁神话"],
            message="【克苏鲁神话】不能通过正常点数分配提升",
        ))
    if "克苏鲁神话" in interest_allocs and interest_allocs["克苏鲁神话"] > 0:
        errors.append(Error(
            code="MYTHOS_PROHIBITED",
            field="skill_allocations.interest.克苏鲁神话",
            expected=0,
            actual=interest_allocs["克苏鲁神话"],
            message="【克苏鲁神话】不能通过正常点数分配提升",
        ))

    if job:
        # --- Credit rating ---
        credit = data.get("credit_rating", 0)
        credit_for_points = 0
        cr_min, cr_max = job["credit_range"]
        if not _is_plain_int(credit):
            errors.append(Error(
                code="CREDIT_RATING_NOT_INTEGER",
                field="credit_rating",
                expected="整数",
                actual=credit,
                message="信用评级必须是整数",
            ))
        elif not cr_min <= credit <= cr_max:
            credit_for_points = credit if credit >= 0 else 0
            errors.append(Error(
                code="CREDIT_RATING_OUT_OF_RANGE",
                field="credit_rating",
                expected=f"{cr_min}~{cr_max}",
                actual=credit,
                message=f"信用评级{credit}超出职业【{job_name}】允许范围{cr_min}~{cr_max}",
            ))
        else:
            credit_for_points = credit

        # --- Pro points total ---
        pro_total = calc_pro_points(job_name, attrs)
        pro_used = sum(pro_allocs.values()) + credit_for_points
        if pro_used > pro_total:
            errors.append(Error(
                code="PRO_POINTS_OVERFLOW",
                field="skill_allocations.pro.sum",
                expected=f"<={pro_total}",
                actual=pro_used,
                message=f"职业点数总和{pro_used}，超过上限{pro_total}（{job['formula_text']}）",
            ))

        # --- Interest points total ---
        interest_total = calc_interest_points(attrs)
        interest_used = sum(interest_allocs.values())
        if interest_used > interest_total:
            errors.append(Error(
                code="INTEREST_POINTS_OVERFLOW",
                field="skill_allocations.interest.sum",
                expected=f"<={interest_total}",
                actual=interest_used,
                message=f"兴趣点数总和{interest_used}，超过上限{interest_total}（INT{attrs.get('int', 0)}×2）",
            ))

        # --- Occupation skills enforcement ---
        allowed_skills = set(job["occupation_skills"])
        for skill_name, points in pro_allocs.items():
            if not _is_allowed_occupation_skill(skill_name, allowed_skills):
                errors.append(Error(
                    code="PRO_SKILL_NOT_OCCUPATION",
                    field=f"skill_allocations.pro.{skill_name}",
                    expected=sorted(allowed_skills),
                    actual=skill_name,
                    message=f"【{skill_name}】不是【{job_name}】的本职技能，职业点数不能投给该技能",
                ))

    # --- Per-skill caps ---
    for skill_name, points in pro_allocs.items():
        init = get_skill_init(skill_name, attrs)
        final = init + points
        if final > PRO_SKILL_CAP:
            errors.append(Error(
                code="PRO_SKILL_CAP_EXCEEDED",
                field=f"skill_allocations.pro.{skill_name}",
                expected=f"<={PRO_SKILL_CAP}",
                actual=final,
                message=f"职业技能【{skill_name}】最终值{final}，超过上限{PRO_SKILL_CAP}（初始{init}+职业点{points}）",
            ))

    for skill_name, points in interest_allocs.items():
        init = get_skill_init(skill_name, attrs)
        final = init + points
        if final > INTEREST_SKILL_CAP:
            errors.append(Error(
                code="INTEREST_SKILL_CAP_EXCEEDED",
                field=f"skill_allocations.interest.{skill_name}",
                expected=f"<={INTEREST_SKILL_CAP}",
                actual=final,
                message=f"兴趣技能【{skill_name}】最终值{final}，超过上限{INTEREST_SKILL_CAP}（初始{init}+兴趣点{points}）",
            ))

    # --- Derived attributes (only if no errors so far) ---
    if not errors:
        derived = calc_derived(attrs, luck, age)
        derived["pro_points_total"] = calc_pro_points(job_name, attrs) if job else 0
        derived["pro_points_used"] = pro_used
        derived["pro_points_remaining"] = derived["pro_points_total"] - pro_used
        derived["interest_points_total"] = calc_interest_points(attrs)
        derived["interest_points_used"] = interest_used
        derived["interest_points_remaining"] = derived["interest_points_total"] - interest_used

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        derived=derived,
    )


def format_validation_result(result: ValidationResult) -> dict:
    """Convert ValidationResult to a plain dict for JSON serialization."""
    return {
        "valid": result.valid,
        "errors": [
            {
                "code": e.code,
                "field": e.field,
                "expected": e.expected,
                "actual": e.actual,
                "message": e.message,
            }
            for e in result.errors
        ],
        "warnings": result.warnings,
        "derived": result.derived,
    }
