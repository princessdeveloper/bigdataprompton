from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import uuid
import os
import time

app = Flask(__name__)
CORS(app)

# =========================
# 0) 저장소 (MVP: 메모리)
# =========================
# 서버 재시작 시 초기화됩니다.
# {TEAM_CODE: {"meta": {...}, "members": [...], "calc": {... or None}, "dirty": bool, "updated_at": float}}
teams_db = {}

# LaaS 조회 보호용 토큰 (LaaS 커넥터에 고정으로 넣어두면 유저는 팀코드만 입력하면 됨)
TEAM_API_TOKEN = os.environ.get("TEAM_API_TOKEN", "dev-token")

# =========================
# 1) 역할/프로젝트/규칙 (B 방식)
# =========================
ROLES = ["Captain", "Specialist", "Ideator", "Coordinator", "Presenter"]

PROJECT_ROLE_BONUS = {
    "발표 중심형": {"Presenter": 15, "Coordinator": 10},
    "보고서 중심형": {"Specialist": 15, "Captain": 10},
    "개발/제작형": {"Specialist": 20, "Captain": 10},
    "조사/분석형": {"Specialist": 15, "Ideator": 10},
    "혼합형": {"Captain": 10, "Coordinator": 10},
}

CHARACTER_BASE = {
    "Captain": {"Captain": 30},
    "Specialist": {"Specialist": 30},
    "Ideator": {"Ideator": 30},
    "Coordinator": {"Coordinator": 30},
    "Presenter": {"Presenter": 30},
}

MBTI_HINT = {
    "ENTJ": {"Captain": 10, "Presenter": 5},
    "ESTJ": {"Captain": 10},
    "ENFJ": {"Presenter": 10, "Captain": 5},
    "INTJ": {"Specialist": 8, "Ideator": 5},
    "ISTJ": {"Specialist": 10},
    "ISFJ": {"Coordinator": 8, "Specialist": 5},
    "ENTP": {"Ideator": 10, "Presenter": 5},
    "ENFP": {"Ideator": 8, "Coordinator": 5},
    "ESFJ": {"Coordinator": 10},
    "ESFP": {"Presenter": 8, "Coordinator": 5},
    "ESTP": {"Presenter": 10},
    "INTP": {"Ideator": 10},
}

# ✅ HTML에서 쓰는 값들과 맞춰야 점수 계산이 정확히 됩니다.
TASK_TO_ROLE = {
    "일정/총괄": ["Captain"],
    "자료조사": ["Specialist", "Ideator"],
    "문서/보고서": ["Specialist", "Captain"],
    "PPT": ["Specialist", "Captain"],
    "회의록": ["Coordinator"],
    "회의록/공유": ["Coordinator"],
    "중재": ["Coordinator"],
    "팀분위기/중재": ["Coordinator"],
    "발표": ["Presenter", "Captain"],
    "Q&A": ["Presenter", "Captain"],
    "Q&A대응": ["Presenter", "Captain"],
}


def score_member_for_role(member: dict, role: str, project_type: str) -> int:
    score = 0
    preferred_tasks = set(member.get("preferred_tasks", []))
    avoid_tasks = set(member.get("avoid_tasks", []))
    experience_tasks = set(member.get("experience_tasks", []))

    mbti = (member.get("mbti") or "").upper().strip()
    character = member.get("character")

    # 1) 선호
    for t in preferred_tasks:
        if role in TASK_TO_ROLE.get(t, []):
            score += 40

    # 2) 비선호 감점
    for t in avoid_tasks:
        if role in TASK_TO_ROLE.get(t, []):
            score -= 30

    # 3) 캐릭터
    score += CHARACTER_BASE.get(character, {}).get(role, 0)

    # 4) MBTI 힌트(약)
    score += MBTI_HINT.get(mbti, {}).get(role, 0)

    # 5) 프로젝트 유형 보정
    score += PROJECT_ROLE_BONUS.get(project_type, {}).get(role, 0)

    # 6) 경험(약)
    for t in experience_tasks:
        if role in TASK_TO_ROLE.get(t, []):
            score += 10

    return score


def build_score_table(members: list, project_type: str) -> dict:
    table = {}
    for m in members:
        name = m["name"]
        table[name] = {role: score_member_for_role(m, role, project_type) for role in ROLES}
    return table


def assign_roles_greedy(members: list, project_type: str) -> dict:
    score_table = build_score_table(members, project_type)

    pairs = []
    for m in members:
        for role in ROLES:
            pairs.append((m["name"], role, score_table[m["name"]][role]))
    pairs.sort(key=lambda x: x[2], reverse=True)

    assigned_member = set()
    assigned_role = set()
    assignments = {}

    # 메인 역할(중복 최소)
    for name, role, sc in pairs:
        if name in assigned_member:
            continue
        if role in assigned_role:
            continue
        assignments[name] = {"main_role": role, "main_score": sc}
        assigned_member.add(name)
        assigned_role.add(role)
        if len(assigned_member) == len(members):
            break

    # 보조 역할 2개 + 전체 점수
    for m in members:
        name = m["name"]
        role_scores = score_table[name]
        sorted_roles = sorted(role_scores.items(), key=lambda kv: kv[1], reverse=True)

        main_role = assignments.get(name, {}).get("main_role")
        backup_roles = [r for r, _ in sorted_roles if r != main_role][:2]

        if name not in assignments:
            best_role, best_sc = sorted_roles[0]
            assignments[name] = {"main_role": best_role, "main_score": best_sc}

        assignments[name]["backup_roles"] = backup_roles
        assignments[name]["all_scores"] = role_scores

    missing_roles = [r for r in ROLES if r not in assigned_role]

    return {
        "assignments": assignments,
        "missing_roles": missing_roles,
        "score_table": score_table,
    }


def ensure_calc(team_code: str):
    """필요하면 자동 분석을 수행하고 teams_db[team_code]['calc']를 최신화."""
    team = teams_db[team_code]
    meta = team.get("meta", {})
    members = team.get("members", [])

    if not meta.get("project_type"):
        return False, "project_type(프로젝트 유형)를 먼저 저장하세요."
    if len(members) == 0:
        return False, "팀원 정보가 없습니다."

    # dirty면 재계산
    if team.get("calc") is None or team.get("dirty", True):
        calc = assign_roles_greedy(members, meta["project_type"])
        team["calc"] = calc
        team["dirty"] = False
        team["updated_at"] = time.time()

    return True, None


# =========================
# 2) 정적 파일 제공 (index.html)
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


# =========================
# 3) 팀 생성/설정/제출
# =========================
@app.route("/create_team", methods=["POST"])
def create_team():
    team_code = str(uuid.uuid4())[:6].upper()
    teams_db[team_code] = {"meta": {}, "members": [], "calc": None, "dirty": True, "updated_at": None}
    return jsonify({"team_code": team_code})


@app.route("/set_team/<team_code>", methods=["POST"])
def set_team(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "존재하지 않는 팀입니다."}), 404

    teams_db[team_code]["meta"] = request.get_json(silent=True) or {}
    teams_db[team_code]["dirty"] = True
    return jsonify({"status": "success"})


@app.route("/submit/<team_code>", methods=["POST"])
def submit_member(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "존재하지 않는 팀입니다."}), 404

    data = request.get_json(silent=True) or {}

    for k in ["name", "mbti", "character"]:
        if not data.get(k):
            return jsonify({"error": f"'{k}' 값이 비어있습니다."}), 400

    data.setdefault("preferred_tasks", [])
    data.setdefault("avoid_tasks", [])
    data.setdefault("experience_tasks", [])

    teams_db[team_code]["members"].append(data)
    teams_db[team_code]["dirty"] = True
    teams_db[team_code]["calc"] = None  # 최신화 유도

    return jsonify({"status": "success", "count": len(teams_db[team_code]["members"])})


# =========================
# 4) (선택) 수동 분석 엔드포인트
#    - 프론트에서 버튼으로 바로 확인용
# =========================
@app.route("/analyze/<team_code>", methods=["POST"])
def analyze(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "존재하지 않는 팀입니다."}), 404

    ok, err = ensure_calc(team_code)
    if not ok:
        return jsonify({"error": err}), 400

    return jsonify({"status": "ok", "team_code": team_code, "calc": teams_db[team_code]["calc"]})


# =========================
# 5) ✅ LaaS 연동용: 팀 데이터 조회 (자동 분석 포함)
#    - LaaS는 여기만 호출해도 됨
#    - 유저는 "팀 코드"만 입력
#    - LaaS 커넥터가 토큰 헤더/쿼리값을 고정으로 넣어주면 됨
# =========================
@app.route("/team/<team_code>", methods=["GET"])
def get_team(team_code):
    # 토큰은 헤더 또는 쿼리스트링 둘 다 지원 (LaaS 환경에 맞게 선택)
    token = request.headers.get("X-Team-Token", "") or request.args.get("token", "")
    if TEAM_API_TOKEN and token != TEAM_API_TOKEN:
        return jsonify({"error": "unauthorized"}), 401

    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "not_found"}), 404

    ok, err = ensure_calc(team_code)
    if not ok:
        return jsonify({
            "team_code": team_code,
            "meta": teams_db[team_code]["meta"],
            "members": teams_db[team_code]["members"],
            "calc": None,
            "error": err,
        }), 400

    return jsonify({
        "team_code": team_code,
        "meta": teams_db[team_code]["meta"],
        "members": teams_db[team_code]["members"],
        "calc": teams_db[team_code]["calc"],   # ✅ 여기엔 항상 최신 분석 결과가 들어감
        "updated_at": teams_db[team_code]["updated_at"],
    })


# (선택) 팀 초기화
@app.route("/reset/<team_code>", methods=["POST"])
def reset(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "not_found"}), 404
    teams_db[team_code] = {"meta": {}, "members": [], "calc": None, "dirty": True, "updated_at": None}
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
