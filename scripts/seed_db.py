"""Seed the database with raga and tala data from JSON files."""

import asyncio
import json
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from src.db.base import Base
from src.db.models.raga import Raga
from src.db.models.tala import Tala
from src.db.models.user import User
from src.api.middleware.auth import hash_password
from src.api.config import settings


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Seed ragas
        data_dir = Path("data/ragas")
        raga_count = 0
        for json_file in sorted(data_dir.glob("*.json")):
            with open(json_file, encoding="utf-8") as f:
                ragas_data = json.load(f)

            for raga_id, rdata in ragas_data.items():
                existing = await session.get(Raga, rdata["id"])
                if existing:
                    continue

                raga = Raga(
                    id=rdata["id"],
                    name_english=rdata["name_english"],
                    name_telugu=rdata.get("name_telugu", ""),
                    melakarta_number=rdata.get("melakarta_number"),
                    arohanam=rdata["arohanam"],
                    avarohanam=rdata["avarohanam"],
                    varja_svaras=rdata.get("varja_svaras", []),
                    characteristic_phrases=rdata.get("characteristic_phrases", []),
                    gamaka_rules=rdata.get("gamaka_rules", {}),
                    janya_of=None,  # Set after all ragas inserted
                    rasa_tags=rdata.get("rasa_tags", []),
                )
                session.add(raga)
                raga_count += 1

        await session.commit()
        print(f"Seeded {raga_count} ragas")

        # Seed talas
        tala_file = Path("data/talas/talas.json")
        with open(tala_file, encoding="utf-8") as f:
            talas_data = json.load(f)

        tala_count = 0
        for tala_id, tdata in talas_data.items():
            existing = await session.get(Tala, tdata["id"])
            if existing:
                continue

            tala = Tala(
                id=tdata["id"],
                name=tdata["name"],
                beats=tdata["beats"],
                jathi=tdata["jathi"],
                structure=tdata["structure"],
            )
            session.add(tala)
            tala_count += 1

        await session.commit()
        print(f"Seeded {tala_count} talas")

        # Create demo user
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.email == "demo@raaga.ai"))
        if not result.scalar_one_or_none():
            demo_user = User(
                id=uuid.uuid4(),
                email="demo@raaga.ai",
                hashed_password=hash_password("demo1234"),
                tier="pro",
                monthly_generations_used=0,
            )
            session.add(demo_user)
            await session.commit()
            print(f"Created demo user: demo@raaga.ai / demo1234")

    await engine.dispose()
    print("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
