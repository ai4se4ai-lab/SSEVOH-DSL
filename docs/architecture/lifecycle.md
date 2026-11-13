# Proposal and component lifecycle

A proposal passes PROPOSED, ANALYSED, VERIFIED, APPROVED and DEPLOYED. Any failed gate rejects it. An approval fingerprint mismatch requires REVALIDATION_REQUIRED. The runtime exposes this lifecycle in approval records and deployment journal events; it does not persist rejected proposal objects or a crash-recoverable workflow database.

An artifact can be active, quarantined, or withdrawn at a specific version. Updating a component quarantines all transitive dependents and provenance descendants. Withdrawal adds its current version to a monotone prohibition set and quarantines the closure. Descendants remain stored, including mixed-origin contributions. Revalidation is an independently approved update to a new version or safe historical recovery. It cannot reactivate an artifact while an ancestor is inactive.

Recovery restores one historical component, never an entire snapshot. The current withdrawal set survives it. Restored capabilities must also fit the current trusted permission ceiling; a historical version cannot silently restore a removed privilege. Exact recovery of a withdrawn version, unknown history, or a component referring to an inactive ancestor is rejected. Independent release of lineage after removing withdrawn contributions is not implemented; the reference engine rejects provenance removal.
