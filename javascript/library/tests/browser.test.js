import { after, before, describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { dirname, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, webkit } from "playwright";

import { formatMismatch } from "../../test-support/task-contract.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const libraryDir = resolve(__dirname, "..");
const repoRoot = resolve(libraryDir, "..", "..");

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
};

function createFixtureServer() {
  return createServer(async (request, response) => {
    const requestUrl = new URL(request.url ?? "/", "http://127.0.0.1");

    if (requestUrl.pathname === "/") {
      response.writeHead(200, { "Content-Type": MIME_TYPES[".html"] });
      response.end("<!doctype html><html><body>task contract tests</body></html>");
      return;
    }

    const routeRoots = [
      { prefix: "/src/", rootDir: libraryDir },
      { prefix: "/common/", rootDir: repoRoot },
    ];

    const route = routeRoots.find(({ prefix }) => requestUrl.pathname.startsWith(prefix));
    if (!route) {
      response.writeHead(404);
      response.end("Not found");
      return;
    }

    const filePath = resolve(route.rootDir, `.${requestUrl.pathname}`);
    try {
      const content = await readFile(filePath);
      response.writeHead(200, {
        "Content-Type": MIME_TYPES[extname(filePath)] ?? "application/octet-stream",
      });
      response.end(content);
    } catch {
      response.writeHead(404);
      response.end("Not found");
    }
  });
}

const browserTargets = [
  {
    label: "Chromium",
    browserType: chromium,
    launchOptions: {},
  },
  {
    label: "WebKit",
    browserType: webkit,
    launchOptions: {},
  },
];

let server;
let baseUrl;

before(async () => {
  server = createFixtureServer();
  await new Promise((resolveServer, rejectServer) => {
    const onError = (error) => {
      rejectServer(error);
    };

    server.once("error", onError);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", onError);
      const address = server.address();
      if (!address || typeof address === "string") {
        rejectServer(new Error("Fixture server failed to bind"));
        return;
      }
      baseUrl = `http://127.0.0.1:${address.port}`;
      resolveServer();
    });
  });
});

after(async () => {
  if (!server?.listening) {
    return;
  }

  await new Promise((resolveServer, rejectServer) => {
    server.close((error) => {
      if (error) {
        rejectServer(error);
        return;
      }

      resolveServer();
    });
  });
});

describe("countTasks in browsers", () => {
  for (const { label, browserType, launchOptions } of browserTargets) {
    it(`matches the canonical contract cases in ${label}`, async () => {
      const browser = await browserType.launch({
        headless: true,
        ...launchOptions,
      });

      try {
        const page = await browser.newPage();
        await page.goto(baseUrl);

        const evaluations = await page.evaluate(async () => {
          const [{ countTasks }, testData] = await Promise.all([
            import("/src/count.js"),
            fetch("/common/functions/task-collections/count-tasks.test.json").then((response) => response.json()),
          ]);

          return testData.tests.map(({ description, input, expected }) => ({
            actual: countTasks(input.tasks),
            description,
            expected,
          }));
        });

        for (const { actual, description, expected } of evaluations) {
          assert.equal(actual, expected, formatMismatch(description, actual, expected));
        }
      } finally {
        await browser.close();
      }
    });
  }
});
