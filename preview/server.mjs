import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)));
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg" };

http.createServer((request, response) => {
  const requestPath = decodeURIComponent((request.url || "/").split("?")[0]);
  const candidate = path.resolve(root, `.${requestPath === "/" ? "/index.html" : requestPath}`);
  if (!candidate.startsWith(root)) { response.writeHead(403); response.end("Forbidden"); return; }
  fs.readFile(candidate, (error, data) => {
    if (error) { response.writeHead(404); response.end("Not found"); return; }
    response.writeHead(200, { "Content-Type": mime[path.extname(candidate)] || "application/octet-stream", "Cache-Control": "no-store" });
    response.end(data);
  });
}).listen(4173, () => console.log("Odysseus preview: http://localhost:4173/"));
