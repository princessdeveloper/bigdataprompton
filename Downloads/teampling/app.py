from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import uuid
import os

app = Flask(__name__)
CORS(app)

# 팀 데이터를 저장할 딕셔너리
teams_db = {}

# [추가] 메인 주소 접속 시 index.html을 보여주는 설정
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# 팀 코드 생성 (POST 방식만 허용)
@app.route('/create_team', methods=['POST'])
def create_team():
    team_code = str(uuid.uuid4())[:6].upper()
    teams_db[team_code] = {"meta": {}, "members": []}
    return jsonify({"team_code": team_code})

# 팀 메타 정보 설정 (POST)
@app.route('/set_team/<team_code>', methods=['POST'])
def set_team(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "팀을 찾을 수 없습니다."}), 404
    data = request.json
    teams_db[team_code]["meta"] = data
    return jsonify({"status": "success"})

# 팀원 추가 (POST)
@app.route('/submit/<team_code>', methods=['POST'])
def submit_member(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "팀을 찾을 수 없습니다."}), 404
    data = request.json
    teams_db[team_code]["members"].append(data)
    return jsonify({"status": "success", "count": len(teams_db[team_code]["members"])})

# [중요] Wanted LaaS가 데이터를 읽어갈 수 있는 조회 경로 (GET 방식)
@app.route('/get_team/<team_code>', methods=['GET'])
def get_team(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "팀 데이터를 찾을 수 없습니다."}), 404
    return jsonify(teams_db[team_code])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)