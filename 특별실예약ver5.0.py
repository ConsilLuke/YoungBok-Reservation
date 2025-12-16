import streamlit as st
from datetime import datetime, date, timedelta
import os

# Google Sheets 관련 import
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSHEET_AVAILABLE = True
except Exception:
    GSHEET_AVAILABLE = False

# ==================== 설정 ====================
st.set_page_config(
    page_title="특별실 예약 시스템",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 데이터 정의 ====================
SPECIAL_ROOMS = [
    "[4층]멀티홀", "[4층]향나무채(자습실)", "[4층]목련채(자습실)", "[4층]미술실", "[4층]물리실",
    "[4층]지구과학실", "[4층]특별교실C(크롬북실)", "[4층]진로상담실", "[4층]동아리실",
    "[4층]학생회실", "[3층]힐링존B", "[3층]특별교실B", "[3층]융합교실",
    "[2층]힐링존A", "[2층]컴퓨터실B", "[1층]YB스튜디오(방송실)", "[1층]YB아트리움",
    "[1층]화학실", "[1층]컴퓨터실A", "[1층]생물실", "[1층]회의실", "[외부]음악실", "[외부]강당", "[신관]특별교실D"
]

PERIODS_DATA = [
    {"key": "조회전", "display": "조회 전 (07:40-08:30)"},
    {"key": "1교시", "display": "1교시 (09:00-09:50)"},
    {"key": "2교시", "display": "2교시 (10:00-10:50)"},
    {"key": "3교시", "display": "3교시 (11:00-11:50)"},
    {"key": "4교시", "display": "4교시 (12:00-12:50)"},
    {"key": "점심1", "display": "점심시간1 (12:50-13:20)"},
    {"key": "점심2", "display": "점심시간2 (13:20-13:50)"},
    {"key": "5교시", "display": "5교시 (13:50-14:40)"},
    {"key": "6교시", "display": "6교시 (14:50-15:40)"},
    {"key": "7교시", "display": "7교시 (15:50-16:40)"},
    {"key": "8교시", "display": "8교시 (16:50-17:40)"},
    {"key": "9교시", "display": "9교시 (17:50-18:40)"},
    {"key": "이후", "display": "이후 (18:50-)"},
]

COLUMNS = ["날짜", "특별실", "교시", "이름", "직책", "사유", "신청일시", "IP주소"]

# ==================== IP 주소 가져오기 ====================
def get_client_ip():
    """접속자 IP 주소 가져오기"""
    try:
        # Streamlit Cloud에서는 x-forwarded-for 헤더 사용
        headers = st.context.headers
        ip = headers.get("x-forwarded-for", "알수없음")
        # 여러 IP가 있으면 첫 번째 (실제 클라이언트)
        if "," in ip:
            ip = ip.split(",")[0].strip()
        return ip
    except:
        return "알수없음"

# ==================== Google Sheets 연결 ====================
@st.cache_resource
def get_google_sheet():
    """Google Sheets 연결"""
    if not GSHEET_AVAILABLE:
        return None
    
    try:
        # Streamlit Cloud secrets 사용
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if 'private_key' in creds_dict:
                creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
            
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            client = gspread.authorize(creds)
            
            sheet_url = st.secrets.get("spreadsheet_url", "")
            if not sheet_url:
                return None
            
            spreadsheet = client.open_by_url(sheet_url)
            worksheet = spreadsheet.sheet1
            
            # 헤더 확인/생성
            try:
                existing_headers = worksheet.row_values(1)
                if not existing_headers:
                    worksheet.append_row(COLUMNS)
            except:
                worksheet.append_row(COLUMNS)
            
            return worksheet
        
        return None
        
    except Exception as e:
        st.error(f"Google Sheets 연결 실패: {e}")
        return None

# ==================== 데이터 관리 ====================
def load_reservations():
    """예약 데이터 로드"""
    sheet = st.session_state.get('sheet')
    if not sheet:
        return []
    
    try:
        return sheet.get_all_records()
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return []

def save_reservation(reservation):
    """예약 저장"""
    sheet = st.session_state.get('sheet')
    if not sheet:
        return False, "스프레드시트 연결 안됨"
    
    try:
        records = sheet.get_all_records()
        for r in records:
            if (str(r.get("날짜", "")) == reservation["날짜"] and 
                r.get("특별실", "") == reservation["특별실"] and 
                r.get("교시", "") == reservation["교시"]):
                return False, f"이미 예약됨: {r.get('이름')}님"
        
        row = [reservation.get(col, "") for col in COLUMNS]
        sheet.append_row(row)
        return True, "예약 완료"
        
    except Exception as e:
        return False, f"저장 실패: {e}"

def delete_reservation(reservation):
    """예약 삭제"""
    sheet = st.session_state.get('sheet')
    if not sheet:
        return False
    
    try:
        records = sheet.get_all_records()
        for i, r in enumerate(records):
            if (str(r.get("날짜", "")) == str(reservation.get("날짜", "")) and
                r.get("특별실", "") == reservation.get("특별실", "") and
                r.get("교시", "") == reservation.get("교시", "") and
                r.get("이름", "") == reservation.get("이름", "")):
                sheet.delete_rows(i + 2)
                return True
        return False
    except Exception as e:
        st.error(f"삭제 실패: {e}")
        return False

def get_reserved_periods(date_str, room):
    """특정 날짜/특별실의 예약된 교시 조회"""
    reservations = load_reservations()
    reserved = {}
    for res in reservations:
        if str(res.get("날짜", "")) == date_str and res.get("특별실", "") == room:
            reserved[res.get("교시", "")] = {
                "이름": res.get("이름", ""), 
                "사유": res.get("사유", ""),
                "직책": res.get("직책", "")
            }
    return reserved

# ==================== 세션 상태 초기화 ====================
def init_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'role' not in st.session_state:
        st.session_state.role = ""
    if 'sheet' not in st.session_state:
        st.session_state.sheet = get_google_sheet()
    if 'page' not in st.session_state:
        st.session_state.page = "login"

# ==================== 페이지: 로그인 ====================
def page_login():
    st.title("🏫 특별실 예약 시스템 v5.3")
    
    if st.session_state.sheet:
        st.success("📊 Google Sheets 연결됨")
    else:
        st.error("❌ Google Sheets 연결 실패 - 관리자에게 문의하세요")
        st.stop()
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("로그인")
        
        with st.form("login_form"):
            name = st.text_input("이름", placeholder="홍길동")
            role = st.selectbox("직책", ["선택하세요", "교사", "학생"])
            submitted = st.form_submit_button("로그인", use_container_width=True)
            
            if submitted:
                if not name.strip():
                    st.error("이름을 입력해주세요.")
                elif role == "선택하세요":
                    st.error("직책을 선택해주세요.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.username = name.strip()
                    st.session_state.role = role
                    st.session_state.page = "main"
                    st.rerun()

# ==================== 페이지: 메인 메뉴 ====================
def page_main():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("🏫 특별실 예약 시스템")
    with col2:
        st.write("")
        st.write(f"👤 **{st.session_state.username}** ({st.session_state.role})")
        if st.button("로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.page = "login"
            st.rerun()
    
    st.caption("📊 Google Sheets 실시간 동기화")
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📅 예약하기", use_container_width=True, type="primary"):
            st.session_state.page = "reserve"
            st.rerun()
    
    with col2:
        if st.button("📋 내 예약 조회", use_container_width=True):
            st.session_state.page = "my_reservations"
            st.rerun()
    
    with col3:
        if st.button("📊 전체 예약 현황", use_container_width=True):
            st.session_state.page = "all_reservations"
            st.rerun()
    
    with col4:
        if st.button("🔄 새로고침", use_container_width=True):
            st.cache_resource.clear()
            st.session_state.sheet = get_google_sheet()
            st.rerun()
    
    st.markdown("---")
    
    # 오늘의 예약 현황
    st.subheader("📌 오늘의 예약 현황")
    today = date.today().strftime("%Y-%m-%d")
    reservations = load_reservations()
    today_res = [r for r in reservations if str(r.get("날짜", "")) == today]
    
    if today_res:
        for res in sorted(today_res, key=lambda x: x.get("교시", "")):
            col1, col2, col3, col4 = st.columns([2, 2, 1, 3])
            col1.write(f"🏫 {res.get('특별실', '')}")
            col2.write(f"⏰ {res.get('교시', '')}")
            col3.write(f"👤 {res.get('이름', '')}")
            col4.write(f"📝 {str(res.get('사유', ''))[:30]}...")
    else:
        st.info("오늘 예약된 특별실이 없습니다.")

# ==================== 페이지: 예약하기 ====================
def page_reserve():
    st.title("📅 특별실 예약")
    
    if st.button("← 메인으로"):
        st.session_state.page = "main"
        st.rerun()
    
    st.markdown("---")
    
    # 배치도
    st.subheader("🗺️ 학교 배치도")
    if os.path.exists("영복배치도.jpg"):
        st.image("영복배치도.jpg", caption="영복여고 특별실 배치도", use_container_width=True)
    else:
        st.info("💡 '영복배치도.jpg' 파일을 GitHub에 업로드하면 배치도가 표시됩니다.")
    
    st.markdown("---")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("1️⃣ 특별실 선택")
        selected_room = st.selectbox("특별실을 선택하세요", SPECIAL_ROOMS)
    
    with col2:
        st.subheader("2️⃣ 날짜 선택")
        selected_date = st.date_input(
            "날짜를 선택하세요",
            min_value=date.today(),
            max_value=date.today() + timedelta(days=30),
            value=date.today()
        )
    
    st.markdown("---")
    st.subheader("3️⃣ 시간대 선택")
    
    date_str = selected_date.strftime("%Y-%m-%d")
    reserved = get_reserved_periods(date_str, selected_room)
    
    st.caption(f"📍 {selected_room} | 📅 {date_str}")
    
    # ✅ 교시 체크박스를 세로로 순서대로 배치 (모바일 호환)
    selected_periods = []
    
    for i, period in enumerate(PERIODS_DATA):
        if period["key"] in reserved:
            reserver = reserved[period["key"]]
            st.checkbox(
                f"🔒 {period['display']} - {reserver['이름']}",
                value=False,
                disabled=True,
                key=f"period_{i}"
            )
        else:
            if st.checkbox(f"✅ {period['display']}", key=f"period_{i}"):
                selected_periods.append(period["key"])
    
    st.markdown("---")
    st.subheader("4️⃣ 예약 정보")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**신청자:** {st.session_state.username} ({st.session_state.role})")
        st.write(f"**특별실:** {selected_room}")
        st.write(f"**날짜:** {date_str}")
        st.write(f"**선택 시간:** {', '.join(selected_periods) if selected_periods else '선택 없음'}")
    
    with col2:
        reason = st.text_area("예약 사유", placeholder="예약 사유를 입력하세요", height=100)
    
    st.markdown("---")
    
    if st.button("🎯 예약 신청", use_container_width=True, type="primary"):
        if not selected_periods:
            st.error("최소 하나의 시간대를 선택해주세요.")
        elif not reason.strip():
            st.error("예약 사유를 입력해주세요.")
        else:
            success_count = 0
            fail_messages = []
            
            for period in selected_periods:
                reservation = {
                    "날짜": date_str,
                    "특별실": selected_room,
                    "교시": period,
                    "이름": st.session_state.username,
                    "직책": st.session_state.role,
                    "사유": reason.strip(),
                    "신청일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "IP주소": get_client_ip(),
                }
                success, msg = save_reservation(reservation)
                if success:
                    success_count += 1
                else:
                    fail_messages.append(f"{period}: {msg}")
            
            if success_count > 0:
                st.success(f"✅ {success_count}개 시간대 예약 완료!")
                st.balloons()
            if fail_messages:
                for msg in fail_messages:
                    st.warning(msg)

# ==================== 페이지: 내 예약 조회 ====================
def page_my_reservations():
    st.title("📋 내 예약 내역")
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← 메인으로"):
            st.session_state.page = "main"
            st.rerun()
    with col2:
        if st.button("🔄 새로고침"):
            st.rerun()
    
    st.markdown("---")
    
    reservations = load_reservations()
    my_reservations = [r for r in reservations if r.get("이름") == st.session_state.username]
    
    if not my_reservations:
        st.info("예약 내역이 없습니다.")
        return
    
    st.caption(f"총 {len(my_reservations)}건의 예약")
    my_reservations.sort(key=lambda x: (str(x.get("날짜", "")), x.get("교시", "")), reverse=True)
    
    for i, res in enumerate(my_reservations):
        col1, col2, col3, col4, col5 = st.columns([2, 2, 1.5, 3, 1])
        
        col1.write(f"📅 **{res.get('날짜', '')}**")
        col2.write(f"🏫 {res.get('특별실', '')}")
        col3.write(f"⏰ {res.get('교시', '')}")
        col4.write(f"📝 {str(res.get('사유', ''))[:25]}...")
        
        with col5:
            if st.button("🗑️ 취소", key=f"delete_{i}"):
                if delete_reservation(res):
                    st.success("예약이 취소되었습니다.")
                    st.rerun()
        
        st.divider()

# ==================== 페이지: 전체 예약 현황 ====================
def page_all_reservations():
    st.title("📊 전체 예약 현황")
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← 메인으로"):
            st.session_state.page = "main"
            st.rerun()
    with col2:
        if st.button("🔄 새로고침"):
            st.rerun()
    
    st.markdown("---")
    
    reservations = load_reservations()
    
    st.subheader("🔍 필터")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        dates = ["전체"] + sorted(list(set(str(r.get("날짜", "")) for r in reservations)), reverse=True)
        filter_date = st.selectbox("날짜", dates)
    
    with col2:
        rooms = ["전체"] + sorted(list(set(r.get("특별실", "") for r in reservations)))
        filter_room = st.selectbox("특별실", rooms)
    
    with col3:
        periods = ["전체"] + [p["key"] for p in PERIODS_DATA]
        filter_period = st.selectbox("교시", periods)
    
    with col4:
        names = ["전체"] + sorted(list(set(r.get("이름", "") for r in reservations)))
        filter_name = st.selectbox("신청자", names)
    
    filtered = reservations
    if filter_date != "전체":
        filtered = [r for r in filtered if str(r.get("날짜", "")) == filter_date]
    if filter_room != "전체":
        filtered = [r for r in filtered if r.get("특별실", "") == filter_room]
    if filter_period != "전체":
        filtered = [r for r in filtered if r.get("교시", "") == filter_period]
    if filter_name != "전체":
        filtered = [r for r in filtered if r.get("이름", "") == filter_name]
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("전체 예약", f"{len(reservations)}건")
    col2.metric("필터 결과", f"{len(filtered)}건")
    col3.metric("데이터 저장소", "📊 Google Sheets")
    
    st.markdown("---")
    
    if not filtered:
        st.info("조건에 맞는 예약이 없습니다.")
        return
    
    import pandas as pd
    df = pd.DataFrame(filtered)
    display_columns = ["날짜", "특별실", "교시", "이름", "직책", "사유", "신청일시", "IP주소"]
    available_columns = [col for col in display_columns if col in df.columns]
    
    if available_columns:
        df = df[available_columns]
        df = df.sort_values(by=["날짜", "교시"], ascending=[False, True])
        st.dataframe(df, use_container_width=True, hide_index=True)

# ==================== 메인 실행 ====================
def main():
    init_session_state()
    
    if not st.session_state.sheet:
        st.error("❌ Google Sheets 연결 실패")
        st.info("관리자에게 문의하세요.")
        st.stop()
    
    if not st.session_state.logged_in:
        page_login()
    else:
        page = st.session_state.page
        if page == "main":
            page_main()
        elif page == "reserve":
            page_reserve()
        elif page == "my_reservations":
            page_my_reservations()
        elif page == "all_reservations":
            page_all_reservations()
        else:
            page_main()

if __name__ == "__main__":
    main()
