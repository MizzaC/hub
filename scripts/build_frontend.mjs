import { copyFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";

const destinationRoot = "Mizzac/Core/static/core/vendor";
const templateIconRoot = "Mizzac/Core/templates/core/icons";
const assets = [
  ["node_modules/@tabler/core/dist/css/tabler.min.css", "tabler/tabler.min.css"],
  ["node_modules/@tabler/core/dist/js/tabler.min.js", "tabler/tabler.min.js"],
  ["scripts/vendor-licenses/tabler-LICENSE", "tabler/LICENSE"],
  ["node_modules/@tabler/icons/LICENSE", "tabler-icons/LICENSE"],
  ["node_modules/apexcharts/dist/apexcharts.min.js", "apexcharts/apexcharts.min.js"],
  ["node_modules/apexcharts/LICENSE", "apexcharts/LICENSE"],
];

const icons = [
  "apps",
  "calculator",
  "chart-pie",
  "chevron-down",
  "coin",
  "device-gamepad-2",
  "home",
  "login",
  "logout",
  "menu-2",
  "moon",
  "pig-money",
  "sun",
  "user-plus",
  "wallet",
];

for (const [source, destination] of assets) {
  const target = join(destinationRoot, destination);
  await mkdir(dirname(target), { recursive: true });
  await copyFile(source, target);
}

for (const icon of icons) {
  const source = `node_modules/@tabler/icons/icons/outline/${icon}.svg`;
  const target = join(destinationRoot, "tabler-icons", `${icon}.svg`);
  const templateTarget = join(templateIconRoot, `${icon}.html`);
  await mkdir(dirname(target), { recursive: true });
  await mkdir(dirname(templateTarget), { recursive: true });
  await copyFile(source, target);
  await copyFile(source, templateTarget);
}

console.log(`Copied ${assets.length + icons.length * 2} versioned frontend assets.`);
