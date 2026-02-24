from flask import Flask, render_template, request, redirect, url_for, flash
import json
import os

app = Flask(__name__)
app.secret_key = "secret_key_for_session"

# 데이터가 저장될 로컬 파일 경로
DB_FILE = "users.json"

def get_users():
    """로컬 JSON 파일에서 모든 사용자 정보를 가져옵니다."""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_user_to_local(email, password):
    """로컬 JSON 파일에 사용자 정보를 저장합니다."""
    users = get_users()
    users.append({"email": email, "password": password})
    
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    
    if not email or not password:
        flash("이메일과 비밀번호를 모두 입력해주세요.")
        return redirect(url_for("index"))
    
    # JSON 파일에서 사용자 확인
    users = get_users()
    user_found = False
    for user in users:
        if user["email"] == email and user["password"] == password:
            user_found = True
            break
    
    if user_found:
        print(f"[로그인 성공] 이메일: {email}")
        # 로그인 성공 시 Streamlit 대시보드(app.py)로 이동
        return redirect("http://localhost:8501")
    else:
        print(f"[로그인 실패] 이메일: {email}")
        flash("이메일 또는 비밀번호가 일치하지 않습니다.")
    
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        if not email or not password:
            flash("이메일과 비밀번호를 모두 입력해주세요.")
            return redirect(url_for("signup"))
            
        # 중복 확인
        users = get_users()
        if any(user["email"] == email for user in users):
            flash("이미 가입된 이메일입니다.")
            return redirect(url_for("signup"))
            
        save_user_to_local(email, password)
        flash("회원가입이 완료되었습니다! 로그인해주세요.")
        return redirect(url_for("index"))
        
    return render_template("signup.html")

if __name__ == "__main__":
    app.run(debug=True)
