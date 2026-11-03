import { readFileSync } from "node:fs";
import { Ajv } from "ajv";
import PptxGenJS from "pptxgenjs";
import type { DeckSpec } from "./deck.generated.js";

const schema: object = JSON.parse(
  readFileSync(new URL("../../../contracts/deck.schema.json", import.meta.url), "utf8"),
);
const validate = new Ajv({ allErrors: false }).compile<DeckSpec>(schema);
const chunks: Buffer[] = [];
let size = 0;
for await (const chunk of process.stdin) {
  const buffer = Buffer.from(chunk);
  size += buffer.length;
  if (size > 100_000) {
    throw new Error("Deck input exceeds renderer limit");
  }
  chunks.push(buffer);
}
const candidate: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
if (!validate(candidate)) {
  throw new Error("Invalid deck contract");
}

const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Authorized presentation owner";
pptx.subject = "Human-reviewed source excerpts; not an autonomous factual certification";
pptx.title = candidate.title;
pptx.theme = { headFontFace: "Aptos Display", bodyFontFace: "Aptos" };

for (const [index, item] of candidate.slides.entries()) {
  const slide = pptx.addSlide();
  slide.background = { color: "FFFFFF" };
  slide.addText(candidate.title, {
    x: 0.65, y: 0.25, w: 12, h: 0.4, fontSize: 16, color: "334155",
    breakLine: false, margin: 0, lang: "en-US",
  });
  slide.addText(item.title, {
    x: 0.65, y: 0.9, w: 12, h: 1.3, fontSize: 32, bold: true,
    color: "0F172A", margin: 0, valign: "top", lang: "en-US",
  });
  slide.addText(item.citation.quote.replace(/\s+/gu, " "), {
    x: 0.65, y: 2.4, w: 12, h: 3.2, fontSize: 24,
    color: "0F172A", margin: 0, valign: "top", breakLine: false, lang: "en-US",
  });
  const reference = [
    `Source: ${item.citation.source_title}`,
    `ID ${item.citation.source_id} | chars ${item.citation.start}-${item.citation.end}`,
    `SHA256 ${item.citation.source_hash}`,
  ].join("\n");
  slide.addText(reference, {
    x: 0.65, y: 6.05, w: 11.6, h: 0.85, fontSize: 10,
    color: "334155", margin: 0, valign: "top", lang: "en-US",
  });
  slide.addText(`${index + 1} / ${candidate.slides.length}`, {
    x: 11.7, y: 7.0, w: 1, h: 0.25, fontSize: 10, color: "334155", margin: 0, lang: "en-US",
  });
  slide.addNotes([item.citation.quote, reference].join("\n\n"));
}
const output = await pptx.write({ outputType: "nodebuffer" });
if (!Buffer.isBuffer(output)) {
  throw new Error("Renderer did not produce a Node buffer");
}
process.stdout.write(output);
