const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('twinkly/index.html', 'utf8');
const app = fs.readFileSync('twinkly/app.py', 'utf8');
const start = html.indexOf('const productLabels =');
const end = html.indexOf('function drawProduct', start);
assert.ok(start >= 0 && end > start, 'model resolver is present');
const context = vm.createContext({lang: {value: 'nl'}});
vm.runInContext(html.slice(start, end), context);
const resolve = (code) => context.modelInfo(code, {leds: 210, profile: 'RGBW'});

const cases = [
  ['TWW210SPP', 'Curtain', 'curtain-rgbw'],
  [' tww210spp-teu ', 'Curtain', 'curtain-rgbw'],
  ['TWW400SPP-TEU', 'Curtain', 'curtain-rgbw'],
  ['TWW480STP-TEU', 'Matrix', 'matrix'],
  ['TWS500SPP1', 'Strings', 'strings-rgbw'],
  ['TWS250STP', 'Strings', 'strings-multicolor'],
  ['TWS250GOP', 'Strings', 'strings-gold-silver'],
  ['TWL100STW', 'Line', 'line'],
  ['TWC9040STP', 'C9 Bulbs', 'c9-bulbs'],
  ['TWDJ1120STP', 'Lightwall', 'lightwall'],
  ['TWWT050SPP', 'Light Tree 2D', 'light-tree-2d'],
];
for (const [sku, name, photo] of cases) {
  assert.match(resolve(sku).name, new RegExp('^Twinkly ' + name + ' ·'));
  assert.equal(resolve(sku).photo, photo);
}
assert.equal(resolve('UNKNOWN').photo, undefined);
assert.equal(resolve('UNKNOWN').name, 'Model · UNKNOWN');

const photoKeys = vm.runInContext(
  'productModels.flatMap(([, , photo, variants]) => [photo, ...Object.values(variants || {})])',
  context,
);
for (const key of photoKeys) {
  assert.ok(app.includes('"' + key + '": "https://'), 'Missing photo source for ' + key);
}
