import os
import time
import datetime
import re
import requests
from bs4 import BeautifulSoup

# Selenium 관련 라이브러리
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 크롬 드라이버 자동 관리 라이브러리
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def run_scraper():
    # ---------------------------------------------------------
    # 1. 기본 설정
    # ---------------------------------------------------------
    save_dir = "pdf_downloads"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    today = datetime.datetime.now()
    date_str = today.strftime("%m%d") 
    target_keyword = "하루에 하나"
    
    print(f"[{today.strftime('%Y-%m-%d')}] '{target_keyword}' ({date_str}) 탐색 시작...")

    # ---------------------------------------------------------
    # 2. Selenium 설정
    # ---------------------------------------------------------
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    # 창 크기를 크게 설정하여 버튼이 잘 보이도록 함
    chrome_options.add_argument("--window-size=1920,1080") 
    
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    chrome_options.add_argument(f"user-agent={user_agent}")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"드라이버 초기화 오류: {e}")
        return

    url = "https://www.hanaw.com/main/research/research/RC_000000_M.cmd"
    
    try:
        driver.get(url)
        # body가 로드될 때까지 대기
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2)

        found = False
        max_clicks = 5
        
        for i in range(max_clicks + 1):
            print(f"\n--- 페이지 스캔 중 (현재 더보기 클릭 횟수: {i}) ---")
            
            # 현재 DOM 파싱
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # ---------------------------------------------------------
            # 3. 게시글 탐색
            # ---------------------------------------------------------
            for a_tag in soup.find_all('a'):
                text = a_tag.get_text().strip()
                href = a_tag.get('href', '')

                if target_keyword in text and date_str in text:
                    print(f"🎯 타겟 발견! : {text}")
                    
                    download_link = None
                    if "download.cmd" in href:
                        download_link = href
                        print(" -> 링크 타입: 직접 다운로드")
                    else:
                        parent_tr = a_tag.find_parent('tr')
                        if parent_tr:
                            file_btn = parent_tr.find('a', href=re.compile(r'download|file', re.I))
                            if file_btn:
                                download_link = file_btn['href']
                                print(" -> 링크 타입: 첨부파일 버튼")

                    if not download_link:
                        print(" -> ⚠️ 다운로드 링크를 찾을 수 없습니다.")
                        continue

                    if not download_link.startswith('http'):
                        full_url = "https://www.hanaw.com" + download_link
                    else:
                        full_url = download_link
                    
                    safe_title = text.replace('/', '_').replace('\\', '_').strip()
                    filename = f"{save_dir}/{today.strftime('%Y-%m-%d')}_{safe_title}.pdf"
                    
                    print(f" -> 다운로드 시도: {full_url}")

                    # 쿠키 동기화 후 다운로드
                    session = requests.Session()
                    cookies = driver.get_cookies()
                    for cookie in cookies:
                        session.cookies.set(cookie['name'], cookie['value'])
                    
                    headers = {"User-Agent": user_agent}
                    file_res = session.get(full_url, headers=headers)
                    
                    if file_res.status_code == 200:
                        with open(filename, 'wb') as f:
                            f.write(file_res.content)
                        print(f"✅ 다운로드 성공: {filename}")
                        found = True
                        break
                    else:
                        print(f"❌ 다운로드 실패 (HTTP {file_res.status_code})")
            
            if found:
                break
            
            # ---------------------------------------------------------
            # 4. '더보기' 버튼 클릭 (강력한 방식)
            # ---------------------------------------------------------
            if i < max_clicks:
                try:
                    # 1) 버튼이 존재할 때까지 대기 (최대 5초)
                    more_btn = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "button.j-moreListBtn"))
                    )
                    
                    # 2) 스크롤을 요소의 중앙으로 이동 (가려짐 방지)
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_btn)
                    time.sleep(0.5) 
                    
                    # 3) JavaScript로 강제 클릭 (가장 확실한 방법)
                    driver.execute_script("arguments[0].click();", more_btn)
                    print("⬇️ '더보기' 버튼 클릭 완료 (JS)")
                    
                    # 4) 데이터 로딩 대기
                    time.sleep(3)
                    
                except TimeoutException:
                    print("🚫 '더보기' 버튼을 찾을 수 없습니다. (마지막 페이지일 가능성)")
                    break
                except Exception as e:
                    print(f"⚠️ 버튼 클릭 중 오류 발생: {e}")
                    break
            else:
                print("⏹️ 최대 탐색 횟수에 도달하여 종료합니다.")

        if not found:
            print(f"❌ 결과: 오늘({date_str})자 '{target_keyword}' 리포트를 찾지 못했습니다.")

    except Exception as e:
        print(f"치명적 오류 발생: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_scraper()