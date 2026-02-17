import { type ExtendedCheckoutResponse, type Order } from '../models';
import { getTransactionsDb } from './db';

/**
 * Represents the structure of a checkout session stored in the database.
 */
export interface CheckoutSession {
  id: string;
  status: string;
  data: string;  // JSON string
}

export interface IdempotencyRecord {
  key: string;
  request_hash: string;
  response_status: number;
  response_body: string;
}

/**
 * Saves or updates a checkout session in the database.
 * If a session with the given ID exists, it updates it; otherwise, it creates a new one.
 *
 * @param checkoutId The unique identifier for the checkout session.
 * @param status The current status of the checkout (e.g., 'in_progress', 'completed').
 * @param checkoutObj The full checkout object to be serialized and stored.
 */
export async function saveCheckout(
  checkoutId: string,
  status: string,
  checkoutObj: ExtendedCheckoutResponse,
): Promise<void> {
  const db = getTransactionsDb();

  const dataStr = JSON.stringify(checkoutObj);

  // Using raw SQL for compatibility with @libsql/client execute()
  await db.execute({
    sql: `INSERT INTO checkouts (id, status, data) 
          VALUES (?, ?, ?) 
          ON CONFLICT(id) DO UPDATE SET status = EXCLUDED.status, data = EXCLUDED.data`,
    args: [checkoutId, status, dataStr]
  });
}

/**
 * Retrieves a checkout session from the database by its ID.
 * Parses the stored JSON data into a Checkout object.
 *
 * @param checkoutId The unique identifier of the checkout session.
 * @returns The Checkout object if found and successfully parsed, otherwise undefined.
 */
export async function getCheckoutSession(
  checkoutId: string,
): Promise<ExtendedCheckoutResponse | undefined> {
  const db = getTransactionsDb();
  const rs = await db.execute({
    sql: 'SELECT data FROM checkouts WHERE id = ?',
    args: [checkoutId]
  });

  if (rs.rows.length > 0) {
    try {
      return JSON.parse(rs.rows[0].data as string) as ExtendedCheckoutResponse;
    } catch (e) {
      console.error('Failed to parse checkout data', e);
      return undefined;
    }
  }
  return undefined;
}

export async function saveOrder(orderId: string, orderObj: Order): Promise<void> {
  const db = getTransactionsDb();
  const dataStr = JSON.stringify(orderObj);

  await db.execute({
    sql: `INSERT INTO orders (id, data) 
          VALUES (?, ?) 
          ON CONFLICT(id) DO UPDATE SET data = EXCLUDED.data`,
    args: [orderId, dataStr]
  });
}

export async function getOrder(orderId: string): Promise<Order | undefined> {
  const db = getTransactionsDb();
  const rs = await db.execute({
    sql: 'SELECT data FROM orders WHERE id = ?',
    args: [orderId]
  });

  if (rs.rows.length > 0) {
    try {
      return JSON.parse(rs.rows[0].data as string) as Order;
    } catch (e) {
      console.error('Failed to parse order data', e);
      return undefined;
    }
  }
  return undefined;
}

export async function logRequest(
  method: string,
  url: string,
  checkoutId: string | undefined,
  payload: unknown,
): Promise<void> {
  const db = getTransactionsDb();
  await db.execute({
    sql: 'INSERT INTO request_logs (method, url, checkout_id, payload) VALUES (?, ?, ?, ?)',
    args: [method, url, checkoutId || null, JSON.stringify(payload)]
  });
}

export async function getIdempotencyRecord(
  key: string,
): Promise<IdempotencyRecord | undefined> {
  const db = getTransactionsDb();
  const rs = await db.execute({
    sql: 'SELECT key, request_hash, response_status, response_body FROM idempotency_keys WHERE key = ?',
    args: [key]
  });

  if (rs.rows.length === 0) return undefined;

  const row = rs.rows[0];
  return {
    key: row.key as string,
    request_hash: row.request_hash as string,
    response_status: Number(row.response_status),
    response_body: row.response_body as string
  };
}

export async function saveIdempotencyRecord(
  key: string,
  requestHash: string,
  status: number,
  responseBody: string,
): Promise<void> {
  const db = getTransactionsDb();
  await db.execute({
    sql: 'INSERT INTO idempotency_keys (key, request_hash, response_status, response_body) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET request_hash = EXCLUDED.request_hash, response_status = EXCLUDED.response_status, response_body = EXCLUDED.response_body',
    args: [key, requestHash, status, responseBody]
  });
}
