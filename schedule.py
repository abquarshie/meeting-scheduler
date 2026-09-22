# snippet illustrating the save button & role restriction pattern in schedule.py / form pages:
from auth import can_manage_midweek, can_manage_weekend, current_user_role

def render(students_df, t, selected_lang, aux_default):
    role = current_user_role()
    
    # Restrict sections based on role
    managing_midweek = can_manage_midweek()
    managing_weekend = can_manage_weekend()

    if not managing_midweek and managing_weekend:
        st.info("ℹ️ You are signed in as **Talk Coordinator**. You can create and manage weekend meetings.")
    elif managing_midweek and not managing_weekend:
        st.info("ℹ️ You are signed in as **Life and Ministry Overseer**. You can create and manage midweek meetings.")

    # Form / editing buffer container
    with st.form("meeting_schedule_form"):
        # ... render form fields for midweek or weekend parts based on permissions ...
        
        # Explicit Save Button to prevent premature write traffic
        submitted = st.form_submit_button("💾 Save Changes", type="primary")
        if submitted:
            # Perform permission and validation checks before committing changes to DB
            if not managing_midweek and contains_midweek_changes:
                st.error("Permission denied: You cannot modify midweek meetings.")
            elif not managing_weekend and contains_weekend_changes:
                st.error("Permission denied: You cannot modify weekend meetings.")
            else:
                # Save data to shared database backend
                save_schedule_to_db(...)
                st.success("Changes saved successfully!")
