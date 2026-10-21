// The fixed lists from constants.py. Keep in step with that file: the Python side uses the same names.
export const MIDWEEK = "Midweek Meeting";
export const WEEKEND = "Weekend Meeting";
export const MEETING_TYPES = [MIDWEEK, WEEKEND] as const;
export type MeetingType = (typeof MEETING_TYPES)[number];

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export const CATEGORIES = ["Brother", "Sister"] as const;
export const GROUPS = ["Child", "Youth", "New student"] as const;

export const PRIVILEGES = [
  "Chairman", "Prayer", "Treasures Talk", "Spiritual Gems", "Bible Reading", "Initial Presentation",
  "Making Disciples", "Explaining Beliefs", "Student Talk", "Living Part", "Bible Study Conductor", "Reader",
  "Aux Classroom Counselor", "Weekend Chairman", "Public Talk", "Watchtower Reader",
] as const;
export const ROLES = PRIVILEGES;

export const LANGUAGES = ["English", "Ga"] as const;
export type Language = (typeof LANGUAGES)[number];

export const MAIN_HALL = "main_hall";
export const HALL_NAMES: Record<string, string> = {
  main_hall: "Main hall", aux_1: "Auxiliary classroom 1", aux_2: "Auxiliary classroom 2",
};

export const SECTION_TITLES: Record<string, string> = {
  Opening: "Opening", Treasures: "Treasures From God’s Word", Ministry: "Apply Yourself to the Field Ministry",
  Living: "Living as Christians", Closing: "Closing", Weekend: "Weekend meeting",
};
// Colour carries meaning only: these three mark the workbook sections.
export const SECTION_COLORS: Record<string, string> = {
  Treasures: "#5B6770", Ministry: "#B7821F", Living: "#8E2A2A", Opening: "#8A94A0", Closing: "#8A94A0",
  Weekend: "#8A94A0",
};

export const EVENT_KINDS = ["assembly", "convention"] as const;
export const EVENT_NAMES: Record<string, string> = { assembly: "Circuit Assembly", convention: "Convention" };
export const EVENT_TEXT: Record<string, { en: string; ga: string }> = {
  assembly: { en: "Assembly Week", ga: "Kpokpaa Nɔ Kpee Otsi" },
  convention: { en: "Convention Week", ga: "Kpokpaa wulu Nɔ Kpee Otsi" },
};

export const SAME_ROLE_GAP_DAYS = 10;
export const BACKUP_REMINDER_DAYS = 14;
