// Dependency-free export helpers for the thesis figures: an SVG chart to a PNG,
// and an array of rows to a CSV. Both run entirely in the browser.

// Serialize an <svg> node, paint it onto a canvas at `scale`x, and download a
// PNG. A solid white background is drawn first so the figure looks right when
// dropped into a document.
export function svgToPng(svgEl, filename, scale = 2) {
  if (!svgEl) return;
  const clone = svgEl.cloneNode(true);
  const vb = svgEl.viewBox.baseVal;
  const w = vb && vb.width ? vb.width : svgEl.clientWidth || 800;
  const h = vb && vb.height ? vb.height : svgEl.clientHeight || 400;
  clone.setAttribute("width", w);
  clone.setAttribute("height", h);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");

  const data = new XMLSerializer().serializeToString(clone);
  const svgBlob = new Blob([data], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(svgBlob);
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = w * scale;
    canvas.height = h * scale;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    URL.revokeObjectURL(url);
    canvas.toBlob((blob) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename.endsWith(".png") ? filename : `${filename}.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
    }, "image/png");
  };
  img.src = url;
}

// rows: array of arrays (first row is the header). Values are CSV-escaped.
export function downloadCsv(filename, rows) {
  const esc = (v) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = rows.map((r) => r.map(esc).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}
