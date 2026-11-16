const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
assert.match(fs.readFileSync('/proc/cmdline', 'utf8'), /droidb_test_vm=1/);
const source = fs.readFileSync('/test/app.js', 'utf8');
const body = source.match(/^function mvtClassify\(t\) \{[\s\S]*?^\}/m);
assert.ok(body, 'production classifier must be present');
const classify = vm.runInNewContext(`(${body[0]})`);
for (const text of ['No malicious files detected', '0 infected', 'Root binary detected', 'Scan finished']) {
  assert.notEqual(classify(text), 'detect', text);
  assert.notEqual(classify(text), 'ok', text);
}
assert.equal(classify('MOCK SPYWARE INDICATORS MATCHED (2)'), 'detect');
assert.equal(classify('no spyware indicators matched'), 'info');
assert.equal(classify('HIGH ALERT root binary'), 'warn');
assert.equal(classify('Coverage: backup is empty'), 'warn');
assert.equal(classify('Analysis failed'), 'warn');
console.log('MVT_LOG_CLASSIFIER_PASS');
