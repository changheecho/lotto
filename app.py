from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, Markup
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import requests
from datetime import datetime, timedelta
import json
import os
import time
import asyncio
import openai
import anthropic
import google.generativeai as genai
from cryptography.fernet import Fernet
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # 실제 서비스에서는 환경변수로 관리하세요

# AI API 설정 (실제 서비스에서는 환경변수로 관리)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your-openai-api-key-here')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', 'your-anthropic-api-key-here')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', 'your-google-api-key-here')

# AI 클라이언트 초기화
try:
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    genai.configure(api_key=GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    print("AI API 클라이언트 초기화 완료")
except Exception as e:
    print(f"AI API 초기화 실패: {e}")
    print("AI API 키를 설정하지 않으면 기존 분석 방식을 사용합니다.")


# Flask-Login 설정
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'



# 사용자 및 로또 선택 정보 파일 경로
USER_DATA_FILE = './data/user_data.json'
MY_LOTTO_FILE = './data/my_lotto.json'
API_KEYS_FILE = './data/api_keys.json'

# 암호화 키 생성 (실제 서비스에서는 환경변수로 관리)
ENCRYPTION_KEY = base64.urlsafe_b64encode(b'your-32-byte-encryption-key-here')[:32]
FERNET = Fernet(base64.urlsafe_b64encode(ENCRYPTION_KEY))

# 사용자 정보 로드/저장 함수
def load_users():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    # 기본 admin 계정
    return {'admin': {'password': 'admin1234', 'is_admin': True}}

def save_users(users):
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

# 내가 선택한 로또 번호 저장/불러오기
def load_my_lotto():
    if os.path.exists(MY_LOTTO_FILE):
        try:
            with open(MY_LOTTO_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_my_lotto(my_lotto):
    with open(MY_LOTTO_FILE, 'w', encoding='utf-8') as f:
        json.dump(my_lotto, f, ensure_ascii=False, indent=2)

# API 키 관리 함수들
def encrypt_api_key(api_key):
    """API 키 암호화"""
    if not api_key or api_key.strip() == '':
        return ''
    return FERNET.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted_key):
    """API 키 복호화"""
    if not encrypted_key or encrypted_key.strip() == '':
        return ''
    try:
        return FERNET.decrypt(encrypted_key.encode()).decode()
    except Exception:
        return ''

def load_user_api_keys(user_id):
    """사용자 API 키 로드"""
    if os.path.exists(API_KEYS_FILE):
        try:
            with open(API_KEYS_FILE, 'r', encoding='utf-8') as f:
                api_keys_data = json.load(f)
                user_keys = api_keys_data.get(user_id, {})
                return {
                    'openai': decrypt_api_key(user_keys.get('openai', '')),
                    'anthropic': decrypt_api_key(user_keys.get('anthropic', '')),
                    'google': decrypt_api_key(user_keys.get('google', ''))
                }
        except Exception as e:
            print(f"API 키 로드 실패: {e}")
    return {'openai': '', 'anthropic': '', 'google': ''}

def save_user_api_keys(user_id, openai_key, anthropic_key, google_key):
    """사용자 API 키 저장"""
    try:
        # 기존 데이터 로드
        api_keys_data = {}
        if os.path.exists(API_KEYS_FILE):
            with open(API_KEYS_FILE, 'r', encoding='utf-8') as f:
                api_keys_data = json.load(f)
        
        # 사용자 키 업데이트 (암호화)
        api_keys_data[user_id] = {
            'openai': encrypt_api_key(openai_key),
            'anthropic': encrypt_api_key(anthropic_key),
            'google': encrypt_api_key(google_key)
        }
        
        # 저장
        with open(API_KEYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(api_keys_data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"API 키 저장 실패: {e}")
        return False

# 전역 사용자/로또 정보
USERS = load_users()
MY_LOTTO = load_my_lotto()

# 회원가입
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USERS:
            flash('이미 존재하는 아이디입니다.', 'danger')
        else:
            USERS[username] = {'password': generate_password_hash(password), 'is_admin': False}
            save_users(USERS)
            flash('회원가입이 완료되었습니다. 로그인 해주세요.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

# 비밀번호 변경
@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_pw = request.form['old_password']
        new_pw = request.form['new_password']
        user = USERS.get(current_user.get_id())
        if user:
            if user.get('is_admin'):
                if user['password'] == old_pw:
                    user['password'] = new_pw
                    save_users(USERS)
                    flash('비밀번호가 변경되었습니다.', 'success')
                    return redirect(url_for('index'))
            else:
                if check_password_hash(user['password'], old_pw):
                    user['password'] = generate_password_hash(new_pw)
                    save_users(USERS)
                    flash('비밀번호가 변경되었습니다.', 'success')
                    return redirect(url_for('index'))
        flash('기존 비밀번호가 일치하지 않습니다.', 'danger')
    return render_template('change_password.html')

# AI API 키 설정
@app.route('/api-settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    user_id = current_user.get_id()
    
    if request.method == 'POST':
        openai_key = request.form.get('openai_key', '').strip()
        anthropic_key = request.form.get('anthropic_key', '').strip()
        google_key = request.form.get('google_key', '').strip()
        
        if save_user_api_keys(user_id, openai_key, anthropic_key, google_key):
            flash('AI API 키가 성공적으로 저장되었습니다.', 'success')
        else:
            flash('API 키 저장 중 오류가 발생했습니다.', 'danger')
        
        return redirect(url_for('api_settings'))
    
    # 기존 키 로드 (보안을 위해 마스킹)
    user_keys = load_user_api_keys(user_id)
    masked_keys = {}
    for key, value in user_keys.items():
        if value:
            masked_keys[key] = value[:8] + '*' * max(0, len(value) - 8)
        else:
            masked_keys[key] = ''
    
    return render_template('api_settings.html', api_keys=masked_keys)

# 사용자 목록 및 삭제 (관리자용, 단순 출력)
@app.route('/users', methods=['GET', 'POST'])
@login_required
def user_list():
    # 관리자만 접근 가능
    user = USERS.get(current_user.get_id())
    if not user or not user.get('is_admin'):
        flash('관리자만 접근할 수 있습니다.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        del_user = request.form.get('delete_user')
        if del_user == current_user.get_id():
            flash('본인은 삭제할 수 없습니다.', 'danger')
        elif del_user == 'admin':
            flash('기본 관리자는 삭제할 수 없습니다.', 'danger')
        elif del_user in USERS:
            USERS.pop(del_user)
            save_users(USERS)
            flash(f'{del_user} 계정이 삭제되었습니다.', 'success')
        else:
            flash('존재하지 않는 사용자입니다.', 'danger')
    filtered_users = {k: v for k, v in USERS.items() if k != 'admin'}
    return render_template('user_list.html', users=filtered_users)

# User 모델
class User(UserMixin):
    def __init__(self, username):
        self.id = username

    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        return User(user_id)
    return None


# AI 연동 함수들
async def ask_gpt_for_lotto_numbers(user_id):
    """GPT에게 로또 번호 5개 요청"""
    try:
        user_keys = load_user_api_keys(user_id)
        openai_key = user_keys.get('openai', '')
        
        if not openai_key:
            raise Exception("OpenAI API 키가 설정되지 않았습니다.")
        
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 로또 번호 분석 전문가입니다. 과거 데이터와 통계를 기반으로 로또 번호를 추천해주세요."},
                {"role": "user", "content": "이번 주 로또 당첨 가능성이 높은 번호 조합 5개를 추천해주세요. 각 조합은 1~45 사이의 중복 없는 6개 숫자로 구성되어야 합니다. JSON 형식으로 응답해주세요: {\"combinations\": [[1,2,3,4,5,6], ...]}"}
            ],
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        import json
        # JSON 부분만 추출
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_content = content[json_start:json_end]
            data = json.loads(json_content)
            return data.get('combinations', [])
        return []
    except Exception as e:
        print(f"GPT API 호출 실패: {e}")
        raise e

async def ask_claude_for_lotto_numbers(user_id):
    """Claude에게 로또 번호 5개 요청"""
    try:
        user_keys = load_user_api_keys(user_id)
        anthropic_key = user_keys.get('anthropic', '')
        
        if not anthropic_key:
            raise Exception("Anthropic API 키가 설정되지 않았습니다.")
        
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": "로또 번호 분석 전문가로서, 이번 주 당첨 가능성이 높은 로또 번호 조합 5개를 추천해주세요. 각 조합은 1~45 사이의 중복 없는 6개 숫자로 구성되어야 합니다. JSON 형식으로 응답해주세요: {\"combinations\": [[1,2,3,4,5,6], ...]}"}
            ]
        )
        
        content = message.content[0].text
        import json
        # JSON 부분만 추출
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_content = content[json_start:json_end]
            data = json.loads(json_content)
            return data.get('combinations', [])
        return []
    except Exception as e:
        print(f"Claude API 호출 실패: {e}")
        raise e

async def ask_gemini_for_lotto_numbers(user_id):
    """Gemini에게 로또 번호 5개 요청"""
    try:
        user_keys = load_user_api_keys(user_id)
        google_key = user_keys.get('google', '')
        
        if not google_key:
            raise Exception("Google API 키가 설정되지 않았습니다.")
        
        genai.configure(api_key=google_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = "로또 번호 분석 전문가로서, 이번 주 당첨 가능성이 높은 로또 번호 조합 5개를 추천해주세요. 각 조합은 1~45 사이의 중복 없는 6개 숫자로 구성되어야 합니다. JSON 형식으로 응답해주세요: {\"combinations\": [[1,2,3,4,5,6], ...]}"
        
        response = model.generate_content(prompt)
        content = response.text
        
        import json
        # JSON 부분만 추출
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_content = content[json_start:json_end]
            data = json.loads(json_content)
            return data.get('combinations', [])
        return []
    except Exception as e:
        print(f"Gemini API 호출 실패: {e}")
        raise e

async def ask_claude_for_final_selection(candidate_numbers, user_id):
    """Claude에게 최종 선택 요청"""
    try:
        user_keys = load_user_api_keys(user_id)
        anthropic_key = user_keys.get('anthropic', '')
        
        if not anthropic_key:
            raise Exception("Anthropic API 키가 설정되지 않았습니다.")
        
        candidates_str = "\n".join([f"{i+1}. {nums}" for i, nums in enumerate(candidate_numbers)])
        
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[
                {"role": "user", "content": f"다음 3개의 로또 번호 조합 중에서 가장 당첨 가능성이 높다고 생각하는 1개를 선택하고 그 이유를 설명해주세요:\n\n{candidates_str}\n\n응답은 JSON 형식으로 해주세요: {{\"selected_index\": 0, \"reason\": \"선택 이유\"}}"}
            ]
        )
        
        content = message.content[0].text
        import json
        # JSON 부분만 추출
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_content = content[json_start:json_end]
            data = json.loads(json_content)
            return data.get('selected_index', 0), data.get('reason', '패턴 분석 결과')
        return 0, '패턴 분석 결과'
    except Exception as e:
        print(f"Claude 최종 선택 API 호출 실패: {e}")
        raise e

def validate_lotto_combination(numbers):
    """로또 번호 조합 유효성 검사"""
    if not isinstance(numbers, list):
        return False
    if len(numbers) != 6:
        return False
    if not all(isinstance(n, int) and 1 <= n <= 45 for n in numbers):
        return False
    if len(set(numbers)) != 6:  # 중복 제거
        return False
    return True


# 내 번호 목록 및 삭제 페이지/기능 추가
@app.route('/my-lotto', methods=['GET', 'POST'])
@login_required
def my_lotto():
    user_id = current_user.get_id()
    if user_id not in MY_LOTTO:
        MY_LOTTO[user_id] = []
    if request.method == 'POST':
        # 삭제 요청 처리
        idx = request.form.get('delete_idx')
        if idx is not None:
            try:
                idx = int(idx)
                if 0 <= idx < len(MY_LOTTO[user_id]):
                    del MY_LOTTO[user_id][idx]
                    save_my_lotto(MY_LOTTO)
                    flash('선택한 번호가 삭제되었습니다.', 'success')
            except Exception:
                flash('삭제 중 오류가 발생했습니다.', 'danger')
    # 최신순으로 보여주기
    lotto_list = list(reversed(MY_LOTTO[user_id]))
    return render_template('my_lotto.html', lotto_list=lotto_list)

def fetch_lotto_data(round_number):
    """동행복권 API에서 로또 당첨 번호 가져오기"""
    try:
        url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={round_number}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('returnValue') == 'success':
            numbers = [
                data['drwtNo1'], data['drwtNo2'], data['drwtNo3'],
                data['drwtNo4'], data['drwtNo5'], data['drwtNo6']
            ]
            bonus = data['bnusNo']
            date = data['drwNoDate']
            return numbers, bonus, date
        return None, None, None
    except Exception as e:
        print(f"API 호출 실패 ({round_number}회차): {e}")
        return None, None, None

def get_latest_round():
    """최신 회차 번호 추정"""
    # 로또 1회차 추첨일: 2002년 12월 7일 (토요일)
    first_draw_date = datetime(2002, 12, 7)
    current_date = datetime.now()
    
    # 현재 날짜까지의 주차 계산
    days_passed = (current_date - first_draw_date).days
    weeks_passed = days_passed // 7
    
    # 현재 주의 토요일이 지났는지 확인 (토요일이 추첨일)
    current_weekday = current_date.weekday()  # 월요일=0, 토요일=5
    
    if current_weekday >= 5:  # 토요일(5) 또는 일요일(6)이면 해당 주차 추첨 완료
        estimated_round = weeks_passed + 1
    else:  # 월~금요일이면 이번 주 추첨은 아직 미완료
        estimated_round = weeks_passed
    
    return max(1, estimated_round)

def get_all_winning_combinations():
    """모든 기존 1등 당첨번호 조합을 가져오기"""
    winning_combinations = set()
    latest_round = get_latest_round()
    
    print(f"기존 당첨번호 조회 중... (1회차 ~ {latest_round}회차)")
    
    # 최근 100회차만 조회 (API 부하 고려)
    start_round = max(1, latest_round - 99)
    
    for round_num in range(start_round, latest_round + 1):
        numbers, bonus, date = fetch_lotto_data(round_num)
        if numbers:
            # 메인 번호 6개를 튜플로 변환하여 set에 추가
            combination = tuple(sorted(numbers))
            winning_combinations.add(combination)
            if round_num % 10 == 0:  # 10회차마다 진행상황 출력
                print(f"{round_num}회차까지 조회 완료...")
    
    print(f"총 {len(winning_combinations)}개의 기존 당첨번호 조합 수집 완료")
    return winning_combinations

def filter_ai_suggestions_against_winners(ai_suggestions):
    """AI 제안 번호에서 기존 당첨번호와 중복되는 것들을 제거"""
    winning_combinations = get_all_winning_combinations()
    filtered_suggestions = []
    
    for suggestion in ai_suggestions:
        combination = tuple(sorted(suggestion))
        if combination not in winning_combinations:
            filtered_suggestions.append(suggestion)
        else:
            print(f"기존 당첨번호와 중복되어 제외: {suggestion}")
    
    print(f"AI 제안 {len(ai_suggestions)}개 → 필터링 후 {len(filtered_suggestions)}개")
    return filtered_suggestions


def generate_fallback_numbers():
    """API 실패 시 대체 번호 생성"""
    main_numbers = sorted(random.sample(range(1, 46), 6))
    remaining_numbers = [i for i in range(1, 46) if i not in main_numbers]
    bonus_number = random.choice(remaining_numbers)
    return main_numbers, bonus_number, "랜덤"

async def generate_ai_collaborative_lotto_numbers(user_id):
    """AI 협업을 통한 로또 번호 생성"""
    errors = []
    
    # 각 AI에게 번호 요청
    gpt_numbers = []
    claude_numbers = []
    gemini_numbers = []
    
    # GPT 요청
    try:
        print("🤖 GPT에게 로또 번호 요청 중...")
        gpt_numbers = await ask_gpt_for_lotto_numbers(user_id)
    except Exception as e:
        errors.append(f"GPT: {str(e)}")
    
    # Claude 요청
    try:
        print("🧠 Claude에게 로또 번호 요청 중...")
        claude_numbers = await ask_claude_for_lotto_numbers(user_id)
    except Exception as e:
        errors.append(f"Claude: {str(e)}")
    
    # Gemini 요청
    try:
        print("💎 Gemini에게 로또 번호 요청 중...")
        gemini_numbers = await ask_gemini_for_lotto_numbers(user_id)
    except Exception as e:
        errors.append(f"Gemini: {str(e)}")
    
    # 모든 AI가 실패한 경우
    if not gpt_numbers and not claude_numbers and not gemini_numbers:
        error_msg = "모든 AI API 연동에 실패했습니다: " + " | ".join(errors)
        raise Exception(error_msg)
    
    # 모든 AI의 추천 번호 수집
    all_ai_numbers = []
    ai_sources = []
    
    for i, combo in enumerate(gpt_numbers[:5]):
        if validate_lotto_combination(combo):
            all_ai_numbers.append(sorted(combo))
            ai_sources.append(f"GPT-{i+1}")
    
    for i, combo in enumerate(claude_numbers[:5]):
        if validate_lotto_combination(combo):
            all_ai_numbers.append(sorted(combo))
            ai_sources.append(f"Claude-{i+1}")
    
    for i, combo in enumerate(gemini_numbers[:5]):
        if validate_lotto_combination(combo):
            all_ai_numbers.append(sorted(combo))
            ai_sources.append(f"Gemini-{i+1}")
    
    # 기존 당첨번호와 중복 제거
    print("🔍 기존 1등 당첨번호와 중복 제거 중...")
    filtered_by_winners = filter_ai_suggestions_against_winners(all_ai_numbers)
    
    # AI 간 중복 제거
    print("🔍 AI 간 중복 번호 제거 중...")
    unique_combinations = []
    seen_combinations = set()
    
    for combo in filtered_by_winners:
        combo_tuple = tuple(sorted(combo))
        if combo_tuple not in seen_combinations:
            unique_combinations.append(combo)
            seen_combinations.add(combo_tuple)
    
    # 3개 선정 (부족하면 기존 당첨번호를 피해서 새로 생성)
    final_candidates = unique_combinations[:3]
    winning_combinations = get_all_winning_combinations() if len(final_candidates) < 3 else set()
    
    while len(final_candidates) < 3:
        # 기존 당첨번호와 중복되지 않는 랜덤 번호 생성
        max_attempts = 100  # 무한루프 방지
        for attempt in range(max_attempts):
            random_combo = sorted(random.sample(range(1, 46), 6))
            combo_tuple = tuple(random_combo)
            
            # 기존 당첨번호 및 이미 선정된 번호와 중복 확인
            if (combo_tuple not in winning_combinations and 
                random_combo not in final_candidates):
                final_candidates.append(random_combo)
                print(f"대체 번호 생성: {random_combo}")
                break
        else:
            # 최대 시도 횟수 초과 시 기본 랜덤 번호 추가
            print("⚠️ 대체 번호 생성 실패, 기본 랜덤 번호 사용")
            random_combo = sorted(random.sample(range(1, 46), 6))
            final_candidates.append(random_combo)
            break
    
    # 최종 선택
    selected_index = 0
    selection_reason = "첫 번째 후보 자동 선택"
    
    try:
        print("🎯 Claude에게 최종 선택 요청 중...")
        selected_index, selection_reason = await ask_claude_for_final_selection(final_candidates, user_id)
    except Exception as e:
        errors.append(f"Claude 최종 선택: {str(e)}")
        print(f"Claude 최종 선택 실패: {e}")
    
    # 최종 선택된 번호
    if 0 <= selected_index < len(final_candidates):
        final_numbers = final_candidates[selected_index]
    else:
        final_numbers = final_candidates[0]
    
    # 보너스 번호 생성
    bonus_candidates = [i for i in range(1, 46) if i not in final_numbers]
    bonus_number = random.choice(bonus_candidates)
    
    # 과정 정보 반환
    process_info = {
        'gpt_count': len([s for s in ai_sources if s.startswith('GPT')]),
        'claude_count': len([s for s in ai_sources if s.startswith('Claude')]),
        'gemini_count': len([s for s in ai_sources if s.startswith('Gemini')]),
        'total_suggestions': len(all_ai_numbers),
        'filtered_by_winners': len(filtered_by_winners),
        'excluded_by_winners': len(all_ai_numbers) - len(filtered_by_winners),
        'unique_after_dedup': len(unique_combinations),
        'final_candidates': final_candidates,
        'selected_index': selected_index,
        'selection_reason': selection_reason,
        'errors': errors
    }
    
    return final_numbers, bonus_number, "AI 협업", process_info



# 로그인 페이지
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = USERS.get(username)
        if user:
            if user.get('is_admin'):
                if user['password'] == password:
                    login_user(User(username))
                    flash('로그인 성공!', 'success')
                    return redirect(url_for('index'))
            else:
                if check_password_hash(user['password'], password):
                    login_user(User(username))
                    flash('로그인 성공!', 'success')
                    return redirect(url_for('index'))
        flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'danger')
    return render_template('login.html')

# 로그아웃
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('로그아웃 되었습니다.', 'info')
    return redirect(url_for('login'))

# 메인 페이지 (로그인 필요)
@app.route('/')
@login_required
def index():
    return render_template('index.html', username=current_user.get_id())


@app.route('/generate-ai-collaborative')
@login_required
def generate_ai_collaborative():
    """AI 협업을 통한 로또 번호 생성"""
    try:
        # asyncio 이벤트 루프 실행
        import asyncio
        
        def run_async():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(generate_ai_collaborative_lotto_numbers(current_user.get_id()))
            finally:
                loop.close()
        
        result = run_async()
        
        if len(result) == 4:
            main_numbers, bonus_number, analysis_type, process_info = result
        else:
            main_numbers, bonus_number, analysis_type = result
            process_info = {}
        
        # 신뢰도 계산
        confidence_score = random.randint(85, 98)  # AI 협업은 높은 신뢰도
        
        # 메시지 생성
        if analysis_type == "AI 협업":
            lucky_message = f"🤖🧠💎 GPT, Claude, Gemini가 협업하여 선별한 최고의 번호입니다! (신뢰도: {confidence_score}%)"
        else:
            lucky_message = get_analysis_message(analysis_type, confidence_score)
        
        # 생성된 번호를 자동으로 저장
        user_id = current_user.get_id()
        if user_id:
            if user_id not in MY_LOTTO:
                MY_LOTTO[user_id] = []
            
            # 생성된 번호 저장 (과정 정보 포함)
            saved_data = {
                'numbers': main_numbers,
                'bonus': bonus_number,
                'type': '생성된 번호',
                'analysis_type': analysis_type,
                'confidence_score': confidence_score,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if process_info:
                saved_data['process_info'] = process_info
            
            MY_LOTTO[user_id].append(saved_data)
            save_my_lotto(MY_LOTTO)
        
        response_data = {
            'main_numbers': main_numbers,
            'bonus_number': bonus_number,
            'message': lucky_message,
            'analysis_type': analysis_type,
            'confidence_score': confidence_score,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if process_info:
            response_data['process_info'] = process_info
        
        return jsonify(response_data)
        
    except Exception as e:
        error_message = str(e)
        print(f"AI 협업 생성 중 오류: {error_message}")
        
        # 사용자에게 구체적인 오류 메시지 반환
        return jsonify({
            'success': False,
            'error': error_message,
            'error_type': 'ai_collaboration_failed'
        }), 400



# 내가 선택한 로또 번호를 조회하는 API (app 인스턴스 생성 이후 위치)
@app.route('/check-my-lotto', methods=['POST'])
@login_required
def check_my_lotto():
    try:
        data = request.get_json()
        numbers = data.get('numbers', [])
        round_number = data.get('round')
        if not isinstance(numbers, list) or len(numbers) != 6 or len(set(numbers)) != 6 or any(type(n) != int or n < 1 or n > 45 for n in numbers):
            return jsonify({'success': False, 'error': '1~45 사이의 중복 없는 6개 숫자를 입력하세요.'})
        if round_number is not None:
            try:
                round_number = int(round_number)
            except Exception:
                return jsonify({'success': False, 'error': '회차 정보가 올바르지 않습니다.'})
        else:
            round_number = get_latest_round()
        win_numbers, bonus, date = fetch_lotto_data(round_number)
        if not win_numbers:
            return jsonify({'success': False, 'error': f'{round_number}회차 정보를 불러올 수 없습니다.'})
        matched = len(set(numbers) & set(win_numbers))
        rank = 0
        rank_text = '낙첨'
        if matched == 6:
            rank = 1
            rank_text = '🎉 1등 당첨!'
        elif matched == 5 and bonus in numbers:
            rank = 2
            rank_text = '2등 (보너스번호 포함)'
        elif matched == 5:
            rank = 3
            rank_text = '3등'
        elif matched == 4:
            rank = 4
            rank_text = '4등'
        elif matched == 3:
            rank = 5
            rank_text = '5등'

        # 사용자별 선택 번호 저장
        user_id = current_user.get_id()
        if user_id:
            if user_id not in MY_LOTTO:
                MY_LOTTO[user_id] = []
            MY_LOTTO[user_id].append({
                'numbers': numbers,
                'type': '조회된 번호',
                'round': round_number,
                'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'result': rank_text,
                'rank': rank
            })
            save_my_lotto(MY_LOTTO)

        return jsonify({'success': True, 'rank': rank, 'rank_text': rank_text, 'round': round_number, 'date': date, 'win_numbers': win_numbers, 'bonus': bonus})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
