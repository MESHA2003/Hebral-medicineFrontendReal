from datetime import datetime

class PatientIDGenerator:
    @staticmethod
    def generate():
        """
        Generates a patient ID with SCH prefix and yearly sequential numbering.
        Example: SCH-2026-00001 (resets each year, year auto-changes)
        """
        from .models import Patient
        current_year = datetime.now().year
        # Find the last patient ID for this year
        last_patient = Patient.objects.filter(
            patient_id__startswith=f"SCH-{current_year}-"
        ).order_by('-id').first()
        if last_patient:
            last_seq = int(last_patient.patient_id.split('-')[-1])
            next_seq = last_seq + 1
        else:
            next_seq = 1
        return f"SCH-{current_year}-{str(next_seq).zfill(5)}"

    @staticmethod
    def generate_ticket_number(visit_sequence):
        """
        Generates a ticket number for visits.
        Format: SHC-YYYYMMDD-XXXX
        Example: SHC-20250427-0001
        """
        date_part = datetime.now().strftime("%Y%m%d")
        return f"SHC-{date_part}-{str(visit_sequence).zfill(4)}"
