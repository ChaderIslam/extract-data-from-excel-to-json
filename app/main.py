import logging
import re
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import Table, Column, String, MetaData
from db import engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

# FastAPI app and SQLAlchemy metadata
app = FastAPI()
metadata = MetaData()

# Function to sanitize table names
def sanitize_table_name(name: str) -> str:
    return re.sub(r'\W+', '_', name.strip().lower())

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        logger.info(f"📁 Received file: {file.filename}")

        # Detect file type
        if file.filename.endswith(".csv"):
            logger.info("📄 Detected CSV format")
            df = pd.read_csv(file.file)
        elif file.filename.endswith((".xls", ".xlsx")):
            logger.info("📊 Detected Excel format")
            df = pd.read_excel(file.file)
        else:
            raise HTTPException(status_code=400, detail="❌ Unsupported file type")

        logger.info(f"📐 Loaded DataFrame with shape: {df.shape}")
        logger.debug(f"🧱 Columns: {df.columns.tolist()}")
        logger.debug(f"🔍 Preview:\n{df.head()}")

        # Normalize column names (safe for SQL)
        df.columns = [col.strip().replace(" ", "_").lower() for col in df.columns]

        # Derive and sanitize table name
        base_name = file.filename.rsplit(".", 1)[0]
        table_name = sanitize_table_name(base_name)
        logger.info(f"🧽 Sanitized table name: {table_name}")

        # Define SQLAlchemy table
        table = Table(
            table_name, metadata,
            *(Column(col, String) for col in df.columns),
            extend_existing=True
        )

        # Create table in the DB
        metadata.create_all(engine)
        logger.info(f"✅ Table '{table_name}' created or already exists")

        # Log full data before insert
        logger.info(f"⬇️ Data to insert:\n{df.to_string(index=False)}")

        # Insert records into DB
        with engine.begin() as conn:
            result = conn.execute(table.insert(), df.to_dict(orient="records"))
            inserted_rows = getattr(result, 'rowcount', len(df))
            logger.info(f"📥 Inserted rows: {inserted_rows}")

        # Return success response
        return JSONResponse(content={
            "status": "success",
            "table_name": table_name,
            "inserted_rows": inserted_rows
        })

    except Exception as e:
        logger.exception("💥 Exception occurred during file upload")
        raise HTTPException(status_code=500, detail=str(e))
