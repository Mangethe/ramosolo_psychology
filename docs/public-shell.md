# Public website and portal shell

Local implementation; no deployment, live migration or real message was sent.

## Sources and pending practice facts

The current repository templates and stylesheet were inspected before editing.
It contained `base.html`, `portal.html`, public pages and medical views, with shared
`partials/flashes.html` and `partials/tables.html`. It did not contain navbar,
footer or chat partials. Those missing files were not inferred from an include.

The user subsequently supplied the actual navbar, footer and chat markup as text.
The navbar and footer were adapted to this checkout's medical routes. Their
corporate/division/search/profile/social endpoints and logo image are absent in
this repository; no broken links, invented destinations or extra division were
added. Education remains an institution placeholder. The original chat example
was reviewed as a reference. The local general-questions chatbot uses preset
answers on the signed-out home and inpatient pages. It uses no free-text input,
network calls or browser storage for replies.

During the original shell phase, readable business-card images, `main_base.html`
and the supplied stylesheet were unavailable. The subsequent privacy phase received
two readable card images and transcribed them on the draft Professional Information
page; practice confirmation remains pending. The reference base/stylesheet are
still unavailable. No claim is made that unseen artwork or unknown template blocks have been reproduced. The navy colour
`#002f4a` is present in the supplied text; blue accents follow the user's design
direction. The small CSS butterfly is an original decorative accent, not a
transcription of an unseen official logo. No font/icon framework was added.

| Public fact | Status |
|---|---|
| Name: **Ponky Ramosolo** | Explicitly supplied by the user; used consistently |
| Exact professional title/qualifications | Now card-attributed on the professional draft; practice confirmation pending |
| Exact service list | Card-listed services are transcribed on the professional draft; current scope and availability need practice confirmation |
| Address/location and contact digits/email | Awaiting confirmation; older conflicting placeholders removed from public templates |
| Practice number | Separate pending field; never represented as an HPCSA registration |
| HPCSA registration number | Separate pending field; no digits invented, no verification/endorsement badge |
| Operating hours | Not supplied; none invented or published |

An early text clarification request asked for the exact card details. Unclear
digits must be confirmed with the practice **before publication**. The local
contact sections state that details await practice confirmation and offer the
existing enquiry form. Card text was subsequently transcribed in the privacy phase, with registration
digits withheld. Exact base/stylesheet matching and live publication still require
source/owner confirmation. Existing booking service codes remain intact, labelled as enquiry
categories; changing them requires confirmed practice information and validation
against the scheduling workflow.

## Components and behaviour

- `partials/_navbar.html`: consistent public navigation and separate public
  appointment action, login/portal entry and native mobile disclosure.
- `partials/_portal_nav.html`: role/capability-aware workspace links and active
  page/section labels. Staff see only applicable workflows; patients see their
  own appointment/shared-plan/preferences actions. Links confer no new permission;
  all existing server route/query checks remain in force.
- `partials/_footer.html`: shared four-column practice/enquiry/contact/privacy
  footer on public and portal pages. Links target working routes and privacy
  anchors. The shared footer links to the cookies policy and HTML sitemap.
  Draft policy pages remain pending owner approval.
- `/sitemap.xml` uses the configured `AUTH_PUBLIC_URL` as its origin and lists
  public, indexable pages. The HTML sitemap also links to the policy drafts.
- `partials/_brand.html`: shared text brand with decorative, hidden-from-assistive-
  technology CSS accent. The unavailable example logo is not referenced as an
  asset, preventing a broken image request.
- Existing flash/table partials remain reused. Appointment tables now expose a
  labelled, keyboard-focusable horizontal scroll region on narrow screens.

The current `title` and `content` template blocks remain. Optional `head`,
`framework_css`, `extra_css` and `scripts` blocks are available; framework CSS, if
introduced through the reviewed hook, precedes custom overrides. No framework is
currently loaded. Inspection found no existing script bundle or font imports to
deduplicate; system fonts and the single local stylesheet remain. No frontend
build, extra icon library, external fonts or production source maps were added.

Colours, spacing, typography, panels, forms and tables use the navy/white/blue
theme. Both mobile menus use native `details/summary`; they work without script
and expose native expanded/collapsed semantics. Active links use text/borders
as well as colour. Skip links focus `main`; focus rings cover links, buttons,
inputs, textareas, summaries and table regions. Reduced-motion CSS covers scroll,
animation and transition effects. Existing CSRF-protected POST sign-out is
retained, rather than copying the reference's GET logout link.

Principal calculated contrast ratios against their actual backgrounds: body
text 13.89:1, muted text 6.00:1, primary button 6.86:1, footer text 10.58:1 and
focus colour against white 5.87:1. These are selected colour checks, not a complete
automated accessibility certification.

## Browser finding and correction

Real Chromium form testing found a pre-existing incompatibility from the earlier
security hardening: global `Referrer-Policy: no-referrer` makes Chrome send
`Origin: null` for these form navigations, causing the legitimate login POST to
be rejected. It also conflicts with HTTPS CSRF referrer checks. The policy is now
`strict-origin`: referrers contain only the origin, never a patient URL path,
query string or guest token. CSRF, HTTPS referrer checking, origin validation,
CSP, cache protection and cross-site POST rejection were **not disabled**.
All five roles were then able to sign in and sign out through the real forms in
the isolated browser. The regression test asserts the new policy.

## Executed checks and limits

Initial targeted run: `python -m pytest -q tests/test_shell.py tests/test_medical.py
tests/test_security.py --tb=short` — **81 passed in 171.39 seconds**. This run
preceded the real-browser referrer correction; the final full-suite result is in
`VERIFICATION.md`: **213 passed, 3 existing expected failures, 6 warnings in 886.85 seconds**.

`node verification/check_shell_browser.mjs` uses installed Chrome headlessly,
Node core APIs and a disposable in-memory synthetic Flask preview. No QA package
or browser library is installed. It uses an isolated temporary profile, blocks
external page requests and terminates its own preview/browser processes. It
does not attach to a real browser profile or load credentials/patient files.
Screenshots remain in `C:/Temp/ramosolo-shell-*`, outside public static hosting;
the latest result manifest is `verification/shell-browser-results.json` (**33 checks passed** after extension for the policy phase, zero external page requests).

The harness checks 1440px desktop and 390px mobile layouts, document overflow,
the native public and role menus with Enter/Tab, the skip link, reduced-motion
media preference, labelled accessibility landmarks, normal CSRF login/logout and
all five medical roles. Public home/menu/login and assistant desktop/mobile
screenshots were inspected. The final manifest records the additional keyboard
table-scroll and desktop-role checks.

Not verified: exact missing base/stylesheet fidelity and independent verification of card facts; physical iOS/Android
devices; Safari/Firefox; screen-reader announcements; live HTTPS proxy/CDN and
production deployment. Headless Chromium checks do not establish all-device
accessibility. No practice/registration/contact number has been independently
verified. Publication remains blocked on confirmed card details and approved
privacy notices, along with the previously documented release blockers.
