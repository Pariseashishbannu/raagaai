import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

async def check():
    db_url = os.getenv('DATABASE_URL')
    print(f"Checking connection to: {db_url}")
    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
            print('DATABASE CONNECTION SUCCESSFUL')
    except Exception as e:
        print(f'DATABASE CONNECTION FAILED: {e}')
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
