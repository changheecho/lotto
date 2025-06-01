from flask import Flask, render_template, jsonify
import random
from datetime import datetime

app = Flask(__name__)

def generate_lotto_numbers():
    """1등 로또 번호 6개와 보너스 번호 1개를 생성"""
    # 1-45 중에서 6개의 서로 다른 번호 선택
    main_numbers = sorted(random.sample(range(1, 46), 6))
    
    # 보너스 번호는 메인 번호와 중복되지 않게 선택
    remaining_numbers = [i for i in range(1, 46) if i not in main_numbers]
    bonus_number = random.choice(remaining_numbers)
    
    return main_numbers, bonus_number

def get_lucky_message():
    """행운의 메시지 랜덤 선택"""
    messages = [
        "오늘이 당신의 행운의 날입니다! 🍀",
        "대박의 기운이 느껴집니다! ✨",
        "행운의 여신이 미소짓고 있어요! 😊",
        "좋은 일이 생길 것 같은 예감이... 🌟",
        "오늘은 특별한 날이 될 거예요! 🎯",
        "행운이 함께하길 바랍니다! 🎊"
    ]
    return random.choice(messages)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate')
def generate():
    main_numbers, bonus_number = generate_lotto_numbers()
    lucky_message = get_lucky_message()
    
    return jsonify({
        'main_numbers': main_numbers,
        'bonus_number': bonus_number,
        'message': lucky_message,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)