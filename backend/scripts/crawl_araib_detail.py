"""
ARAIB 항공사고조사보고서 상세 페이지 크롤링 스크립트

기존 araib_accidents.csv의 사고번호를 기반으로 상세 페이지에서 추가 정보 수집:
- 사고 개요
- 사고 원인
- 항공사
- 탑승 인원
- 피해 내용
"""

import csv
import time
import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional


LIST_URL = "https://araib.molit.go.kr/USR/airboard0201/m_34497/lst.jsp"
DETAIL_URL = "https://araib.molit.go.kr/USR/airboard0201/m_34497/dtl.jsp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def get_r_id_mapping() -> Dict[str, str]:
    """목록 페이지에서 사고번호 -> r_id 매핑 수집"""
    mapping = {}

    try:
        # 여러 페이지에서 매핑 수집
        for page in range(1, 11):  # 최대 10페이지
            params = {"currentPage": page}
            response = requests.get(LIST_URL, params=params, headers=HEADERS, timeout=30)
            soup = BeautifulSoup(response.text, "lxml")

            table = soup.find("table")
            if not table:
                break

            tbody = table.find("tbody")
            if not tbody:
                break

            rows = tbody.find_all("tr")
            if not rows:
                break

            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue

                accident_id = cols[0].get_text(strip=True)
                link = cols[1].find("a")
                if link:
                    href = link.get("href", "")
                    # javascript:dtl('352') 형태에서 r_id 추출
                    match = re.search(r"dtl\('(\d+)'\)", href)
                    if match:
                        r_id = match.group(1)
                        mapping[accident_id] = r_id
                        print(f"  매핑: 사고번호 {accident_id} -> r_id {r_id}")

            time.sleep(0.3)

    except Exception as e:
        print(f"매핑 수집 오류: {e}")

    return mapping


def fetch_detail_page(r_id: str) -> Optional[str]:
    """상세 페이지 HTML 가져오기 (POST 요청)"""
    try:
        data = {"r_id": r_id}
        response = requests.post(DETAIL_URL, data=data, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"  r_id {r_id} 페이지 조회 실패: {e}")
        return None


def parse_detail_page(html: str) -> Dict[str, str]:
    """상세 페이지에서 필요한 정보 추출

    HTML 구조:
    - 테이블 class="view_area" 내 기본 정보
    - <td colspan="4"> 내 <p> 태그들에 상세 정보
    """
    soup = BeautifulSoup(html, "lxml")

    result = {
        "사고개요": "",
        "사고원인": "",
        "항공사": "",
        "탑승인원": "",
        "피해내용": "",
    }

    # view_area 테이블에서 상세 내용 찾기
    table = soup.find("table", class_="view_area")
    if not table:
        return result

    # colspan="4"인 td 찾기 (상세 내용이 들어있는 셀)
    detail_td = table.find("td", colspan="4")
    if not detail_td:
        detail_td = table.find("td", attrs={"colspan": "4"})

    if detail_td:
        # 전체 텍스트를 줄 단위로 분리
        full_text = detail_td.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]

        # 첫 번째 의미있는 라인을 사고개요로 사용
        for line in lines[:5]:
            if len(line) > 10 and not line.startswith("ㅇ") and not line.startswith("◦"):
                result["사고개요"] = line[:200]
                break

        # 각 줄에서 정보 추출
        for line in lines:
            # 항공기 운영자 (항공사) - "ㅇ 항공기 운영자: xxx" 형태
            if "항공기 운영자" in line:
                match = re.search(r"[：:]\s*([^◦\n]+)", line)
                if match:
                    result["항공사"] = match.group(1).strip()
            # 운영자 (초경량비행장치용)
            elif line.startswith("ㅇ 운영자") or line.startswith("◦ 운영자"):
                match = re.search(r"[：:]\s*([^◦\n]+)", line)
                if match:
                    result["항공사"] = match.group(1).strip()

            # 탑승인원 - "ㅇ 탑승인원: xxx" 형태
            if "탑승인원" in line or "탑승 인원" in line:
                match = re.search(r"[：:]\s*([^◦\n]+)", line)
                if match:
                    result["탑승인원"] = match.group(1).strip()
            elif "승무원" in line and "명" in line:
                match = re.search(r"[：:]\s*([^◦\n]+)", line)
                if match:
                    result["탑승인원"] = match.group(1).strip()

            # 피해 내용
            if "인명피해" in line or "항공기피해" in line:
                match = re.search(r"[：:]\s*([^◦\n]+)", line)
                if match:
                    result["피해내용"] = match.group(1).strip()
            elif ("피해" in line or "부상" in line or "사망" in line) and ":" in line:
                match = re.search(r"[：:]\s*([^◦\n]+)", line)
                if match:
                    if not result["피해내용"]:
                        result["피해내용"] = match.group(1).strip()

            # 사고 원인
            if "사고원인" in line or "사고 원인" in line:
                match = re.search(r"[：:]\s*([^◦\n]+)", line)
                if match:
                    result["사고원인"] = match.group(1).strip()

    return result


def read_accidents_csv(filename: str = "araib_accidents.csv") -> List[Dict]:
    """기존 CSV 파일 읽기"""
    accidents = []

    try:
        with open(filename, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                accidents.append(row)
    except FileNotFoundError:
        print(f"{filename} 파일을 찾을 수 없습니다.")

    return accidents


def crawl_details(accidents: List[Dict], r_id_map: Dict[str, str]) -> List[Dict]:
    """모든 사고의 상세 정보 수집"""
    results = []
    total = len(accidents)

    for idx, accident in enumerate(accidents, 1):
        accident_id = accident.get("사고번호", "")

        if not accident_id:
            continue

        r_id = r_id_map.get(accident_id)
        if not r_id:
            print(f"[{idx}/{total}] 사고번호 {accident_id}: r_id를 찾을 수 없음")
            results.append({**accident, "사고개요": "", "사고원인": "", "항공사": "", "탑승인원": "", "피해내용": ""})
            continue

        print(f"[{idx}/{total}] 사고번호 {accident_id} (r_id: {r_id}) 상세 정보 수집 중...")

        html = fetch_detail_page(r_id)

        if html:
            detail = parse_detail_page(html)

            # 기존 정보와 상세 정보 병합
            merged = {**accident, **detail}
            results.append(merged)

            # 수집된 정보 출력
            if detail["사고개요"]:
                print(f"  -> 사고개요: {detail['사고개요'][:50]}...")
            if detail["항공사"]:
                print(f"  -> 항공사: {detail['항공사']}")
        else:
            results.append({**accident, "사고개요": "", "사고원인": "", "항공사": "", "탑승인원": "", "피해내용": ""})

        # 서버 부하 방지
        time.sleep(0.5)

    return results


def save_to_csv(data: List[Dict], filename: str = "araib_accidents_detail.csv"):
    """CSV 파일로 저장"""
    if not data:
        print("저장할 데이터가 없습니다.")
        return

    # 필드명 정의 (기존 + 신규)
    fieldnames = [
        "사고번호", "발생일자", "보고서일자", "사고유형", "소속운영자",
        "항공기기종", "발생위치", "진행상태",
        "사고개요", "사고원인", "항공사", "탑승인원", "피해내용"
    ]

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)

    print(f"\n{filename}에 {len(data)}건 저장 완료")


if __name__ == "__main__":
    print("ARAIB 항공사고 상세 정보 크롤링 시작\n")

    # 1. 목록 페이지에서 사고번호 -> r_id 매핑 수집
    print("1. 사고번호 -> r_id 매핑 수집 중...")
    r_id_map = get_r_id_mapping()
    print(f"   {len(r_id_map)}개 매핑 수집 완료\n")

    # 2. 기존 CSV 읽기
    print("2. 기존 CSV 로드 중...")
    accidents = read_accidents_csv("araib_accidents.csv")
    print(f"   {len(accidents)}건 로드 완료\n")

    if not accidents:
        print("수집할 사고 정보가 없습니다.")
        exit(1)

    # 3. 상세 정보 수집
    print("3. 상세 정보 수집 중...")
    detailed = crawl_details(accidents, r_id_map)

    # 4. CSV 저장
    save_to_csv(detailed, "araib_accidents_detail.csv")

    print("\n크롤링 완료")
