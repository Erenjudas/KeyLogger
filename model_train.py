import pandas as pd
import numpy as np
import pyodbc
import pickle
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.model_selection import cross_val_score

# ------------------------------------------------------
# SQL DATABASE CONNECTION
# ------------------------------------------------------
def get_connection():
    conn = pyodbc.connect(
        r"DRIVER={SQL Server};"
        r"SERVER=DESKTOP-8JG6SC3\SQLEXPRESS;"
        r"DATABASE=KeystrokeTestDB;"
        r"Trusted_Connection=yes;"
    )
    return conn


# ------------------------------------------------------
# LOAD DATA FROM SQL
# ------------------------------------------------------
def load_data_from_sql():
    conn = get_connection()
    query = """
        SELECT user_name, key_pressed, typing_speed, risk_level
        FROM TestKeystrokes
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


# ------------------------------------------------------
# TRAINING STARTS HERE
# ------------------------------------------------------
def train_model():
    print("[1] Loading data from SQL...")
    df = load_data_from_sql()
    print("  ✔ Data Loaded:", len(df), "rows")

    # ------------------------------------------------------
    # ENCODING SECTION
    # ------------------------------------------------------
    print("[2] Encoding Categorical Columns...")

    encoders = {}
    cat_cols = ["user_name", "key_pressed", "risk_level"]

    for col in cat_cols:
        le = LabelEncoder()
        df[col + "_encoded"] = le.fit_transform(df[col])
        encoders[col] = le

    # ------------------------------------------------------
    # FEATURES
    # ------------------------------------------------------
    X = df[["typing_speed", "user_name_encoded", "key_pressed_encoded"]]
    y = df["risk_level_encoded"]

    # ------------------------------------------------------
    # TRAIN / TEST SPLIT
    # ------------------------------------------------------
    print("[3] Splitting dataset...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42
    )

    # ------------------------------------------------------
    # MODEL TRAINING
    # ------------------------------------------------------
    print("[4] Training RandomForest Model...")
    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=10,
        random_state=42
    )
    model.fit(X_train, y_train)
    print("  ✔ Model Training Completed")

    # ------------------------------------------------------
    # SAVE MODEL + ENCODERS
    # ------------------------------------------------------
    with open("model.pkl", "wb") as f:
        pickle.dump(model, f)

    with open("encoders.pkl", "wb") as f:
        pickle.dump(encoders, f)

    print("[5] Saved model.pkl & encoders.pkl successfully")

    # ------------------------------------------------------
    # BASIC ACCURACY
    # ------------------------------------------------------
    accuracy = model.score(X_test, y_test)
    print(f"\n🎯 Model Accuracy = {accuracy * 100:.2f}%")

    # ------------------------------------------------------
    # OVERFITTING ANALYSIS
    # ------------------------------------------------------
    print("\n[6] Checking for Overfitting...\n")

    # Train accuracy
    train_pred = model.predict(X_train)
    train_acc = accuracy_score(y_train, train_pred)

    # Test accuracy
    test_pred = model.predict(X_test)
    test_acc = accuracy_score(y_test, test_pred)

    print(f"🔹 Train Accuracy: {train_acc * 100:.2f}%")
    print(f"🔹 Test  Accuracy: {test_acc * 100:.2f}%")

    # Confusion Matrix
    print("\n📊 Confusion Matrix:")
    print(confusion_matrix(y_test, test_pred))

    # Classification Report
    print("\n📄 Classification Report:")
    print(classification_report(y_test, test_pred))

    # Cross Validation
    print("\n🔁 Cross Validation Score (5 Folds)...")
    cv_scores = cross_val_score(model, X, y, cv=5)

    print(f"Cross Validation Scores: {cv_scores}")
    print(f"Mean CV Accuracy: {np.mean(cv_scores) * 100:.2f}%")
    print(f"Std Dev: {np.std(cv_scores) * 100:.2f}%")

    print("\n✔ Overfitting analysis completed.")



# ------------------------------------------------------
# MAIN CALL
# ------------------------------------------------------
if __name__ == "__main__":
    train_model()
