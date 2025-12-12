import pyodbc

def get_connection():
    """
    Returns a connection object to the KeystrokeTestDB database
    """
    SERVER_NAME = r"DESKTOP-8JG6SC3\SQLEXPRESS"
    DATABASE_NAME = "KeystrokeTestDB"   # Updated

    conn = pyodbc.connect(
        f"DRIVER={{SQL Server}};"
        f"SERVER={SERVER_NAME};"
        f"DATABASE={DATABASE_NAME};"
        "Trusted_Connection=yes;"
    )
    return conn
