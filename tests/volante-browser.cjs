/* Browser checks against a generated offline fixture; no service credentials required. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {
  const root = path.resolve(__dirname, '..');
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'volante-browser-'));
  const python = process.env.PYTHON || 'python3';
  const generator = path.join(root, 'centaur-driven-graphify/scripts/render-volante.py');
  execFileSync(python, [path.join(__dirname, 'support.py'), fixture]);
  execFileSync(python, [generator, fixture]);
  const pageUrl = pathToFileURL(path.join(fixture, '.centaur/volante.html')).href;
  const browser = await chromium.launch({ headless: true, ...(process.env.VOLANTE_CHROMIUM ? { executablePath: process.env.VOLANTE_CHROMIUM } : {}) });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage();
  const errors = [];
  const network = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (/^https?:/.test(r.url())) network.push(r.url()); });
  try {
    await page.goto(pageUrl);
    await page.getByRole('heading', { name: 'O que o sistema faz' }).waitFor();
    await page.emulateMedia({ colorScheme: 'dark' });
    assert.match(await page.evaluate(() => getComputedStyle(document.documentElement).colorScheme), /only light|light only/);
    assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), 'rgb(246, 247, 249)');
    await page.emulateMedia({ colorScheme: 'light' });
    assert.equal(await page.getByRole('link', { name: /Reservar e cancelar consultas/ }).count(), 1);
    const shots = process.env.VOLANTE_SCREENSHOTS || os.tmpdir();
    fs.mkdirSync(shots, { recursive: true });
    await page.screenshot({ path: path.join(shots, 'volante-overview.png'), fullPage: true });

    await page.getByRole('link', { name: /Reservar e cancelar consultas/ }).click();
    await page.getByRole('heading', { name: 'Reservar e cancelar consultas' }).waitFor();
    await page.locator('#rule-RES-01').getByText('Código relacionado · 1 fontes', { exact: true }).click();
    await page.locator('#rule-RES-01 .source summary').click();
    assert.match(await page.locator('#rule-RES-01 .source code').innerText(), /def horarios_disponiveis/);
    await page.locator('#rule-RES-01').getByText('Evidências · 1 registros', { exact: true }).click();
    assert.match(await page.locator('#rule-RES-01 .evidence').innerText(), /Evidência fictícia/);
    await page.screenshot({ path: path.join(shots, 'volante-contract.png'), fullPage: true });

    await page.getByLabel('Suas notas').fill('Ajustar prazo de cancelamento.');
    await page.reload();
    assert.equal(await page.getByLabel('Suas notas').inputValue(), 'Ajustar prazo de cancelamento.');
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Exportar contexto para a IA' }).first().click();
    const download = await downloadPromise;
    const text = fs.readFileSync(await download.path(), 'utf8');
    assert.match(text, /Ajustar prazo de cancelamento/);
    assert.match(text, /reservas\/RES-01/);
    assert.match(text, /não altera aprovações/);

    await page.getByRole('navigation').getByRole('link', { name: 'Contratos', exact: true }).click();
    await page.getByRole('heading', { name: 'Contratos', exact: true }).waitFor();
    await page.getByLabel('Buscar no visor').fill('nenhum-resultadotest');
    await page.getByRole('heading', { name: 'Nenhum contrato encontrado' }).waitFor();
    await page.getByRole('button', { name: 'Limpar busca' }).click();
    assert.equal(await page.getByLabel('Buscar no visor').inputValue(), '');
    assert.equal(await page.getByLabel('Buscar no visor').evaluate(el => el === document.activeElement), true);
    await page.getByLabel('Módulo', { exact: true }).selectOption('notificacoes');
    assert.equal(await page.getByRole('link', { name: 'Reservar e cancelar consultas', exact: true }).count(), 0);
    await page.reload();
    assert.equal(await page.getByLabel('Módulo', { exact: true }).inputValue(), 'notificacoes');
    await page.getByLabel('Módulo', { exact: true }).selectOption('');

    for (const label of ['Código', 'Evidências', 'Próximos passos', 'Specs', 'Documentos', 'Visão geral']) {
      await page.getByRole('navigation').getByRole('link', { name: label, exact: true }).click();
      await page.waitForFunction(expected => document.querySelector('nav [aria-current="page"]')?.textContent.trim() === expected, label);
      assert.equal(await page.locator('main h1').count(), 1);
    }
    await page.getByRole('heading', { name: 'O que o sistema faz' }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByLabel('Módulo', { exact: true }).focus();
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    await page.getByLabel('Módulo', { exact: true }).selectOption('');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: path.join(shots, 'volante-mobile.png'), fullPage: true });
    await page.getByRole('link', { name: /Reservar e cancelar consultas/ }).click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.locator('#rule-RES-02 > details').first().locator('summary').first().focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#rule-RES-02 > details').first().getAttribute('open'), '');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    assert.notEqual(await page.evaluate(() => getComputedStyle(document.documentElement).scrollbarColor), 'auto');

    // Storage failure keeps edits and enables exporting them.
    const blocked = await browser.newContext();
    await blocked.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } }); });
    const bp = await blocked.newPage();
    await bp.goto(pageUrl);
    await bp.getByLabel('Suas notas').fill('Preservar mesmo sem armazenamento.');
    assert.match(await bp.locator('#note-help').innerText(), /Armazenamento indisponível/);
    await blocked.close();

    // Imported HTML remains literal text, even inside embedded JSON.
    const contractPath = path.join(fixture, '.centaur/contracts/reservas/v001.json');
    const c = JSON.parse(fs.readFileSync(contractPath, 'utf8'));
    c.title = '</script><img src=x onerror="window.hacked=true">';
    fs.writeFileSync(contractPath, JSON.stringify(c));
    execFileSync(python, [generator, fixture]);
    await page.goto(pageUrl);
    assert.equal(await page.evaluate(() => Boolean(window.hacked)), false);
    assert.equal(await page.locator('img').count(), 0);
    assert.match(await page.locator('main').innerText(), /desatualizada/);
    assert.deepEqual(errors, []);
    assert.deepEqual(network, []);
    console.log('PASS: navigation, code/evidence drilldown, export, notes, storage failure, search/filter persistence, keyboard, mobile, XSS, stale evidence, offline.');
    console.log('Screenshots: ' + shots);
  } finally {
    await browser.close();
    fs.rmSync(fixture, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
