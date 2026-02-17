import { getTransactionsDb } from './db';

/**
 * Retrieves the available inventory quantity for a given product.
 *
 * @param productId The ID of the product to check.
 * @returns The quantity available, or undefined if the product is not found in inventory.
 */
export async function getInventory(productId: string): Promise<number | undefined> {
  const db = getTransactionsDb();
  const rs = await db.execute({
    sql: 'SELECT quantity FROM inventory WHERE product_id = ?',
    args: [productId]
  });

  if (rs.rows.length === 0) return undefined;
  return Number(rs.rows[0].quantity);
}

/**
 * Attempts to reserve a specified quantity of stock for a product.
 * Decrements the inventory only if sufficient stock is available.
 *
 * @param productId The ID of the product.
 * @param quantity The amount to reserve (decrement).
 * @returns True if the stock was successfully reserved, false if there was insufficient stock.
 */
export async function reserveStock(productId: string, quantity: number): Promise<boolean> {
  const db = getTransactionsDb();
  const rs = await db.execute({
    sql: `
      UPDATE inventory
      SET quantity = quantity - ?
      WHERE product_id = ? AND quantity >= ?
    `,
    args: [quantity, productId, quantity]
  });

  return rs.rowsAffected > 0;
}

/**
 * Releases reserved stock back to the inventory.
 * Used for rollbacks or cancellations.
 *
 * @param productId The ID of the product.
 * @param quantity The amount to release (increment).
 */
export async function releaseStock(productId: string, quantity: number): Promise<void> {
  const db = getTransactionsDb();
  await db.execute({
    sql: `
      UPDATE inventory
      SET quantity = quantity + ?
      WHERE product_id = ?
    `,
    args: [quantity, productId]
  });
}
