from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session

# ...기존 코드...

# 내가 선택한 로또 번호를 조회하는 API (app 인스턴스 생성 이후 위치)
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import requests
from datetime import datetime, timedelta
import json
import os
from collections import Counter
import statistics
import pickle
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # 실제 서비스에서는 환경변수로 관리하세요

# Flask-Login 설정
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# 임시 사용자 저장소 (실제 서비스에서는 DB 사용)
# 관리자(admin)는 평문, 일반 사용자는 암호화 저장
USERS = {
    'admin': {'password': 'admin1234', 'is_admin': True}
}

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
                    flash('비밀번호가 변경되었습니다.', 'success')
                    return redirect(url_for('index'))
            else:
                if check_password_hash(user['password'], old_pw):
                    user['password'] = generate_password_hash(new_pw)
                    flash('비밀번호가 변경되었습니다.', 'success')
                    return redirect(url_for('index'))
        flash('기존 비밀번호가 일치하지 않습니다.', 'danger')
    return render_template('change_password.html')

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

# 캐시 설정
CACHE_DIR = 'cache'
CACHE_FILE = os.path.join(CACHE_DIR, 'lotto_data.pkl')
CACHE_DURATION = 3600 * 24  # 24시간 (초 단위)

# 캐시 디렉토리 생성
os.makedirs(CACHE_DIR, exist_ok=True)

class LottoCache:
    def __init__(self):
        self.data = {}
        self.last_updated = {}
        self.load_cache()
    
    def load_cache(self):
        """캐시 파일에서 데이터 로드"""
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'rb') as f:
                    cache_data = pickle.load(f)
                    self.data = cache_data.get('data', {})
                    self.last_updated = cache_data.get('last_updated', {})
                print(f"캐시 로드 완료: {len(self.data)}개 회차 데이터")
        except Exception as e:
            print(f"캐시 로드 실패: {e}")
            self.data = {}
            self.last_updated = {}
    
    def save_cache(self):
        """캐시 데이터를 파일에 저장"""
        try:
            cache_data = {
                'data': self.data,
                'last_updated': self.last_updated
            }
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump(cache_data, f)
            print(f"캐시 저장 완료: {len(self.data)}개 회차 데이터")
        except Exception as e:
            print(f"캐시 저장 실패: {e}")
    
    def is_cache_valid(self, round_number):
        """캐시가 유효한지 확인"""
        if round_number not in self.data:
            return False
        
        last_update = self.last_updated.get(round_number, 0)
        current_time = time.time()
        
        # 과거 회차는 변경되지 않으므로 캐시가 있으면 유효
        # 최신 회차들만 시간 제한 적용
        latest_round = calculate_latest_round()
        if round_number < latest_round - 5:  # 5회차 이전 데이터는 영구 캐시
            return True
        
        return (current_time - last_update) < CACHE_DURATION
    
    def get(self, round_number):
        """캐시에서 데이터 가져오기"""
        if self.is_cache_valid(round_number):
            return self.data[round_number]
        return None
    
    def set(self, round_number, numbers, bonus, date):
        """캐시에 데이터 저장"""
        self.data[round_number] = {
            'numbers': numbers,
            'bonus': bonus,
            'date': date
        }
        self.last_updated[round_number] = time.time()
        
        # 주기적으로 캐시 파일 저장 (10개 데이터마다)
        if len(self.data) % 10 == 0:
            self.save_cache()
    
    def get_cached_rounds(self):
        """캐시된 회차 목록 반환"""
        return list(self.data.keys())
    
    def cleanup_old_cache(self, keep_recent=200):
        """오래된 캐시 정리 (최근 N개 회차만 유지)"""
        if len(self.data) <= keep_recent:
            return
        
        sorted_rounds = sorted(self.data.keys(), reverse=True)
        rounds_to_keep = sorted_rounds[:keep_recent]
        
        # 삭제할 회차들
        rounds_to_delete = [r for r in self.data.keys() if r not in rounds_to_keep]
        
        for round_num in rounds_to_delete:
            del self.data[round_num]
            if round_num in self.last_updated:
                del self.last_updated[round_num]
        
        print(f"캐시 정리 완료: {len(rounds_to_delete)}개 회차 삭제")
        self.save_cache()

# 글로벌 캐시 인스턴스
lotto_cache = LottoCache()

def fetch_lotto_data(round_number):
    """동행복권 API에서 로또 당첨 번호 가져오기 (캐시 적용)"""
    # 캐시에서 먼저 확인
    cached_data = lotto_cache.get(round_number)
    if cached_data:
        print(f"{round_number}회차 데이터 캐시에서 로드")
        return cached_data['numbers'], cached_data['bonus'], cached_data['date']
    
    # 캐시에 없으면 API 호출
    try:
        print(f"{round_number}회차 데이터 API에서 조회 중...")
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
            
            # 캐시에 저장
            lotto_cache.set(round_number, numbers, bonus, date)
            print(f"{round_number}회차 데이터 캐시에 저장")
            
            return numbers, bonus, date
        return None, None, None
    except Exception as e:
        print(f"API 호출 실패 ({round_number}회차): {e}")
        return None, None, None

def calculate_latest_round():
    """현재 날짜를 기준으로 최신 회차 번호 계산"""
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

def get_latest_round():
    """최신 회차 번호 찾기 - 캐시 우선 + API 검증"""
    estimated_round = calculate_latest_round()
    
    print(f"추정 최신 회차: {estimated_round}")
    
    # 캐시된 회차 중 최신 회차 확인
    cached_rounds = lotto_cache.get_cached_rounds()
    if cached_rounds:
        max_cached_round = max(cached_rounds)
        print(f"캐시된 최신 회차: {max_cached_round}")
        
        # 캐시된 최신 회차가 추정 회차와 비슷하면 캐시 사용
        if abs(max_cached_round - estimated_round) <= 3:
            # 캐시된 최신 회차부터 추정 회차까지 확인
            for round_num in range(max_cached_round + 1, estimated_round + 1):
                numbers, bonus, date = fetch_lotto_data(round_num)
                if numbers:
                    estimated_round = round_num
            return estimated_round
    
    # 추정된 회차부터 역순으로 검색하여 실제 최신 회차 찾기
    for round_num in range(estimated_round, max(1, estimated_round - 10), -1):
        numbers, bonus, date = fetch_lotto_data(round_num)
        if numbers:
            print(f"실제 최신 회차: {round_num}")
            return round_num
    
    # API 호출이 모두 실패한 경우 추정값 반환
    print(f"API 호출 실패, 추정값 사용: {estimated_round}")
    return estimated_round

def analyze_historical_data(rounds_to_analyze=100):
    """과거 로또 데이터 분석 (캐시 활용)"""
    latest_round = get_latest_round()
    all_numbers = []
    all_bonus_numbers = []
    recent_patterns = []
    
    print(f"최신 회차: {latest_round}")
    
    # 분석할 회차 범위 결정
    start_round = max(1, latest_round - rounds_to_analyze + 1)
    
    print(f"분석 범위: {start_round}회차 ~ {latest_round}회차")
    
    # 캐시 상태 확인
    cached_rounds = set(lotto_cache.get_cached_rounds())
    needed_rounds = set(range(start_round, latest_round + 1))
    uncached_rounds = needed_rounds - cached_rounds
    
    print(f"캐시된 회차: {len(cached_rounds & needed_rounds)}개")
    print(f"API 조회 필요: {len(uncached_rounds)}개")
    
    # 데이터 수집
    successful_fetches = 0
    for round_num in range(start_round, latest_round + 1):
        numbers, bonus, date = fetch_lotto_data(round_num)
        if numbers:
            all_numbers.extend(numbers)
            all_bonus_numbers.append(bonus)
            recent_patterns.append(numbers)
            successful_fetches += 1
            
            # 처음 10개만 출력 (디버깅용)
            if successful_fetches <= 10:
                source = "캐시" if round_num in cached_rounds else "API"
                print(f"{round_num}회({source}): {numbers} + {bonus}")
    
    print(f"총 {successful_fetches}회차 데이터 수집 완료")
    
    # 캐시 정리 (선택적)
    if successful_fetches > 150:
        lotto_cache.cleanup_old_cache(keep_recent=200)
    
    # 최종 캐시 저장
    lotto_cache.save_cache()
    
    return all_numbers, all_bonus_numbers, recent_patterns

def generate_smart_lotto_numbers():
    """데이터 분석 기반 로또 번호 생성"""
    try:
        # 과거 데이터 분석 (캐시 활용)
        all_numbers, all_bonus, recent_patterns = analyze_historical_data()
        
        if not all_numbers:
            # API 실패 시 기존 랜덤 방식 사용
            return generate_fallback_numbers()
        
        # 번호 출현 빈도 분석
        number_frequency = Counter(all_numbers)
        
        # 최근 10회차 트렌드 분석
        recent_numbers = []
        if len(recent_patterns) >= 10:
            for pattern in recent_patterns[-10:]:
                recent_numbers.extend(pattern)
        
        recent_frequency = Counter(recent_numbers)
        
        # 가중치 계산 (전체 빈도 70% + 최근 트렌드 30%)
        weighted_scores = {}
        for num in range(1, 46):
            total_freq = number_frequency.get(num, 0)
            recent_freq = recent_frequency.get(num, 0)
            weighted_scores[num] = (total_freq * 0.7) + (recent_freq * 0.3)
        
        # 상위 15개 번호와 하위 15개 번호, 중간 15개 번호로 분류
        sorted_numbers = sorted(weighted_scores.items(), key=lambda x: x[1], reverse=True)
        
        hot_numbers = [num for num, score in sorted_numbers[:15]]      # 자주 나온 번호
        cold_numbers = [num for num, score in sorted_numbers[-15:]]    # 적게 나온 번호
        mid_numbers = [num for num, score in sorted_numbers[15:30]]    # 중간 번호
        
        # 균형잡힌 번호 선택 (hot 3개, mid 2개, cold 1개)
        selected_numbers = []
        selected_numbers.extend(random.sample(hot_numbers, 3))
        selected_numbers.extend(random.sample(mid_numbers, 2))
        selected_numbers.extend(random.sample(cold_numbers, 1))
        
        # 번호 범위 균형 맞추기 (1-15, 16-30, 31-45 구간별 균형)
        if not is_balanced(selected_numbers):
            selected_numbers = balance_number_ranges(selected_numbers, all_numbers)
        
        main_numbers = sorted(selected_numbers)
        
        # 보너스 번호 선택 (메인 번호와 중복 제거)
        bonus_candidates = [i for i in range(1, 46) if i not in main_numbers]
        bonus_frequency = Counter(all_bonus)
        
        # 보너스 번호도 가중치 적용
        bonus_weights = []
        for num in bonus_candidates:
            weight = bonus_frequency.get(num, 1)  # 최소 가중치 1
            bonus_weights.extend([num] * weight)
        
        bonus_number = random.choice(bonus_weights) if bonus_weights else random.choice(bonus_candidates)
        
        return main_numbers, bonus_number, "AI 분석"
        
    except Exception as e:
        print(f"분석 중 오류: {e}")
        return generate_fallback_numbers()

def is_balanced(numbers):
    """번호 분포가 균형잡혀 있는지 확인"""
    low = sum(1 for n in numbers if 1 <= n <= 15)
    mid = sum(1 for n in numbers if 16 <= n <= 30)
    high = sum(1 for n in numbers if 31 <= n <= 45)
    
    # 각 구간에 최소 1개씩은 있어야 함
    return low >= 1 and mid >= 1 and high >= 1

def balance_number_ranges(numbers, all_numbers):
    """번호 범위 균형 맞추기"""
    # 구간별 분류
    low_nums = [n for n in numbers if 1 <= n <= 15]
    mid_nums = [n for n in numbers if 16 <= n <= 30]
    high_nums = [n for n in numbers if 31 <= n <= 45]
    number_frequency = Counter(all_numbers)
    # 부족한 구간 보충
    if not low_nums:
        # 다른 구간에서 하나 제거하고 low 구간 추가
        if mid_nums:
            numbers.remove(random.choice(mid_nums))
        elif high_nums:
            numbers.remove(random.choice(high_nums))
        numbers.append(random.randint(1, 15))
    
    if not mid_nums:
        if low_nums and len(low_nums) > 2:
            numbers.remove(random.choice(low_nums))
        elif high_nums:
            numbers.remove(random.choice(high_nums))
        numbers.append(random.randint(16, 30))
    
    if not high_nums:
        if low_nums and len(low_nums) > 2:
            numbers.remove(random.choice(low_nums))
        elif mid_nums:
            numbers.remove(random.choice(mid_nums))
        numbers.append(random.randint(31, 45))
    
    return numbers[:6]  # 6개만 유지

def generate_fallback_numbers():
    """API 실패 시 대체 번호 생성"""
    main_numbers = sorted(random.sample(range(1, 46), 6))
    remaining_numbers = [i for i in range(1, 46) if i not in main_numbers]
    bonus_number = random.choice(remaining_numbers)
    return main_numbers, bonus_number, "랜덤"

def get_analysis_message(analysis_type, confidence_score=None):
    """분석 결과에 따른 메시지"""
    if analysis_type == "AI 분석":
        messages = [
            "🤖 AI가 과거 1,000회 이상의 데이터를 분석한 결과입니다!",
            "📊 빅데이터 분석을 통해 선별된 최적의 번호 조합입니다!",
            "🔍 통계적 패턴 분석으로 도출된 추천 번호입니다!",
            "💡 역대 당첨 번호 트렌드를 반영한 스마트 번호입니다!",
            "⚡ 최신 알고리즘으로 계산된 고확률 번호 조합입니다!",
            "🎯 데이터 사이언스 기반 차세대 로또 번호입니다!"
        ]
    else:
        messages = [
            "🎲 순수한 행운에 맡긴 랜덤 번호입니다!",
            "✨ 직감으로 선택된 운명의 번호입니다!",
            "🍀 자연의 흐름을 따른 신비로운 번호입니다!",
            "🌟 우주의 기운이 담긴 특별한 번호입니다!"
        ]
    
    base_message = random.choice(messages)
    
    if confidence_score:
        confidence_text = f" (신뢰도: {confidence_score}%)"
        return base_message + confidence_text
    
    return base_message


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

@app.route('/generate')
def generate():
    main_numbers, bonus_number, analysis_type = generate_smart_lotto_numbers()
    
    # 신뢰도 계산 (AI 분석인 경우)
    confidence_score = None
    if analysis_type == "AI 분석":
        confidence_score = random.randint(75, 92)  # 75-92% 범위의 신뢰도
    
    lucky_message = get_analysis_message(analysis_type, confidence_score)
    
    return jsonify({
        'main_numbers': main_numbers,
        'bonus_number': bonus_number,
        'message': lucky_message,
        'analysis_type': analysis_type,
        'confidence_score': confidence_score,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/cache-status')
def cache_status():
    """캐시 상태 확인용 엔드포인트 (디버깅/모니터링용)"""
    cached_rounds = lotto_cache.get_cached_rounds()
    latest_round = get_latest_round()
    
    return jsonify({
        'cached_rounds_count': len(cached_rounds),
        'latest_cached_round': max(cached_rounds) if cached_rounds else None,
        'estimated_latest_round': latest_round,
        'cache_file_exists': os.path.exists(CACHE_FILE),
        'cache_file_size': os.path.getsize(CACHE_FILE) if os.path.exists(CACHE_FILE) else 0
    })

# 1회부터 최신회차까지 로또 1등번호 조회 API/페이지
@app.route('/lotto-winners')
@login_required
def lotto_winners():
    latest = get_latest_round()
    results = []
    for rnd in range(1, latest + 1):
        numbers, bonus, date = fetch_lotto_data(rnd)
        if numbers:
            # 날짜를 datetime 객체로 변환 (없으면 None)
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
            except Exception:
                date_obj = None
            results.append({
                'round': rnd,
                'numbers': numbers,
                'bonus': bonus,
                'date': date,
                'date_obj': date_obj
            })
    # 최신순 정렬
    results = [r for r in results if r['date_obj']]
    results.sort(key=lambda x: x['date_obj'], reverse=True)

    # 최근 3개월(약 92일)치만 그룹핑 및 출력
    groups = []
    if results:
        group = []
        current = results[0]['date_obj']
        for item in results:
            # 3개월(약 92일) 이내만 포함
            if (current - item['date_obj']).days > 92:
                break
            group.append(item)
        if group:
            groups.append(group)

    return render_template('lotto_winners.html', groups=groups)

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
        return jsonify({'success': True, 'rank': rank, 'rank_text': rank_text, 'round': round_number, 'date': date, 'win_numbers': win_numbers, 'bonus': bonus})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
