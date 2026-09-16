from datetime import date
import io
import sqlite3
import pandas as pd
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


def generate_pdf_slips(meeting_date, filtered_df):
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
      Paragraph(f"<b>Meeting Assignment Slips - {meeting_date}</b>", title_style)
  )
  story.append(Spacer(1, 10))

  for index, row in filtered_df.iterrows():
    slip_text = (
        f"<b>Part:</b> {row['part_name']}<br/><b>Assigned To:"
        f"</b> {row['assigned_person']}<br/><b>Date:</b> {meeting_date}"
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
st.write("Manage meeting assignments, prevent conflicts, and generate slips.")

# Sidebar Navigation
menu = st.sidebar.selectbox(
    "Navigation",
    ["View Schedules", "Create/Edit Schedule", "Manage Participants", "Export"],
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
      st.subheader(f"Assign Parts for {meeting_type}")
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

    # PDF Download Button
    pdf_data = generate_pdf_slips(selected_date, filtered_df)
    st.download_button(
        label="📄 Download Printable PDF Slips",
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
                        <th style="text-align:left; border-bottom:1px solid black; padding: 6px;">Part</th>
                        <th style="text-align:left; border-bottom:1px solid black; padding: 6px;">Assigned Person</th>
                    </tr>
            """
      for index, row in filtered_df.iterrows():
        print_html += f"<tr><td style='padding: 6px;'>{row['part_name']}</td><td style='padding: 6px;'>{row['assigned_person']}</td></tr>"
      print_html += "</table>"
      st.markdown(print_html, unsafe_allow_html=True)
      st.info("Tip: Press Ctrl+P (or Cmd+P) to print this view.")
  else:
    st.info("No schedules have been created yet.")

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
