import { getProductsDb } from './db';

/**
 * Represents a product in the catalog.
 */
export interface Product {
  id: string;
  title: string;
  price: number; // Price in cents
  image_url: string | undefined;
}

/**
 * Retrieves a product from the database by its ID.
 *
 * @param productId The unique identifier of the product.
 * @returns The Product object if found, otherwise undefined.
 */
export async function getProduct(productId: string): Promise<Product | undefined> {
  const db = getProductsDb();
  const rs = await db.execute({
    sql: 'SELECT id, title, price, image_url FROM products WHERE id = ?',
    args: [productId]
  });

  if (rs.rows.length === 0) return undefined;

  const row = rs.rows[0];
  return {
    id: row.id as string,
    title: row.title as string,
    price: Number(row.price),
    image_url: row.image_url as string | undefined
  };
}
