import os
import sys
import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests

# 깃허브 Secrets에서 텔레그램 토큰 및 채팅방 ID 가져오기
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 중복 발송 방지를 위한 기록 파일명
HISTORY_FILE = "sent_links.txt"

def load_sent_links():
    """이미 발송한 기사 링크 목록 불러오기"""
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_link(link):
    """발송한 기사 링크 기록 저장"""
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

def send_telegram_msg(text):
    """텔레그램 메시지 단건 발송 함수"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 설정값이 없습니다.")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ 텔레그램 기사 전송 성공!")
            return True
        else:
            print(f"❌ 텔레그램 전송 실패 (상태 코드: {response.status_code})")
            print(f"상세 내용: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 텔레그램 발송 중 네트워크 오류 발생: {e}")
        return False

def fetch_target_news():
    """
    조건에 맞는 최신 기사 1개를 탐색하는 함수
    - 제목에 필수 키워드 포함
    - 중복 발송되지 않은 기사
    - 기자 이름, 날짜, 시간 포함
    """
    # 탐색할 핵심 키워드 설정 (원하시는 키워드로 수정 가능)
    target_keywords = ["삼성전자", "반도체", "AI", "증권", "금리", "주식"]
    
    # 예시로 네이버 금융/증권 뉴스 홈 또는 특정 RSS 크롤링 (구조에 맞게 조정 필요)
    url = "https://news.naver.com/main/list.naver?mode=LS2D&mid=shm&sid1=101&sid2=258"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    sent_links = load_sent_links()
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ 뉴스 페이지 접속 실패 (코드: {response.status_code})")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 네이버 뉴스 목록형 기준 기사 아이템 파싱
        news_items = soup.select('.news_list dl, .type06_headline li, .press_edit_news li')
        
        for item in news_items:
            # 제목 및 링크 추출
            a_tag = item.select_one('a')
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            link = a_tag.get('href', '')
            
            if not title or not link or link in sent_links:
                continue
                
            # 제목에 키워드 중 하나라도 포함되어 있는지 확인
            if not any(kw in title for kw in target_keywords):
                continue
                
            # 부가 정보(기자명, 작성일시 등) 크롤링 시도 (언론사별 구조에 맞춰 조정)
            # 예시 데이터 (실제 파싱 구조가 다를 경우 대체 텍스트 삽입)
            info_tag = item.select_one('.writing, .date, .info')
            author_date_str = info_tag.get_text(strip=True) if info_tag else "기자 정보 없음 / " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            
            return {
                "title": title,
                "link": link,
                "details": author_date_str
            }
            
    except Exception as e:
        print(f"❌ 뉴스 크롤링 중 오류 발생: {e}")
        
    return None

def main():
    print("🚀 맞춤형 단건 뉴스 알림 봇 구동 시작...")
    
    # 조건에 맞는 새로운 기사 1개만 탐색
    news = fetch_target_news()
    
    if not news:
        print("ℹ️ 조건에 맞는 새로운 기사가 없습니다.")
        return

    # 요청하신 포맷으로 메시지 구성 (제목 키워드 포함, 기자/날짜/시간, 1건 단독 발송)
    message = (
        f"🚨 <b>[속보/맞춤 키워드 기사]</b>\n\n"
        f"📌 <b>제목:</b> <a href='{news['link']}'>{news['title']}</a>\n"
        f"✍️ <b>상세정보 (기자/시간):</b> {news['details']}\n\n"
        f"🔗 <a href='{news['link']}'>기사 원문 읽기</a>"
    )
    
    # 텔레그램 전송
    success = send_telegram_msg(message)
    
    if success:
        # 전송 성공 시 중복 방지용 링크 기록 저장
        save_sent_link(news['link'])
        print(f"🎉 기사 발송 및 히스토리 저장 완료: {news['title']}")
    else:
        print("⚠️ 텔레그램 전송 실패로 인해 히스토리를 저장하지 않습니다.")

if __name__ == "__main__":
    main()
