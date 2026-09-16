from datetime import date
import io
import re
import sqlite3
import pandas as pd
import pypdf
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
import streamlit as st

# --- DATABASE SETUP ---
DB_FILE = "meeting_scheduler.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Students / Participants table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT,
            privileges TEXT
        )
    """)
    # Schedules table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_date TEXT,
            meeting_type TEXT,
            part_name TEXT,
            assigned_person TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


# --- MULTI-LANGUAGE TEMPLATES ---
TRANSLATIONS = {
    "English": {
        "slip_title": "Meeting Assignment Slips",
        "part": "Part",
        "assigned": "Assigned To",
        "date": "Date",
    },
    "Spanish (Español)": {
        "slip_title": "Hoja de Designaciones",
        "part": "Parte",
        "assigned": "Designado a",
        "date": "Fecha",
    },
    "French (Français)": {
        "slip_title": "Fiches de Désignations",
        "part": "Partie",
        "assigned": "Attribué à",
        "date": "Date",
    },
}


# --- HELPER FUNCTIONS ---
def get_students():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM students", conn)
    conn.close()
    return df


def add_student(name, gender, privileges):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO students (name, gender, privileges) VALUES (?, ?, ?)",
        (name, gender, privileges),
    )
    conn.commit()
    conn.close()


def delete_student(student_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()


def get_schedules():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM schedules", conn)
    conn.close()
    return df


def save_schedule(meeting_date, meeting_type, assignments):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for part_name, person in assignments.items():
        cursor.execute(
            """
                INSERT INTO schedules (meeting_date, meeting_type, part_name, assigned_person)
                VALUES (?, ?, ?, ?)
            """,
            (str(meeting_date), meeting_type, part_name, person),
        )
    conn.commit()
    conn.close()


def generate_pdf_slips(meeting_date, filtered_df, lang_dict):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "SlipTitle", parent=styles["Heading2"], fontSize=14, spaceAfter=6
    )
    body_style = ParagraphStyle(
        "SlipBody", parent=styles["Normal"], fontSize=10, spaceAfter=12
    )

    story.append(
        Paragraph(
            f"<b>{lang_dict['slip_title']} - {meeting_date}</b>", title_style
        )
    )
    story.append(Spacer(1, 10))

    for index, row in filtered_df.iterrows():
        slip_text = (
            f"<b>{lang_dict['part']}:</b> {row['part_name']}<br/>"
            f"<b>{lang_dict['assigned']}:</b> {row['assigned_person']}<br/>"
            f"<b>{lang_dict['date']}:</b> {meeting_date}"
        )
        story.append(Paragraph(slip_text, body_style))
        story.append(Spacer(1, 15))

    doc.build(story)
    buffer.seek(0)
    return buffer


# --- STREAMLIT UI ---
st.set_page_config(
    page_title="Meeting Scheduler", page_icon="📅", layout="wide"
)

st.title("📅 Midweek & Weekend Meeting Scheduler")
st.write(
    "Manage meeting assignments, avoid double bookings, and generate multi-lang slips."
)

# Sidebar Options & Navigation
selected_lang = st.sidebar.selectbox(
    "Language Template", list(TRANSLATIONS.keys())
)
t = TRANSLATIONS[selected_lang]

menu = st.sidebar.selectbox(
    "Navigation",
    [
        "View Schedules",
        "Create/Edit Schedule",
        "Manage Participants",
        "Upload PDF Brochure",
        "Export",
    ],
)

students_df = get_students()

if menu == "Manage Participants":
    st.header("👥 Participant File")

    with st.form("add_student_form", clear_on_submit=True):
        st.subheader("Add New Participant")
        name = st.text_input("Full Name")
        gender = st.selectbox("Category", ["Brother", "Sister"])
        privileges = st.multiselect(
            "Assigned Privileges",
            [
                "Chairman",
                "Prayer",
                "Bible Reading",
                "Initial Presentation",
                "Making Disciples",
                "Explaining Beliefs",
                "Talk",
                "Reader",
            ],
        )
        submitted = st.form_submit_button("Add Participant")
        if submitted and name:
            add_student(name, gender, ", ".join(privileges))
            st.success(f"Successfully added {name}!")
            st.rerun()

    st.subheader("Current List")
    if not students_df.empty:
        st.dataframe(students_df, use_container_width=True)

        student_to_delete = st.selectbox(
            "Select Participant to Delete",
            students_df["id"].tolist(),
            format_func=lambda x: students_df.loc[
                students_df["id"] == x, "name"
            ].values[0],
        )
        if st.button("Delete Selected Participant"):
            delete_student(student_to_delete)
            st.warning("Participant deleted.")
            st.rerun()
    else:
        st.info("No participants added yet.")

elif menu == "Create/Edit Schedule":
    st.header("📝 Create Meeting Schedule")

    meeting_type = st.selectbox(
        "Meeting Type", ["Midweek Meeting", "Weekend Meeting"]
    )
    
    # Check if we have imported weeks from the PDF
    selected_imported_week = None
    if "available_weeks" in st.session_state and st.session_state["available_weeks"]:
        use_import = st.checkbox("Auto-fill details from uploaded PDF brochure")
        if use_import:
            selected_imported_week = st.selectbox(
                "Select Week from Brochure", st.session_state["available_weeks"]
            )

    meeting_date = st.date_input("Meeting Date", value=date.today())

    if students_df.empty:
        st.warning(
            "Please add participants in the 'Manage Participants' tab first."
        )
    else:
        student_names = students_df["name"].tolist()

        if meeting_type == "Midweek Meeting":
            parts = [
                "Chairman",
                "Opening Prayer",
                "Treasures Talk",
                "Digging Gems",
                "Bible Reading",
                "Initial Presentation",
                "Making Disciples",
                "Explaining Beliefs",
                "Living Part 1",
                "Living Part 2",
                "Conductor",
                "Reader",
                "Closing Prayer",
            ]
        else:
            parts = [
                "Chairman",
                "Opening Prayer / Song",
                "Public Talk Speaker",
                "Watchtower Conductor",
                "Watchtower Reader",
                "Closing Prayer",
            ]

        assignments = {}
        with st.form("schedule_form"):
            title_text = f"Assign Parts for {meeting_type}"
            if selected_imported_week:
                title_text += f" ({selected_imported_week.title()})"
            st.subheader(title_text)

            for part in parts:
                assignments[part] = st.selectbox(
                    f"{part}", ["-- Unassigned --"] + student_names, key=part
                )

            submitted = st.form_submit_button("Save Schedule")
            if submitted:
                valid_assignments = {
                    k: v for k, v in assignments.items() if v != "-- Unassigned --"
                }
                chosen_people = list(valid_assignments.values())

                # Check for duplicates in form submission
                duplicates = set(
                    [
                        person
                        for person in chosen_people
                        if chosen_people.count(person) > 1
                    ]
                )

                # Check for existing database conflicts on this date
                existing_schedules = get_schedules()
                already_booked = []
                if not existing_schedules.empty:
                    date_matches = existing_schedules[
                        existing_schedules["meeting_date"] == str(meeting_date)
                    ]
                    booked_people_on_date = date_matches["assigned_person"].tolist()
                    already_booked = [p for p in chosen_people if p in booked_people_on_date]

                if duplicates:
                    st.error(
                        "⚠️ Scheduling Conflict: The following person is assigned to"
                        f" multiple parts this week: {', '.join(duplicates)}"
                    )
                elif already_booked:
                    st.error(
                        "⚠️ Scheduling Conflict: The following person is already assigned"
                        f" on {meeting_date}: {', '.join(already_booked)}"
                    )
                else:
                    save_schedule(meeting_date, meeting_type, valid_assignments)
                    st.success(f"Schedule for {meeting_date} saved successfully!")

elif menu == "View Schedules":
    st.header("📋 View Saved Schedules")
    schedules_df = get_schedules()

    if not schedules_df.empty:
        selected_date = st.selectbox(
            "Select Meeting Date", schedules_df["meeting_date"].unique()
        )
        filtered_df = schedules_df[schedules_df["meeting_date"] == selected_date]

        st.subheader(f"Schedule for: {selected_date}")
        st.table(filtered_df[["meeting_type", "part_name", "assigned_person"]])

        # PDF Download Button (Using selected language template)
        pdf_data = generate_pdf_slips(selected_date, filtered_df, t)
        st.download_button(
            label=f"📄 Download PDF Slips ({selected_lang})",
            data=pdf_data,
            file_name=f"assignment_slips_{selected_date}.pdf",
            mime="application/pdf",
        )

        # Print View Section
        if st.button("🖨️ Open Print View"):
            print_html = f"""
                <h3>Meeting Schedule - {selected_date}</h3>
                <hr>
                <table style="width:100%; border-collapse: collapse;">
                    <tr>
                        <th style="text-align:left; border-bottom:1px solid black; padding: 6px;">{t['part']}</th>
                        <th style="text-align:left; border-bottom:1px solid black; padding: 6px;">{t['assigned']}</th>
                    </tr>
            """
            for index, row in filtered_df.iterrows():
                print_html += f"<tr><td style='padding: 6px;'>{row['part_name']}</td><td style='padding: 6px;'>{row['assigned_person']}</td></tr>"
            print_html += "</table>"
            st.markdown(print_html, unsafe_allow_html=True)
            st.info("Tip: Press Ctrl+P (or Cmd+P) to print this view.")
    else:
        st.info("No schedules have been created yet.")

elif menu == "Upload PDF Brochure":
    st.header("📖 Import Meeting Brochure (PDF)")
    st.write(
        "Upload the official meeting workbook brochure PDF downloaded from jw.org. "
        "The app will extract the text and parse upcoming schedule weeks."
    )

    uploaded_pdf = st.file_uploader("Choose PDF file", type=["pdf"])

    if uploaded_pdf is not None:
        reader = pypdf.PdfReader(uploaded_pdf)
        extracted_text = ""

        for i, page in enumerate(reader.pages):
            extracted_text += f"\n--- Page {i+1} ---\n" + page.extract_text()

        # Save to session state so other tabs can access it
        st.session_state["extracted_brochure_text"] = extracted_text

        # Regex to find weekly headers (e.g., "SEPTEMBER 7-13")
        date_pattern = r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+\d{1,2}[–-]\d{1,2}"
        found_weeks = re.findall(date_pattern, extracted_text, re.IGNORECASE)

        if found_weeks:
            st.session_state["available_weeks"] = list(dict.fromkeys(found_weeks))
            st.success(f"Successfully parsed {len(st.session_state['available_weeks'])} meeting weeks from the brochure!")
        else:
            st.warning("PDF uploaded, but standard date headers weren't automatically recognized.")

        with st.expander("View Extracted Raw Text"):
            st.text_area("Raw Text Preview", extracted_text, height=350)

elif menu == "Export":
    st.header("📤 Export Data")
    schedules_df = get_schedules()

    if not schedules_df.empty:
        csv = schedules_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Schedule as CSV",
            data=csv,
            file_name="meeting_schedule.csv",
            mime="text/csv",
        )
    else:
        st.info("No schedule data available for export.")
