import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, date

# Cấu hình trang
st.set_page_config(
    page_title="Quản Lý Văn Phòng",
    page_icon="🏢",
    layout="wide"
)

# Khởi tạo database
def init_db():
    conn = sqlite3.connect('office.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT,
            progress INTEGER,
            deadline DATE,
            created_date DATE
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT,
            file_path TEXT,
            created_date DATE
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def get_conn():
    return sqlite3.connect('office.db')

# Sidebar
st.sidebar.title("🏢 HỆ THỐNG QUẢN LÝ")
page = st.sidebar.selectbox(
    "Chọn chức năng",
    ["Tổng quan", "Quản lý công việc", "Quản lý hồ sơ"]
)

# Trang tổng quan
if page == "Tổng quan":
    st.title("📊 TỔNG QUAN")
    
    with get_conn() as conn:
        tasks = pd.read_sql("SELECT * FROM tasks", conn)
        documents = pd.read_sql("SELECT * FROM documents", conn)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Tổng công việc", len(tasks))
    with col2:
        completed = len(tasks[tasks['status'] == 'Hoàn thành']) if not tasks.empty else 0
        st.metric("Công việc hoàn thành", completed)
    with col3:
        st.metric("Tổng hồ sơ", len(documents))
    
    if not tasks.empty:
        st.subheader("Tiến độ công việc")
        st.dataframe(tasks[['title', 'status', 'progress', 'deadline']])

# Quản lý công việc
elif page == "Quản lý công việc":
    st.title("📝 QUẢN LÝ CÔNG VIỆC")
    
    tab1, tab2 = st.tabs(["Thêm công việc", "Danh sách công việc"])
    
    with tab1:
        st.subheader("Thêm công việc mới")
        
        with st.form("task_form"):
            title = st.text_input("Tiêu đề công việc")
            description = st.text_area("Mô tả")
            status = st.selectbox("Trạng thái", ["Chưa bắt đầu", "Đang thực hiện", "Hoàn thành"])
            progress = st.slider("Tiến độ (%)", 0, 100, 0)
            deadline = st.date_input("Hạn chót")
            
            submitted = st.form_submit_button("Lưu công việc")
            
            if submitted and title:
                with get_conn() as conn:
                    conn.execute(
                        "INSERT INTO tasks (title, description, status, progress, deadline, created_date) VALUES (?, ?, ?, ?, ?, ?)",
                        (title, description, status, progress, deadline, date.today())
                    )
                    conn.commit()
                st.success("✅ Đã thêm công việc thành công!")
    
    with tab2:
        st.subheader("Danh sách công việc")
        
        with get_conn() as conn:
            tasks = pd.read_sql("SELECT * FROM tasks ORDER BY created_date DESC", conn)
        
        if not tasks.empty:
            for _, task in tasks.iterrows():
                with st.expander(f"📋 {task['title']} - {task['status']}"):
                    st.write(f"**Mô tả:** {task['description']}")
                    st.write(f"**Tiến độ:** {task['progress']}%")
                    st.write(f"**Hạn chót:** {task['deadline']}")
                    
                    # Cập nhật tiến độ
                    new_progress = st.slider("Cập nhật tiến độ", 0, 100, task['progress'], key=f"progress_{task['id']}")
                    if st.button("Cập nhật", key=f"btn_{task['id']}"):
                        with get_conn() as conn:
                            conn.execute(
                                "UPDATE tasks SET progress = ? WHERE id = ?",
                                (new_progress, task['id'])
                            )
                            conn.commit()
                        st.rerun()
        else:
            st.info("Chưa có công việc nào")

# Quản lý hồ sơ
elif page == "Quản lý hồ sơ":
    st.title("📁 QUẢN LÝ HỒ SƠ")
    
    tab1, tab2 = st.tabs(["Thêm hồ sơ", "Danh sách hồ sơ"])
    
    with tab1:
        st.subheader("Thêm hồ sơ mới")
        
        with st.form("doc_form"):
            title = st.text_input("Tiêu đề hồ sơ")
            category = st.selectbox("Danh mục", ["Hợp đồng", "Báo cáo", "Tài liệu", "Khác"])
            uploaded_file = st.file_uploader("Tải lên file", type=['pdf', 'docx', 'txt'])
            
            submitted = st.form_submit_button("Lưu hồ sơ")
            
            if submitted and title:
                file_path = None
                if uploaded_file is not None:
                    os.makedirs('documents', exist_ok=True)
                    file_path = f"documents/{uploaded_file.name}"
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                
                with get_conn() as conn:
                    conn.execute(
                        "INSERT INTO documents (title, category, file_path, created_date) VALUES (?, ?, ?, ?)",
                        (title, category, file_path, date.today())
                    )
                    conn.commit()
                st.success("✅ Đã lưu hồ sơ thành công!")
    
    with tab2:
        st.subheader("Danh sách hồ sơ")
        
        with get_conn() as conn:
            documents = pd.read_sql("SELECT * FROM documents ORDER BY created_date DESC", conn)
        
        if not documents.empty:
            for _, doc in documents.iterrows():
                with st.expander(f"📄 {doc['title']} - {doc['category']}"):
                    st.write(f"**Ngày tạo:** {doc['created_date']}")
                    if doc['file_path'] and os.path.exists(doc['file_path']):
                        with open(doc['file_path'], "rb") as f:
                            st.download_button(
                                "📥 Tải xuống",
                                f,
                                file_name=os.path.basename(doc['file_path'])
                            )
        else:
            st.info("Chưa có hồ sơ nào")
# DASHBOARD tổng quan
elif page == "Dashboard tổng quan":
    st.title("📁 DASHBOARD tổng quan")
    
    tab1, tab2 = st.tabs(["Công việc đã giải quyết đúng hạn", "Công việc chưa giải quyết"])
    
    with tab1:
        st.subheader("Xem số lượng công việc")
        
        with st.form("doc_form"):
            title = st.text_input("Tiêu đề hồ sơ")
            category = st.selectbox("Danh mục", ["Hợp đồng", "Báo cáo", "Tài liệu", "Khác"])
            uploaded_file = st.file_uploader("Tải lên file", type=['pdf', 'docx', 'txt'])
            
            submitted = st.form_submit_button("Lưu hồ sơ")
            
            if submitted and title:
                file_path = None
                if uploaded_file is not None:
                    os.makedirs('documents', exist_ok=True)
                    file_path = f"documents/{uploaded_file.name}"
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                
                with get_conn() as conn:
                    conn.execute(
                        "INSERT INTO documents (title, category, file_path, created_date) VALUES (?, ?, ?, ?)",
                        (title, category, file_path, date.today())
                    )
                    conn.commit()
                st.success("✅ Đã lưu hồ sơ thành công!")
    
    with tab2:
        st.subheader("Danh sách hồ sơ")
        
        with get_conn() as conn:
            documents = pd.read_sql("SELECT * FROM documents ORDER BY created_date DESC", conn)
        
        if not documents.empty:
            for _, doc in documents.iterrows():
                with st.expander(f"📄 {doc['title']} - {doc['category']}"):
                    st.write(f"**Ngày tạo:** {doc['created_date']}")
                    if doc['file_path'] and os.path.exists(doc['file_path']):
                        with open(doc['file_path'], "rb") as f:
                            st.download_button(
                                "📥 Tải xuống",
                                f,
                                file_name=os.path.basename(doc['file_path'])
                            )
        else:
            st.info("Chưa có hồ sơ nào")

st.sidebar.markdown("---")
st.sidebar.info("PHẦN MỀM QUẢN LÝ CÔNG VIỆC NỘI BỘ")