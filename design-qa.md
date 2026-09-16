# Design QA

Result: passed

Flow under test: landing page -> open workspace -> PDF upload/extraction workspace.

Reference: supplied visual direction and the local product brief.

Checked:

- Focused product entry: compact header, direct workspace CTA, short hero, extraction visual, and three-step workflow with no footer.
- Removed non-product content: announcement bar, social links, book-a-demo CTA, sign-in CTA, marketing mega menus, use-case catalog, testimonials, newsletter, and Solutions/Products/Resources/Company footer columns.
- Desktop at 1440x900: headline stays within two lines, primary workspace action is visible, layout remains split and the visual hierarchy is intact.
- Mobile at 390x844: headline, actions, artwork, compact header, and focused navigation remain usable without horizontal overflow.
- Interactions: workspace links use the dedicated `/workspace` route, which loads the extraction UI without relying on a hash or client-side query toggle. Legacy `#workspace` and `?workspace=1` links redirect to the same route.
- Workspace alignment: the landing and workspace now share the same logo mark, wordmark scale, 76px header, white canvas, neutral hairlines, square control geometry, container width, and type stack. The competing subtitle, local-processing status, overview link, workspace hero, pipeline status card, and session label were removed.
- Pane structure: source, setup, schema, and results states now use one 96px desktop header contract (88px on mobile). Their lower rules meet the pane divider at the same coordinate, eliminating the broken seam in the uploaded-PDF state.
- Navigation cleanup: removed the header How it works and Workflow actions; kept workflow education in the body only.
- Accessibility: semantic headings, labelled controls, visible focus styles, keyboard-friendly links, and reduced-motion support.
- Verification: `npm run build`, rendered desktop/mobile captures, landing-to-workspace interaction, pane-edge geometry checks, DOM identity checks, and console error/warning checks all passed.
