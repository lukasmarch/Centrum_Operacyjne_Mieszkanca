/**
 * usePushNotifications Hook (Sprint 5C)
 *
 * Zarządza subskrypcją Web Push Notifications:
 * - Sprawdza wsparcie przeglądarki
 * - Rejestruje service worker
 * - Subskrybuje/wypisuje push notifications
 * - Pobiera publiczny klucz VAPID z backendu
 */
import { useState, useEffect, useCallback } from 'react';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

type PushStatus = 'unsupported' | 'denied' | 'granted' | 'default' | 'subscribed' | 'loading';

interface PushSubscriptionState {
  status: PushStatus;
  isSubscribed: boolean;
  isSupported: boolean;
  subscribe: (categories?: string[]) => Promise<boolean>;
  unsubscribe: () => Promise<boolean>;
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  return new Uint8Array([...rawData].map((char) => char.charCodeAt(0)));
}

async function getVapidPublicKey(): Promise<string | null> {
  try {
    const res = await fetch(`${API_URL}/push/vapid-public-key`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.publicKey || null;
  } catch {
    return null;
  }
}

async function sendSubscriptionToServer(
  subscription: PushSubscription,
  categories: string[]
): Promise<boolean> {
  try {
    const key = subscription.getKey('p256dh');
    const auth = subscription.getKey('auth');
    if (!key || !auth) return false;

    const p256dh = btoa(String.fromCharCode(...new Uint8Array(key)));
    const authStr = btoa(String.fromCharCode(...new Uint8Array(auth)));

    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_URL}/push/subscribe`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        endpoint: subscription.endpoint,
        p256dh: p256dh,
        auth: authStr,
        categories,
        user_agent: navigator.userAgent,
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function removeSubscriptionFromServer(endpoint: string): Promise<boolean> {
  try {
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_URL}/push/subscribe`, {
      method: 'DELETE',
      headers,
      body: JSON.stringify({ endpoint }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export function usePushNotifications(): PushSubscriptionState {
  const [status, setStatus] = useState<PushStatus>('loading');
  const [isSubscribed, setIsSubscribed] = useState(false);

  const isSupported =
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window;

  useEffect(() => {
    if (!isSupported) {
      setStatus('unsupported');
      return;
    }

    // Sprawdź bieżące pozwolenie
    const permission = Notification.permission;
    if (permission === 'denied') {
      setStatus('denied');
      return;
    }

    // Sprawdź czy jest aktywna subskrypcja
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => {
        if (sub) {
          setIsSubscribed(true);
          setStatus('subscribed');
        } else {
          setStatus(permission === 'granted' ? 'granted' : 'default');
        }
      })
      .catch(() => setStatus('default'));
  }, [isSupported]);

  const subscribe = useCallback(
    async (categories: string[] = ['alerty', 'powietrze', 'artykuly']): Promise<boolean> => {
      if (!isSupported) return false;

      setStatus('loading');

      try {
        // Pobierz VAPID public key
        const vapidKey = await getVapidPublicKey();
        if (!vapidKey) {
          console.error('Push: VAPID public key not available');
          setStatus('default');
          return false;
        }

        // Poproś o pozwolenie
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
          setStatus(permission as PushStatus);
          return false;
        }

        // Zarejestruj subskrypcję
        const reg = await navigator.serviceWorker.ready;
        const subscription = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapidKey),
        });

        // Wyślij do backendu
        const success = await sendSubscriptionToServer(subscription, categories);
        if (success) {
          setIsSubscribed(true);
          setStatus('subscribed');
          return true;
        } else {
          setStatus('granted');
          return false;
        }
      } catch (err) {
        console.error('Push subscription error:', err);
        setStatus('default');
        return false;
      }
    },
    [isSupported]
  );

  const unsubscribe = useCallback(async (): Promise<boolean> => {
    if (!isSupported) return false;

    try {
      const reg = await navigator.serviceWorker.ready;
      const subscription = await reg.pushManager.getSubscription();

      if (subscription) {
        await removeSubscriptionFromServer(subscription.endpoint);
        await subscription.unsubscribe();
      }

      setIsSubscribed(false);
      setStatus('granted');
      return true;
    } catch (err) {
      console.error('Push unsubscribe error:', err);
      return false;
    }
  }, [isSupported]);

  return { status, isSubscribed, isSupported, subscribe, unsubscribe };
}
