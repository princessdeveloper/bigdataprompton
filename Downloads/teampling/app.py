from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import uuid
import os

app = Flask(__name__)
# 모든 도메인에서 접속을 허용하여 CORS 에러를 방지합니다.
CORS(app)

# 데이터를 저장할 변수 (서버 재시작 시 초기화됩니다)
teams_db = {}

# 1. 메인 페이지 (브라우저 접속 시 index.html을 보여줍니다)
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# 2. 팀 코드 생성
@app.route('/create_team', methods=['POST'])
def create_team():
    # 6자리의 고유한 팀 코드를 생성하고 대문자로 변환합니다.
    team_code = str(uuid.uuid4())[:6].upper()
    teams_db[team_code] = {"meta": {}, "members": []}
    print(f"✅ 새 팀 생성됨: {team_code}")
    return jsonify({"team_code": team_code})

# 3. 팀 메타 정보 설정 (전공, 프로젝트 유형 등)
@app.route('/set_team/<team_code>', methods=['POST'])
def set_team(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "존재하지 않는 팀입니다."}), 404
    
    data = request.json
    teams_db[team_code]["meta"] = data
    print(f"⚙️ 팀[{team_code}] 설정 업데이트: {data}")
    return jsonify({"status": "success", "message": "팀 설정 저장 완료"})

# 4. 팀원 데이터 추가 (MBTI, 선호/기피 과업 등)
@app.route('/submit/<team_code>', methods=['POST'])
def submit_member(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "존재하지 않는 팀입니다."}), 404
    
    data = request.json
    if not data:
        return jsonify({"error": "데이터가 비어있습니다."}), 400
        
    teams_db[team_code]["members"].append(data)
    print(f"👤 팀[{team_code}] 신규 팀원 추가: {data.get('name')}")
    return jsonify({"status": "success", "count": len(teams_db[team_code]["members"])})

# 5. Wanted LaaS 연동용 데이터 조회 (GET 방식)
@app.route('/get_team/<team_code>', methods=['GET'])
def get_team(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "팀 데이터를 찾을 수 없습니다."}), 404
    
    # LaaS가 읽어갈 팀의 전체 데이터를 반환합니다.
    return jsonify(teams_db[team_code])

if __name__ == '__main__':
    # Render와 같은 클라우드 환경에서 포트를 자동으로 할당받습니다.
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)