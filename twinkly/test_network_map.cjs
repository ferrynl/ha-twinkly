const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const html = fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
const source = html.slice(html.indexOf('const networkText ='),html.indexOf('async function refreshNetwork()'));
function createMap() {
  class Element {
    constructor() {
      this.children = [];
      this.dataset = {};
      this.style = {setProperty() {}};
      this.clientWidth = 1100;
      this.clientHeight = 720;
      const classes = new Set();
      this.classList = {
        add: name => classes.add(name), remove: name => classes.delete(name),
        contains: name => classes.has(name),
      };
    }
    append(child) { this.children.push(child); }
    replaceChildren() { this.children = []; }
    getBoundingClientRect() { return {left:0,top:0}; }
    addEventListener() {}
    setAttribute() {}
    setPointerCapture() {}
    showModal() { this.open = true; }
    select() {}
    closest(selector) { return selector === '[data-network-node]' && this.dataset.networkNode ? this : null; }
  }
  const elements = new Map(), storage = new Map();
  const byId = id => {
    if (!elements.has(id)) elements.set(id,new Element());
    return elements.get(id);
  };
  const body = source + `
    return {renderNetwork, networkText, networkMap, networkCamera, fitNetwork,
            startNetworkGesture, moveNetworkGesture, endNetworkGesture, zoomNetwork,
            setGroups: groups => { networkGroups = groups; },
            nodes: () => networkNodes, links: () => networkLinks};
  `;
  const map = new Function('byId','document','localStorage','ResizeObserver','requestAnimationFrame','lang','button',body)(
    byId,{activeElement:null,createElement:()=>new Element(),addEventListener(){}},
    {getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)},
    class { observe() {} },()=>1,{value:'en'},(parent,key,action)=>parent.append({key,action}),
  );
  return {map, storage, byId};
}
function lamps(count) {
  return Array.from({length:count},(_,i)=>({
    id:String(i),name:'Light '+i,kind:'wifi',ssid:'Home',gateway:'192.168.1.1',seconds:120,rssi:-68,
  }));
}
test('fits 64 lights without overlapping and connects direct peers',()=>{
  const {map} = createMap();
  const rows = lamps(64);
  rows[0].kind = 'ap';
  rows[1].peer = '0';
  map.renderNetwork(rows,map.networkText.en);
  assert.equal(map.nodes().size,65);
  assert.equal(map.links().length,63);
  assert.equal(map.links().filter(link=>link[2]).length,1);
  const nodes = [...map.nodes().values()];
  for (const a of nodes) {
    assert.ok(a.x * map.networkCamera.scale + map.networkCamera.x >= 0);
    assert.ok((a.x+a.width) * map.networkCamera.scale + map.networkCamera.x <= map.networkMap.clientWidth);
    assert.ok(a.y * map.networkCamera.scale + map.networkCamera.y >= 0);
    assert.ok((a.y+a.height) * map.networkCamera.scale + map.networkCamera.y <= map.networkMap.clientHeight);
    for (const b of nodes) {
      if (a === b) continue;
      assert.ok(a.x+a.width<=b.x || b.x+b.width<=a.x || a.y+a.height<=b.y || b.y+b.height<=a.y);
    }
  }
});
test('dragged light keeps its position and link after refresh; the backdrop pans',()=>{
  const {map,storage} = createMap();
  const rows = lamps(64);
  map.renderNetwork(rows,map.networkText.en);
  const node = map.nodes().get('device:0'), oldX = node.x, oldY = node.y;
  const at = (target,x,y) => ({target,clientX:x,clientY:y,button:0,pointerId:1});
  map.startNetworkGesture(at(node.el,0,0));
  map.renderNetwork(rows,map.networkText.en);
  assert.equal(map.nodes().get(node.id),node);
  map.moveNetworkGesture(at(node.el,50,20));
  map.endNetworkGesture(at(node.el,50,20));
  const updated = map.nodes().get(node.id);
  assert.ok(updated.x > oldX && updated.y > oldY);
  assert.deepEqual(JSON.parse(storage.get('twinkly-network-positions-v1')),[[node.id,[updated.x,updated.y]]]);
  assert.ok(map.links().some(([source])=>source===updated));
  const x = map.networkCamera.x;
  map.startNetworkGesture(at(map.networkMap,0,0));
  map.moveNetworkGesture(at(map.networkMap,50,20));
  map.endNetworkGesture(at(map.networkMap,50,20));
  assert.equal(map.networkCamera.x,x+50);
  const worldX = (200-map.networkCamera.x)/map.networkCamera.scale;
  map.zoomNetwork(map.networkCamera.scale*1.3,200,100);
  assert.ok(Math.abs((200-map.networkCamera.x)/map.networkCamera.scale-worldX)<1e-9);
});

test('shows the join parent and four separate cards with membership links',()=>{
  const {map,byId} = createMap();
  const rows = lamps(5);
  rows[3].kind = 'offline';
  map.setGroups({wall:{name:'Muur',native:true,layout_size:840,members:['2','0','1','3']}});
  map.renderNetwork(rows,map.networkText.en);
  assert.equal(map.nodes().size,7);
  const group = map.nodes().get('group:wall');
  assert.equal(group.el.children[0].textContent,'Muur');
  assert.equal(group.el.children[1].textContent,'Join (inferred) · 840 LEDs');
  assert.equal(group.el.children[2].textContent,'4 lights · 1 offline');
  assert.deepEqual(group.el.children[3].children.map(button=>button.key || button.textContent),['on','off','Rename']);
  group.el.children[3].children[2].onclick();
  assert.equal(byId('network-name-dialog').open,true);
  assert.equal(byId('network-name').value,'Muur');
  assert.equal(group.y,map.nodes().get('device:4').y);
  const memberLinks = map.links().filter(([source,,kind])=>source===group && kind==='member');
  assert.deepEqual(memberLinks.map(([,target])=>target.id),['device:2','device:0','device:1','device:3']);
  assert.ok(memberLinks.every(([,target])=>target.y > group.y));
  assert.ok(map.nodes().get('device:3').el.children.some(child=>child.textContent==='Offline'));
  assert.equal(map.links().filter(([source,,kind])=>source===group && !kind).length,1);
  byId('network-members').onclick();
  assert.equal(map.nodes().size,6);
  assert.equal(map.nodes().has('group:wall'),false);
});

test('shows a reported group role even without a matched group',()=>{
  const {map} = createMap();
  const [row] = lamps(1);
  row.group_role = 'slave';
  map.renderNetwork([row],map.networkText.en);
  assert.ok(map.nodes().get('device:0').el.children.some(child=>child.textContent==='Group member'));
});

test('the same discovered group appears in settings and as one controllable home card',()=>{
  const elements = new Map();
  const make = () => ({
    children: [], setAttribute(key,value) { this[key]=value; }, append(...values) { this.children.push(...values); },
    replaceChildren() { this.children = []; }, querySelectorAll() { return []; },
  });
  const byId = id => {
    if (!elements.has(id)) elements.set(id,make());
    return elements.get(id);
  };
  const devices = [{id:'a',name:'Muur 1'},{id:'b',name:'Muur 2'}];
  const status = {devices,groups:{},display_groups:{
    'native:wall':{name:'Kerstmuur',members:['b','a']},
  }};
  const source = html.slice(html.indexOf('const groupCards ='),html.indexOf("byId('group-cancel').onclick"));
  new Function('byId','document','status','lang','extra','controls','networkNameLabels',
    'memberSignature','groupSignature',source + '\nrenderGroups();')(
    byId,{createElement:make},status,{value:'en'},()=>'',(actions,id,group)=>{ actions.group = group; },
    {en:['Rename']},'',null,
  );
  const [card] = byId('group-cards').children;
  assert.equal(byId('group-cards').children.length,1);
  assert.equal(card.children[0].textContent,'Kerstmuur');
  assert.equal(card.children[1].textContent,'Sync · Contains · Muur 2 · Muur 1');
  assert.equal(card.children[2].group,'native:wall');
  assert.equal(card.children.length,3);
  assert.ok(html.includes('id="tests-page"'));
  assert.ok(html.includes('function renderTestPage()'));
  assert.ok(html.includes('content.append(map)'));
  const [settings] = byId('group-management').children;
  assert.equal(settings.children[0].textContent,'Kerstmuur');
  assert.equal(settings.children[1].textContent,'Twinkly group · Sync · Contains · Muur 2 · Muur 1');
  assert.equal(settings.children[2].textContent,'Rename');
});

test('device diagnostics are mounted outside homepage cards',()=>{
 assert.ok(html.includes('deviceControls.append(actions,effectsFold)'));
 assert.ok(html.includes("byId('individual-tests-list').append(testPanel)"));
 assert.ok(html.includes("byId('device-settings-list').append(settingsPanel)"));
 assert.ok(!html.includes('deviceControls.append(actions, details, effects, map)'));
 assert.ok(html.includes('card.testPanel.remove(); card.settingsPanel.remove();'));
});
