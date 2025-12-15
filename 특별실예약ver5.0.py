import streamlit as st
from datetime import datetime, date, timedelta
import json
import os

# Firebase 관련 import (선택)
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except Exception:
    FIREBASE_AVAILABLE = False

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

DATA_FILE = "reservations.json"

# ==================== Firebase 초기화 ====================
def init_firebase():
    """Firebase 초기화"""
    if not FIREBASE_AVAILABLE:
        return None
    try:
        if not os.path.exists("firebase_key.json"):
            return None
        if not firebase_admin._apps:
            cred = credentials.Certificate("firebase_key.json")
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        st.error(f"Firebase 연결 실패: {e}")
        return None

# ==================== 데이터 관리 ====================
def load_reservations():
    """예약 데이터 로드 (클라우드 우선)"""
    db = st.session_state.get('db')
    if db:
        try:
            cloud_data = [doc.to_dict() for doc in db.collection('reservations').stream()]
            if cloud_data:
                save_reservations_local(cloud_data)
                return cloud_data
        except Exception as e:
            st.warning(f"클라우드 로드 실패, 로컬 사용: {e}")
    return load_reservations_local()

def load_reservations_local():
    """로컬 JSON 파일에서 로드"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_reservations_local(data):
    """로컬 JSON 파일에 저장"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_reservation(reservation):
    """예약 저장 (로컬 + 클라우드)"""
    reservations = load_reservations_local()
    
    # 중복 체크
    for r in reservations:
        if (r["날짜"] == reservation["날짜"] and 
            r["특별실"] == reservation["특별실"] and 
            r["교시"] == reservation["교시"]):
            return False, f"이미 예약됨: {r['이름']}님"
    
    reservations.append(reservation)
    save_reservations_local(reservations)
    
    # 클라우드 저장
    db = st.session_state.get('db')
    if db:
        try:
            doc_id = f"{reservation['날짜']}_{reservation['특별실']}_{reservation['교시']}_{reservation['이름']}"
            db.collection('reservations').document(doc_id).set(reservation)
        except Exception as e:
            st.warning(f"클라우드 저장 실패: {e}")
    
    return True, "예약 완료"

def delete_reservation(reservation):
    """예약 삭제 (로컬 + 클라우드)"""
    reservations = load_reservations_local()
    reservations = [r for r in reservations if not (
        r.get("날짜") == reservation.get("날짜") and
        r.get("특별실") == reservation.get("특별실") and
        r.get("교시") == reservation.get("교시") and
        r.get("이름") == reservation.get("이름")
    )]
    save_reservations_local(reservations)
    
    # 클라우드 삭제
    db = st.session_state.get('db')
    if db:
        try:
            doc_id = f"{reservation['날짜']}_{reservation['특별실']}_{reservation['교시']}_{reservation['이름']}"
            db.collection('reservations').document(doc_id).delete()
        except Exception as e:
            st.warning(f"클라우드 삭제 실패: {e}")

def get_reserved_periods(date_str, room):
    """특정 날짜/특별실의 예약된 교시 조회"""
    reservations = load_reservations()
    reserved = {}
    for res in reservations:
        if res.get("날짜") == date_str and res.get("특별실") == room:
            reserved[res.get("교시")] = {
                "이름": res.get("이름"), 
                "사유": res.get("사유"),
                "직책": res.get("직책")
            }
    return reserved

# ==================== 세션 상태 초기화 ====================
def init_session_state():
    """세션 상태 초기화"""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'role' not in st.session_state:
        st.session_state.role = ""
    if 'db' not in st.session_state:
        st.session_state.db = init_firebase()
    if 'page' not in st.session_state:
        st.session_state.page = "login"

# ==================== 페이지: 로그인 ====================
def page_login():
    st.title("🏫 특별실 예약 시스템 v5.0")
    
    # 클라우드 상태 표시
    if st.session_state.db:
        st.success("🌐 클라우드 연결됨")
    else:
        st.warning("💻 로컬 모드 (Firebase 미연결)")
    
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
    # 헤더
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
    
    # 클라우드 상태
    if st.session_state.db:
        st.caption("🌐 클라우드 동기화 활성")
    else:
        st.caption("💻 로컬 저장 모드")
    
    st.markdown("---")
    
    # 메뉴 버튼
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
        if st.button("🔄 데이터 새로고침", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    st.markdown("---")
    
    # 오늘의 예약 현황 미리보기
    st.subheader("📌 오늘의 예약 현황")
    today = date.today().strftime("%Y-%m-%d")
    reservations = load_reservations()
    today_res = [r for r in reservations if r.get("날짜") == today]
    
    if today_res:
        for res in sorted(today_res, key=lambda x: x.get("교시", "")):
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 2, 1, 3])
                col1.write(f"🏫 {res.get('특별실', '')}")
                col2.write(f"⏰ {res.get('교시', '')}")
                col3.write(f"👤 {res.get('이름', '')}")
                col4.write(f"📝 {res.get('사유', '')[:30]}...")
    else:
        st.info("오늘 예약된 특별실이 없습니다.")

# ==================== 페이지: 예약하기 ====================
def page_reserve():
    st.title("📅 특별실 예약")
    
    if st.button("← 메인으로"):
        st.session_state.page = "main"
        st.rerun()
    
    st.markdown("---")
    
    # 배치도 이미지 표시
    st.subheader("🗺️ 학교 배치도")
    if os.path.exists("영복배치도.jpg"):
        st.image("영복배치도.jpg", caption="영복여고 특별실 배치도", use_container_width=True)
    else:
        st.info("💡 '영복배치도.jpg' 파일을 프로그램과 같은 폴더에 넣으면 배치도가 표시됩니다.")
    
    st.markdown("---")
    
    # Step 1: 특별실 선택
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("1️⃣ 특별실 선택")
        
        # 층별 그룹화
        floors = {}
        for room in SPECIAL_ROOMS:
            floor = room.split("]")[0] + "]"
            if floor not in floors:
                floors[floor] = []
            floors[floor].append(room)
        
        selected_room = st.selectbox(
            "특별실을 선택하세요",
            SPECIAL_ROOMS,
            format_func=lambda x: x
        )
    
    with col2:
        st.subheader("2️⃣ 날짜 선택")
        selected_date = st.date_input(
            "날짜를 선택하세요",
            min_value=date.today(),
            max_value=date.today() + timedelta(days=30),
            value=date.today()
        )
    
    st.markdown("---")
    
    # Step 2: 교시 선택
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
    
    # Step 3: 사유 입력 및 제출
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
                }
                success, msg = save_reservation(reservation)
                if success:
                    success_count += 1
                else:
                    fail_messages.append(f"{period}: {msg}")
            
            if success_count > 0:
                st.success(f"✅ {success_count}개 시간대 예약 완료!")
            if fail_messages:
                for msg in fail_messages:
                    st.warning(msg)
            
            if success_count > 0:
                st.balloons()

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
    
    # 날짜순 정렬
    my_reservations.sort(key=lambda x: (x.get("날짜", ""), x.get("교시", "")), reverse=True)
    
    for i, res in enumerate(my_reservations):
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1.5, 3, 1])
            
            col1.write(f"📅 **{res.get('날짜', '')}**")
            col2.write(f"🏫 {res.get('특별실', '')}")
            col3.write(f"⏰ {res.get('교시', '')}")
            col4.write(f"📝 {res.get('사유', '')[:25]}...")
            
            with col5:
                if st.button("🗑️ 취소", key=f"delete_{i}"):
                    delete_reservation(res)
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
    
    # 필터
    st.subheader("🔍 필터")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        dates = ["전체"] + sorted(list(set(r.get("날짜", "") for r in reservations)), reverse=True)
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
    
    # 필터 적용
    filtered = reservations
    if filter_date != "전체":
        filtered = [r for r in filtered if r.get("날짜") == filter_date]
    if filter_room != "전체":
        filtered = [r for r in filtered if r.get("특별실") == filter_room]
    if filter_period != "전체":
        filtered = [r for r in filtered if r.get("교시") == filter_period]
    if filter_name != "전체":
        filtered = [r for r in filtered if r.get("이름") == filter_name]
    
    st.markdown("---")
    
    # 통계
    col1, col2, col3 = st.columns(3)
    col1.metric("전체 예약", f"{len(reservations)}건")
    col2.metric("필터 결과", f"{len(filtered)}건")
    col3.metric("클라우드 상태", "연결됨" if st.session_state.db else "로컬")
    
    st.markdown("---")
    
    if not filtered:
        st.info("조건에 맞는 예약이 없습니다.")
        return
    
    # 테이블 형태로 표시
    import pandas as pd
    
    df = pd.DataFrame(filtered)
    display_columns = ["날짜", "특별실", "교시", "이름", "직책", "사유", "신청일시"]
    available_columns = [col for col in display_columns if col in df.columns]
    
    if available_columns:
        df = df[available_columns]
        df = df.sort_values(by=["날짜", "교시"], ascending=[False, True])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("표시할 데이터가 없습니다.")

# ==================== 메인 실행 ====================
def main():
    init_session_state()
    
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
