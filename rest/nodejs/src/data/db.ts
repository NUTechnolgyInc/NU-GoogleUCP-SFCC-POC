import { createClient, type Client } from '@libsql/client';

let productsClient: Client | null = null;
let transactionsClient: Client | null = null;

/**
 * Initializes the LibSQL (Turso) database connections for products and transactions.
 * Creates the necessary tables if they do not exist.
 * 
 * In Vercel, this uses environment variables:
 * - TURSO_URL: the Turso database URL (e.g., libsql://my-db.turso.io)
 * - TURSO_AUTH_TOKEN: the Turso auth token
 */
export async function initDbs(productsPath: string, transactionsPath: string) {
  // Use environment variables if available, fallback to local file paths
  const url = process.env.TURSO_URL || `file:${productsPath}`;
  const authToken = process.env.TURSO_AUTH_TOKEN;

  console.log(`Initializing Turso DB with URL: ${url}`);
  productsClient = createClient({
    url: url,
    authToken: authToken,
  });

  // For transactions, we can use the same DB or a different one. 
  // In Turso, it's common to use one DB with multiple tables.
  transactionsClient = createClient({
    url: process.env.TURSO_URL || `file:${transactionsPath}`,
    authToken: authToken,
  });

  // Initialize Products DB schema
  await productsClient.execute(`
    CREATE TABLE IF NOT EXISTS products (
      id TEXT PRIMARY KEY,
      title TEXT,
      price INTEGER,
      image_url TEXT
    )
  `);

  // Initialize Transactions DB schema
  await transactionsClient.execute(`
    CREATE TABLE IF NOT EXISTS inventory (
      product_id TEXT PRIMARY KEY,
      quantity INTEGER DEFAULT 0
    )
  `);

  await transactionsClient.execute(`
    CREATE TABLE IF NOT EXISTS checkouts (
      id TEXT PRIMARY KEY,
      status TEXT,
      data TEXT
    )
  `);

  await transactionsClient.execute(`
    CREATE TABLE IF NOT EXISTS orders (
      id TEXT PRIMARY KEY,
      data TEXT
    )
  `);

  await transactionsClient.execute(`
    CREATE TABLE IF NOT EXISTS request_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      method TEXT,
      url TEXT,
      checkout_id TEXT,
      payload TEXT,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);

  await transactionsClient.execute(`
    CREATE TABLE IF NOT EXISTS idempotency_keys (
      key TEXT PRIMARY KEY,
      request_hash TEXT,
      response_status INTEGER,
      response_body TEXT
    )
  `);
}

/**
 * Returns the initialized products database client.
 * Throws an error if initDbs has not been called.
 */
export function getProductsDb(): Client {
  if (!productsClient) {
    throw new Error('Products DB client not initialized. Call initDbs first.');
  }
  return productsClient;
}

/**
 * Returns the initialized transactions database client.
 * Throws an error if initDbs has not been called.
 */
export function getTransactionsDb(): Client {
  if (!transactionsClient) {
    throw new Error('Transactions DB client not initialized. Call initDbs first.');
  }
  return transactionsClient;
}
