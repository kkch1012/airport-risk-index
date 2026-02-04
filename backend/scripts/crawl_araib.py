"""
ARAIB 항공사고조사보고서 크롤링 스크립트

URL: https://araib.molit.go.kr/USR/airboard0201/m_34497/lst.jsp
"""

import csv
import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict


BASE_URL = "https://araib.molit.go.kr/USR/airboard0201/m_34497/lst.jsp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def fetch_page(page_num: int = 1) -> str:
    """페이지 HTML 가져오기"""
    params = {
        "currentPage": page_num,
        "srchKeyword": "",
    }

    response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def parse_accidents(html: str) -> List[Dict[str, str]]:
    """HTML에서 사고 목록 파싱"""
    soup = BeautifulSoup(html, "html.parser")
    accidents = []

    # 테이블 찾기 (여러 선택자 시도)
    table = soup.find("table", class_="tbl_list") or soup.find("table", class_="board_list") or soup.find("table")

    if not table:
        print("테이블을 찾을 수 없습니다.")
        return accidents

    # tbody 내 tr 찾기
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]  # 헤더 제외

    for row in rows:
        cols = row.find_all("td")

        if len(cols) < 5:
            continue

        # 실제 테이블 구조 기준 파싱
        # 순서: 사고번호, 발생일자, 보고서일자, 사고유형, 소속/운영자, ...
        try:
            accident = {
                "사고번호": cols[0].get_text(strip=True) if len(cols) > 0 else "",
                "발생일자": cols[1].get_text(strip=True) if len(cols) > 1 else "",
                "보고서일자": cols[2].get_text(strip=True) if len(cols) > 2 else "",
                "사고유형": cols[3].get_text(strip=True) if len(cols) > 3 else "",
                "소속운영자": cols[4].get_text(strip=True) if len(cols) > 4 else "",
                "항공기기종": cols[5].get_text(strip=True) if len(cols) > 5 else "",
                "발생위치": cols[6].get_text(strip=True) if len(cols) > 6 else "",
                "진행상태": cols[7].get_text(strip=True) if len(cols) > 7 else "",
            }

            # 빈 행 제외
            if any(v for v in accident.values()):
                accidents.append(accident)

        except Exception as e:
            print(f"행 파싱 오류: {e}")
            continue

    return accidents


def get_total_pages(html: str) -> int:
    """총 페이지 수 추출"""
    soup = BeautifulSoup(html, "html.parser")

    # 페이지네이션에서 마지막 페이지 번호 찾기
    pagination = soup.find("div", class_="paging") or soup.find("div", class_="pagination") or soup.find("ul", class_="pagination")

    if pagination:
        # 마지막 페이지 링크 찾기
        links = pagination.find_all("a")
        max_page = 1

        for link in links:
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # 숫자인 경우
            if text.isdigit():
                max_page = max(max_page, int(text))

            # href에서 페이지 번호 추출
            if "currentPage=" in href:
                try:
                    page_num = int(href.split("currentPage=")[1].split("&")[0])
                    max_page = max(max_page, page_num)
                except:
                    pass

        return max_page

    # 페이지 정보 텍스트에서 추출 시도
    page_info = soup.find(string=lambda t: t and ("/" in t or "페이지" in t))
    if page_info:
        try:
            # "1/10" 또는 "1 / 10" 형태
            parts = page_info.split("/")
            if len(parts) == 2:
                return int(parts[1].strip().split()[0])
        except:
            pass

    return 1


def crawl_all_accidents(max_pages: int = None) -> List[Dict[str, str]]:
    """모든 페이지의 사고 정보 수집"""
    all_accidents = []

    # 첫 페이지에서 총 페이지 수 확인
    print("첫 페이지 조회 중...")
    first_page_html = fetch_page(1)
    total_pages = get_total_pages(first_page_html)

    if max_pages:
        total_pages = min(total_pages, max_pages)

    print(f"총 {total_pages} 페이지 수집 예정")

    # 첫 페이지 파싱
    accidents = parse_accidents(first_page_html)
    all_accidents.extend(accidents)
    print(f"페이지 1: {len(accidents)}건 수집")

    # 나머지 페이지 수집
    for page in range(2, total_pages + 1):
        time.sleep(0.5)  # 서버 부하 방지

        try:
            html = fetch_page(page)
            accidents = parse_accidents(html)
            all_accidents.extend(accidents)
            print(f"페이지 {page}: {len(accidents)}건 수집")
        except Exception as e:
            print(f"페이지 {page} 수집 실패: {e}")
            continue

    return all_accidents


def save_to_csv(accidents: List[Dict[str, str]], filename: str = "araib_accidents.csv"):
    """CSV 파일로 저장"""
    if not accidents:
        print("저장할 데이터가 없습니다.")
        return

    fieldnames = ["사고번호", "발생일자", "보고서일자", "사고유형", "소속운영자", "항공기기종", "발생위치", "진행상태"]

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(accidents)

    print(f"\n{filename}에 {len(accidents)}건 저장 완료")


if __name__ == "__main__":
    print("ARAIB 항공사고조사보고서 크롤링 시작\n")

    # 전체 수집 (max_pages로 제한 가능)
    accidents = crawl_all_accidents(max_pages=10)

    # CSV 저장
    save_to_csv(accidents, "araib_accidents.csv")

    print("\n크롤링 완료")
