import uuid
from datetime import datetime

class PatientIDGenerator:
    @staticmethod
    def generate():
        """
        Generates a 20-digit numeric patient ID.
        Format: YYYYMMDDHHMMSS + 6 random digits (20 digits total)
        Example: 20250427143052123456
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")  # 14 digits
        random_part = str(uuid.uuid4().int)[-6:]              # last 6 digits
        return f"{timestamp}{random_part}"                    # 20 digits

    @staticmethod
    def generate_ticket_number(visit_sequence):
        """
        Generates a ticket number for visits.
        Format: T-YYYYMMDD-XXXX
        Example: T-20250427-0001
        """
        date_part = datetime.now().strftime("%Y%m%d")
        return f"T-{date_part}-{str(visit_sequence).zfill(4)}"