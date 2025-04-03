import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import urllib.parse
import re
from datetime import datetime
import os
import json
import base64

# 페이지 설정 및 스타일
st.set_page_config(
    page_title="네이버 뉴스 크롤러",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일 추가
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #0D47A1;
        margin-bottom: 1rem;
    }
    .stProgress > div > div {
        background-color: #1E88E5;
    }
    .css-1adrfps {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .result-container {
        background-color: #ffffff;
        border-radius: 5px;
        padding: 15px;
        margin-bottom: 10px;
        border-left: 4px solid #1E88E5;
    }
    .css-1v3fvcr {
        background-color: #f9f9f9;
    }
    .stButton>button {
        background-color: #1E88E5;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #0D47A1;
    }
</style>
""", unsafe_allow_html=True)

# 앱 제목
st.markdown('<div class="main-header">📰 네이버 뉴스 크롤러</div>', unsafe_allow_html=True)
st.markdown('네이버 뉴스를 검색어와 원하는 개수만큼 수집하여 CSV 또는 Excel 파일로 저장합니다.')

# 검색 기록 로드 함수
@st.cache_data(show_spinner=False)
def load_search_history():
    config_file = os.path.join(os.path.expanduser("~"), "naver_news_crawler_streamlit.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("search_history", [])
        except Exception as e:
            st.error(f"검색 기록 로드 중 오류: {str(e)}")
            return []
    return []

# 검색 기록 저장 함수
def save_search_history(history):
    config_file = os.path.join(os.path.expanduser("~"), "naver_news_crawler_streamlit.json")
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump({"search_history": history}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"검색 기록 저장 중 오류: {str(e)}")

# 크롤링 함수
def crawl_naver_news(query, count, progress_bar, status_text):
    try:
        # 결과 저장용 리스트
        news_list = []
        
        # 인코딩된 검색어
        encoded_query = urllib.parse.quote(query)
        
        # 필요한 페이지 수 계산 (한 페이지에 10개 기사)
        pages_needed = (count + 9) // 10
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        
        collected = 0
        
        for page in range(1, pages_needed + 1):
            if collected >= count:
                break
            
            # 페이지당 10개씩, 시작 인덱스 계산
            start = (page - 1) * 10 + 1
            
            # 네이버 뉴스 검색 URL
            url = f"https://search.naver.com/search.naver?where=news&sm=tab_jum&query={encoded_query}&start={start}"
            
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()  # 오류 검사
                soup = BeautifulSoup(response.text, 'html.parser')
                
                status_text.text(f"페이지 {page} 분석 중... (상태 코드: {response.status_code})")
                
                # 뉴스 기사 컨테이너 찾기 (최신 네이버 뉴스 검색 구조)
                news_items = soup.select("div.news_area")
                
                if not news_items:
                    status_text.text(f"페이지 {page}에서 뉴스를 찾을 수 없습니다. 구조 확인 필요.")
                    continue
                    
                status_text.text(f"페이지 {page}에서 {len(news_items)}개 뉴스 항목 발견")
                
                for item in news_items:
                    if collected >= count:
                        break
                    
                    # 제목 추출
                    title_elem = item.select_one("a.news_tit")
                    if not title_elem:
                        continue
                        
                    title = title_elem.get_text(strip=True)
                    news_url = title_elem.get('href', '')
                    
                    # 언론사 추출
                    press_elem = item.select_one("a.press")
                    press_name = press_elem.get_text(strip=True) if press_elem else "정보 없음"
                    
                    # 날짜 정보 추출
                    date_time = "날짜 정보 없음"
                    info_group = item.select_one("div.news_info")
                    if info_group:
                        date_spans = info_group.select("span.info")
                        for span in date_spans:
                            date_text = span.get_text(strip=True)
                            
                            # 다양한 날짜 형식 처리
                            if "분 전" in date_text or "시간 전" in date_text:
                                date_time = datetime.now().strftime("%Y-%m-%d")
                                break
                            elif "일 전" in date_text:
                                date_time = datetime.now().strftime("%Y-%m-%d")
                                break
                            else:
                                # YYYY.MM.DD. 형식 처리
                                date_match = re.search(r'(\d{4})\.(\d{2})\.(\d{2})\.?', date_text)
                                if date_match:
                                    year, month, day = date_match.groups()
                                    date_time = f"{year}-{month}-{day}"
                                    break
                    
                    # 본문 미리보기 추출 (있는 경우)
                    desc_elem = item.select_one("div.news_dsc")
                    description = desc_elem.get_text(strip=True) if desc_elem else "본문 미리보기 없음"
                    
                    # 네이버 뉴스 링크 찾기 (있는 경우)
                    naver_news_link = news_url  # 기본 링크
                    info_group = item.select_one("div.info_group")
                    if info_group:
                        for link in info_group.find_all('a'):
                            href = link.get('href', '')
                            if 'news.naver.com' in href:
                                naver_news_link = href
                                break
                    
                    # 결과 리스트에 추가
                    news_list.append({
                        "제목": title,
                        "언론사": press_name,
                        "날짜": date_time,
                        "미리보기": description,
                        "링크": naver_news_link
                    })
                    
                    collected += 1
                    
                    # 진행 상황 업데이트
                    progress_bar.progress(collected / count if count > 0 else 1.0)
                    status_text.text(f"크롤링 중... ({collected}/{count})")
                
            except requests.exceptions.RequestException as e:
                status_text.text(f"페이지 {page} 요청 오류: {str(e)}")
                time.sleep(2)  # 오류 발생 시 더 긴 대기 시간
                continue
            
            # 페이지 간 간격 두기 (봇 감지 방지)
            time.sleep(1.5)
            
        return news_list
    
    except Exception as e:
        st.error(f"크롤링 중 오류가 발생했습니다: {str(e)}")
        return []

# 파일 다운로드 링크 생성 함수
def get_table_download_link(df, filename, file_format):
    if file_format == 'CSV':
        csv = df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="{filename}.csv" class="download-link">다운로드 {filename}.csv</a>'
    else:  # Excel
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        writer.close()
        excel_data = output.getvalue()
        b64 = base64.b64encode(excel_data).decode()
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}.xlsx" class="download-link">다운로드 {filename}.xlsx</a>'
    return href

# 메인 앱 로직
def main():
    # 사이드바
    st.sidebar.markdown('<div class="sub-header">설정</div>', unsafe_allow_html=True)
    
    # 검색 기록 로드
    search_history = load_search_history()
    
    # 검색어 입력 (검색 기록 포함)
    if search_history:
        search_options = ["직접 입력"] + search_history
        search_option = st.sidebar.selectbox("검색 방식 선택:", search_options)
        
        if search_option == "직접 입력":
            query = st.sidebar.text_input("검색어 입력:", placeholder="검색할 키워드를 입력하세요")
        else:
            query = search_option
            st.sidebar.text_input("검색어:", value=query, disabled=True)
    else:
        query = st.sidebar.text_input("검색어 입력:", placeholder="검색할 키워드를 입력하세요")
    
    # 뉴스 개수 설정
    count = st.sidebar.slider("크롤링할 뉴스 개수:", min_value=1, max_value=100, value=20)
    
    # 파일 형식 선택
    file_format = st.sidebar.radio("저장 파일 형식:", ["Excel", "CSV"])
    
    # 파일 이름 설정
    default_filename = f"네이버뉴스_{query}_{datetime.now().strftime('%Y%m%d')}" if query else "네이버뉴스"
    filename = st.sidebar.text_input("파일명:", value=default_filename)
    
    # 검색 기록 관리
    with st.sidebar.expander("검색 기록 관리"):
        if st.button("모든 검색 기록 삭제"):
            search_history = []
            save_search_history(search_history)
            st.success("모든 검색 기록이 삭제되었습니다.")
            st.experimental_rerun()
        
        if query and st.button("현재 검색어 삭제"):
            if query in search_history:
                search_history.remove(query)
                save_search_history(search_history)
                st.success(f"'{query}' 검색어가 기록에서 삭제되었습니다.")
                st.experimental_rerun()
    
    # 메인 컨텐츠
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.markdown('<div class="sub-header">실행</div>', unsafe_allow_html=True)
        start_button = st.button("크롤링 시작", type="primary", use_container_width=True)
    
    with col1:
        # 진행 상태 표시
        progress_placeholder = st.empty()
        progress_bar = progress_placeholder.progress(0)
        status_placeholder = st.empty()
        status_text = status_placeholder.text("대기 중...")
    
    # 결과 표시 영역
    result_container = st.container()
    
    # 크롤링 시작
    if start_button:
        if not query:
            st.error("검색어를 입력해주세요.")
        else:
            # 검색 기록에 추가
            if query not in search_history:
                search_history.insert(0, query)
                # 최대 20개 유지
                if len(search_history) > 20:
                    search_history = search_history[:20]
                save_search_history(search_history)
            elif query in search_history:
                # 이미 존재하면 맨 앞으로 이동
                search_history.remove(query)
                search_history.insert(0, query)
                save_search_history(search_history)
            
            # 크롤링 시작
            with st.spinner("뉴스 크롤링 중..."):
                news_list = crawl_naver_news(query, count, progress_bar, status_text)
            
            # 결과 처리
            if news_list:
                df = pd.DataFrame(news_list)
                
                with result_container:
                    st.markdown('<div class="sub-header">크롤링 결과</div>', unsafe_allow_html=True)
                    
                    # 결과 통계
                    st.markdown(f"**총 {len(news_list)}개의 뉴스 기사를 수집했습니다.**")
                    
                    # 다운로드 링크
                    from io import BytesIO
                    download_link = get_table_download_link(df, filename, file_format)
                    st.markdown(download_link, unsafe_allow_html=True)
                    
                    # 데이터 테이블로 표시
                    st.dataframe(df, use_container_width=True)
                
                # 진행 표시 업데이트
                status_text.text(f"크롤링 완료! {len(news_list)}개 뉴스 저장됨")
                progress_bar.progress(1.0)
            else:
                status_text.text("검색 결과가 없거나 크롤링 중 오류가 발생했습니다.")
                st.warning("검색 결과가 없습니다. 다른 검색어를 시도해보세요.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"오류가 발생했습니다: {str(e)}")