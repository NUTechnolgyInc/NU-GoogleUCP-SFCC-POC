import { serve } from '@hono/node-server';
import { zValidator } from '@hono/zod-validator';
import { type Context, Hono } from 'hono';
import { requestId } from 'hono/request-id';
import { pinoHttp } from 'pino-http';
import { config } from 'dotenv';

// Load environment variables from .env file
config();

import { CheckoutService, zCompleteCheckoutRequest } from './api/checkout';
import { DiscoveryService } from './api/discovery';
import { OrderService } from './api/order';
import { TestingService } from './api/testing';
import { initDbs } from './data/db';
import { ExtendedCheckoutCreateRequestSchema, ExtendedCheckoutUpdateRequestSchema, OrderSchema, } from './models';
import { IdParamSchema, prettyValidation } from './utils/validation';

const app = new Hono();

// Initialize DBs (handles remote Turso or local SQLite)
// Note: In Vercel, this runs on every cold start.
initDbs('databases/products.db', 'databases/transactions.db').catch(err => {
  console.error('Failed to initialize databases:', err);
});

const checkoutService = new CheckoutService();
const orderService = new OrderService();
const discoveryService = new DiscoveryService();
const testingService = new TestingService(checkoutService);

// Setup logging for each request
app.use(requestId());
app.use(async (c: Context, next: () => Promise<void>) => {
  if (c.env?.incoming) {
    c.env.incoming.id = c.var.requestId;

    await new Promise<void>((resolve) =>
      pinoHttp({
        quietReqLogger: true,
        transport: {
          target: 'pino-http-print',
          options: {
            destination: 1,
            all: true,
            translateTime: true,
          },
        },
      })(c.env.incoming, c.env.outgoing, () => resolve()),
    );

    c.set('logger', c.env.incoming.log);
  }
  await next();
});

// Middleware for Version Negotiation
app.use(async (c: Context, next: () => Promise<void>) => {
  const ucpAgent = c.req.header('UCP-Agent');
  if (ucpAgent) {
    const match = ucpAgent.match(/version="([^"]+)"/);
    if (match) {
      const clientVersion = match[1];
      const serverVersion = discoveryService.ucpVersion;
      if (clientVersion > serverVersion) {
        return c.json(
          { error: `Unsupported UCP version: ${clientVersion}` },
          400,
        );
      }
    }
  }
  await next();
});

/* Discovery endpoints */
app.get('/.well-known/ucp', discoveryService.getMerchantProfile);

/* Checkout Capability endpoints */
app.post(
  '/checkout-sessions',
  zValidator('json', ExtendedCheckoutCreateRequestSchema, prettyValidation),
  checkoutService.createCheckout,
);
app.get(
  '/checkout-sessions/:id',
  zValidator('param', IdParamSchema, prettyValidation),
  checkoutService.getCheckout,
);
app.put(
  '/checkout-sessions/:id',
  zValidator('param', IdParamSchema, prettyValidation),
  zValidator('json', ExtendedCheckoutUpdateRequestSchema, prettyValidation),
  checkoutService.updateCheckout,
);
app.post(
  '/checkout-sessions/:id/complete',
  zValidator('param', IdParamSchema, prettyValidation),
  zValidator('json', zCompleteCheckoutRequest, prettyValidation),
  checkoutService.completeCheckout,
);
app.post(
  '/checkout-sessions/:id/cancel',
  zValidator('param', IdParamSchema, prettyValidation),
  checkoutService.cancelCheckout,
);

/* Order Capability endpoints */
app.get(
  '/orders/:id',
  zValidator('param', IdParamSchema, prettyValidation),
  orderService.getOrder,
);
app.put(
  '/orders/:id',
  zValidator('param', IdParamSchema, prettyValidation),
  zValidator('json', OrderSchema, prettyValidation),
  orderService.updateOrder,
);

/* Testing endpoints */
app.post(
  '/testing/simulate-shipping/:id',
  zValidator('param', IdParamSchema, prettyValidation),
  testingService.shipOrder,
);

// For local development
if (process.env.NODE_ENV !== 'production') {
  const port = 3000;
  serve(
    {
      fetch: app.fetch,
      port: port,
    },
    (info) => {
      console.log(`Server is running on http://localhost:${info.port}`);
    },
  );
}

// Export for Vercel
export default app;
