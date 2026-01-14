
import { TrafficCondition, RoadStatus, GroundingSource } from "../../types";

const API_BASE_URL = 'http://localhost:8000'; // Or use current origin if deployed

export const fetchTrafficData = async (latitude?: number, longitude?: number): Promise<{ roads: RoadStatus[], sources: GroundingSource[] }> => {
    try {
        const response = await fetch(`${API_BASE_URL}/api/traffic`);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        const data = await response.json();

        // Map backend response status strings to TrafficCondition enum if needed
        const roads = data.roads.map((r: any) => ({
            ...r,
            status: mapStatus(r.status)
        }));

        return {
            roads: roads,
            sources: data.sources
        };
    } catch (error) {
        console.error("Error fetching traffic data from backend:", error);
        // Fallback or re-throw
        throw error;
    }
};

const mapStatus = (status: string): TrafficCondition => {
    switch (status) {
        case 'Płynnie': return TrafficCondition.FLUID;
        case 'Utrudnienia': return TrafficCondition.DIFFICULTIES;
        case 'Korki': return TrafficCondition.JAM;
        default: return TrafficCondition.UNKNOWN;
    }
}
