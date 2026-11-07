import io
import datetime
import pandas as pd
import streamlit as st
from supabase import create_client
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ---------------------------------------------------------
# 1. INITIALIZE SUPABASE CLIENT
# ---------------------------------------------------------
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# ---------------------------------------------------------
# 2. AUTHENTICATION MODULE
# ---------------------------------------------------------
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🔒 Restricted Access")
        password = st.text_input("Enter Password", type="password")
        if st.button("Log In"):
            if password == "Aadadv01!Aadadv01!":  # Change your password here
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password")
        return False
    return True

if check_password():
    st.sidebar.title("Navigation")
    menu = st.sidebar.radio("Go to", ["Daily Attendance", "Monthly Invoicing", "Manage Students"])

    # ---------------------------------------------------------
    # 3. MANAGE STUDENTS
    # ---------------------------------------------------------
    if menu == "Manage Students":
        st.header("👥 Manage Student Roster")
        
        # Add new student
        new_student = st.text_input("Enter Student Name")
        if st.button("Add Student"):
            if new_student:
                supabase.table("students").insert({"student_name": new_student}).execute()
                st.success(f"Added {new_student} successfully!")
                st.rerun()

        # View current students
        response = supabase.table("students").select("*").execute()
        students_data = response.data
        if students_data:
            st.write("### Current Students")
            df_students = pd.DataFrame(students_data)
            st.dataframe(df_students[["student_name"]])

    # ---------------------------------------------------------
    # 4. DAILY ATTENDANCE MARKER
    # ---------------------------------------------------------
    elif menu == "Daily Attendance":
        st.header("📋 Daily Attendance Register")
        
        selected_date = st.date_input("Select Date", datetime.date.today())
        month_str = selected_date.strftime("%Y-%m")
        
        # Fetch students from Supabase
        res = supabase.table("students").select("student_name").execute()
        students = [row["student_name"] for row in res.data] if res.data else []
        
        if students:
            with st.form("attendance_form"):
                st.write(f"Marking attendance for **{selected_date.strftime('%d %B %Y')}**")
                
                attendance_states = {}
                for name in students:
                    attendance_states[name] = st.checkbox(f"Present: {name}", value=False)
                
                submitted = st.form_submit_button("Save Attendance")
                
                if submitted:
                    records_to_insert = []
                    for name, is_present in attendance_states.items():
                        if is_present:
                            records_to_insert.append({
                                "date": str(selected_date),
                                "month": month_str,
                                "student_name": name,
                                "status": "Present"
                            })
                    
                    if records_to_insert:
                        supabase.table("attendance").insert(records_to_insert).execute()
                        st.success("Attendance saved securely to Supabase cloud!")
                    else:
                        st.info("No students marked present.")
        else:
            st.warning("No students found. Please add students in the 'Manage Students' tab first.")

    # ---------------------------------------------------------
    # 5. MONTHLY INVOICE GENERATOR & PDF ENGINE
    # ---------------------------------------------------------
    elif menu == "Monthly Invoicing":
        st.header("🧾 Generate Monthly PDF Invoice")

        res = supabase.table("students").select("student_name").execute()
        students = [row["student_name"] for row in res.data] if res.data else []
        
        selected_student = st.selectbox("Select Student", students) if students else None
        selected_month = st.text_input("Enter Month (YYYY-MM)", datetime.date.today().strftime("%Y-%m"))
        per_class_rate = st.number_input("Per Class Rate (₹)", min_value=0.0, value=150.0, step=10.0)

        if st.button("Generate & Download PDF Invoice") and selected_student:
            # Fetch attendance records for this student and month from Supabase
            att_res = supabase.table("attendance").select("*").eq("student_name", selected_student).eq("month", selected_month).execute()
            att_records = att_res.data if att_res.data else []
            
            present_dates = [row["date"] for row in att_records]
            total_classes = len(present_dates)
            total_amount = total_classes * per_class_rate

            # Build PDF Document in memory
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
            story = []
            styles = getSampleStyleSheet()

            # Add Logo Banner
            try:
                logo = RLImage("WhatsApp Image 2026-10-31 at 08.57.01.jpeg", width=500, height=120)[cite: 2]
                story.append(logo)
                story.append(Spacer(1, 15))
            except Exception:
                pass

            # Invoice Title & Metadata
            title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#1A2B4C'))
            story.append(Paragraph(f"INVOICE - {selected_month}", title_style))
            story.append(Spacer(1, 10))

            meta_text = f"""
            <b>Student Name:</b> {selected_student}<br/>
            <b>Billing Period:</b> {selected_month}<br/>
            <b>Date Issued:</b> {datetime.date.today().strftime('%d %b %Y')}
            """
            story.append(Paragraph(meta_text, styles['Normal']))
            story.append(Spacer(1, 15))

            # Itemized Attendance Table
            table_data = [["S.No", "Date Attended", "Status", "Rate per Class", "Amount"]]
            for i, d in enumerate(present_dates, start=1):
                table_data.append([str(i), str(d), "Present", f"₹{per_class_rate:.2f}", f"₹{per_class_rate:.2f}"])

            table_data.append(["", "", "", "Total Classes:", str(total_classes)])
            table_data.append(["", "", "", "Total Amount Due:", f"₹{total_amount:.2f}"])

            t = Table(table_data, colWidths=[40, 150, 100, 120, 90])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A2B4C')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -3), 0.5, colors.grey),
                ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (3, -2), (-1, -1), colors.HexColor('#EAEAEA')),
            ]))
            story.append(t)

            doc.build(story)
            buffer.seek(0)

            st.download_button(
                label="📄 Download Printable PDF Invoice",
                data=buffer,
                file_name=f"Invoice_{selected_student}_{selected_month}.pdf",
                mime="application/pdf"
            )