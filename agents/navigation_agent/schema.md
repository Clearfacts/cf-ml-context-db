# Navigation Ontology Extension

The interactive navigation agent extends `ontology.md` with these sections:

1. `Exploration Targets`
   - seeded from the navigation source YAML
   - identifies initial pages or flows worth exploring

2. `Screens`
   - discovered pages/screens
   - includes name, URL/title when known, purpose, optional user help summary, navigation hints, labels, role scope, and evidence

3. `Actions`
   - visible user actions or affordances
   - includes description, page linkage, optional target hint, role scope, and evidence

4. `Labels`
   - important labels/headings/menu items/button text
   - includes optional page linkage, label type, and evidence

5. `Navigation Paths`
   - observed paths between screens
   - includes origin, destination, action summary, reusable route steps, optional executable `typed_route_steps`, success criteria, confidence, and evidence
   - `typed_route_steps` are used by the deterministic navigation cache and should never contain raw credential values

6. `Validation Notes`
   - uncertainty, warnings, blocked points, and follow-up notes

7. `Open Questions`
   - unresolved questions discovered during exploration

The file remains markdown, but the section bodies use YAML so the agent can merge observations incrementally.
