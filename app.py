import streamlit as st
import pandas as pd
import pymongo
import json
import io
import logging
from bson import json_util

# --- Configure Logging (To Docker Console) ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

st.set_page_config(page_title="Mongo Data Extractor", page_icon="🍃", layout="centered")

# --- UI Header ---
st.title("🍃 Mongo Data Extractor")
st.markdown("Connect to your MongoDB, filter data, and download reports.")

# --- Sidebar: Connection Details ---
st.sidebar.header("1. Connection Details")
mongo_uri = st.sidebar.text_input("MongoDB URI", value="mongodb://chewy.marketmedium.net:27085/", help="Enter full connection string")
db_name = st.sidebar.text_input("Database Name", value="effiser")
col_name = st.sidebar.text_input("Collection Name", value="efsr_transactions_archive")

# --- Main Area: Filter & Options ---
st.header("2. Filter & Export Settings")

# Default JSON structure based on your code
default_filter = """{
    "JOB_INTG_NAME": "STOCKRECEIPT_INTF",
    "BUYING_SOURCE": ""
}"""

filter_input = st.text_area(
    "3. Filter Criteria (JSON Format)", 
    value=default_filter, 
    height=200,
    help="Enter standard JSON. For dates, standard JSON doesn't support datetime objects directly. Use strings."
)

file_format = st.radio("4. Export Format", ["CSV", "Excel"], horizontal=True)

# --- Helper Function: Flatten MongoDB ObjectIds ---
def clean_data(df):
    """Converts ObjectIds and other BSON types to strings for export."""
    if "_id" in df.columns:
        df["_id"] = df["_id"].astype(str)
    return df

# --- Main Logic ---
if st.button("Fetch & Generate Download", type="primary"):
    client = None
    try:
        # 1. Parse Filter
        try:
            # We use json_util to handle MongoDB specific types if passed as strict JSON
            query_filter = json.loads(filter_input, object_hook=json_util.object_hook)
        except json.JSONDecodeError as e:
            st.error(f"❌ Invalid JSON format in Filter Criteria: {e}")
            logging.error(f"Invalid JSON input: {e}")
            st.stop()

        # 2. Connect to MongoDB
        logging.info(f"Attempting to connect to {mongo_uri}...")
        client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        # Trigger a connection check
        client.server_info() 
        logging.info("Connection successful.")

        db = client[db_name]
        collection = db[col_name]

        # 3. Fetch Data
        logging.info(f"Querying collection: {col_name} with filter: {query_filter}")
        cursor = collection.find(query_filter)
        data = list(cursor)

        if not data:
            msg = "No records found matching the criteria."
            st.warning(msg)
            logging.warning(msg)
        else:
            logging.info(f"Retrieved {len(data)} records.")
            
            # 4. Convert to DataFrame
            df = pd.DataFrame(data)
            df = clean_data(df)

            # 5. Prepare Download Buffer
            buffer = io.BytesIO()
            mime_type = ""
            file_name = ""

            if file_format == "CSV":
                df.to_csv(buffer, index=False)
                mime_type = "text/csv"
                file_name = "mongo_export.csv"
            else:
                df.to_excel(buffer, index=False, engine='openpyxl')
                mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                file_name = "mongo_export.xlsx"

            buffer.seek(0)

            # 6. Success & Download Button
            st.success(f"✅ Successfully fetched {len(data)} records!")
            st.download_button(
                label=f"📥 Download {file_format}",
                data=buffer,
                file_name=file_name,
                mime=mime_type
            )
            logging.info("Download button generated successfully.")

    except pymongo.errors.ServerSelectionTimeoutError as e:
        err_msg = f"❌ Connection Timeout: Could not connect to MongoDB host. Check your VPN or Host settings."
        st.error(err_msg)
        st.error(f"Details: {e}")
        logging.error(f"Connection Timeout: {e}")

    except pymongo.errors.OperationFailure as e:
        err_msg = f"❌ Authentication or Database Error."
        st.error(err_msg)
        st.error(f"Details: {e}")
        logging.error(f"Operational Failure: {e}")

    except Exception as e:
        st.error(f"❌ An unexpected error occurred: {e}")
        logging.error(f"Unexpected Error: {e}")

    finally:
        if client:
            client.close()
            logging.info("MongoDB connection closed.")