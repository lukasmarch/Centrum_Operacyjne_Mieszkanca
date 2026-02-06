import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { WeatherData, DailySummary, CinemaRepertoire, CinemaLocation } from '../../types';

interface CacheEntry<T> {
    data: T;
    timestamp: number;
    expiresIn: number; // milliseconds
}

interface DataCacheContextType {
    // Weather
    getWeather: (location: string) => WeatherData | null;
    setWeather: (location: string, data: WeatherData) => void;

    // Daily Summary
    getSummary: () => DailySummary | null;
    setSummary: (data: DailySummary) => void;

    // Cinema
    getCinema: (location: CinemaLocation) => CinemaRepertoire | null;
    setCinema: (location: CinemaLocation, data: CinemaRepertoire) => void;

    // Clear cache
    clearCache: () => void;
}

const DataCacheContext = createContext<DataCacheContextType | undefined>(undefined);

const CACHE_DURATION = 2 * 60 * 60 * 1000; // 2 hours in milliseconds

export const DataCacheProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [weatherCache, setWeatherCache] = useState<Map<string, CacheEntry<WeatherData>>>(new Map());
    const [summaryCache, setSummaryCache] = useState<CacheEntry<DailySummary> | null>(null);
    const [cinemaCache, setCinemaCache] = useState<Map<CinemaLocation, CacheEntry<CinemaRepertoire>>>(new Map());

    // Helper to check if cache is valid
    const isCacheValid = <T,>(entry: CacheEntry<T> | null | undefined): boolean => {
        if (!entry) return false;
        return Date.now() - entry.timestamp < entry.expiresIn;
    };

    const getWeather = (location: string): WeatherData | null => {
        const entry = weatherCache.get(location);
        if (isCacheValid(entry)) {
            return entry!.data;
        }
        return null;
    };

    const setWeather = (location: string, data: WeatherData) => {
        setWeatherCache(prev => {
            const newCache = new Map(prev);
            newCache.set(location, {
                data,
                timestamp: Date.now(),
                expiresIn: CACHE_DURATION
            });
            return newCache;
        });
    };

    const getSummary = (): DailySummary | null => {
        if (isCacheValid(summaryCache)) {
            return summaryCache!.data;
        }
        return null;
    };

    const setSummary = (data: DailySummary) => {
        setSummaryCache({
            data,
            timestamp: Date.now(),
            expiresIn: CACHE_DURATION
        });
    };

    const getCinema = (location: CinemaLocation): CinemaRepertoire | null => {
        const entry = cinemaCache.get(location);
        if (isCacheValid(entry)) {
            return entry!.data;
        }
        return null;
    };

    const setCinema = (location: CinemaLocation, data: CinemaRepertoire) => {
        setCinemaCache(prev => {
            const newCache = new Map(prev);
            newCache.set(location, {
                data,
                timestamp: Date.now(),
                expiresIn: CACHE_DURATION
            });
            return newCache;
        });
    };

    const clearCache = () => {
        setWeatherCache(new Map());
        setSummaryCache(null);
        setCinemaCache(new Map());
    };

    return (
        <DataCacheContext.Provider
            value={{
                getWeather,
                setWeather,
                getSummary,
                setSummary,
                getCinema,
                setCinema,
                clearCache
            }}
        >
            {children}
        </DataCacheContext.Provider>
    );
};

export const useDataCache = () => {
    const context = useContext(DataCacheContext);
    if (!context) {
        throw new Error('useDataCache must be used within DataCacheProvider');
    }
    return context;
};
