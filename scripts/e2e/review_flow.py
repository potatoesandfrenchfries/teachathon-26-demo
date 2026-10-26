"""End-to-end check of the student map and the professor review screen in a real browser.

Run it with scripts/e2e/run.sh, which seeds a scratch database, starts the backend and the dev
server, runs this against them and shuts everything down. Usage: review_flow.py <screenshot dir>
"""
import re, sys
from playwright.sync_api import sync_playwright, expect

OUT = sys.argv[1]
BASE = 'http://localhost:5173'
errors = []

def check(name, condition, detail=''):
    print(('PASS ' if condition else 'FAIL ') + name + (f'  [{detail}]' if detail and not condition else ''))
    if not condition:
        errors.append(name)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1500, 'height': 900})
    console_errors = []
    page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)
    page.on('dialog', lambda d: d.accept())

    # --- Student map from the API
    page.goto(BASE + '/'); page.wait_for_load_state('networkidle')
    page.wait_for_selector('.react-flow__node')
    check('student map shows 16 concepts from the API', page.locator('.react-flow__node').count() == 16)
    check('student map shows the draft banner', page.get_by_text('Draft graph: the professor has not approved it yet').is_visible())
    page.screenshot(path=f'{OUT}/1_student_map.png')

    # --- Review page, read-only
    page.goto(BASE + '/review'); page.wait_for_load_state('networkidle')
    page.wait_for_selector('.react-flow__node')
    check('review shows 16 nodes', page.locator('.react-flow__node').count() == 16)
    check('counts shown', page.get_by_text('29', exact=False).first.is_visible() and 'to review' in page.locator('.review__toolbar').inner_text())
    check('read-only notice without a key', page.get_by_text('Read-only until you enter the admin key').is_visible())
    check('approve disabled without a key', page.get_by_role('button', name='Approve graph').is_disabled())
    visible_edges = page.locator('.react-flow__edge').count()
    page.screenshot(path=f'{OUT}/2_review_readonly.png')

    # --- Enter the key, inspect a disagreement
    page.get_by_label('Admin key').fill('test-key')
    page.get_by_role('button', name='Save').click()
    check('read-only notice gone after entering the key', page.get_by_text('Read-only until').count() == 0)
    first = page.locator('.review__queue li button').first
    check('first queued edge is a disagreement', 'A≠B' in first.inner_text(), first.inner_text())
    first.click()
    panel = page.locator('.review__detail')
    check('panel shows both pipelines', 'Pipeline A' in panel.inner_text() and 'Pipeline B' in panel.inner_text())
    check('panel shows evidence', 'cross-references' in panel.inner_text())
    check('panel flags the disagreement', 'pipelines disagree' in panel.inner_text())
    page.screenshot(path=f'{OUT}/3_edge_selected.png')

    # --- Accept, reject, retype
    page.get_by_role('button', name='Accept').click()
    page.wait_for_function("document.querySelector('.review__toolbar').innerText.includes('28 to review')")
    check('accepting moves the counts', '1 accepted' in page.locator('.review__toolbar').inner_text())
    # Reject an edge that is actually drawn (not implied), picked from the server's own data.
    graph = page.request.get('http://localhost:8000/graph').json()
    queue_ids = [e for e in graph['review_queue']]
    by_id = {e['id']: e for e in graph['edges']}
    target = next(i for i in queue_ids if not by_id[i]['hidden'])
    page.locator('.review__queue li button').nth(queue_ids.index(target)).click()
    check('the edge to reject is drawn', page.locator(f'.react-flow__edge[data-id="{target}"]').count() == 1)
    page.get_by_role('button', name='Reject').click()
    page.wait_for_function("document.querySelector('.review__toolbar').innerText.includes('1 rejected')")
    check('rejected edge appears under Rejected', 'rejected (1)' in page.locator('.review__queue').inner_text().lower())
    check('a rejected edge is no longer drawn', page.locator(f'.react-flow__edge[data-id="{target}"]').count() == 0)
    page.locator('.review__queue li button').last.click()  # the rejected entry
    page.get_by_role('button', name='Restore as accepted').click()
    page.wait_for_function("document.querySelector('.review__toolbar').innerText.includes('0 rejected')")
    check('restore brings it back', page.locator(f'.react-flow__edge[data-id="{target}"]').count() == 1)

    page.locator('.review__queue li button').first.click()
    before = page.locator('.review__detail .chips').inner_text()
    page.get_by_role('button', name=re.compile('Make (optional|required)')).click()
    page.wait_for_timeout(400)
    after = page.locator('.review__detail .chips').inner_text()
    check('retype flips the type chip', before != after, f'{before!r} -> {after!r}')

    # --- Implied edges toggle
    page.get_by_label('Show implied edges').check()
    page.wait_for_timeout(300)
    check('showing implied edges draws more edges', page.locator('.react-flow__edge').count() > visible_edges)
    page.get_by_label('Show implied edges').uncheck()

    # --- Drag to add edges: a cycle is refused, a valid edge is added
    def drag(src_id, dst_id):
        s = page.locator(f'.react-flow__node[data-id="{src_id}"] .react-flow__handle-bottom').bounding_box()
        d = page.locator(f'.react-flow__node[data-id="{dst_id}"] .react-flow__handle-top').bounding_box()
        page.mouse.move(s['x'] + s['width'] / 2, s['y'] + s['height'] / 2)
        page.mouse.down()
        page.mouse.move(d['x'] + d['width'] / 2, d['y'] + d['height'] / 2, steps=12)
        page.mouse.up()
    drag(16, 1)  # 5.2 -> 1.1 would close a loop
    page.wait_for_selector('.review__message--error')
    msg = page.locator('.review__message--error').inner_text()
    check('a cycle is refused with a message naming it', msg.startswith('Cycle:') and '5.2' in msg and '1.1' in msg, msg)
    page.screenshot(path=f'{OUT}/4_cycle_refused.png')
    page.get_by_label('Dismiss').click()
    accepted_before = page.locator('.review__toolbar').inner_text()
    drag(1, 15)  # 1.1 -> 5.1 is fine
    page.wait_for_selector('.review__message--info:has-text("Edge added by hand")')
    check('a valid edge is added by dragging', 'accepted' in page.locator('.review__toolbar').inner_text() and page.locator('.review__toolbar').inner_text() != accepted_before)
    # Select the new manual edge through its node, then delete it.
    page.locator('.react-flow__node[data-id="1"] .level-node__label').click()
    page.locator('.review__detail .edge-list button', has_text='1.1 → 5.1').click()
    check('the manual edge is labelled as added by hand', 'added by hand' in page.locator('.review__detail').inner_text())
    page.get_by_role('button', name='Delete').click()
    page.wait_for_selector('.review__message--info:has-text("Edge deleted")')
    graph = page.request.get('http://localhost:8000/graph').json()
    check('the deleted manual edge is gone from the server', not any(e['source'] == 'manual' and e['status'] != 'rejected' for e in graph['edges']))

    # --- Approve
    page.get_by_role('button', name='Approve graph').click()
    page.wait_for_selector('.status-pill--approved')
    check('approval freezes the graph', 'Approved and frozen' in page.locator('.status-pill').inner_text())
    check('approve disabled afterwards', page.get_by_role('button', name='Approve graph').is_disabled())
    page.locator('.review__queue li button').first.click() if page.locator('.review__queue li button').count() else None
    page.screenshot(path=f'{OUT}/5_approved.png')

    # --- Student map after approval, and the offline fallback
    page.goto(BASE + '/'); page.wait_for_load_state('networkidle')
    page.wait_for_selector('.react-flow__node')
    check('student map says the graph is approved', page.get_by_text('Approved graph.').is_visible())
    page.route('**/graph', lambda route: route.abort())
    page.goto(BASE + '/'); page.wait_for_load_state('networkidle')
    page.wait_for_selector('.map-notice')
    check('backend down: says so and shows the sample levels', 'Cannot reach the backend' in page.locator('.map-notice').inner_text() and page.locator('.react-flow__node').count() == 9)
    page.screenshot(path=f'{OUT}/6_fallback.png')

    unexpected = [e for e in console_errors if '409' not in e and 'Failed to load resource' not in e and 'ERR_FAILED' not in e]
    check('no unexpected console errors', not unexpected, '; '.join(unexpected)[:300])
    browser.close()

print('\nFAILED: ' + ', '.join(errors) if errors else '\nall checks passed')
sys.exit(1 if errors else 0)
