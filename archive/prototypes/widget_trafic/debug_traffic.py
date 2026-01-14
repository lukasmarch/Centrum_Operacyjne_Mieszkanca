
import asyncio
import os
import sys

# Add backend directory to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.integrations.traffic_service import TrafficService

async def main():
    print("Initializing TrafficService...")
    try:
        service = TrafficService()
        print("Service initialized.")
        
        print("Fetching traffic data...")
        data = await service.get_traffic_data()
        print("Data fetched successfully!")
        print(data)
    except Exception as e:
        print("\nCAUGHT EXCEPTION:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
