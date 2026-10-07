// Genera los PNG de la PWA a partir de los SVG de marca (desde frontend/sgi-app: node scripts/generar-iconos.cjs).
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const pub = path.resolve('public');
const marca = path.resolve('../../docs/marca');
const salidas = [
  [path.join(pub, 'favicon.svg'), 'pwa-192x192.png', 192],
  [path.join(pub, 'favicon.svg'), 'pwa-512x512.png', 512],
  [path.join(pub, 'favicon.svg'), 'favicon-32x32.png', 32],
  [path.join(marca, 'icono-maskable.svg'), 'pwa-maskable-512x512.png', 512],
  [path.join(marca, 'icono-maskable.svg'), 'apple-touch-icon.png', 180],
];
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  for (const [svg, out, size] of salidas) {
    await page.setViewportSize({ width: size, height: size });
    const data = fs.readFileSync(svg, 'utf8').replace('<svg ', `<svg width="${size}" height="${size}" `);
    await page.setContent(`<html><body style="margin:0;background:transparent">${data}</body></html>`);
    await page.screenshot({ path: path.join(pub, out), omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
    console.log('ok', out);
  }
  await browser.close();
})();
