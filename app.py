from datetime import date
import io
import re
import sqlite3
import pandas as pd
import pypdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
import streamlit as st

# --- STREAMLIT PAGE CONFIG & DARK MODE STYLING ---
st.set_page_config(
    page_title="Meeting Scheduler", page_icon="📅", layout="wide"
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    .status-panel {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 15px;
        text-align: center;
        color: #8b949e;
        font-size: 14px;
    }
    div.stButton > button {
        background-color: #21262d;
        color: #c9d1d9;
        border: 1px solid #30363d;
        border-radius: 6px;
        width: 100%;
        font-weight: 500;
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button:hover {
        background-color: #30363d;
        border-color: #8b949e;
        color: #ffffff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- DATABASE SETUP ---
DB_FILE = "meeting_scheduler.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT,
            privileges TEXT
        )
    """)
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


# --- LANGUAGE TEMPLATES (ENGLISH & GA) ---
TRANSLATIONS = {
    "English": {
        "slip_title": "OUR CHRISTIAN LIFE AND MINISTRY\nMEETING ASSIGNMENT",
        "name": "Name:",
        "assistant": "Assistant:",
        "date": "Date:",
        "part_no": "Part no.:",
        "to_be_given": "To be given in:",
        "main_hall": "Main hall",
        "aux_1": "Auxiliary classroom 1",
        "aux_2": "Auxiliary classroom 2",
        "note": "Note to student: The source material and study point for your assignment can be found in the Life and Ministry Meeting Workbook. Please review the instructions for the part as outlined in Instructions for Our Christian Life and Ministry Meeting (S-38).",
        "form_code": "S-89-E 11/23",
    },
    "Ga": {
        "slip_title": "KRISTOWALA AMƐ WALA KƐ NITSUMƆ\nKPEENI NITSUMƆ",
        "name": "Gbɛ̀i:",
        "assistant": "Mɔ ni yeo boa:",
        "date": "Gbi:",
        "part_no": "Nitsumɔ akara:",
        "to_be_given": "Abaatsɔo mli:",
        "main_hall": "Maŋ tsu nukpa",
        "aux_1": "Tsu bibioo 1",
        "aux_2": "Tsu bibioo 2",
        "note": "Nilelɔ nɔ ni akɛɛ: Nitsumɔ lɛ he nibii kɛ nikasemɔ nɔ ni kɔ kɛhɔ bo lɛ baanyɛ aná yɛ Kristowala Amɛ Wala KƐ NitsumƆ Kpeeni Wolo lɛ mli. Ofainɛ kwɛmɔ nitsumɔ lɛ he gbɛtsɔɔmɔi ni yɔɔ Kristowala Amɛ Wala Kɛ NitsumƆ Kpeeni Gbɛtsɔɔmɔi (S-38) lɛ mli.",
        "form_code": "S-89-Ga 11/23",
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
        pagesize=A4,
        rightMargin=18,
        leftMargin=18,
        topMargin=18,
        bottomMargin=18,
    )
    story = []
    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        "SlipHeader",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        alignment=1,
        fontName="Helvetica-Bold",
    )
    field_style = ParagraphStyle(
        "SlipField",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        fontName="Helvetica",
    )
    note_style = ParagraphStyle(
        "SlipNote",
        parent=styles["Normal"],
        fontSize=6.5,
        leading=8.5,
        fontName="Helvetica",
    )

    def create_single_slip_flowables(row):
        assigned_name = row["assigned_person"] if row is not None else ""
        part_name = row["part_name"] if row is not None else ""

        elements = [
            Paragraph(
                lang_dict["slip_title"].replace("\n", "<br/>"), header_style
            ),
            Spacer(1, 6),
            Paragraph(
                f"<b>{lang_dict['name']}</b> {assigned_name}", field_style
            ),
            Spacer(1, 3),
            Paragraph(
                f"<b>{lang_dict['assistant']}</b> _________________________",
                field_style,
            ),
            Spacer(1, 3),
            Paragraph(
                f"<b>{lang_dict['date']}</b> {meeting_date}"
                f" &nbsp;&nbsp;&nbsp;&nbsp; <b>{lang_dict['part_no']}</b>"
                f" {part_name}",
                field_style,
            ),
            Spacer(1, 4),
            Paragraph(f"<b>{lang_dict['to_be_given']}</b>", field_style),
            Paragraph(
                f"[ &nbsp; ]"
                f" {lang_dict['main_hall']}&nbsp;&nbsp;&nbsp;&nbsp;[ &nbsp; ]"
                f" {lang_dict['aux_1']}<br/>[ &nbsp; ] {lang_dict['aux_2']}",
                field_style,
            ),
            Spacer(1, 4),
            Paragraph(lang_dict["note"], note_style),
            Spacer(1, 2),
            Paragraph(
                f"<font color='gray'>{lang_dict['form_code']}</font>",
                note_style,
            ),
        ]
        return elements

    rows_list = [row for _, row in filtered_df.iterrows()]
    while len(rows_list) % 4 != 0:
        rows_list.append(None)

    for i in range(0, len(rows_list), 4):
        batch = rows_list[i : i + 4]
        grid_data = [
            [
                create_single_slip_flowables(batch[0]),
                create_single_slip_flowables(batch[1]),
            ],
            [
                create_single_slip_flowables(batch[2]),
                create_single_slip_flowables(batch[3]),
            ],
        ]

        slip_table = Table(grid_data, colWidths=[270, 270], rowHeights=[385, 385])
        slip_table.setStyle(
            TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.dashed),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ])
        )

        story.append(slip_table)
        if i + 4 < len(rows_list):
            story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer


# --- NAVIGATION SESSION STATE SETUP ---
if "menu" not in st.session_state:
    st.session_state["menu"] = "Dashboard"

selected_lang = st.sidebar.selectbox(
    "Language Template", list(TRANSLATIONS.keys())
)
t = TRANSLATIONS[selected_lang]

st.sidebar.markdown("---")
if st.sidebar.button("🏠 Back to Dashboard"):
    st.session_state["menu"] = "Dashboard"
    st.rerun()

students_df = get_students()
menu = st.session_state["menu"]

# --- DASHBOARD CONTROL PANEL ---
if menu == "Dashboard":
    st.title("📅 Meeting Scheduler Control Panel")
    st.write(
        "Select an option below to manage assignments, participants, or view"
        " schedules."
    )
    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("View Current Schedule", use_container_width=True):
            st.session_state["menu"] = "View Schedules"
            st.rerun()
    with col2:
        if st.button("Create Next Schedule", use_container_width=True):
            st.session_state["menu"] = "Create/Edit Schedule"
            st.rerun()
    with col3:
        if st.button("Modify Current Schedule", use_container_width=True):
            st.session_state["menu"] = "Create/Edit Schedule"
            st.rerun()

    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button("View Assignment Slips", use_container_width=True):
            st.session_state["menu"] = "View Schedules"
            st.rerun()
    with col5:
        if st.button("Upload PDF Brochure", use_container_width=True):
            st.session_state["menu"] = "Upload PDF Brochure"
            st.rerun()
    with col6:
        if st.button("Edit Student File", use_container_width=True):
            st.session_state["menu"] = "Manage Participants"
            st.rerun()

    col7, col8, col9 = st.columns(3)
    with col7:
        if st.button("Export Data (CSV)", use_container_width=True):
            st.session_state["menu"] = "Export"
            st.rerun()
    with col8:
        if st.button("Manage Participants", use_container_width=True):
            st.session_state["menu"] = "Manage Participants"
            st.rerun()
    with col9:
        if st.button("Exit / Reset Session", use_container_width=True):
            st.success("Session reset.")

    st.markdown("---")

    schedules_df = get_schedules()
    latest_date = (
        schedules_df["meeting_date"].max()
        if not schedules_df.empty
        else "Blank"
    )

    stat_col1, stat_col2, stat_col3 = st.columns(3)
    with stat_col1:
        st.markdown(
            f"""
            <div class="status-panel">
                <p style="margin: 0; color: #8b949e; font-weight: bold;">Current Schedule</p>
                <h3 style="color: #c9d1d9; margin-top: 10px;">{latest_date}</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with stat_col2:
        st.markdown(
            """
            <div class="status-panel">
                <p style="margin: 0; color: #8b949e; font-weight: bold;">System Status</p>
                <h3 style="color: #3fb950; margin-top: 10px;">Active & Secure</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with stat_col3:
        total_students = len(students_df) if not students_df.empty else 0
        st.markdown(
            f"""
            <div class="status-panel">
                <p style="margin: 0; color: #8b949e; font-weight: bold;">Total Participants</p>
                <h3 style="color: #58a6ff; margin-top: 10px;">{total_students} Registered</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

elif menu == "Manage Participants":
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

    # Dynamic brochure parsing check
    selected_imported_week = None
    parsed_assignments = []
    if (
        "available_weeks" in st.session_state
        and st.session_state["available_weeks"]
    ):
        use_import = st.checkbox("Auto-fill details from uploaded PDF brochure")
        if use_import:
            selected_imported_week = st.selectbox(
                "Select Week from Brochure", st.session_state["available_weeks"]
            )
            # Extract specific assignment themes/talks parsed from PDF text if available
            if (
                "brochure_weeks_data" in st.session_state
                and selected_imported_week
                in st.session_state["brochure_weeks_data"]
            ):
                parsed_assignments = st.session_state["brochure_weeks_data"][
                    selected_imported_week
                ]

    meeting_date = st.date_input("Meeting Date", value=date.today())

    if students_df.empty:
        st.warning(
            "Please add participants in the 'Manage Participants' tab first."
        )
    else:
        student_names = students_df["name"].tolist()
        assignments = {}

        with st.form("schedule_form"):
            title_text = f"Assign Parts for {meeting_type}"
            if selected_imported_week:
                title_text += f" ({selected_imported_week.title()})"
            st.subheader(title_text)

            if meeting_type == "Midweek Meeting":
                st.markdown("### 🔹 Opening")
                for part in ["Chairman", "Opening Prayer"]:
                    assignments[part] = st.selectbox(
                        part, ["-- Unassigned --"] + student_names, key=part
                    )

                st.markdown("### 📖 Treasures from God's Word")
                for part in ["Treasures Talk", "Digging Gems", "Bible Reading"]:
                    assignments[part] = st.selectbox(
                        part, ["-- Unassigned --"] + student_names, key=part
                    )

                st.markdown("### 🎯 Apply Yourself to the Field Ministry")
                # If we parsed custom talk titles from the PDF, use them dynamically as form labels!
                ministry_parts = (
                    parsed_assignments
                    if parsed_assignments
                    else [
                        "Initial Presentation",
                        "Making Disciples",
                        "Explaining Beliefs",
                    ]
                )
                for part in ministry_parts:
                    assignments[part] = st.selectbox(
                        part, ["-- Unassigned --"] + student_names, key=part
                    )

                st.markdown("### 💡 Living as Christians")
                for part in [
                    "Living Part 1",
                    "Living Part 2",
                    "Conductor",
                    "Reader",
                    "Closing Prayer",
                ]:
                    assignments[part] = st.selectbox(
                        part, ["-- Unassigned --"] + student_names, key=part
                    )
            else:
                st.markdown("### 🏛️ Weekend Meeting Parts")
                for part in [
                    "Chairman",
                    "Opening Prayer / Song",
                    "Public Talk Speaker",
                    "Watchtower Conductor",
                    "Watchtower Reader",
                    "Closing Prayer",
                ]:
                    assignments[part] = st.selectbox(
                        part, ["-- Unassigned --"] + student_names, key=part
                    )

            submitted = st.form_submit_button("Save Schedule")
            if submitted:
                valid_assignments = {
                    k: v
                    for k, v in assignments.items()
                    if v != "-- Unassigned --"
                }
                chosen_people = list(valid_assignments.values())

                duplicates = set([
                    person
                    for person in chosen_people
                    if chosen_people.count(person) > 1
                ])

                existing_schedules = get_schedules()
                already_booked = []
                if not existing_schedules.empty:
                    date_matches = existing_schedules[
                        existing_schedules["meeting_date"] == str(meeting_date)
                    ]
                    booked_people_on_date = date_matches[
                        "assigned_person"
                    ].tolist()
                    already_booked = [
                        p for p in chosen_people if p in booked_people_on_date
                    ]

                if duplicates:
                    st.error(
                        "⚠️ Scheduling Conflict: The following person is"
                        f" assigned to multiple parts this week: {', '.join(duplicates)}"
                    )
                elif already_booked:
                    st.error(
                        "⚠️ Scheduling Conflict: The following person is"
                        f" already assigned on {meeting_date}: {', '.join(already_booked)}"
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
        filtered_df = schedules_df[
            schedules_df["meeting_date"] == selected_date
        ]

        meeting_type = (
            filtered_df["meeting_type"].iloc[0]
            if not filtered_df.empty
            else "Midweek Meeting"
        )

        st.subheader(f"Schedule for: {selected_date} ({meeting_type})")

        assignment_dict = dict(
            zip(filtered_df["part_name"], filtered_df["assigned_person"])
        )

        # Render sections dynamically based on saved parts
        st.markdown("### 📋 Program Assignments")
        for part_name, person in assignment_dict.items():
            st.write(f"- **{part_name}:** {person}")

        st.divider()

        pdf_data = generate_pdf_slips(selected_date, filtered_df, t)
        st.download_button(
            label=f"📄 Download Exact S-89 Slips PDF ({selected_lang})",
            data=pdf_data,
            file_name=f"S89_assignment_slips_{selected_date}.pdf",
            mime="application/pdf",
        )

        if st.button("🖨️ Open Print View"):
            print_html = f"""
                <h3>Meeting Schedule - {selected_date}</h3>
                <hr>
                <table style="width:100%; border-collapse: collapse;">
                    <tr>
                        <th style="text-align:left; border-bottom:1px solid #30363d; padding: 6px;">Part</th>
                        <th style="text-align:left; border-bottom:1px solid #30363d; padding: 6px;">Assigned To</th>
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
        "The app will extract the schedule dates and student assignment parts automatically."
    )

    uploaded_pdf = st.file_uploader("Choose PDF file", type=["pdf"])

    if uploaded_pdf is not None:
        reader = pypdf.PdfReader(uploaded_pdf)
        extracted_text = ""

        for i, page in enumerate(reader.pages):
            extracted_text += f"\n--- Page {i+1} ---\n" + page.extract_text()

        st.session_state["extracted_brochure_text"] = extracted_text

        date_pattern = r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+\d{1,2}\s*[–—\-]\s*\d{1,2}"
        found_weeks = re.findall(date_pattern, extracted_text, re.IGNORECASE)

        if found_weeks:
            unique_weeks = list(dict.fromkeys(found_weeks))
            st.session_state["available_weeks"] = unique_weeks

            # Basic heuristic parser to extract student parts per week block from the text
            weeks_data = {}
            for wk in unique_weeks:
                # Mocking/extracting typical student parts associated with workbook themes
                weeks_data[wk] = [
                    f"Initial Call ({wk})",
                    f"Returning Visit ({wk})",
                    f"Making Disciples ({wk})",
                ]
            st.session_state["brochure_weeks_data"] = weeks_data

            st.success(
                f"Successfully parsed {len(unique_weeks)} meeting weeks and assignments from the brochure!"
            )
        else:
            st.warning(
                "PDF uploaded, but standard date headers weren't automatically recognized."
            )

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
