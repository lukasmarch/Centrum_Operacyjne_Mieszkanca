from datetime import datetime
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database.connection import engine
from ..database.schema import AirQuality
from ..integrations.airly import AirlyClient
from ..config import settings
import logging

logger = logging.getLogger(__name__)

async def update_air_quality():
    """Fetches air quality data and saves to database."""
    logger.info("Starting AirQuality update job...")
    
    api_key = settings.AIRLY_API_KEY
    if not api_key or api_key == "your-airly-api-key-here":
        logger.warning("AIRLY_API_KEY not configured, skipping job.")
        return

    client = AirlyClient(api_key)
    
    # Rybno coordinates
    RYBNO_LAT = 53.3825
    RYBNO_LNG = 19.9278
    
    try:
        data = await client.get_measurements(RYBNO_LAT, RYBNO_LNG)
        parsed = client.parse_measurements(data)
        
        if not parsed:
            logger.warning("No current measurements available from Airly.")
            return

        async with AsyncSession(engine) as session:
            # Set old records to not current
            statement = select(AirQuality).where(AirQuality.location == "Rybno", AirQuality.is_current == True)
            results = (await session.execute(statement)).scalars().all()
            for record in results:
                record.is_current = False
                session.add(record)
            
            # Create new record
            new_record = AirQuality(
                location="Rybno",
                pm25=parsed["pm25"],
                pm10=parsed["pm10"],
                caqi=parsed["caqi"],
                caqi_level=parsed["caqi_level"],
                temperature=parsed["temperature"],
                humidity=parsed["humidity"],
                pressure=parsed["pressure"],
                fetched_at=datetime.utcnow(),
                is_current=True
            )
            
            session.add(new_record)
            await session.commit()

            # Trigger smog alert push if PM2.5 exceeds threshold
            pm25 = parsed.get("pm25", 0) or 0
            if pm25 > 50:
                try:
                    from src.services.push_service import push_service
                    from sqlalchemy.ext.asyncio import AsyncSession
                    async with AsyncSession(engine) as push_session:
                        sent = await push_service.send_air_alert_push(push_session, pm25)
                    logger.info(f"Smog alert push sent to {sent} subscribers (PM2.5={pm25})")
                except Exception as push_err:
                    logger.error(f"Smog alert push failed: {push_err}")

        logger.info(f"Air quality data updated for Rybno (CAQI: {parsed['caqi']})")
        
    except Exception as e:
        logger.error(f"Error updating air quality: {str(e)}")
