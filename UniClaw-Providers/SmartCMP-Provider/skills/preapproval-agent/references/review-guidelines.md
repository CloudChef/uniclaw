# Review Guidelines

Use this file when the approval detail contains enough context to make a more concrete judgment.

## Strong Approval Signals

- The requester states a clear business goal.
- Requested capacity aligns with the expected workload.
- Non-production environments are used for development, testing, or validation scenarios.
- The notes explain why the selected service or size is needed.
- Cost estimate, if present, is proportional to the expected value or urgency.

## Strong Rejection Signals

- The request says only "for business", "urgent", or similarly vague text.
- The request asks for large capacity but gives no workload expectation.
- Production environment is selected without production-grade justification.
- Parameters appear contradictory, incomplete, or copied from another request.
- Requested configuration is unusually expensive without explaining why cheaper options are not sufficient.

## Guidance To Include On Rejection

Encourage the requester to provide:

- concrete business purpose
- expected workload or user scale
- target environment and why it is needed
- explanation for CPU, memory, storage, or premium options
- any urgency or compliance requirement that materially affects sizing
