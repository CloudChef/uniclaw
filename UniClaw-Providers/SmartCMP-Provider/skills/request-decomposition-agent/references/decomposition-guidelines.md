# Decomposition Guidelines

Use this file when a descriptive requirement needs to be turned into multiple CMP request candidates.

## Good Decomposition Signals

- The request clearly implies more than one resource type.
- There are explicit dependencies such as app plus database, app plus storage, or app plus network exposure.
- The requirement includes environment, expected workload, or resilience hints that can guide service selection.

## Stop And Leave For Manual Review When

- Core business purpose is unclear.
- No matching CMP catalog item can be found.
- Required identifiers such as business group or application are unavailable.
- High-cost or production-sensitive components depend on guessed values.

## Preferred Output Shape

- one sub-request per CMP catalog item
- assumptions listed separately
- unresolved fields listed explicitly
- operator follow-up items stated in plain language
