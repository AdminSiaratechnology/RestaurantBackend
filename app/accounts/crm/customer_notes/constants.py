from enum import Enum


class CustomerNoteType(str, Enum):
    GENERAL = "general"
    COMPLAINT = "complaint"
    FEEDBACK = "feedback"
    PREFERENCE = "preference"
    FOLLOW_UP = "follow_up"
    ALLERGY = "allergy"


NOTE_TYPE_LABELS = {
    CustomerNoteType.GENERAL: "General",
    CustomerNoteType.COMPLAINT: "Complaint",
    CustomerNoteType.FEEDBACK: "Feedback",
    CustomerNoteType.PREFERENCE: "Preference",
    CustomerNoteType.FOLLOW_UP: "Follow-up",
    CustomerNoteType.ALLERGY: "Allergy",
}