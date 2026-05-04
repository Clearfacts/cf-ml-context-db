# Navigation Ontology Extension

The interactive navigation agent extends `ontology.md` with these sections:

1. `Exploration Targets`
   - seeded from the navigation source YAML
   - identifies initial pages or flows worth exploring

2. `Screens`
   - discovered pages/screens
   - includes name, URL/title when known, purpose, labels, role scope, and evidence

3. `Actions`
   - visible user actions or affordances
   - includes description, page linkage, optional target hint, role scope, and evidence

4. `Labels`
   - important labels/headings/menu items/button text
   - includes optional page linkage, label type, and evidence

5. `Navigation Paths`
   - observed paths between screens
   - includes origin, destination, action summary, and evidence

6. `Validation Notes`
   - uncertainty, warnings, blocked points, and follow-up notes

7. `Open Questions`
   - unresolved questions discovered during exploration

The file remains markdown, but the section bodies use YAML so the agent can merge observations incrementally.
