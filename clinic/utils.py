import uuid
from datetime import datetime

class PatientIDGenerator:
    @staticmethod
    def generate():
        """
        Generates a patient ID with CSH prefix.
        Example: CSH-20250427143052123456
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")  # 14 digits
        random_part = str(uuid.uuid4().int)[-6:]              # last 6 digits
        return f"CSH-{timestamp}{random_part}"

    @staticmethod
    def generate_ticket_number(visit_sequence):
        """
        Generates a ticket number for visits.
        Format: SHC-YYYYMMDD-XXXX
        Example: SHC-20250427-0001
        """
        date_part = datetime.now().strftime("%Y%m%d")
        return f"SHC-{date_part}-{str(visit_sequence).zfill(4)}"