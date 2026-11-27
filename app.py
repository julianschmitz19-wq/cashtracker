import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import base64
from html import escape
import time

# --- KONFIGURATION & PFADE ---
DATA_DIR = "data"
INV_FILE = os.path.join(DATA_DIR, "inventory.json")
LOG_FILE = os.path.join(DATA_DIR, "transactions.csv")
ASSETS_DIR = "assets"

CURRENCIES = [1, 2, 5, 10, 20, 50, 100, 200, 500]
pw_hash = os.environ.get("CASHTRACKER_EXPORT_PASSWORD", "")

# --- SESSION STATE ZÄHLER FÜR RESET-LOGIK ---
# Diese Zähler sorgen dafür, dass wir Eingabefelder sicher zurücksetzen können
if "add_counter" not in st.session_state:
    st.session_state.add_counter = 0
if "rem_counter" not in st.session_state:
    st.session_state.rem_counter = 0


# --- HELFERFUNKTIONEN ---
def init_files():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    if not os.path.exists(INV_FILE) or os.path.getsize(INV_FILE) == 0:
        with open(INV_FILE, "w") as f:
            json.dump(
                {"low_val": {str(c): 0 for c in CURRENCIES if c < 50}, "high_val": []},
                f,
            )

    if not os.path.exists(LOG_FILE):
        df = pd.DataFrame(columns=["Timestamp", "Action", "Value", "Serial"])
        df.to_csv(LOG_FILE, index=False)


def load_data():
    try:
        with open(INV_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        st.warning(
            "Warnung: inventory.json war beschädigt oder leer und wurde temporär zurückgesetzt."
        )
        return {"low_val": {str(c): 0 for c in CURRENCIES if c < 50}, "high_val": []}


def save_data(data):
    with open(INV_FILE, "w") as f:
        json.dump(data, f, indent=4)


def log_action(action, value, serial=""):
    new_entry = pd.DataFrame(
        [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), action, value, serial]],
        columns=["Timestamp", "Action", "Value", "Serial"],
    )
    new_entry.to_csv(
        LOG_FILE, mode="a", header=not os.path.exists(LOG_FILE), index=False
    )


def get_image_base64(val):
    path = os.path.join(ASSETS_DIR, f"{val}euro.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


# --- UI RENDERING ---
st.set_page_config(page_title="CashTracker", layout="wide")
init_files()
data = load_data()

# Sidebar: Export
with st.sidebar:
    st.header("📦 Exporte")

    inv_df = pd.DataFrame(
        [{"Wert": k, "Anzahl": v} for k, v in data["low_val"].items()]
    )

    st.download_button(
        "Finanzielle Übersicht exportieren",
        data=inv_df.to_csv(index=False),
        file_name="bestand.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("🔒 Log Export")
    pw_input = st.text_input("Passwort eingeben", type="password")
    if pw_hash and pw_input == pw_hash:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "rb") as f:
                st.download_button(
                    "Detailliertes Log herunterladen", f, "log.csv", "text/csv"
                )

# Hauptfenster
tabs = st.tabs(["📊 Übersicht", "➕ Eintragung", "➖ Austragung"])

# TAB 1: ÜBERSICHT
with tabs[0]:
    total_low = sum(int(k) * v for k, v in data["low_val"].items())
    total_high = sum(item["value"] for item in data["high_val"])
    total = total_low + total_high

    st.metric("Gesamtsumme", f"{total} €")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Bestand < 50€")
        for val in [c for c in CURRENCIES if c < 50]:
            count = data["low_val"][str(val)]
            if count > 0:
                st.write(f"**{count}×** {val} €")

    with col2:
        st.subheader("Einzelaufstellung >= 50€")
        if data["high_val"]:
            # HTML ohne Einrückungen, um Markdown-Code-Block-Fehler zu vermeiden
            html_table = "<style>.cash-table { width: 100%; border-collapse: collapse; margin-top: 5px; } .cash-table th { border-bottom: 2px solid #A8C7FA; padding: 8px; text-align: left; color: #A8C7FA; font-weight: bold; } .cash-table td { border-bottom: 1px solid #333; padding: 8px; vertical-align: middle; }</style>"
            html_table += "<table class='cash-table'><thead><tr><th>Wert</th><th>Seriennummer</th></tr></thead><tbody>"
            for item in data["high_val"]:
                val = item["value"]
                serial = escape(str(item["serial"]))
                img_b64 = get_image_base64(val)
                html_table += f"<tr><td>{val} €</td><td>{serial}</td></tr>"
            html_table += "</tbody></table>"

            st.markdown(html_table, unsafe_allow_html=True)
        else:
            st.info("Keine Scheine registriert.")

# TAB 2: EINTRAGUNG
with tabs[1]:
    col_left, col_right = st.columns([3, 1])

    with col_left:
        val_add = st.selectbox("Wert auswählen", CURRENCIES, key="add_val")

        # Dynamische Eingabefelder - verknüpft mit dem add_counter für sauberes Reset
        serial = ""
        amount = 1
        if val_add >= 50:
            serial = st.text_input(
                "Kennnummer (Pflicht)", key=f"add_serial_{st.session_state.add_counter}"
            )
        else:
            amount = st.number_input(
                "Anzahl",
                min_value=1,
                value=1,
                step=1,
                key=f"add_amount_{st.session_state.add_counter}",
            )

        if st.button("Zum Portfolio hinzufügen"):
            if val_add >= 50 and not serial.strip():
                st.error("Kennnummer für Scheine ab 50€ zwingend erforderlich!")
            else:
                if val_add < 50:
                    data["low_val"][str(val_add)] += amount
                    for _ in range(amount):
                        log_action("Einzahlung", val_add)
                    st.success(f"{amount}x {val_add}€ erfolgreich hinzugefügt.")
                else:
                    data["high_val"].append(
                        {"value": val_add, "serial": serial.strip()}
                    )
                    log_action("Einzahlung", val_add, serial)
                    st.success(f"Schein {val_add}€ erfolgreich hinzugefügt.")

                save_data(data)

                # --- STATE RESET ---
                st.session_state.add_counter += 1
                time.sleep(1.5)
                st.rerun()

    with col_right:
        img_b64 = get_image_base64(val_add)
        if img_b64:
            st.markdown(
                f"""
                <div style="display: flex; height: 100%; align-items: center; justify-content: center; padding-top: 25px;">

                </div>
                """,
                unsafe_allow_html=True,
            )

# TAB 3: AUSTRAGUNG
with tabs[2]:
    col_left_rem, col_right_rem = st.columns([3, 1])

    with col_left_rem:
        val_rem = st.selectbox("Wert zum Austragen", CURRENCIES, key="rem_val")

        if val_rem < 50:
            current_stock = data["low_val"].get(str(val_rem), 0)

            if current_stock > 0:
                amount_rem = st.number_input(
                    "Anzahl zum Austragen",
                    min_value=1,
                    max_value=current_stock,
                    value=1,
                    step=1,
                    key=f"rem_amount_{st.session_state.rem_counter}",
                )

                if st.button("Von Portfolio entfernen"):
                    data["low_val"][str(val_rem)] -= amount_rem
                    save_data(data)
                    for _ in range(amount_rem):
                        log_action("Auszahlung", val_rem)
                    st.success(f"{amount_rem}x {val_rem}€ entfernt.")

                    # --- STATE RESET ---
                    st.session_state.rem_counter += 1
                    time.sleep(1.5)
                    st.rerun()
            else:
                st.warning(f"Kein Bestand für {val_rem}€ vorhanden.")

        else:
            available_serials = [
                item["serial"] for item in data["high_val"] if item["value"] == val_rem
            ]
            if available_serials:
                serial_rem = st.selectbox(
                    "Kennnummer auswählen",
                    available_serials,
                    key=f"rem_serial_{st.session_state.rem_counter}",
                )
                if st.button("Schein entfernen"):
                    for i, item in enumerate(data["high_val"]):
                        if item["value"] == val_rem and item["serial"] == serial_rem:
                            data["high_val"].pop(i)
                            break
                    save_data(data)
                    log_action("Auszahlung", val_rem, serial_rem)
                    st.success(f"Schein {val_rem}€ ({serial_rem}) entfernt.")

                    # --- STATE RESET ---
                    st.session_state.rem_counter += 1
                    time.sleep(1.5)
                    st.rerun()
            else:
                st.warning(f"Keine {val_rem}€ Scheine im Bestand.")

    with col_right_rem:
        img_b64_rem = get_image_base64(val_rem)
        if img_b64_rem:
            st.markdown(
                f"""
                <div style="display: flex; height: 100%; align-items: center; justify-content: center; padding-top: 25px;">
                    <img src='data:image/png;base64,{img_b64_rem}' style='max-width: 100%; max-height: 180px; object-fit: contain;'>
                </div>
                """,
                unsafe_allow_html=True,
            )
