from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import os

app = Flask(__name__)
# 모든 도메인에서 접속 가능하도록 설정 (LaaS 커넥터와 index.html 연동을 위해 필수)
CORS(app) 

teams_db = {}

@app.route('/create_team', methods=['POST'])
def create_team():
    team_code = str(uuid.uuid4())[:6].upper() # 코드를 대문자로 하면 가독성이 좋습니다.
    teams_db[team_code] = {"members": []}
    return jsonify({"team_code": team_code})

@app.route('/submit/<team_code>', methods=['POST'])
def submit_member(team_code):
    # 대소문자 구분 없이 매칭되도록 처리
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "존재하지 않는 팀입니다."}), 404
    
    data = request.json
    # 데이터가 비어있는지 확인하는 안전장치
    if not data:
        return jsonify({"error": "데이터가 없습니다."}), 400
        
    teams_db[team_code]["members"].append(data)
    return jsonify({"status": "success", "count": len(teams_db[team_code]["members"])})

# Wanted LaaS에서 데이터를 가져갈 수 있는 '조회' 경로가 필요합니다.
@app.route('/get_team/<team_code>', methods=['GET'])
def get_team(team_code):
    team_code = team_code.upper()
    if team_code not in teams_db:
        return jsonify({"error": "팀을 찾을 수 없습니다."}), 404
    return jsonify(teams_db[team_code])

if __name__ == '__main__':
    # 클라우드 환경의 포트 번호를 동적으로 할당받도록 수정
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)