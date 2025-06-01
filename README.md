# 🎰 로또 번호 추천 시스템

Flask와 Docker를 사용한 로또 번호 추천 웹 애플리케이션입니다.

## 🚀 빠른 시작

### 필요 조건
- Docker
- Docker Compose

### 1. 프로젝트 구조 생성

다음과 같은 폴더 구조를 만들어주세요:

```
lotto-app/
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── nginx.conf (선택사항)
├── templates/
│   └── index.html
└── README.md
```

### 2. 애플리케이션 실행

#### 개발 환경 (Flask만 사용)
```bash
# 1. 프로젝트 디렉토리로 이동
cd lotto-app

# 2. Docker 이미지 빌드 및 실행
docker-compose up --build
```

#### 프로덕션 환경 (Nginx + Flask)
```bash
# Nginx 프록시와 함께 실행
docker-compose --profile production up --build
```

### 3. 웹 사이트 접속

- **개발 환경**: http://localhost:5000
- **프로덕션 환경**: http://localhost

## 📋 기능

- **로또 번호 생성**: 1-45 범위에서 중복되지 않는 6개의 번호 생성
- **보너스 번호**: 메인 번호와 중복되지 않는 보너스 번호 생성
- **행운의 메시지**: 랜덤한 응원 메시지 제공
- **반응형 디자인**: 모바일과 데스크톱 모두 지원
- **실시간 생성**: 버튼 클릭 시 즉시 새로운 번호 생성

## 🛠️ 기술 스택

- **Backend**: Python Flask
- **Frontend**: HTML, CSS, JavaScript
- **Container**: Docker, Docker Compose
- **Web Server**: Nginx (프로덕션 환경)

## 📁 주요 파일 설명

- `app.py`: Flask 웹 애플리케이션 메인 파일
- `templates/index.html`: 웹 페이지 템플릿
- `requirements.txt`: Python 패키지 의존성
- `Dockerfile`: Docker 이미지 빌드 설정
- `docker-compose.yml`: 서비스 구성 파일
- `nginx.conf`: Nginx 설정 (프로덕션용)

## 🎯 사용법

1. 웹 사이트에 접속
2. "행운의 번호 생성하기" 버튼 클릭
3. 생성된 6개의 메인 번호와 1개의 보너스 번호 확인
4. 행운의 메시지와 함께 번호를 로또 구매 시 활용

## 🔧 커스터마이징

### 번호 범위 변경
`app.py`의 `generate_lotto_numbers()` 함수에서 범위를 수정할 수 있습니다:
```python
# 현재: 1-45 (한국 로또)
main_numbers = sorted(random.sample(range(1, 46), 6))

# 예시: 1-49로 변경 (다른 나라 로또)
main_numbers = sorted(random.sample(range(1, 50), 6))
```

### 행운의 메시지 추가
`app.py`의 `get_lucky_message()` 함수에서 메시지를 추가할 수 있습니다.

## 🐳 Docker 명령어

```bash
# 애플리케이션 빌드
docker-compose build

# 백그라운드에서 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down

# 이미지와 함께 완전 삭제
docker-compose down --rmi all
```

## 📱 스크린샷 기능

- 아름다운 그라데이션 배경
- 애니메이션 효과가 있는 번호 표시
- 로딩 스피너와 부드러운 전환 효과
- 반응형 모바일 지원

## 🎊 행운을 빕니다!

이 로또 번호 추천 시스템이 여러분에게 행운을 가져다주길 바랍니다! 🍀