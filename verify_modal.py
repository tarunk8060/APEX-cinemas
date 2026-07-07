import re

with open('frontend/app.js', encoding='utf-8') as f:
    js = f.read()

with open('frontend/index.html', encoding='utf-8') as f:
    html = f.read()

print("=" * 55)
print("  APEX CINEMAS — MODAL CODE VERIFICATION")
print("=" * 55)

# 1. Leftover browser confirm()
old_confirms = re.findall(r'\bconfirm\s*\(', js)
status = "PASS" if len(old_confirms) == 0 else "FAIL"
print(f"\n[{status}] Leftover confirm() calls: {len(old_confirms)}")

# 2. Stale function/variable references
stale = ['executeConfirmBooking', 'pendingBooking', 'confirm-modal-content']
for s in stale:
    found = s in js or s in html
    status = "FAIL" if found else "PASS"
    print(f"[{status}] Stale ref '{s}': {'FOUND - fix needed!' if found else 'Clean'}")

# 3. showModal call count
modal_calls = len(re.findall(r'\bshowModal\(', js))
status = "PASS" if modal_calls == 4 else "WARN"
print(f"\n[{status}] showModal() called {modal_calls} times (expected 4)")

# 4. Check modal DOM IDs used in JS all exist in HTML
id_pattern = re.compile(r"getElementById\(['\"]([^'\"]+)['\"]\)")
js_ids = id_pattern.findall(js)
html_ids = set(re.findall(r'id="([^"]+)"', html))
modal_js_ids = sorted(set(i for i in js_ids if 'modal' in i.lower()))
print(f"\n  Modal IDs referenced in JS:")
for mid in modal_js_ids:
    present = mid in html_ids
    print(f"    [{'PASS' if present else 'FAIL - MISSING IN HTML'}] #{mid}")

# 5. Key onclick handlers in HTML exist as JS functions
handlers = ['handleModalOverlayClick', 'closeConfirmModal', 'runModalAction']
print(f"\n  onclick handlers in HTML exist in JS:")
for h in handlers:
    in_html = h in html
    in_js = h in js
    status = "PASS" if in_html and in_js else "FAIL"
    print(f"    [{status}] {h}: HTML={'yes' if in_html else 'NO'}, JS={'yes' if in_js else 'NO'}")

print("\n" + "=" * 55)
