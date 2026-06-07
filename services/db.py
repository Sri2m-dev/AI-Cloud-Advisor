import psycopg2

def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="AI-Cloud-Advisor-Dev",
        user="postgres",
        password="Siri@18068479"
    )

