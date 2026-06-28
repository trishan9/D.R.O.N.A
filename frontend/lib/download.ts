/**
 * Dependency-free client-side download helpers. We build certificates and badges
 * as self-contained SVG strings (hard-coded colours, system fonts), then either
 * save the SVG directly or rasterise it to PNG through a canvas - no html2canvas.
 */

function triggerDownload(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function downloadSvg(svg: string, filename: string) {
  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  triggerDownload(url, filename);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Rasterise an SVG string (must carry explicit width/height) to a PNG download. */
export async function downloadPng(svg: string, filename: string, scale = 2): Promise<void> {
  const svgUrl = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  const img = new Image();
  img.crossOrigin = "anonymous";
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error("Could not render the image."));
    img.src = svgUrl;
  });

  const w = img.naturalWidth || 1200;
  const h = img.naturalHeight || 849;
  const canvas = document.createElement("canvas");
  canvas.width = w * scale;
  canvas.height = h * scale;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable.");
  ctx.scale(scale, scale);
  ctx.drawImage(img, 0, 0, w, h);

  await new Promise<void>((resolve) => {
    canvas.toBlob((blob) => {
      if (blob) {
        const url = URL.createObjectURL(blob);
        triggerDownload(url, filename);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
      resolve();
    }, "image/png");
  });
}

/** Slugify a name for filenames. */
export function slug(s: string): string {
  return (s || "drona").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "drona";
}
