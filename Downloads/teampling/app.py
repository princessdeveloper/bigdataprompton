from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import uuid
import os

app = Flask(__name__)
CORS(app)

# 팀 데이터를 저장할 공간 (서버 재시작 시 초기화됩니다)
teams_db = {}

# [추가] 브라우저에서 주소만 입력했을 때 index.html을 보여주는 코드
@app.route('/')
def index():
    # 현재 폴더에 있는 index.html 파일을 사용자에게 보냅니다.
    return send_from_directory('.', 'index.html')

# 팀 코드 생성 (POST 방식)
@app.route('/create_team', methods=['POST'])
def create_team():
    team_code = str(uuid.uuid4())[:6].upper()
    teams_db[team_code] = {"meta": {}, "members": []}
    return jsonify({"team_code": team_code})

# 팀 설정 저장 (POST)
@app.route('/set_team/<team_code>', methods=['POST'])
def set_team(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "존재하지 않는 팀입니다."}), 404
    teams_db[team_code]["meta"] = request.json
    return jsonify({"status": "success"})

# 팀원 추가 (POST)
@app.route('/submit/<team_code>', methods=['POST'])
def submit_member(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "존재하지 않는 팀입니다."}), 404
    teams_db[team_code]["members"].append(request.json)
    return jsonify({"status": "success", "count": len(teams_db[team_code]["members"])})

# [중요] Wanted LaaS가 데이터를 읽어갈 때 사용하는 조회 경로 (GET)
@app.route('/get_team/<team_code>', methods=['GET'])
def get_team(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "데이터를 찾을 수 없습니다."}), 404
    return jsonify(teams_db[team_code])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)