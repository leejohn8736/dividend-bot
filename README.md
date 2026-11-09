Dividend Alert Bot 📈🤖주식 배당락일 이틀 전인 고배당 종목을 매일 아침 텔레그램 채널로 알려주는 자동화 봇입니다.✨ 주요 기능NASDAQ 공식 API 연동: 정확하고 신뢰성 높은 배당 캘린더 데이터를 실시간 조회고배당 종목 필터링: 연간 배당 수익률 3% 이상인 알짜 종목만 엄선다양한 발송 채널 지원: 텔레그램 개인 채팅, 그룹, 공식 채널 모두 발송 가능무료 자동화 구축: GitHub Actions를 활용한 100% 무료 매일 아침 스케줄링 운영🚀 시작하기1. 시스템 요구사항Python: 3.10+텔레그램 계정 (봇 생성 및 채널 관리용)GitHub 계정 (GitHub Actions 스케줄링용)2. 환경 변수 설정 (Environment Variables)프로젝트 루트 디렉토리에 .env 파일을 생성하거나 GitHub Repository Secrets에 아래 항목을 등록합니다.변수명설명예시TELEGRAM_BOT_TOKENBotFather로부터 발급받은 텔레그램 봇 토큰123456789:AA...TELEGRAM_CHAT_ID알림을 받을 텔레그램 채널/그룹/개인 Chat ID@my_channel 또는 -100...MIN_YIELD최소 배당 수익률 기준 (기본값: 3.0%)3.03. 설치 및 실행 방법(1) 저장소 클론 및 디렉토리 이동git clone https://github.com/your-username/dividend-alert-bot.git
cd dividend-alert-bot
(2) 가상환경 생성 및 패키지 설치python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
(3) 로컬에서 실행 테스트python main.py
⏰ GitHub Actions 자동화 설정이 프로젝트는 별도의 서버 비용 없이 매일 아침 8시(KST)에 자동으로 실행되도록 설정되어 있습니다..github/workflows/daily_alert.yml 파일 예시:name: Daily Dividend Alert

on:
  schedule:
    # 매일 UTC 23:00 (한국 시간 기준 다음날 오전 08:00)
    - cron: '0 23 * * *'
  workflow_dispatch: # 수동 실행 지원

jobs:
  alert:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt

      - name: Run Dividend Bot
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python main.py
📂 프로젝트 구조dividend-alert-bot/
├── .github/
│   └── workflows/
│       └── daily_alert.yml   # GitHub Actions 스케줄러
├── config.py                 # 환경변수 및 설정 관리
├── main.py                   # 실행 메인 파일
├── nasdaq_api.py             # NASDAQ 배당 API 파싱 로직
├── telegram_bot.py           # 텔레그램 메시지 포맷팅 및 전송
├── requirements.txt          # 의존성 라이브러리 목록
└── README.md                 # 프로젝트 설명서
📜 라이선스이 프로젝트는 MIT License를 따릅니다.
