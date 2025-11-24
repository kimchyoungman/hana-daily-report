import os
import time
import datetime
import re
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import pdfplumber

# Selenium 관련 라이브러리
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------
# [설정] Gemini API 설정
# ---------------------------------------------------------
# GitHub Secrets 또는 .env에서 GEMINI_API_KEY를 가져옵니다.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def summarize_pdf_with_gemini(pdf_path, output_path):
    """
    PDF 내용을 추출하여 Gemini에게 약 3장 분량의 상세 요약을 요청하고 저장하는 함수
    """
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY가 설정되지 않아 요약 과정을 건너뜁니다.")
        return

    print(f"🤖 Gemini AI가 상세 요약을 시작합니다... (대상: {os.path.basename(pdf_path)})")
    
    # 1. PDF 텍스트 추출 (pdfplumber 사용)
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
    except Exception as e:
        print(f"❌ PDF 텍스트 추출 실패: {e}")
        return

    # 텍스트가 너무 짧으면 요약 스킵
    if len(full_text) < 100:
        print("⚠️ 추출된 텍스트가 너무 적어 요약을 건너뜁니다.")
        return

    # 2. Gemini 모델 설정 및 요청
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # 긴 문맥 처리에 강한 1.5 Flash 모델 사용
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 3장 분량 유도를 위한 구체적인 프롬프트
        prompt = f"""
        당신은 월가에서 20년 이상 경력을 쌓은 수석 금융 애널리스트입니다.
        아래 제공된 금융 리포트의 원문을 바탕으로, 투자자가 읽기 편하면서도 깊이 있는 **'심층 분석 보고서'**를 작성해주세요.

        [작성 지침]
        1. **분량 필수**: A4 용지 3장 분량이 나올 수 있도록 내용을 아주 상세하게 풀어서 작성하십시오. (공백 제외 최소 2500자 이상)
        2. **언어**: 한국어(Korean)로 작성하세요.
        3. **형식**: 가독성 높은 Markdown 형식을 사용하세요 (볼드체, 리스트, 헤더 등 활용).
        4. **포함해야 할 핵심 섹션**:
           - 📊 **시장/산업 전망 (Market Outlook)**: 거시 경제 및 해당 산업의 현재 상황과 미래 전망
           - 🏢 **주요 기업 분석 (Key Companies)**: 언급된 종목들의 실적 추이, 목표 주가, 투자의견
           - 📈 **핵심 데이터 (Key Metrics)**: 리포트에 나온 매출액, 영업이익, PER, PBR 등 구체적인 수치를 반드시 표나 텍스트로 인용할 것
           - 💡 **투자 포인트 및 리스크 (Investment Points & Risks)**: 매수해야 할 이유와 주의해야 할 점
           - 📝 **종합 결론 (Conclusion)**: 애널리스트로서의 최종 인사이트

        [리포트 원문]
        {full_text}
        """
        
        # 텍스트 생성 요청
        response = model.generate_content(prompt)
        
        # 3. 결과 파일 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# 📑 {os.path.basename(pdf_path)} 심층 요약 보고서\n\n")
            f.write(f"**분석 일시:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**원본 파일:** {os.path.basename(pdf_path)}\n\n")
            f.write("---\n\n")
            f.write(response.text)
            
        print(f"✅ 요약 보고서 저장 완료: {output_path}")
        
    except Exception as e:
        print(f"❌ Gemini API 호출 중 오류 발생: {e}")

def run_scraper():
    # ---------------------------------------------------------
    # 1. 기본 설정 및 준비
    # ---------------------------------------------------------
    # 결과물 저장 폴더 생성
    save_dir = "pdf_downloads"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # 오늘 날짜 (예: 11월 24일 -> "1124")
    today = datetime.datetime.now()
    date_str = today.strftime("%m%d") 
    target_keyword = "하루에 하나"

    print(f"[{today.strftime('%Y-%m-%d')}] 스크래퍼 시작 (Target: '{target_keyword}' + '{date_str}')")

    # ---------------------------------------------------------
    # 2. Selenium 브라우저 설정 (Headless 모드)
    # ---------------------------------------------------------
    chrome_options = Options()
    chrome_options.add_argument("--headless") # 화면 없이 실행
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # 봇 차단 회피용 User-Agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    driver = None
    
    try:
        # 크롬 드라이버 자동 설치 및 실행
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 사이트 접속
        url = "https://www.hanaw.com/main/research/research/RC_000000_M.cmd"
        driver.get(url)
        
        # 페이지 로딩 대기 (최대 15초)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3) # 안정적인 로딩을 위해 추가 대기
        
        # HTML 파싱
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        found = False

        # ---------------------------------------------------------
        # 3. 게시글 탐색 및 다운로드 로직
        # ---------------------------------------------------------
        for a_tag in soup.find_all('a'):
            text = a_tag.get_text().strip()
            
            # 제목에 키워드와 오늘 날짜가 모두 포함된지 확인
            if target_keyword in text and date_str in text:
                print(f"🎯 타겟 게시글 발견: {text}")
                
                # 다운로드 링크 찾기
                link = None
                parent_tr = a_tag.find_parent('tr')
                
                # (1) 첨부파일 아이콘 버튼 우선 탐색
                if parent_tr:
                    file_btn = parent_tr.find('a', href=re.compile(r'download|file|down', re.I))
                    if file_btn: link = file_btn['href']
                
                # (2) 없으면 본문 링크 사용
                if not link: link = a_tag.get('href')
                
                if not link: continue

                # URL 절대경로 변환
                if link.startswith('http'): download_url = link
                elif link.startswith('/'): download_url = "https://www.hanaw.com" + link
                else: 
                    print(f"⚠️ 처리할 수 없는 링크 형식: {link}")
                    continue

                print(f"🔗 다운로드 링크: {download_url}")

                # 파일명 생성 (특수문자 제거)
                safe_title = text.replace('/', '_').replace('\\', '_').strip()
                pdf_filename = f"{save_dir}/{today.strftime('%Y-%m-%d')}_{safe_title}.pdf"
                summary_filename = f"{save_dir}/{today.strftime('%Y-%m-%d')}_{safe_title}_summary.md"

                # PDF 다운로드 실행 (requests 사용)
                headers = {"User-Agent": "Mozilla/5.0"}
                file_res = requests.get(download_url, headers=headers)
                file_res.raise_for_status()
                
                with open(pdf_filename, 'wb') as f:
                    f.write(file_res.content)
                
                print(f"✅ PDF 다운로드 완료: {pdf_filename}")
                
                # -----------------------------------------------------
                # 4. Gemini AI 요약 실행
                # -----------------------------------------------------
                summarize_pdf_with_gemini(pdf_filename, summary_filename)
                
                found = True
                break # 목표를 찾았으니 루프 종료

        if not found:
            print(f"❌ 오늘({date_str})자 '{target_keyword}' 리포트를 찾지 못했습니다.")

    except Exception as e:
        print(f"🚨 치명적 오류 발생: {e}")
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    run_scraper()
