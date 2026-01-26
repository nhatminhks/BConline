import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime, date, timedelta, time as dt_time
import time
import urllib.parse
import os
import calendar
import io

# ==========================================
# 1. CẤU HÌNH & GIAO DIỆN
# ==========================================
st.set_page_config(
    page_title="HỆ THỐNG BÁO CÁO TRỰC TUYẾN",
    page_icon="🇻🇳",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .clock-container {
        background: linear-gradient(to right, #f8f9fa, #e9ecef);
        padding: 15px 20px;
        border-radius: 12px;
        border-left: 6px solid #0068c9;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        display: flex; justify-content: space-between; align-items: center;
    }
    .clock-time { font-size: 26px; font-weight: 800; color: #0f52ba; }
    .clock-date { font-size: 16px; color: #495057; font-weight: 500; }
    
    .comment-box { padding: 10px; margin-bottom: 8px; border-radius: 8px; font-size: 14px; }
    .role-CT { background-color: #ffebee; border: 1px solid #ffcdd2; color: #b71c1c; }
    .role-PCT { background-color: #e3f2fd; border: 1px solid #bbdefb; color: #0d47a1; }
    .role-LD { background-color: #e8f5e9; border: 1px solid #c8e6c9; color: #1b5e20; }
    .role-DV { background-color: #f5f5f5; border: 1px solid #e0e0e0; color: #424242; }
    
    .notif-box {
        padding: 12px; border-bottom: 1px solid #eee; margin-bottom: 8px;
        background-color: #fff; border-radius: 8px; border: 1px solid #eee;
    }
    .notif-unread { background-color: #e3f2fd; border-left: 5px solid #2196f3; font-weight: 500;}
    
    /* Style hiển thị trạng thái nộp */
    .status-badge { display: inline-block; padding: 5px 10px; border-radius: 15px; font-size: 0.9em; font-weight: bold; margin-left: 10px;}
    .early { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .late { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .ontime { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

DB_FILE = 'system_db.sqlite'
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

# ==========================================
# 2. XỬ LÝ DATABASE
# ==========================================
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, name TEXT, role TEXT, phone TEXT)')
    
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, don_vi TEXT, user_account TEXT, 
        loai_bao_cao TEXT, nam INTEGER, ky_bao_cao INTEGER, 
        noi_nhan TEXT, ket_qua TEXT, kho_khan TEXT, kien_nghi TEXT, phuong_huong TEXT, file_path TEXT, 
        ngay_gui DATE, file_chinh_sua TEXT, ngay_chinh_sua TEXT, y_kien_lanh_dao TEXT, 
        trang_thai TEXT DEFAULT 'Cho_duyet')''')

    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, report_id INTEGER, username TEXT, fullname TEXT, role TEXT, content TEXT, created_at TEXT)''')

    # CẬP NHẬT BẢNG TASKS: Thêm cột ngay_hoan_thanh để tính toán sớm/muộn
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nguoi_giao TEXT, don_vi_nhan TEXT, 
        noi_dung TEXT, yeu_cau_ket_qua TEXT, muc_do TEXT, 
        han_xu_ly DATE, 
        trang_thai TEXT DEFAULT 'Mới', 
        ket_qua_file TEXT, 
        ket_qua_text TEXT, 
        ngay_tao DATE,
        ngay_hoan_thanh DATE)''') 
    
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_target TEXT, message TEXT, link_id INTEGER, type TEXT, is_read INTEGER DEFAULT 0, created_at TEXT)''')
    
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    conn.commit()
    conn.close()

def check_users_exist():
    conn = sqlite3.connect(DB_FILE)
    try: count = conn.execute('SELECT count(*) FROM users').fetchone()[0]
    except: count = 0
    conn.close()
    return count > 0

def get_conn(): return sqlite3.connect(DB_FILE)

# --- HÀM TÍNH TOÁN ĐÁNH GIÁ TIẾN ĐỘ (LOGIC MỚI) ---
def evaluate_performance(deadline_str, completed_date_str):
    """So sánh ngày hạn và ngày hoàn thành thực tế"""
    if not completed_date_str: return "", ""
    
    deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
    completed = datetime.strptime(completed_date_str, '%Y-%m-%d').date()
    
    delta = (deadline - completed).days
    
    if delta > 0:
        return f"🌟 Nộp sớm {delta} ngày", "early"
    elif delta == 0:
        return "✅ Nộp đúng hạn", "ontime"
    else:
        return f"🚨 Nộp muộn {abs(delta)} ngày", "late"

# --- HÀM ĐẾM NGƯỢC (CHO VIỆC CHƯA XONG) ---
def get_time_countdown(deadline_date):
    if not deadline_date: return "", ""
    today = date.today()
    if isinstance(deadline_date, str):
        deadline_date = datetime.strptime(deadline_date, '%Y-%m-%d').date()
    delta = (deadline_date - today).days
    if delta > 0: return f"⏳ Còn {delta} ngày", "green"
    elif delta == 0: return "⚠️ Hạn chót hôm nay", "orange"
    else: return f"🚨 Quá hạn {abs(delta)} ngày", "red"

def send_notification(target_username, message, link_id=0, n_type="SYSTEM"):
    conn = get_conn()
    now_str = datetime.now().strftime("%H:%M %d/%m")
    if target_username == 'ALL_LEADERS':
        leaders = pd.read_sql("SELECT username FROM users WHERE role IN ('CHU_TICH', 'PHO_CHU_TICH', 'LANH_DAO')", conn)['username'].tolist()
        for l in leaders:
            conn.execute("INSERT INTO notifications (user_target, message, link_id, type, created_at) VALUES (?,?,?,?,?)", (l, message, link_id, n_type, now_str))
    else:
        conn.execute("INSERT INTO notifications (user_target, message, link_id, type, created_at) VALUES (?,?,?,?,?)", (target_username, message, link_id, n_type, now_str))
    conn.commit()
    conn.close()

def save_uploaded_file(uploaded_file):
    if uploaded_file is not None:
        ts = int(time.time())
        fpath = os.path.join(UPLOAD_FOLDER, f"{ts}_{uploaded_file.name}")
        with open(fpath, "wb") as f: f.write(uploaded_file.getbuffer())
        return fpath
    return None

def get_original_filename(filepath):
    if filepath and os.path.exists(filepath):
        try: return os.path.basename(filepath).split('_', 1)[1]
        except: return os.path.basename(filepath)
    return "file"

def to_excel(df):
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
    except: return df.to_csv(index=False).encode('utf-8-sig')
    return output.getvalue()

# ==========================================
# 3. LOGIC THỜI GIAN
# ==========================================
def render_header_clock():
    now = datetime.now()
    week_num = now.isocalendar()[1]
    quarter = (now.month - 1) // 3 + 1
    weekday_vn = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"][now.weekday()]
    st.markdown(f"""
        <div class="clock-container">
            <div><div class="clock-time">🕰️ {now.strftime('%H:%M')}</div>
            <div style="color: #6c757d;">{weekday_vn}, ngày {now.strftime('%d/%m/%Y')}</div></div>
            <div style="text-align: right;"><div class="clock-date">📅 <b>Tuần {week_num}</b> &nbsp;|&nbsp; Tháng {now.month}</div>
            <div class="clock-date">📊 Quý {quarter} &nbsp;|&nbsp; Năm {now.year}</div></div>
        </div>
    """, unsafe_allow_html=True)

def get_date_range_for_period(mode, value, year):
    if mode == "Tuần":
        d = date.fromisocalendar(year, value, 1) 
        return d, d + timedelta(days=6)
    elif mode == "Tháng":
        _, last_day = calendar.monthrange(year, value)
        return date(year, value, 1), date(year, value, last_day)
    elif mode == "Quý":
        start_m = 3 * value - 2
        end_m = start_m + 2
        _, last_d = calendar.monthrange(year, end_m)
        return date(year, start_m, 1), date(year, end_m, last_d)
    elif mode == "Năm": return date(year, 1, 1), date(year, 12, 31)

def get_sub_periods(mode, value, year):
    sub_periods = []
    start_date, end_date = get_date_range_for_period(mode, value, year)
    if mode == "Tháng":
        current = start_date
        while current <= end_date:
            wk = current.isocalendar()[1]
            w_start = current - timedelta(days=current.weekday())
            w_end = w_start + timedelta(days=6)
            label = f"Tuần {wk}"
            if not any(x[0] == label for x in sub_periods): sub_periods.append((label, w_start, w_end))
            current += timedelta(days=7)
    elif mode == "Quý":
        start_m = 3 * value - 2
        for m in range(start_m, start_m + 3):
            ms, me = get_date_range_for_period("Tháng", m, year)
            sub_periods.append((f"Tháng {m}", ms, me))
    elif mode == "Năm":
        for q in range(1, 5):
            qs, qe = get_date_range_for_period("Quý", q, year)
            sub_periods.append((f"Quý {q}", qs, qe))
    return sub_periods

def render_comments_section(report_id, current_user, report_owner_account):
    conn = get_conn()
    comments = pd.read_sql(f"SELECT * FROM comments WHERE report_id={report_id} ORDER BY id ASC", conn)
    conn.close()
    st.markdown("#### 💬 Ý kiến trao đổi:")
    if not comments.empty:
        for _, c in comments.iterrows():
            css_class, role_label = "role-DV", "Đơn vị"
            if c['role'] == 'CHU_TICH': css_class, role_label = "role-CT", "⭐ CHỦ TỊCH"
            elif c['role'] == 'PHO_CHU_TICH': css_class, role_label = "role-PCT", "💠 PHÓ CHỦ TỊCH"
            elif c['role'] == 'LANH_DAO': css_class, role_label = "role-LD", "👤 LÃNH ĐẠO"
            st.markdown(f"""
                <div class="comment-box {css_class}">
                    <div class="comment-header"><span>{role_label}: {c['fullname']}</span><span>{c['created_at']}</span></div>
                    {c['content']}
                </div>
            """, unsafe_allow_html=True)
    else: st.caption("Chưa có ý kiến nào.")
    
    with st.form(key=f"add_cmt_{report_id}"):
        new_cmt = st.text_area("Thêm ý kiến/Giải trình:", height=80)
        if st.form_submit_button("Gửi ý kiến"):
            if new_cmt:
                conn = get_conn()
                now_str = datetime.now().strftime("%H:%M %d/%m")
                conn.execute("INSERT INTO comments (report_id, username, fullname, role, content, created_at) VALUES (?,?,?,?,?,?)",
                            (report_id, current_user['username'], current_user['name'], current_user['role'], new_cmt, now_str))
                conn.commit()
                conn.close()
                is_leader = current_user['role'] in ['CHU_TICH', 'PHO_CHU_TICH', 'LANH_DAO']
                if is_leader: send_notification(report_owner_account, f"💬 {role_label} đã bình luận báo cáo", report_id, "REPORT")
                else: send_notification('ALL_LEADERS', f"💬 {current_user['name']} đã giải trình", report_id, "REPORT")
                st.rerun()

# ==========================================
# 4. KHỞI TẠO & NAVIGATOR
# ==========================================
init_db()
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'nav_target' not in st.session_state: st.session_state['nav_target'] = None 
if 'focus_id' not in st.session_state: st.session_state['focus_id'] = None

if not check_users_exist():
    with st.form("setup"):
        st.subheader("🛠️ KHỞI TẠO ADMIN")
        u = st.text_input("Username Admin", value="admin")
        p = st.text_input("Password", type="password")
        n = st.text_input("Tên hiển thị", value="Quản Trị Viên")
        if st.form_submit_button("Khởi tạo"):
            conn = get_conn()
            conn.execute('INSERT INTO users VALUES (?,?,?,?,?)', (u, make_hashes(p), n, "ADMIN", ""))
            conn.commit()
            conn.close()
            st.rerun()
    st.stop()

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h2 style='text-align: center; color: #004a8f;'>🇻🇳 HỆ THỐNG ĐIỀU HÀNH</h2>", unsafe_allow_html=True)
        with st.form("login"):
            u = st.text_input("Tài khoản")
            p = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Đăng nhập", use_container_width=True):
                conn = get_conn()
                user = conn.execute('SELECT * FROM users WHERE username=?', (u,)).fetchone()
                conn.close()
                if user and check_hashes(p, user[1]):
                    st.session_state['logged_in'] = True
                    st.session_state['user'] = {"username": user[0], "name": user[2], "role": user[3], "phone": user[4]}
                    st.rerun()
                else: st.error("Sai thông tin")
    st.stop()

user = st.session_state['user']
render_header_clock()

conn = get_conn()
unread_count = len(pd.read_sql(f"SELECT * FROM notifications WHERE user_target='{user['username']}' AND is_read=0", conn))
conn.close()
notif_label = f"🔔 Thông báo ({unread_count})" if unread_count > 0 else "🔔 Thông báo"

if unread_count > 0:
    st.toast(f"Bạn có {unread_count} thông báo mới!", icon="📨")

st.sidebar.markdown(f"### 👤 {user['name']}")
if st.sidebar.button("🔄 LÀM MỚI DỮ LIỆU", use_container_width=True): st.rerun()

is_leader = user['role'] in ['CHU_TICH', 'PHO_CHU_TICH', 'LANH_DAO']
if is_leader:
    role_name = "⭐ CHỦ TỊCH" if user['role']=='CHU_TICH' else "💠 PHÓ CHỦ TỊCH" if user['role']=='PHO_CHU_TICH' else "👤 LÃNH ĐẠO"
    st.sidebar.success(role_name)
    menu = ["📌 Theo dõi công việc", "📊 Báo cáo tổng hợp", notif_label, "⚙️ Cài đặt hạn nộp", "🔑 Đổi mật khẩu"]
elif user['role'] == 'DON_VI':
    st.sidebar.info("🏢 ĐƠN VỊ")
    menu = ["📥 Công việc", "📝 Gửi Báo cáo", notif_label, "🔑 Đổi mật khẩu"]
else:
    menu = ["Quản lý Người dùng", "🔑 Đổi mật khẩu"]

default_idx = 0
if st.session_state['nav_target']:
    clean_menu = [m.replace(f" ({unread_count})", "") for m in menu]
    target = st.session_state['nav_target']
    for i, m in enumerate(clean_menu):
        if target in m: 
            default_idx = i
            break
    st.session_state['nav_target'] = None

choice = st.sidebar.radio("MENU", menu, index=default_idx)
st.sidebar.markdown("---")
if st.sidebar.button("Đăng xuất"):
    st.session_state['logged_in'] = False
    st.rerun()

# ==========================================
# MODULE: THÔNG BÁO
# ==========================================
if "Thông báo" in choice:
    st.title("🔔 TRUNG TÂM THÔNG BÁO")
    conn = get_conn()
    notifs = pd.read_sql(f"SELECT * FROM notifications WHERE user_target='{user['username']}' ORDER BY id DESC LIMIT 50", conn)
    
    c1, c2 = st.columns([6, 2])
    if c2.button("Đánh dấu tất cả đã đọc"):
        conn.execute(f"UPDATE notifications SET is_read=1 WHERE user_target='{user['username']}'")
        conn.commit()
        st.rerun()
    if c2.button("Xóa tất cả thông báo"):
        conn.execute(f"DELETE FROM notifications WHERE user_target='{user['username']}'")
        conn.commit()
        st.rerun()

    if notifs.empty: st.info("Hiện không có thông báo nào.")
    else:
        for _, row in notifs.iterrows():
            style = "notif-unread" if row['is_read'] == 0 else ""
            icon = "🔴" if row['is_read'] == 0 else "⚪"
            
            with st.container():
                c_icon, c_content, c_action = st.columns([0.5, 7, 2.5])
                with c_icon: st.write(icon)
                with c_content:
                    st.markdown(f"<div class='{style}'>{row['created_at']} - {row['message']}</div>", unsafe_allow_html=True)
                with c_action:
                    c_act1, c_act2 = st.columns(2)
                    if c_act1.button("Xem", key=f"v_{row['id']}"):
                        conn.execute("UPDATE notifications SET is_read=1 WHERE id=?", (row['id'],))
                        conn.commit()
                        if row['type'] == 'TASK': 
                            st.session_state['nav_target'] = "Theo dõi công việc" if is_leader else "Công việc"
                        elif row['type'] == 'REPORT':
                            st.session_state['nav_target'] = "Báo cáo tổng hợp" if is_leader else "Gửi Báo cáo"
                        st.session_state['focus_id'] = row['link_id']
                        st.rerun()
                    if c_act2.button("Xóa", key=f"d_{row['id']}"):
                        conn.execute("DELETE FROM notifications WHERE id=?", (row['id'],))
                        conn.commit()
                        st.rerun()
                st.write("---")
    conn.close()

# ==========================================
# MODULE: LÃNH ĐẠO
# ==========================================
elif "Theo dõi công việc" in choice and is_leader:
    st.write("### 🗓️ Chọn khung thời gian")
    now = datetime.now()
    cur_week = now.isocalendar()[1]
    
    c_mode, c_val, c_year = st.columns([1, 1, 1])
    view_mode = c_mode.selectbox("Xem theo", ["Tuần", "Tháng", "Quý", "Năm"], index=0)
    
    if view_mode == "Tuần": period_val = c_val.number_input("Tuần", 1, 53, cur_week)
    elif view_mode == "Tháng": period_val = c_val.number_input("Tháng", 1, 12, now.month)
    elif view_mode == "Quý": period_val = c_val.selectbox("Quý", [1, 2, 3, 4], index=(now.month-1)//3)
    else: period_val = now.year
    sel_year = c_year.number_input("Năm", value=now.year)
    main_start, main_end = get_date_range_for_period(view_mode, period_val, sel_year)
    
    tab_track, tab_assign, tab_chart = st.tabs(["📋 Theo dõi Tiến độ", "➕ Giao việc Mới", "🏆 Thi đua"])
    
    with tab_track:
        conn = get_conn()
        q = f"""SELECT t.*, u.name as unit, u.phone as u_phone FROM tasks t JOIN users u ON t.don_vi_nhan=u.username 
                WHERE t.han_xu_ly BETWEEN ? AND ? ORDER BY t.han_xu_ly"""
        df = pd.read_sql(q, conn, params=(main_start, main_end))
        
        if df.empty: st.warning(f"Chưa có nhiệm vụ.")
        else:
            for unit in df['unit'].unique():
                u_tasks = df[df['unit'] == unit]
                pending = len(u_tasks[u_tasks['trang_thai']!='Hoàn thành'])
                icon = "🟢" if pending==0 else "🔴"
                
                with st.expander(f"{icon} **{unit}** (Còn {pending} việc)"):
                    for _, row in u_tasks.iterrows():
                        is_focus = st.session_state['focus_id'] == row['id']
                        if is_focus: st.markdown("👉 **MỤC CẦN XỬ LÝ:**")
                        
                        col_a, col_b = st.columns([3, 1])
                        with col_a:
                            st.markdown(f"**{row['noi_dung']}**")
                            # Đếm ngược thời gian
                            t_str, t_color = get_time_status(row['han_xu_ly'])
                            st.markdown(f"Yêu cầu: {row['yeu_cau_ket_qua']} | Hạn: {row['han_xu_ly']} | :{t_color}[**{t_str}**]")
                            
                            # --- HIỂN THỊ ĐÁNH GIÁ TIẾN ĐỘ (MỚI) ---
                            if row['trang_thai'] == 'Hoàn thành' and row['ngay_hoan_thanh']:
                                perf_text, perf_css = evaluate_performance(row['han_xu_ly'], row['ngay_hoan_thanh'])
                                st.markdown(f"<div class='status-badge {perf_css}'>{perf_text}</div>", unsafe_allow_html=True)

                            if row['trang_thai'] != 'Hoàn thành' and row['u_phone']:
                                msg = f"NHẮC NHỞ: Đơn vị {unit} chưa hoàn thành việc: '{row['noi_dung']}'. Hạn chót: {row['han_xu_ly']}."
                                z_url = f"https://zalo.me/{row['u_phone']}?text={urllib.parse.quote(msg)}"
                                st.link_button("🔔 Nhắc nhở Zalo", z_url)

                        with col_b:
                            if row['trang_thai'] == 'Hoàn thành':
                                st.success("✅ Đã xong")
                                if row['ket_qua_file'] and os.path.exists(row['ket_qua_file']):
                                    # Hiện tên file rõ ràng
                                    fname = get_original_filename(row['ket_qua_file'])
                                    with open(row['ket_qua_file'],"rb") as f: st.download_button(f"📥 Tải: {fname}", f, file_name=fname, key=f"d_{row['id']}")
                            else: st.warning(f"🚧 {row['trang_thai']}")
                        st.divider()
        conn.close()

    with tab_assign:
        st.subheader(f"Giao nhiệm vụ cho: {view_mode} {period_val}")
        suggested_deadline = date.today()
        if view_mode == "Tuần": suggested_deadline = main_start + timedelta(days=4)
        
        conn = get_conn()
        units = pd.read_sql("SELECT username, name, phone FROM users WHERE role='DON_VI'", conn)
        conn.close()
        
        if not units.empty:
            unit_dict = {r['name']: (r['username'], r['phone']) for _, r in units.iterrows()}
            with st.form("assign_form"):
                c1, c2 = st.columns(2)
                u_select = c1.selectbox("Đơn vị", list(unit_dict.keys()))
                muc_do = c2.selectbox("Mức độ", ["🔴 Khẩn", "🟠 Trọng tâm", "🟢 Thường xuyên"])
                cont = st.text_area("Nội dung công việc")
                req = st.text_input("Yêu cầu kết quả")
                deadline = st.date_input("Hạn hoàn thành", value=suggested_deadline)
                submit_save = st.form_submit_button("💾 Lưu & Giao việc")

            if submit_save:
                uid, uphone = unit_dict[u_select]
                conn = get_conn()
                conn.execute("INSERT INTO tasks (nguoi_giao, don_vi_nhan, noi_dung, yeu_cau_ket_qua, muc_do, han_xu_ly, ngay_tao) VALUES (?,?,?,?,?,?,?)",
                            (user['name'], uid, cont, req, muc_do, deadline, date.today()))
                conn.commit()
                send_notification(uid, f"📌 Nhiệm vụ mới: {cont} (Hạn: {deadline})", 0, "TASK")
                conn.close()
                st.success("✅ Đã lưu nhiệm vụ!")
                if uphone:
                    msg = f"🔔 GIAO VIỆC MỚI:\n- Đơn vị: {u_select}\n- Nội dung: {cont}\n- Hạn: {deadline.strftime('%d/%m')}"
                    zalo_url = f"https://zalo.me/{uphone}?text={urllib.parse.quote(msg)}"
                    st.info("👇 Gửi thông báo qua Zalo:")
                    st.link_button("📱 Gửi Zalo ngay", zalo_url)

    with tab_chart:
        conn = get_conn()
        df_rank = pd.read_sql("""SELECT u.name, COUNT(t.id) as total, SUM(CASE WHEN t.trang_thai='Hoàn thành' THEN 1 ELSE 0 END) as done 
                                 FROM users u LEFT JOIN tasks t ON u.username=t.don_vi_nhan WHERE u.role='DON_VI' GROUP BY u.name ORDER BY done DESC""", conn)
        conn.close()
        c_chart, c_table = st.columns([1.5, 1])
        with c_chart:
            st.markdown("##### 📊 Biểu đồ tỷ lệ")
            if not df_rank.empty:
                df_rank['percent'] = (df_rank['done'] / df_rank['total'].replace(0, 1)) * 100
                st.bar_chart(df_rank.set_index('name')['percent'], color="#4CAF50")
        with c_table:
            st.markdown("##### 🏆 Bảng xếp hạng")
            if not df_rank.empty:
                st.dataframe(df_rank[['name', 'total', 'done', 'percent']], use_container_width=True)

# ==========================================
# MODULE: BÁO CÁO (LÃNH ĐẠO)
# ==========================================
elif "Cài đặt hạn nộp" in choice and is_leader:
    st.title("⚙️ Cấu hình Hạn nộp Báo cáo")
    with st.form("config_deadline"):
        c1, c2 = st.columns(2)
        wd = c1.selectbox("Thứ trong tuần", options=[0,1,2,3,4,5,6], format_func=lambda x: f"Thứ {x+2}" if x<6 else "Chủ Nhật", index=3)
        tm = c2.time_input("Giờ chốt số liệu", value=dt_time(15, 0))
        if st.form_submit_button("Lưu cấu hình"):
            val_str = f"{wd}-{tm.strftime('%H:%M')}"
            conn = get_conn()
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('DEADLINE_TUAN', val_str))
            conn.commit()
            conn.close()
            st.success("Đã lưu!")

elif "Báo cáo tổng hợp" in choice and is_leader:
    st.title("📊 DUYỆT BÁO CÁO")
    c1, c2, c3 = st.columns(3)
    l_bc = c1.selectbox("Loại", ["Báo cáo Tuần", "Báo cáo Tháng", "Báo cáo Quý"])
    now = datetime.now()
    def_ky = now.isocalendar()[1] if "Tuần" in l_bc else now.month
    if "Quý" in l_bc: def_ky = (now.month-1)//3 + 1
    k_bc = c2.number_input("Kỳ", value=def_ky)
    n_bc = c3.number_input("Năm", value=now.year)
    
    conn = get_conn()
    all_units = pd.read_sql("SELECT name FROM users WHERE role='DON_VI'", conn)['name'].tolist()
    submitted = pd.read_sql(f"SELECT * FROM reports WHERE loai_bao_cao='{l_bc}' AND ky_bao_cao={k_bc} AND nam={n_bc}", conn)
    conn.close()
    
    done = submitted['don_vi'].unique().tolist()
    missing = [u for u in all_units if u not in done]
    m1, m2 = st.columns(2)
    m1.metric("Đã nộp", len(done))
    m2.metric("Chưa nộp", len(missing), delta_color="inverse")
    
    if not submitted.empty:
        st.download_button("📥 Xuất Excel danh sách", data=to_excel(submitted), file_name=f'Bao_cao_{k_bc}_{n_bc}.xlsx')
    
    if missing:
        st.subheader("🚨 DANH SÁCH CHƯA NỘP")
        st.dataframe(pd.DataFrame(missing, columns=["Tên đơn vị"]), use_container_width=True)
    
    st.markdown("---")
    st.subheader("📝 NỘI DUNG CHI TIẾT")
    
    for _, row in submitted.iterrows():
        is_focus = st.session_state['focus_id'] == row['id']
        with st.expander(f"📄 {row['don_vi']} - Kính gửi: {row['noi_nhan']}", expanded=is_focus):
            if is_focus: st.markdown("👉 **Mục bạn vừa chọn:**")
            st.write(f"**Kết quả:** {row['ket_qua']}")
            st.write(f"**Khó khăn:** {row['kho_khan']}")
            
            c_file1, c_file2 = st.columns(2)
            with c_file1:
                if row['file_path'] and os.path.exists(row['file_path']):
                    fname = get_original_filename(row['file_path'])
                    with open(row['file_path'],"rb") as f: st.download_button(f"📂 Tải gốc: {fname}", f, file_name=fname, key=f"r_{row['id']}")
            with c_file2:
                if row['file_chinh_sua'] and os.path.exists(row['file_chinh_sua']):
                    fname_edit = get_original_filename(row['file_chinh_sua'])
                    st.success(f"✨ Đã nộp lại lúc: {row['ngay_chinh_sua']}")
                    with open(row['file_chinh_sua'],"rb") as f: st.download_button(f"📥 Tải bản SỬA: {fname_edit}", f, file_name=fname_edit, key=f"r_edit_{row['id']}")

            render_comments_section(row['id'], user, row['user_account'])

# ==========================================
# MODULE: ĐƠN VỊ
# ==========================================
elif "Công việc" in choice and user['role'] == 'DON_VI':
    st.title("📥 CÔNG VIỆC CỦA TÔI")
    tm_tabs = st.tabs(["📅 Tuần này", "🗓️ Tháng này", "infinity Tất cả"])
    now = datetime.now()
    conn = get_conn()
    
    with tm_tabs[0]:
        s, e = get_date_range_for_period("Tuần", now.isocalendar()[1], now.year)
        tasks = pd.read_sql(f"SELECT * FROM tasks WHERE don_vi_nhan='{user['username']}' AND han_xu_ly BETWEEN ? AND ? ORDER BY han_xu_ly", conn, params=(s,e))
        if tasks.empty: st.info(f"Tuần này không có việc.")
        else:
            for _, t in tasks.iterrows():
                is_focus = st.session_state['focus_id'] == t['id']
                with st.expander(f"📌 {t['muc_do']} | {t['noi_dung']}", expanded=is_focus):
                    if is_focus: st.caption("👉 Mục từ thông báo")
                    
                    t_str, t_color = get_time_status(t['han_xu_ly'])
                    st.markdown(f"**Hạn chót:** {t['han_xu_ly']} (:{t_color}[{t_str}])")
                    st.info(f"Yêu cầu: {t['yeu_cau_ket_qua']}")
                    
                    # Hiển thị đánh giá tiến độ cho đơn vị xem
                    if t['trang_thai'] == 'Hoàn thành' and t['ngay_hoan_thanh']:
                        perf_text, perf_css = evaluate_performance(t['han_xu_ly'], t['ngay_hoan_thanh'])
                        st.markdown(f"<div class='status-badge {perf_css}'>{perf_text}</div>", unsafe_allow_html=True)
                    
                    with st.form(f"f_{t['id']}"):
                        res_text = st.text_area("Kết quả", value=t['ket_qua_text'] if t['ket_qua_text'] else "")
                        res_file = st.file_uploader("File minh chứng")
                        done = st.checkbox("Đánh dấu hoàn thành")
                        if st.form_submit_button("Cập nhật"):
                            stt = "Hoàn thành" if done else "Đang làm"
                            fp = t['ket_qua_file']
                            if res_file: fp = save_uploaded_file(res_file)
                            
                            # CẬP NHẬT NGÀY HOÀN THÀNH (MỚI)
                            finish_date = date.today() if done else None
                            
                            conn_sub = get_conn()
                            conn_sub.execute("UPDATE tasks SET trang_thai=?, ket_qua_text=?, ket_qua_file=?, ngay_hoan_thanh=? WHERE id=?", 
                                            (stt, res_text, fp, finish_date, t['id']))
                            conn_sub.commit()
                            
                            if done:
                                st.balloons()
                                send_notification('ALL_LEADERS', f"✅ {user['name']} đã hoàn thành: {t['noi_dung']}", t['id'], "TASK")
                            
                            conn_sub.close()
                            st.success("Đã cập nhật!")
                            time.sleep(1)
                            st.rerun()
    conn.close()

elif "Gửi Báo cáo" in choice and user['role'] == 'DON_VI':
    st.title("📝 BÁO CÁO ĐỊNH KỲ")
    tab_compose, tab_history = st.tabs(["✍️ Soạn báo cáo mới", "🗂️ Lịch sử & Thu hồi & Sửa"])
    
    with tab_compose:
        l = st.selectbox("Loại", ["Báo cáo Tuần", "Báo cáo Tháng", "Báo cáo Quý"])
        now = datetime.now()
        def_k = now.isocalendar()[1] if "Tuần" in l else now.month
        if "Quý" in l: def_k = (now.month-1)//3 + 1
        c1, c2 = st.columns(2)
        k = c1.number_input("Kỳ", value=def_k)
        n = c2.number_input("Năm", value=now.year)
        
        conn = get_conn()
        all_users = pd.read_sql("SELECT name FROM users WHERE role IN ('CHU_TICH', 'PHO_CHU_TICH', 'LANH_DAO', 'DON_VI')", conn)
        leader_list = all_users['name'].tolist()
        conn.close()
        
        recv_options = st.multiselect("Nơi nhận (Mặc định Chủ tịch luôn xem được)", ["Gửi tất cả các đơn vị"] + leader_list)
        if "Gửi tất cả các đơn vị" in recv_options:
            noi_nhan_str = "Tất cả các cơ quan, đơn vị"
        else:
            noi_nhan_str = ", ".join(recv_options)
        
        with st.form("send"):
            kq = st.text_area("Kết quả")
            kk = st.text_area("Khó khăn")
            f = st.file_uploader("File đính kèm")
            if st.form_submit_button("Gửi báo cáo"):
                conn = get_conn()
                check = pd.read_sql(f"SELECT * FROM reports WHERE user_account='{user['username']}' AND loai_bao_cao='{l}' AND ky_bao_cao={k} AND nam={n}", conn)
                if check.empty:
                    fp = save_uploaded_file(f)
                    conn.execute("INSERT INTO reports (don_vi, user_account, loai_bao_cao, nam, ky_bao_cao, noi_nhan, ket_qua, kho_khan, file_path, ngay_gui) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (user['name'], user['username'], l, n, k, noi_nhan_str, kq, kk, fp, date.today()))
                    conn.commit()
                    send_notification('ALL_LEADERS', f"📄 {user['name']} đã gửi {l} kỳ {k}", 0, "REPORT")
                    st.success("✅ Đã gửi thành công!")
                else: st.warning("⚠️ Kỳ này đã gửi rồi! Vào Tab 'Lịch sử' để xem lại.")
                conn.close()
    
    with tab_history:
        conn = get_conn()
        his = pd.read_sql(f"SELECT * FROM reports WHERE user_account='{user['username']}' ORDER BY id DESC", conn)
        conn.close()
        for _, row in his.iterrows():
            is_focus = st.session_state['focus_id'] == row['id']
            with st.expander(f"{row['loai_bao_cao']} - Kỳ {row['ky_bao_cao']} (Gửi: {row['ngay_gui']})", expanded=is_focus):
                st.write(f"**Nơi nhận:** {row['noi_nhan']}")
                st.write(f"**Kết quả:** {row['ket_qua']}")
                
                if row['file_path'] and os.path.exists(row['file_path']):
                    fname = get_original_filename(row['file_path'])
                    with open(row['file_path'], "rb") as f: st.download_button("📥 Tải file gốc", f, file_name=fname, key=f"dl_his_{row['id']}")
                
                render_comments_section(row['id'], user, row['user_account'])
                
                st.markdown("---")
                st.markdown("##### 📎 Nộp lại bản chỉnh sửa (Nếu có chỉ đạo):")
                with st.form(key=f"edit_report_{row['id']}"):
                    f_edit = st.file_uploader("Chọn file báo cáo đã chỉnh sửa", type=['docx', 'xlsx', 'pdf', 'doc'])
                    if st.form_submit_button("Gửi bản chỉnh sửa"):
                        if f_edit:
                            fp_edit = save_uploaded_file(f_edit)
                            now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
                            conn = get_conn()
                            conn.execute("UPDATE reports SET file_chinh_sua=?, ngay_chinh_sua=? WHERE id=?", (fp_edit, now_str, row['id']))
                            conn.commit()
                            conn.close()
                            send_notification('ALL_LEADERS', f"✏️ {user['name']} đã cập nhật lại báo cáo", row['id'], "REPORT")
                            st.success("Đã cập nhật bản chỉnh sửa!")
                            st.rerun()
                        else: st.warning("Vui lòng chọn file!")
                
                conn_chk = get_conn()
                has_cmt = pd.read_sql(f"SELECT * FROM comments WHERE report_id={row['id']}", conn_chk)
                conn_chk.close()
                
                if has_cmt.empty:
                    if st.button("🗑️ Thu hồi báo cáo này", key=f"del_{row['id']}"):
                        conn = get_conn()
                        conn.execute("DELETE FROM reports WHERE id=?", (row['id'],))
                        conn.commit()
                        conn.close()
                        st.warning("Đã thu hồi báo cáo!")
                        time.sleep(1)
                        st.rerun()
                else: st.info("🔒 Đã có ý kiến chỉ đạo, không thể thu hồi.")

# MODULE ADMIN
elif choice == "Quản lý Người dùng" and user['role'] == 'ADMIN':
    st.title("🛠️ QUẢN TRỊ USER")
    tab_new, tab_list = st.tabs(["➕ Thêm", "📋 Danh sách & Xóa"])
    with tab_new:
        with st.form("new_u"):
            c1, c2 = st.columns(2)
            u = c1.text_input("Username")
            n = c2.text_input("Tên đơn vị/Lãnh đạo")
            r = st.selectbox("Role", ["DON_VI", "CHU_TICH", "PHO_CHU_TICH", "LANH_DAO", "ADMIN"])
            ph = st.text_input("Zalo")
            p = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Tạo"):
                if u and p and n:
                    conn = get_conn()
                    try:
                        conn.execute("INSERT INTO users VALUES (?,?,?,?,?)", (u, make_hashes(p), n, r, ph))
                        conn.commit()
                        st.success("Tạo thành công!")
                    except: st.error("Trùng User")
                    conn.close()
                else: st.error("Nhập đủ thông tin")
    with tab_list:
        conn = get_conn()
        df = pd.read_sql("SELECT * FROM users", conn)
        st.dataframe(df)
        d_u = st.selectbox("Xóa User", df['username'])
        if st.button("Xóa vĩnh viễn"):
            if d_u != user['username']:
                conn.execute("DELETE FROM users WHERE username=?", (d_u,))
                conn.commit()
                st.success("Đã xóa")
                st.rerun()
            else: st.error("Không được xóa chính mình")
        conn.close()

elif choice == "🔑 Đổi mật khẩu":
    st.title("Đổi mật khẩu")
    with st.form("cp"):
        o = st.text_input("Cũ", type="password")
        new = st.text_input("Mới", type="password")
        if st.form_submit_button("Lưu"):
            conn = get_conn()
            real = conn.execute("SELECT password FROM users WHERE username=?", (user['username'],)).fetchone()[0]
            if check_hashes(o, real):
                conn.execute("UPDATE users SET password=? WHERE username=?", (make_hashes(new), user['username']))
                conn.commit()
                st.success("Xong!")
            else: st.error("Sai pass cũ")

            conn.close()
