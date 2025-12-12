from flask import Flask, request, jsonify
from flask_cors import CORS
import pickle
import os
import pandas as pd
import pyodbc
from datetime import datetime, timedelta
from sklearn.exceptions import NotFittedError

# -----------------------------
# Flask API Initialization
# -----------------------------
# Flask application ko initialize kiya gaya hai.
app = Flask(__name__)
# Frontend (Client) se communication allow karne ke liye CORS enable kiya gaya hai.
CORS(app) 

# -----------------------------
# Global Variables for Database & Security
# -----------------------------
DB_TABLE_NAME = "KeystrokeLogs" 
# Login ki nakam koshish (failed attempts) ko store karta hai.
LOGIN_ATTEMPTS = {} 
MAX_ATTEMPTS = 5         # Lockout se pehle max koshish (attempts).
LOCKOUT_DURATION = 60    # Lockout ka waqt (seconds mein). 
CORRECT_PASSWORD = "password123"
MODEL_FILE = "model.pkl"
ENCODERS_FILE = "encoders.pkl"

model = None
encoders = None

# -----------------------------
# Database Connection Logic 
# -----------------------------
def get_connection():
    """KeystrokeTestDB database se connection object return karta hai."""
    SERVER_NAME = r"DESKTOP-8JG6SC3\SQLEXPRESS"
    DATABASE_NAME = "KeystrokeTestDB"

    try:
        conn = pyodbc.connect(
            f"DRIVER={{SQL Server}};"
            f"SERVER={SERVER_NAME};"
            f"DATABASE={DATABASE_NAME};"
            "Trusted_Connection=yes;"
        )
        return conn
    except Exception as e:
        print(f"Database Connection Error: {e}")
        return None

# -----------------------------
# Table Creation on Startup 
# -----------------------------
def create_table_if_not_exists():
    """Agar table maujood nahi hai toh use banata hai."""
    conn = None
    try:
        conn = get_connection()
        if not conn:
            print("Cannot check/create table: DB connection failed.")
            return False

        cursor = conn.cursor()
        
        check_query = f"""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='{DB_TABLE_NAME}' and xtype='U')
        BEGIN
            CREATE TABLE {DB_TABLE_NAME} (
                LogID INT IDENTITY(1,1) PRIMARY KEY, 
                UserName VARCHAR(100) NOT NULL,
                KeyPressed VARCHAR(50) NOT NULL,
                TypingSpeed DECIMAL(10, 2) NOT NULL, 
                WindowTitle VARCHAR(255) NULL, 
                RiskLevel VARCHAR(50) NULL, 
                Timestamp DATETIME NOT NULL 
            );
            PRINT 'Table {DB_TABLE_NAME} created successfully.';
        END
        """
        cursor.execute(check_query)
        conn.commit()
        print(f"Database table '{DB_TABLE_NAME}' ensured/created successfully.")
        return True
    except pyodbc.Error as ex:
        print(f"Error checking/creating database table: {ex}")
        return False
    finally:
        if conn:
            conn.close()

# -----------------------------
# Load Model & Encoders
# -----------------------------
def load_ml_assets():
    """Machine Learning model aur encoders ko files se load karta hai."""
    global model, encoders

    if not os.path.exists(MODEL_FILE) or not os.path.exists(ENCODERS_FILE):
        print("ML Model or Encoders files not found. Prediction API will be unavailable.")
        return False
    
    try:
        with open(MODEL_FILE, 'rb') as f:
            model = pickle.load(f)
        with open(ENCODERS_FILE, 'rb') as f:
            encoders = pickle.load(f)
        print("ML Model and Encoders loaded successfully.")
        return True
    except Exception as e:
        print(f"Error loading ML assets: {e}")
        return False

# ------------------------------------------------------------------
# UTILITY FUNCTIONS
# ------------------------------------------------------------------
def is_locked(username):
    """Check karta hai agar user is waqt locked out hai."""
    entry = LOGIN_ATTEMPTS.get(username)
    if not entry:
        return False, 0

    locked_until = entry.get('locked_until')
    if locked_until and locked_until > datetime.now():
        # Calculate time remaining in seconds (rounded down)
        time_left = int((locked_until - datetime.now()).total_seconds())
        return True, time_left

    return False, 0

def record_failure(username):
    """Login ki nakam koshish record karta hai aur lockout ko handle karta hai."""
    now = datetime.now()
    entry = LOGIN_ATTEMPTS.get(username)

    # First failure ever for this user
    if not entry:
        LOGIN_ATTEMPTS[username] = {'failures': 1, 'locked_until': None, 'last_failure': now}
    else:
        locked_until = entry.get('locked_until')
        # If user was previously locked but the lock has expired, reset failures
        if locked_until and locked_until <= now:
            LOGIN_ATTEMPTS[username] = {'failures': 1, 'locked_until': None, 'last_failure': now}
        else:
            # Normal increment of failures (when not locked or lock still in future)
            # If locked_until is set and still in the future, we still allow counting to prevent bypassing,
            # but `is_locked` will prevent login attempts before lock expiration.
            LOGIN_ATTEMPTS[username]['failures'] = entry.get('failures', 0) + 1
            LOGIN_ATTEMPTS[username]['last_failure'] = now

    failures = LOGIN_ATTEMPTS[username].get('failures', 0)
    attempts_left = max(0, MAX_ATTEMPTS - failures)

    # Lockout trigger
    if failures >= MAX_ATTEMPTS:
        lockout_time = now + timedelta(seconds=LOCKOUT_DURATION)
        LOGIN_ATTEMPTS[username]['locked_until'] = lockout_time
        # FAILURE_LOCKED ke liye, LOCKOUT_DURATION seconds return karte hain
        return "FAILURE_LOCKED", LOCKOUT_DURATION, 0

    return "FAILURE_WARN", 0, attempts_left

def record_success(username):
    """Kamyab login par failure count clear karta hai."""
    if username in LOGIN_ATTEMPTS:
        del LOGIN_ATTEMPTS[username]


# ------------------------------------------------------------------
# Risk Prediction Function
# ------------------------------------------------------------------
def predict_risk(username, key_pressed, typing_speed):
    """Load kiye gaye model ka use karke risk level predict karta hai."""
    global model, encoders
    
    if not model or not encoders:
        print("DEBUG: Model or Encoders not loaded. Returning Unknown.")
        return "Unknown"

    try:
        # 1. User Name Encoding
        user_encoder = encoders.get('user_name')
        
        # Agar username known nahi hai, toh default encoding (0) use karte hain.
        if user_encoder and username in user_encoder.classes_:
            user_name_encoded = user_encoder.transform([username])[0]
        else:
            user_name_encoded = 0 
            
        # 2. Key Pressed Encoding
        key_encoder = encoders.get('key_pressed')
        
        # Agar key known nahi hai, toh default encoding (0) use karte hain.
        if key_encoder and key_pressed in key_encoder.classes_:
            key_pressed_encoded = key_encoder.transform([key_pressed])[0]
        else:
            key_pressed_encoded = 0
            
        # 3. Model ke liye Data tayyar karna
        input_data = pd.DataFrame([[typing_speed, user_name_encoded, key_pressed_encoded]],
                                      columns=['typing_speed', 'user_name_encoded', 'key_pressed_encoded'])
        
        # 4. Prediction
        prediction_index = model.predict(input_data)[0]
        
        # 5. Risk Level ko wapas asli value mein badalna
        risk_level_encoder = encoders.get('risk_level')
        if risk_level_encoder:
            risk_level = risk_level_encoder.inverse_transform([prediction_index])[0]
        else:
            risk_level = "Unknown (Encoder Missing)"

        return risk_level
    
    except NotFittedError as e:
        print(f"CRITICAL PREDICTION ERROR: Model/Encoder Not Fitted Correctly: {e}")
        return "Unknown"
    except Exception as e:
        print(f"CRITICAL PREDICTION ERROR (General): {e}")
        return "Unknown"

def log_keystroke_to_db(user_name, key_pressed, typing_speed, risk_level):
    """Keystroke data ko SQL database mein log karta hai."""
    conn = None
    try:
        window_title = "Login_Simulator"
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_connection()
        if not conn:
             return 

        cursor = conn.cursor()

        insert_query = f"""
        INSERT INTO {DB_TABLE_NAME} (UserName, KeyPressed, TypingSpeed, WindowTitle, RiskLevel, Timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(insert_query, 
                         (user_name, 
                          key_pressed, 
                          float(typing_speed), 
                          window_title, 
                          risk_level, 
                          current_datetime))
        
        conn.commit()
    except pyodbc.Error as ex:
        print(f"Database Error during log: {ex}") 
    finally:
        if conn:
            conn.close()


# ------------------------------------------------------------------
# FLASK ROUTES (API Endpoints)
# ------------------------------------------------------------------

# 1. Root Route - Health Check
@app.route("/")
def serve_dashboard():
    """API health status return karta hai."""
    return jsonify({"message": "Keystroke Risk Analysis API is Running."}), 200


# 2. Login Attempt API (POST) - Main Endpoint
@app.route("/login_attempt", methods=["POST"])
def login_attempt():
    """Login attempt process karta hai, risk predict karta hai, aur lockout manage karta hai."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "ERROR", "message": "Invalid JSON or no payload provided."}), 400 
        
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"status": "ERROR", "message": "Missing 'username' or 'password' in JSON payload."}), 400 

        # --- 1. Lockout Check ---
        locked, time_left = is_locked(username)
        if locked:
            # Agar user locked out hai, toh 429 status code return karega.
            return jsonify({
                "status": "LOCKED_OUT",
                "message": f"Account is locked. Try again in {time_left} seconds.",
                "auth_time": datetime.now().strftime("%H:%M:%S"),
                "risk_level": "High",
                "time_remaining": time_left 
            }), 429

        # --- 2. Authentication Check ---
        if password == CORRECT_PASSWORD:
            # Kamyab login
            risk_level = predict_risk(username, "ENTER", 150) # Normal speed
            log_keystroke_to_db(username, "ENTER", 150, risk_level)
            record_success(username)
            return jsonify({
                "status": "SUCCESS",
                "message": "Login successful. Welcome!",
                "auth_time": datetime.now().strftime("%H:%M:%S"),
                "risk_level": risk_level
            }), 200
        else:
            # Nakam login: attempt record karo aur lockout check karo.
            status_type, lock_seconds, attempts_left = record_failure(username)
            
            # High Risk prediction ke liye extreme FAST speed (1ms) use kar rahe hain.
            risk_level = predict_risk(username, "BACKSPACE", 1) 
            log_keystroke_to_db(username, "BACKSPACE", 1, risk_level)
            
            response = {
                "auth_time": datetime.now().strftime("%H:%M:%S"),
                "risk_level": risk_level
            }

            if status_type == "FAILURE_LOCKED":
                # Account lock hone par 403 status code return karega.
                response.update({
                    "status": "FAILURE_LOCKED",
                    "message": f"Login failed. Account locked due to {MAX_ATTEMPTS} failures. Try again in {lock_seconds} seconds.",
                    "lock_duration": lock_seconds
                })
                return jsonify(response), 403 
            else: 
                # Warning status par 401 status code return karega.
                response.update({
                    "status": "FAILURE_WARN",
                    "message": f"Login failed. {attempts_left} attempts remaining before lockout."
                })
                return jsonify(response), 401

    except Exception as e:
        print(f"Login Attempt Error: {e}")
        return jsonify({"status": "ERROR", "message": f"Server-side error: {str(e)}"}), 500


# 3. Latest Prediction API (GET)
@app.route("/predict_latest", methods=["GET"])
def predict_latest():
    """Database se latest risk prediction data fetch karta hai."""
    try:
        conn = get_connection()
        if not conn:
             return jsonify({"error": "Database connection error"}), 500

        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT TOP 1 UserName, RiskLevel, TypingSpeed, Timestamp 
            FROM {DB_TABLE_NAME} 
            ORDER BY Timestamp DESC
        """)
        row = cursor.fetchone()

        if not row:
            return jsonify({"message": "No data found for prediction", "user_name": None}), 200

        data = {
            "user_name": row.UserName,
            "risk_level": row.RiskLevel,
            "typing_speed": float(row.TypingSpeed), 
            "timestamp": row.Timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        cursor.close()
        conn.close()
        return jsonify(data), 200

    except Exception as e:
        print(f"Predict Latest Error: {e}")
        return jsonify({"error": str(e)}), 500


# 4. Logs API (GET)
@app.route("/logs", methods=["GET"])
def logs():
    """Database se recent keystroke logs (50 entries) fetch karta hai."""
    try:
        conn = get_connection()
        if not conn:
             return jsonify({"error": "Database connection error"}), 500
        
        cursor = conn.cursor()
        cursor.execute(f"SELECT TOP 50 UserName, RiskLevel, KeyPressed, TypingSpeed, Timestamp FROM {DB_TABLE_NAME} ORDER BY Timestamp DESC")
        rows = cursor.fetchall()
        
        logs_list = []
        for row in rows:
            logs_list.append({
                "user_name": row.UserName,
                "risk_level": row.RiskLevel,
                "key_pressed": row.KeyPressed,
                "typing_speed": float(row.TypingSpeed), 
                "timestamp": row.Timestamp.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        cursor.close()
        conn.close()
        return jsonify(logs_list), 200

    except Exception as e:
        print(f"Logs Fetch Error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# MAIN EXECUTION
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("Starting Flask API Server on Port 5000...")
    load_ml_assets() 
    create_table_if_not_exists() 
    # FIX: debug=False aur use_reloader=False set kiya gaya hai.
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)