const {test,expect}=require('@playwright/test');
if (process.env.TWINKLY_TEST_CHROME) {
 test.use({launchOptions:{executablePath:process.env.TWINKLY_TEST_CHROME}});
}
for(const viewport of [{width:1440,height:900},{width:390,height:844}]){
 test('studio navigation and layout '+viewport.width,async({page})=>{
  await page.setViewportSize(viewport);
  await page.goto('http://127.0.0.1:8765/index.html',{waitUntil:'domcontentloaded'});
  await expect(page).toHaveTitle('Christmas Control Center');
  await expect(page.locator('h1')).toHaveAttribute('aria-label','Christmas Control Center');
  await expect(page.locator('#lighting-panel')).toBeVisible();
  expect(await page.locator('.workspace-nav a').evaluateAll(links => links.map(link => link.id))).toEqual([
   'nav-home','nav-control','nav-hue','nav-govee','nav-tests','nav-network','nav-settings',
  ]);
  await expect(page.getByRole('link',{name:'Twinkly',exact:true}).locator('img')).toHaveAttribute('src','twinkly-nav-logo.svg');
  await expect(page.getByRole('link',{name:'Philips Hue',exact:true}).locator('img')).toHaveAttribute('src','hue-app-icon.webp');
  await expect.poll(() => page.locator('.workspace-nav img').evaluateAll(images =>
   images.filter(image => image.complete && image.naturalWidth > 0).length,
  )).toBe(3);
  await expect(page.locator('#tests-page')).toBeHidden();
  for(const id of ['settings','network','tests','control']){
   await page.locator('#nav-'+id).click();
   await expect(page.locator('#'+id+'-page')).toBeVisible();
   await expect(page.locator('#nav-'+id)).toHaveAttribute('aria-current','page');
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  }
  await page.locator('#nav-settings').click();
  for(const lang of ['en','es','de','nl']) await page.locator('#language').selectOption(lang);
  await page.locator('#nav-control').click();
  await page.screenshot({path:'test-results/studio-'+viewport.width+'.png',fullPage:true,animations:'disabled'});
 });
}

test('spatial test shows the specific Join conflict', async ({page})=>{
 const id='native:wall-uid';
 const error='Join offset is missing for Muur 3. Refresh discovery and check the group mapping in Twinkly.';
 await page.route('**/status', route=>route.fulfill({json:{
  display_groups:{[id]:{name:'Muur2026',members:[],mode:'join',missing_master:id}}, devices:[]
 }}));
 await page.route('**/physical-test', async route=>{
  expect(route.request().postDataJSON()).toEqual({group:id,test:'rainbow'});
  await route.fulfill({status:409,json:{error}});
 });
 await page.goto('http://127.0.0.1:8765/index.html#testcontrole',{waitUntil:'domcontentloaded'});
 const rainbow=page.locator('#tests-content article').filter({hasText:'Regenboog'});
 await rainbow.getByRole('button').click();
 await expect(page.locator('#message')).toHaveText('HTTP 409 · '+error);
});

test('Security Center maps all Hue lights to their own bridge beside Twinkly', async ({page}) => {
 await page.route('**/network', route => route.fulfill({json:{
  devices:[{id:'tree',name:'Tree',ip:'192.168.1.10',kind:'unknown'}], groups:{},
 }}));
 await page.route('**/providers/hue/inventory', route => route.fulfill({json:{devices:[
  {id:'unavailable',address:'192.168.1.21',status:'unavailable',lights:[]},
  {id:'living',address:'192.168.1.22',status:'online',lights:[{id:'one',name:'Hue window'},{id:'two',name:'Hue table'}]},
  {id:'hall',address:'192.168.1.23',status:'online',lights:[{id:'one',name:'Hue hall'}]},
 ]}}));
 await page.goto('http://127.0.0.1:8765/index.html#netwerk',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('heading',{name:'Security Center'})).toBeVisible();
 await expect(page.locator('#network-world article')).toHaveCount(7);
 await expect(page.locator('#network-world').getByText('Hue window')).toBeVisible();
 await expect(page.locator('#network-world').getByText('Hue table')).toBeVisible();
 await expect(page.locator('#network-world').getByText('Hue hall')).toBeVisible();
 const links = await page.evaluate(() => networkLinks.map(([source,target]) => [
  JSON.parse(source.id.slice('device:'.length)), JSON.parse(target.id.slice('device:'.length)),
 ]));
 expect(links).toEqual([
  [['hue','living'],['hue','living','one']], [['hue','living'],['hue','living','two']],
  [['hue','hall'],['hue','hall','one']],
 ]);
 expect(await page.evaluate(() => [...networkNodes.values()].every(node => Number.isFinite(node.y)))).toBe(true);
});

test('Home combines providers and keeps pairing in Settings', async ({page}) => {
 const light = (id, provider, name, rgb, status='online') => ({
  id, provider, name, status, capabilities:{power:provider!=='govee', brightness:rgb, rgb},
  state:{on:true, brightness:rgb?65:null, color:rgb?[255,120,30]:null},
 });
 const groups = {};
 let groupControl;
 let pairing;
 await page.route('**/lighting', route => route.fulfill({json:{
  lights:[light('t','twinkly','Tree',true),light('h','hue','Living room',false),light('g','govee','Strip',false,'unknown')],
  connections:{hue:[{id:'bridge',address:'192.168.1.2',status:'online'}],govee:[]}, groups,
 }}));
 await page.route('**/lighting/groups', route => {
  const {name,members}=route.request().postDataJSON();
  groups.mixed={name,members};
  return route.fulfill({json:{id:'mixed'}});
 });
 await page.route('**/lighting/control', route => {
  groupControl=route.request().postDataJSON();
  return route.fulfill({json:{results:{t:'accepted',h:'skipped',g:'unconfirmed'}}});
 });
 const fingerprint = 'ab'.repeat(32);
 await page.route('**/providers/hue/certificate', route => {
  expect(route.request().postDataJSON()).toEqual({address:'192.168.1.2'});
  return route.fulfill({json:{certificate_sha256:fingerprint,verified:false}});
 });
 await page.route('**/providers/hue/connect', route => {
  pairing=route.request().postDataJSON();
  return route.fulfill({json:{ok:true}});
 });
 await page.setViewportSize({width:390,height:844});
 await page.goto('http://127.0.0.1:8765/index.html',{waitUntil:'domcontentloaded'});
 const home=page.locator('#lighting-panel');
 await expect(home.locator('article')).toHaveCount(3);
 await expect(home.locator('[data-provider=hue] input[type=color]')).toHaveCount(0);
 await expect(home.locator('[data-provider=govee]')).toContainText('onbevestigd');
 await expect(home.locator('[data-provider=govee] button')).toHaveCount(0);
 await expect(page.getByText('Certificaat ophalen')).toHaveCount(0);
 await home.getByLabel('Groepsnaam').fill('Together');
 await home.getByLabel('Tree · Twinkly').check();
 await home.getByLabel('Living room · Philips Hue').check();
 await home.getByLabel('Strip · Govee').check();
 await home.getByRole('button',{name:'Opslaan'}).click();
 const group=home.locator('article').filter({hasText:'Together'});
 await group.getByRole('button',{name:'Aan',exact:true}).click();
 await expect(page.locator('#lighting-feedback')).toContainText('Onbevestigd · 1');
 expect(groupControl).toEqual({group:'mixed',action:'power',value:true});
 await page.locator('#nav-hue').click();
 await expect(home.locator('article')).toHaveCount(1);
 await expect(home.getByText('Living room')).toBeVisible();
 await expect(home.getByText('Tree')).toHaveCount(0);
 await page.locator('#nav-govee').click();
 await expect(home.getByText('Strip')).toBeVisible();
 await page.locator('#nav-control').click();
 await expect(page.locator('#twinkly-lighting').getByText('Tree')).toBeVisible();
 await page.locator('#nav-settings').click();
 const settings=page.locator('#lighting-settings');
 await expect(settings.getByText('bridge · 192.168.1.2 · Verbonden')).toBeVisible();
 await settings.getByRole('button',{name:'Opnieuw koppelen',exact:true}).click();
 await expect(settings.getByLabel('LAN-adres').first()).toHaveValue('192.168.1.2');
 const certificate=settings.getByRole('button',{name:'Certificaat ophalen'});
 await Promise.all([
  page.waitForEvent('dialog').then(dialog => dialog.dismiss()),
  certificate.click(),
 ]);
 await expect(settings.getByLabel('SHA256-vingerafdruk')).toHaveValue('');
 await Promise.all([
  page.waitForEvent('dialog').then(async dialog => {
   expect(dialog.message()).toContain(fingerprint);
   await dialog.accept();
  }),
  certificate.click(),
 ]);
 await expect(settings.getByLabel('SHA256-vingerafdruk')).toHaveValue(fingerprint);
 await settings.locator('form').getByRole('button',{name:'Opnieuw koppelen'}).click();
 await expect.poll(() => pairing).toEqual({id:'bridge',address:'192.168.1.2',certificate_sha256:fingerprint});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
});
