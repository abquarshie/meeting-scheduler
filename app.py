from datetime import date
import sqlite3
import pandas as pd
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
            INSERT INTO schedules (meeting_date, meeting_type, part_name,"
            " assigned_person)
            VALUES (?, ?, ?, ?)
        """,
        (str(meeting_date), meeting_type, part_name, person),
    )
  conn.commit()
  conn.close()


# --- STREAMLIT UI ---
st.set_page_config(
    page_title="Meeting Scheduler", page_icon="📅", layout="wide"
)

st.title("📅 Midweek & Weekend Meeting Scheduler")
st.write(
    "A custom, self-hosted web app built to handle your meeting parts and"
    " assignments cleanly."
)

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
