import sys
import os
import asyncio

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.utils.db_utils import db_pool, test_connection, initialize_database, close_database

async def main():
    await initialize_database()
    success = await test_connection()
    print("✅ Database connection successful!" if success else "❌ Database connection failed.")
    await close_database()

if __name__ == "__main__":
    asyncio.run(main())
